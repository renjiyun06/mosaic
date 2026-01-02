"""Mosaic instance runtime representation"""
import asyncio
import logging
from typing import Dict, Optional, List, Any, TYPE_CHECKING, Type
from pathlib import Path

from ..enum import MosaicStatus, NodeStatus, NodeType
from ..exception import (
    MosaicAlreadyRunningError,
    MosaicNotRunningError,
    NodeNotFoundError,
    RuntimeInternalError,
)
from .command import (
    Command,
    StopMosaicCommand,
    StartNodeCommand,
    StopNodeCommand,
    GetNodeStatusCommand,
    CreateSessionCommand,
    SendMessageCommand,
    InterruptSessionCommand,
    CloseSessionCommand,
)

if TYPE_CHECKING:
    from ..model.mosaic import Mosaic
    from ..model.node import Node
    from ..model.session import Session
    from .mosaic_node import MosaicNode

logger = logging.getLogger(__name__)


# ========== Node Type Registry ==========

def _get_node_type_registry() -> Dict[NodeType, Type['MosaicNode']]:
    """
    Get the node type to node class mapping.

    This registry maps NodeType enum values to their corresponding
    MosaicNode subclass implementations.

    Returns:
        Dictionary mapping NodeType to MosaicNode subclass

    Note:
        Imports are done inside the function to avoid circular dependencies.
    """
    from .node.claude_code import ClaudeCodeNode

    return {
        NodeType.CLAUDE_CODE: ClaudeCodeNode,
    }


class MosaicInstance:
    """
    Runtime representation of a Mosaic.

    Runs in a single worker thread's event loop.
    All commands are processed sequentially through a command queue.

    Architecture:
    - Commands are submitted via process_command() (synchronous, called by RuntimeManager)
    - Commands are queued and processed one-by-one by the command loop
    - All state modifications happen in the command loop (single-threaded)

    Lifecycle:
    1. __init__: Initialize state (STOPPED)
    2. start(): Start command loop, load nodes, start auto_start nodes → RUNNING
    3. [process commands via queue]
    4. StopMosaicCommand → _handle_stop_mosaic(): Stop all nodes → STOPPED, then loop exits

    Note:
        Only start() is called directly (by RuntimeManager via run_coroutine_threadsafe).
        All other operations (including stop) go through the command queue.
    """

    def __init__(
        self,
        mosaic: 'Mosaic',
        mosaic_path: Path,
        async_session_factory,
        config: dict
    ):
        """
        Initialize mosaic instance.

        Args:
            mosaic: Mosaic model object from database
            mosaic_path: Mosaic working directory path
            async_session_factory: AsyncSession factory for database access
            config: Configuration dict

        Note:
            Does NOT start the instance. Call start() to begin operation.
        """
        self.mosaic = mosaic
        self.mosaic_path = mosaic_path
        self.async_session_factory = async_session_factory
        self.config = config

        # Initialize state
        self._status = MosaicStatus.STOPPED
        self._command_queue: asyncio.Queue = asyncio.Queue()
        self._command_loop_task: Optional[asyncio.Task] = None

        # Initialize node mapping
        self._nodes: Dict[int, 'MosaicNode'] = {}

        logger.info(
            f"MosaicInstance initialized: id={mosaic.id}, "
            f"name={mosaic.name}, path={mosaic_path}"
        )

    # ========== Lifecycle Methods ==========

    async def start(self) -> None:
        """
        Start the mosaic instance.

        Steps:
        1. Validate current status (must be STOPPED)
        2. Start command processing loop
        3. Load all nodes from database
        4. Start all auto_start nodes (sequentially)
        5. Set status to RUNNING

        Raises:
            MosaicAlreadyRunningError: If already running
            RuntimeInternalError: If startup fails

        Note:
            Auto-start nodes are started via internal method (not command queue)
            to avoid blocking the start() method itself.
        """
        if self._status != MosaicStatus.STOPPED:
            raise MosaicAlreadyRunningError(
                f"Mosaic {self.mosaic.name} is already running"
            )

        logger.info(
            f"Starting mosaic: id={self.mosaic.id}, name={self.mosaic.name}"
        )

        try:
            # 1. Start command processing loop
            self._command_loop_task = asyncio.create_task(self._command_loop())
            logger.debug("Command processing loop started")

            # 2. Load all nodes from database
            nodes = await self._load_nodes()
            logger.info(f"Loaded {len(nodes)} nodes from database")

            # 3. Start auto_start nodes
            auto_start_nodes = [n for n in nodes if n.auto_start]
            if auto_start_nodes:
                logger.info(f"Starting {len(auto_start_nodes)} auto-start nodes...")
                for node in auto_start_nodes:
                    try:
                        await self._start_node_internal(node)
                    except Exception as e:
                        logger.error(
                            f"Failed to start auto-start node {node.node_id}: {e}"
                        )
                        # Continue starting other nodes

            # 4. Set status to RUNNING
            self._status = MosaicStatus.RUNNING

            logger.info(
                f"Mosaic started successfully: id={self.mosaic.id}, "
                f"running_nodes={len(self._nodes)}"
            )

        except Exception as e:
            logger.error(f"Failed to start mosaic: {e}")
            # Cleanup on failure
            await self._cleanup()
            raise RuntimeInternalError(f"Mosaic startup failed: {e}") from e

    async def _cleanup(self) -> None:
        """
        Cleanup all resources.

        Called on startup failure to ensure clean state.

        Steps:
        1. Cancel command processing loop (if running)
        2. Clear node mapping
        3. Clear pending commands in queue
        """
        # Cancel command processing loop (only during startup failure)
        if self._command_loop_task and not self._command_loop_task.done():
            self._command_loop_task.cancel()
            try:
                await self._command_loop_task
            except asyncio.CancelledError:
                pass
            self._command_loop_task = None

        # Clear node mapping
        self._nodes.clear()

        # Clear pending commands
        while not self._command_queue.empty():
            try:
                self._command_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        logger.debug("MosaicInstance cleanup complete")

    # ========== Command Processing ==========

    def process_command(self, command: Command) -> None:
        """
        Submit a command to the processing queue.

        This is a synchronous method called by RuntimeManager via call_soon_threadsafe.
        Commands are processed sequentially by the command loop.

        Args:
            command: Command object to execute

        Note:
            This method does NOT wait for command completion.
            Results are returned via command.future.
        """
        # Put command into queue (non-blocking)
        self._command_queue.put_nowait(command)

        logger.debug(
            f"Command queued: {command.__class__.__name__}, "
            f"queue_size={self._command_queue.qsize()}"
        )

    async def _command_loop(self) -> None:
        """
        Command processing loop (long-running coroutine).

        Continuously fetches and executes commands from the queue.
        Exits when status becomes STOPPED after processing a command.

        Each command is executed sequentially, ensuring no concurrent modifications.
        """
        logger.info("Command processing loop started")

        try:
            while True:
                # Fetch next command (blocking)
                command = await self._command_queue.get()

                logger.debug(f"Processing command: {command.__class__.__name__}")

                # Execute command
                try:
                    result = await self._execute_command(command)

                    # Resolve future if present
                    if command.future and not command.future.done():
                        command.set_result(result)

                except Exception as e:
                    logger.error(
                        f"Command execution failed: {command.__class__.__name__}, "
                        f"error: {e}",
                        exc_info=True
                    )

                    # Reject future if present
                    if command.future and not command.future.done():
                        command.set_exception(e)

                finally:
                    # Mark task as done
                    self._command_queue.task_done()

                # Check if mosaic is stopped (exit loop)
                if self._status == MosaicStatus.STOPPED:
                    logger.info("Mosaic stopped, exiting command loop")
                    break

        except asyncio.CancelledError:
            logger.info("Command processing loop cancelled")
            raise
        except Exception as e:
            logger.critical(f"Command loop crashed: {e}", exc_info=True)
            raise
        finally:
            logger.info("Command processing loop exited")

    async def _execute_command(self, command: Command) -> Any:
        """
        Execute a single command.

        Dispatches to the appropriate handler based on command type (using isinstance).

        Args:
            command: Command to execute

        Returns:
            Command execution result

        Raises:
            MosaicNotRunningError: If mosaic is stopped (for runtime commands)
            Exception: Any exception from command execution
        """
        # Check if mosaic is running (StopMosaicCommand is allowed when stopped)
        if not isinstance(command, StopMosaicCommand):
            if self._status != MosaicStatus.RUNNING:
                raise MosaicNotRunningError(
                    f"Mosaic {self.mosaic.name} is not running"
                )

        # Dispatch by command type
        if isinstance(command, StopMosaicCommand):
            return await self._handle_stop_mosaic(command)
        elif isinstance(command, StartNodeCommand):
            return await self._handle_start_node(command)
        elif isinstance(command, StopNodeCommand):
            return await self._handle_stop_node(command)
        elif isinstance(command, GetNodeStatusCommand):
            return await self._handle_get_node_status(command)
        elif isinstance(command, CreateSessionCommand):
            return await self._handle_create_session(command)
        elif isinstance(command, SendMessageCommand):
            return await self._handle_send_message(command)
        elif isinstance(command, InterruptSessionCommand):
            return await self._handle_interrupt_session(command)
        elif isinstance(command, CloseSessionCommand):
            return await self._handle_close_session(command)
        else:
            raise RuntimeInternalError(
                f"Unknown command type: {command.__class__.__name__}"
            )

    # ========== Command Handlers (TODO: Implementation) ==========

    async def _handle_stop_mosaic(self, command: StopMosaicCommand) -> None:
        """
        Handle StopMosaicCommand.

        Steps:
        1. Check if already stopped (idempotent)
        2. Set status to STOPPED (command loop will exit after this)
        3. Stop all running nodes (parallel, with exception tolerance)
        4. Clear node mapping
        5. Return None

        Args:
            command: StopMosaicCommand instance

        Returns:
            None

        Note:
            Command loop will exit after this handler completes.
        """
        # 1. Check if already stopped (idempotent)
        if self._status == MosaicStatus.STOPPED:
            logger.info(f"Mosaic {self.mosaic.name} already stopped")
            return

        logger.info(
            f"Stopping mosaic: id={self.mosaic.id}, name={self.mosaic.name}"
        )

        # 2. Set status to STOPPED (command loop will exit after this command completes)
        self._status = MosaicStatus.STOPPED

        # 3. Stop all running nodes (sequential, to avoid cross-task resource cleanup issues)
        if self._nodes:
            logger.info(f"Stopping {len(self._nodes)} running nodes...")
            for node in list(self._nodes.values()):
                await self._stop_node_internal(node)

        # 4. Clear node mapping
        self._nodes.clear()

        logger.info(f"Mosaic stopped: id={self.mosaic.id}")

    async def _handle_start_node(self, command: StartNodeCommand) -> None:
        """
        Handle StartNodeCommand.

        Steps:
        1. Call self._start_node_internal(command.node)
        2. Return None

        Args:
            command: StartNodeCommand instance

        Returns:
            None
        """
        await self._start_node_internal(command.node)

    async def _handle_stop_node(self, command: StopNodeCommand) -> None:
        """
        Handle StopNodeCommand.

        Steps:
        1. Get the MosaicNode instance via self._get_node(command.node)
        2. Call self._stop_node_internal(mosaic_node)
        3. Return None

        Args:
            command: StopNodeCommand instance

        Returns:
            None

        Raises:
            NodeNotFoundError: If node is not running
        """
        mosaic_node = self._get_node(command.node)
        await self._stop_node_internal(mosaic_node)

    async def _handle_get_node_status(self, command: GetNodeStatusCommand) -> NodeStatus:
        """
        Handle GetNodeStatusCommand.

        Steps:
        1. Try to get the MosaicNode instance via self._get_node(command.node)
        2. If found, return the node's status (mosaic_node.status)
        3. If NodeNotFoundError, return NodeStatus.STOPPED

        Args:
            command: GetNodeStatusCommand instance

        Returns:
            NodeStatus: RUNNING if node exists, STOPPED otherwise
        """
        try:
            mosaic_node = self._get_node(command.node)
            return mosaic_node.status
        except NodeNotFoundError:
            return NodeStatus.STOPPED

    async def _handle_create_session(self, command: CreateSessionCommand) -> None:
        """
        Handle CreateSessionCommand.

        Steps:
        1. Get the MosaicNode instance via self._get_node(command.node)
        2. Delegate to mosaic_node.create_session(command.session_id, command.config)
        3. Return None

        Args:
            command: CreateSessionCommand instance

        Returns:
            None

        Raises:
            NodeNotFoundError: If node is not running
            SessionConflictError: If session already exists in database
        """
        mosaic_node = self._get_node(command.node)
        await mosaic_node.create_session(
            session_id=command.session_id,
            config=command.config
        )

    async def _handle_send_message(self, command: SendMessageCommand) -> None:
        """
        Handle SendMessageCommand.

        Steps:
        1. Get the MosaicNode instance via self._get_node(command.node)
        2. Delegate to mosaic_node.send_message(command.session_id, command.message)
        3. Return None

        Args:
            command: SendMessageCommand instance

        Returns:
            None

        Raises:
            NodeNotFoundError: If node is not running
        """
        mosaic_node = self._get_node(command.node)
        await mosaic_node.send_message(command.session.session_id, command.message)

    async def _handle_interrupt_session(self, command: InterruptSessionCommand) -> None:
        """
        Handle InterruptSessionCommand.

        Steps:
        1. Get the MosaicNode instance via self._get_node(command.node)
        2. Delegate to mosaic_node.interrupt_session(command.session_id)
        3. Return None

        Args:
            command: InterruptSessionCommand instance

        Returns:
            None

        Raises:
            NodeNotFoundError: If node is not running
        """
        mosaic_node = self._get_node(command.node)
        await mosaic_node.interrupt_session(command.session_id)

    async def _handle_close_session(self, command: CloseSessionCommand) -> None:
        """
        Handle CloseSessionCommand.

        Steps:
        1. Get the MosaicNode instance via self._get_node(command.node)
        2. Delegate to mosaic_node.close_session(command.session_id)
        3. Return None

        Args:
            command: CloseSessionCommand instance

        Returns:
            None

        Raises:
            NodeNotFoundError: If node is not running
        """
        mosaic_node = self._get_node(command.node)
        await mosaic_node.close_session(command.session.session_id)

    # ========== Node Management (Internal) ==========

    async def _start_node_internal(self, node: 'Node') -> None:
        """
        Start a node (internal method, not via command queue).

        Steps:
        1. Check if node is already running (idempotent)
        2. Lookup node class from registry based on node.node_type
        3. Create MosaicNode subclass instance
        4. Call mosaic_node.start()
        5. Cache in self._nodes mapping

        Args:
            node: Node model object

        Raises:
            RuntimeInternalError: If node startup fails or node type is unknown

        Note:
            This method is called during mosaic startup (for auto_start nodes)
            and by StartNodeCommand handler.
        """
        # 1. Check if node is already running (idempotent)
        if node.id in self._nodes:
            logger.info(f"Node {node.node_id} already running, skipping")
            return

        logger.info(
            f"Starting node: id={node.id}, node_id={node.node_id}, "
            f"node_type={node.node_type}"
        )

        # 2. Lookup node class from registry
        node_type_registry = _get_node_type_registry()
        node_class = node_type_registry.get(node.node_type)

        if node_class is None:
            raise RuntimeInternalError(
                f"Unknown node type: {node.node_type}. "
                f"Available types: {list(node_type_registry.keys())}"
            )

        logger.debug(f"Using node class: {node_class.__name__}")

        # 3. Create MosaicNode subclass instance
        # Compute node working directory path
        node_path = self.mosaic_path / str(node.id)

        mosaic_node = node_class(
            node=node,
            node_path=node_path,
            mosaic_instance=self,
            async_session_factory=self.async_session_factory,
            config=self.config
        )

        # 4. Start the node
        try:
            await mosaic_node.start()
        except Exception as e:
            logger.error(f"Failed to start node {node.node_id}: {e}")
            raise RuntimeInternalError(f"Node startup failed: {e}") from e

        # 5. Cache in mapping
        self._nodes[node.id] = mosaic_node

        logger.info(f"Node started: node_id={node.node_id}")

    async def _stop_node_internal(self, mosaic_node: 'MosaicNode') -> None:
        """
        Stop a node (internal method).

        Steps:
        1. Call mosaic_node.stop()
        2. Remove from self._nodes mapping
        3. Handle exceptions and log errors

        Args:
            mosaic_node: MosaicNode instance to stop

        Note:
            This method does not raise exceptions (used during cleanup).
        """
        node_id = mosaic_node.node.node_id

        logger.info(f"Stopping node: node_id={node_id}")

        try:
            await mosaic_node.stop()
            self._nodes.pop(mosaic_node.node.id, None)
            logger.info(f"Node stopped: node_id={node_id}")
        except Exception as e:
            logger.error(f"Failed to stop node {node_id}: {e}", exc_info=True)
            # Don't raise - this is used during cleanup

    def _get_node(self, node: 'Node') -> 'MosaicNode':
        """
        Get a running MosaicNode instance.

        Args:
            node: Node model object

        Returns:
            MosaicNode instance

        Raises:
            NodeNotFoundError: If node is not running
        """
        if node.id not in self._nodes:
            raise NodeNotFoundError(
                f"Node {node.node_id} is not running in mosaic {self.mosaic.name}"
            )
        return self._nodes[node.id]

    # ========== Database Access ==========

    async def _load_nodes(self) -> List['Node']:
        """
        Load all active nodes for this mosaic from database.

        Query conditions:
        - mosaic_id == self.mosaic.id
        - deleted_at IS NULL

        Returns:
            List of Node model objects (ordered by created_at)
        """
        from sqlmodel import select
        from ..model.node import Node

        async with self.async_session_factory() as session:
            stmt = (
                select(Node)
                .where(Node.mosaic_id == self.mosaic.id)
                .where(Node.deleted_at.is_(None))
                .order_by(Node.created_at)
            )
            result = await session.execute(stmt)
            nodes = result.scalars().all()
            return list(nodes)

    # ========== State Properties ==========

    @property
    def status(self) -> MosaicStatus:
        """Get current mosaic status"""
        return self._status

    def is_running(self) -> bool:
        """Check if mosaic is running"""
        return self._status == MosaicStatus.RUNNING

    def get_running_node_count(self) -> int:
        """Get number of running nodes"""
        return len(self._nodes)
