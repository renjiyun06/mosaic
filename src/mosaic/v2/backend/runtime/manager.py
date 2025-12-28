"""Runtime manager for all mosaic instances"""
import asyncio
import threading
import logging
from typing import Dict, Optional, Any, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..enum import MosaicStatus, NodeStatus
from ..exception import (
    RuntimeConfigError,
    RuntimeAlreadyStartedError,
    RuntimeNotStartedError,
    MosaicAlreadyRunningError,
    MosaicNotRunningError,
    NodeNotFoundError,
    SessionNotFoundError,
    RuntimeTimeoutError,
    RuntimeInternalError,
)

if TYPE_CHECKING:
    from ..model.mosaic import Mosaic
    from ..model.node import Node
    from ..model.session import Session
    from .mosaic_instance import MosaicInstance
    from .command import Command

logger = logging.getLogger(__name__)


class RuntimeManager:
    """
    Global runtime manager for all mosaic instances.

    This is the ONLY interface between FastAPI layer and runtime layer.

    Architecture:
    - Manages a fixed-size thread pool (e.g., 4 threads)
    - Each thread runs a persistent event loop
    - Multiple MosaicInstance objects can run in the same event loop
    - MosaicInstance objects are assigned to threads using round-robin

    Cross-thread Communication:
    - Direct call (run_coroutine_threadsafe): ONLY for start_mosaic()
    - Command queue (call_soon_threadsafe + Future): For ALL other operations

    Responsibilities:
    - Start/stop the global ZMQ server
    - Manage thread pool lifecycle
    - Schedule mosaic instances to worker threads
    - Provide command submission interface for API layer
    """

    _instance: Optional['RuntimeManager'] = None

    def __init__(self, async_session_factory, config: dict):
        """
        Initialize runtime manager.

        Args:
            async_session_factory: AsyncSession factory from app.state
            config: Configuration dict from app.state
        """
        self.async_session_factory = async_session_factory
        self.config = config

        # Runtime state
        self._started = False
        self._executor: Optional[ThreadPoolExecutor] = None
        self._thread_loops: Dict[threading.Thread, asyncio.AbstractEventLoop] = {}
        self._thread_ready_events: Dict[int, threading.Event] = {}
        self._mosaic_instances: Dict[int, tuple['MosaicInstance', threading.Thread]] = {}
        self._next_thread_index = 0
        self._zmq_server = None

        # Thread safety: lock for _thread_loops (accessed by worker threads)
        self._thread_loops_lock = threading.Lock()

        logger.info("RuntimeManager initialized")

    @classmethod
    def create_instance(
        cls,
        async_session_factory,
        config: dict
    ) -> 'RuntimeManager':
        """
        Create and store the singleton instance.

        Args:
            async_session_factory: AsyncSession factory from app.state
            config: Configuration dict from app.state

        Returns:
            Created RuntimeManager instance

        Raises:
            RuntimeAlreadyStartedError: If instance already exists
        """
        if cls._instance is not None:
            raise RuntimeAlreadyStartedError("RuntimeManager already initialized")

        cls._instance = cls(async_session_factory, config)
        return cls._instance

    # ========== Manager Lifecycle ==========

    async def start(self):
        """
        Start the runtime manager.

        This must be called from the main event loop (FastAPI startup).

        Steps:
        1. Validate and read ZMQ configuration from self.config
        2. Validate and read runtime configuration from self.config
        3. Start global ZMQ server in main event loop
        4. Create thread pool with max_threads workers
        5. Pre-create event loops in each worker thread
        6. Wait for all event loops to be ready

        Raises:
            RuntimeAlreadyStartedError: If already started
            RuntimeConfigError: If required configuration is missing
        """
        if self._started:
            raise RuntimeAlreadyStartedError("RuntimeManager already started")

        logger.info("Starting RuntimeManager...")

        # 1. Validate and read ZMQ configuration
        zmq_config = self.config.get('zmq')
        if not zmq_config:
            raise RuntimeConfigError("Missing required configuration: [zmq]")

        zmq_host = zmq_config.get('host')
        zmq_pull_port = zmq_config.get('pull_port')
        zmq_pub_port = zmq_config.get('pub_port')

        if not all([zmq_host, zmq_pull_port, zmq_pub_port]):
            raise RuntimeConfigError(
                "Missing required ZMQ configuration fields: host, pull_port, pub_port"
            )

        # 2. Validate and read runtime configuration
        runtime_config = self.config.get('runtime')
        if not runtime_config:
            raise RuntimeConfigError("Missing required configuration: [runtime]")

        max_threads = runtime_config.get('max_threads')
        if not max_threads:
            raise RuntimeConfigError("Missing required runtime configuration field: max_threads")

        logger.info(f"Runtime configuration: max_threads={max_threads}")

        # 3. Start global ZMQ server
        from .zmq import ZmqServer

        self._zmq_server = await ZmqServer.get_instance(
            async_session_factory=self.async_session_factory,
            host=zmq_host,
            pull_port=zmq_pull_port,
            pub_port=zmq_pub_port
        )
        logger.info("ZMQ server started")

        # 4. Create thread pool
        self._executor = ThreadPoolExecutor(
            max_workers=max_threads,
            thread_name_prefix="mosaic-worker-"
        )
        logger.info(f"Thread pool created with {max_threads} workers")

        # 5. Pre-create event loops in worker threads
        for i in range(max_threads):
            ready_event = threading.Event()
            self._thread_ready_events[i] = ready_event
            self._executor.submit(self._create_event_loop, ready_event)

        # 6. Wait for all event loops to be ready
        for i, event in self._thread_ready_events.items():
            event.wait()
            logger.debug(f"Worker thread {i} event loop ready")

        self._started = True
        logger.info(
            f"RuntimeManager started successfully with {max_threads} worker threads"
        )

    async def stop(self):
        """
        Stop the runtime manager.

        This must be called from the main event loop (FastAPI shutdown).

        Steps:
        1. Stop all running mosaic instances (via command queue)
        2. Stop all worker thread event loops
        3. Shutdown thread pool (wait for all threads to finish)
        4. Stop global ZMQ server

        Note:
            All mosaic stop operations use command queue for consistency.
        """
        if not self._started:
            logger.warning("RuntimeManager is not started, nothing to stop")
            return

        logger.info("Stopping RuntimeManager...")

        try:
            # 1. Stop all running mosaic instances (parallel)
            mosaic_items = list(self._mosaic_instances.items())

            if mosaic_items:
                logger.info(f"Stopping {len(mosaic_items)} running mosaic instances...")

                # Import command here to avoid circular import
                from .command import StopMosaicCommand

                # Create stop tasks for all mosaics
                stop_tasks = []
                for mosaic_id, (instance, thread) in mosaic_items:
                    # Create StopMosaicCommand for each
                    command = StopMosaicCommand(mosaic=instance.mosaic)

                    # Submit command and collect the task
                    task = self._submit_command_and_wait(mosaic_id, command, timeout=30.0)
                    stop_tasks.append((mosaic_id, task))

                # Wait for all stop operations to complete (with exception tolerance)
                results = await asyncio.gather(
                    *[task for _, task in stop_tasks],
                    return_exceptions=True
                )

                # Log any failures
                for i, result in enumerate(results):
                    mosaic_id = stop_tasks[i][0]
                    if isinstance(result, Exception):
                        logger.error(f"Failed to stop mosaic {mosaic_id}: {result}")
                    else:
                        logger.info(f"Mosaic {mosaic_id} stopped successfully")

                # Clear the instances map
                self._mosaic_instances.clear()
                logger.info("All mosaic instances stopped")

            # 2. Stop all worker thread event loops
            logger.info("Stopping all worker thread event loops...")

            # Get all loops and stop them
            with self._thread_loops_lock:
                loops = list(self._thread_loops.values())

            for loop in loops:
                loop.call_soon_threadsafe(loop.stop)

            logger.info(f"Sent stop signal to {len(loops)} event loops")

            # 3. Shutdown thread pool (wait for all threads to finish)
            if self._executor:
                logger.info("Shutting down thread pool...")
                self._executor.shutdown(wait=True)
                self._executor = None
                logger.info("Thread pool shutdown complete")

            # 4. Stop global ZMQ server
            if self._zmq_server:
                logger.info("Stopping ZMQ server...")
                await self._zmq_server.stop()
                self._zmq_server = None
                logger.info("ZMQ server stopped")

            # 5. Clear all state
            self._thread_loops.clear()
            self._thread_ready_events.clear()
            self._next_thread_index = 0
            self._started = False

            logger.info("RuntimeManager stopped successfully")

        except Exception as e:
            logger.error(f"Error during RuntimeManager shutdown: {e}")
            raise

    # ========== Mosaic Lifecycle ==========

    async def start_mosaic(self, mosaic: 'Mosaic', timeout: float = 30.0) -> None:
        """
        Start a mosaic instance.

        This is the ONLY operation that uses direct cross-thread call.

        Steps:
        1. Validate mosaic is not already running
        2. Select a worker thread using round-robin
        3. Create MosaicInstance with mosaic model object
        4. Start instance in worker thread (run_coroutine_threadsafe)
        5. Wait for startup to complete
        6. Cache instance in _mosaic_instances

        Args:
            mosaic: Mosaic model object (validated by FastAPI layer)
            timeout: Maximum wait time in seconds

        Raises:
            MosaicAlreadyRunningError: If mosaic already running
            RuntimeInternalError: If no worker threads available
            RuntimeTimeoutError: If startup times out

        Note:
            Uses run_coroutine_threadsafe for synchronous startup guarantee.
            FastAPI layer must validate mosaic existence and permissions before calling.
        """
        # TODO: Implementation
        pass

    async def stop_mosaic(self, mosaic: 'Mosaic', timeout: float = 60.0) -> None:
        """
        Stop a mosaic instance.

        Uses command queue with Future for async wait.

        Steps:
        1. Create StopMosaicCommand
        2. Submit command and wait for completion
        3. Remove instance from _mosaic_instances cache

        Args:
            mosaic: Mosaic model object (validated by FastAPI layer)
            timeout: Maximum wait time in seconds

        Raises:
            MosaicNotRunningError: If mosaic not running
            RuntimeTimeoutError: If stop operation times out

        Note:
            Session cleanup (database + WebSocket) should be done BEFORE calling this.
            FastAPI layer must validate mosaic existence and permissions before calling.
        """
        logger.info(f"Stopping mosaic: id={mosaic.id}, mosaic_id={mosaic.mosaic_id}")

        # Import command here to avoid circular import
        from .command import StopMosaicCommand

        # 1. Create StopMosaicCommand
        command = StopMosaicCommand(mosaic=mosaic)

        # 2. Submit command and wait for completion
        await self._submit_command_and_wait(mosaic.id, command, timeout)

        # 3. Remove instance from _mosaic_instances cache
        self._mosaic_instances.pop(mosaic.id, None)

        logger.info(f"Mosaic stopped successfully: id={mosaic.id}, mosaic_id={mosaic.mosaic_id}")

    async def restart_mosaic(self, mosaic: 'Mosaic', timeout: float = 90.0) -> None:
        """
        Restart a mosaic instance.

        Args:
            mosaic: Mosaic model object (validated by FastAPI layer)
            timeout: Maximum wait time in seconds

        Raises:
            MosaicNotRunningError: If mosaic not running
            RuntimeTimeoutError: If restart times out

        Note:
            FastAPI layer must validate mosaic existence and permissions before calling.
        """
        logger.info(f"Restarting mosaic: id={mosaic.id}, mosaic_id={mosaic.mosaic_id}")

        # Import command here to avoid circular import
        from .command import RestartMosaicCommand

        # Create RestartMosaicCommand
        command = RestartMosaicCommand(mosaic=mosaic)

        # Submit command and wait for completion
        await self._submit_command_and_wait(mosaic.id, command, timeout)

        logger.info(f"Mosaic restarted successfully: id={mosaic.id}, mosaic_id={mosaic.mosaic_id}")

    async def get_mosaic_status(self, mosaic: 'Mosaic') -> MosaicStatus:
        """
        Get mosaic runtime status.

        Args:
            mosaic: Mosaic model object (validated by FastAPI layer)

        Returns:
            MosaicStatus.RUNNING or MosaicStatus.STOPPED

        Note:
            FastAPI layer must validate mosaic existence and permissions before calling.
            Currently uses simple implementation (check instance existence).
        """
        if mosaic.id in self._mosaic_instances:
            return MosaicStatus.RUNNING
        return MosaicStatus.STOPPED

    # ========== Node Lifecycle ==========

    async def start_node(self, node: 'Node', timeout: float = 30.0) -> None:
        """
        Start a node in a mosaic.

        Uses command queue with Future for async wait.

        Args:
            node: Node model object (validated by FastAPI layer)
            timeout: Maximum wait time in seconds

        Raises:
            MosaicNotRunningError: If mosaic not running
            RuntimeTimeoutError: If operation times out

        Note:
            FastAPI layer must validate node existence and permissions before calling.
        """
        logger.info(
            f"Starting node: id={node.id}, node_id={node.node_id}, "
            f"mosaic_id={node.mosaic_id}"
        )

        # Import command here to avoid circular import
        from .command import StartNodeCommand

        # Create StartNodeCommand
        command = StartNodeCommand(node=node)

        # Submit command and wait for completion
        await self._submit_command_and_wait(node.mosaic_id, command, timeout)

        logger.info(
            f"Node started successfully: id={node.id}, node_id={node.node_id}"
        )

    async def stop_node(self, node: 'Node', timeout: float = 30.0) -> None:
        """
        Stop a node in a mosaic.

        Uses command queue with Future for async wait.

        Args:
            node: Node model object (validated by FastAPI layer)
            timeout: Maximum wait time in seconds

        Raises:
            MosaicNotRunningError: If mosaic not running
            RuntimeTimeoutError: If operation times out

        Note:
            Session cleanup (database + WebSocket) should be done BEFORE calling this.
            This method only handles runtime node shutdown.
            FastAPI layer must validate node existence and permissions before calling.
        """
        logger.info(
            f"Stopping node: id={node.id}, node_id={node.node_id}, "
            f"mosaic_id={node.mosaic_id}"
        )

        # Import command here to avoid circular import
        from .command import StopNodeCommand

        # Create StopNodeCommand
        command = StopNodeCommand(node=node)

        # Submit command and wait for completion
        await self._submit_command_and_wait(node.mosaic_id, command, timeout)

        logger.info(
            f"Node stopped successfully: id={node.id}, node_id={node.node_id}"
        )

    async def restart_node(self, node: 'Node', timeout: float = 60.0) -> None:
        """
        Restart a node in a mosaic.

        Uses command queue with Future for async wait.

        Args:
            node: Node model object (validated by FastAPI layer)
            timeout: Maximum wait time in seconds

        Raises:
            MosaicNotRunningError: If mosaic not running
            RuntimeTimeoutError: If operation times out

        Note:
            FastAPI layer must validate node existence and permissions before calling.
        """
        logger.info(
            f"Restarting node: id={node.id}, node_id={node.node_id}, "
            f"mosaic_id={node.mosaic_id}"
        )

        # Import command here to avoid circular import
        from .command import RestartNodeCommand

        # Create RestartNodeCommand
        command = RestartNodeCommand(node=node)

        # Submit command and wait for completion
        await self._submit_command_and_wait(node.mosaic_id, command, timeout)

        logger.info(
            f"Node restarted successfully: id={node.id}, node_id={node.node_id}"
        )

    async def get_node_status(self, node: 'Node') -> NodeStatus:
        """
        Get node runtime status.

        Args:
            node: Node model object (validated by FastAPI layer)

        Returns:
            NodeStatus.RUNNING or NodeStatus.STOPPED

        Note:
            FastAPI layer must validate node existence and permissions before calling.
            If mosaic is not running, returns NodeStatus.STOPPED.
        """
        # If mosaic is not running, node must be stopped
        if node.mosaic_id not in self._mosaic_instances:
            return NodeStatus.STOPPED

        # Import command here to avoid circular import
        from .command import GetNodeStatusCommand

        # Create GetNodeStatusCommand
        command = GetNodeStatusCommand(node=node)

        # Submit command and wait for result (with short timeout for query)
        try:
            status = await self._submit_command_and_wait(
                node.mosaic_id, command, timeout=5.0
            )
            return status
        except Exception as e:
            logger.warning(
                f"Failed to query node status: id={node.id}, node_id={node.node_id}, "
                f"error: {e}"
            )
            # On error, assume stopped
            return NodeStatus.STOPPED

    # ========== Session Operations ==========

    async def create_session(
        self,
        session: 'Session',
        timeout: float = 10.0
    ) -> None:
        """
        Create a runtime session in a node.

        Uses command queue with Future for async wait.

        Steps:
        1. Create CreateSessionCommand
        2. Submit command and wait for completion

        Args:
            session: Session model object (validated by FastAPI layer)
            timeout: Maximum wait time in seconds

        Raises:
            MosaicNotRunningError: If mosaic not running
            NodeNotFoundError: If node not found
            RuntimeTimeoutError: If operation times out

        Note:
            FastAPI layer must validate session and node existence/permissions before calling.
        """
        logger.info(
            f"Creating session: id={session.id}, session_id={session.session_id}, "
            f"node_id={session.node.node_id}, mosaic_id={session.node.mosaic_id}"
        )

        # Import command here to avoid circular import
        from .command import CreateSessionCommand

        # Create CreateSessionCommand
        command = CreateSessionCommand(session=session)

        # Submit command and wait for completion
        await self._submit_command_and_wait(session.mosaic_id, command, timeout)

        logger.info(
            f"Session created successfully: id={session.id}, session_id={session.session_id}"
        )

    def submit_send_message(self, session: 'Session', message: str) -> None:
        """
        Submit a send message command (fire-and-forget).

        Does NOT wait for completion. Message sending is asynchronous.

        Args:
            session: Session model object (validated by FastAPI layer)
            message: User message content

        Raises:
            MosaicNotRunningError: If mosaic not running

        Note:
            This is a non-blocking operation. Use this for user message submission.
            FastAPI layer must validate session existence and permissions before calling.
        """
        logger.info(
            f"Submitting message for session: id={session.id}, "
            f"session_id={session.session_id}, message_length={len(message)}"
        )

        # Import command here to avoid circular import
        from .command import SendMessageCommand

        # Create SendMessageCommand
        command = SendMessageCommand(session=session, message=message)

        # Submit command without waiting (fire-and-forget)
        self._submit_command_no_wait(session.mosaic_id, command)

        logger.debug(
            f"Message submitted for session: id={session.id}, session_id={session.session_id}"
        )

    async def interrupt_session(self, session: 'Session', timeout: float = 5.0) -> None:
        """
        Interrupt a running session.

        Uses command queue with Future for async wait.

        Args:
            session: Session model object (validated by FastAPI layer)
            timeout: Maximum wait time in seconds

        Raises:
            SessionNotFoundError: If session not found
            RuntimeTimeoutError: If operation times out

        Note:
            FastAPI layer must validate session existence and permissions before calling.
        """
        logger.info(
            f"Interrupting session: id={session.id}, session_id={session.session_id}"
        )

        # Import command here to avoid circular import
        from .command import InterruptSessionCommand

        # Create InterruptSessionCommand
        command = InterruptSessionCommand(session=session)

        # Submit command and wait for completion
        await self._submit_command_and_wait(session.mosaic_id, command, timeout)

        logger.info(
            f"Session interrupted successfully: id={session.id}, session_id={session.session_id}"
        )

    async def close_session(
        self,
        session: 'Session',
        force: bool = False,
        timeout: float = 10.0
    ) -> None:
        """
        Close a runtime session.

        Uses command queue with Future for async wait.

        Steps:
        1. Create CloseSessionCommand
        2. Submit command and wait for completion

        Args:
            session: Session model object (validated by FastAPI layer)
            force: Force close even if session is busy
            timeout: Maximum wait time in seconds

        Raises:
            SessionNotFoundError: If session not found
            RuntimeTimeoutError: If operation times out

        Note:
            Database status should be updated BEFORE calling this method.
            FastAPI layer must validate session existence and permissions before calling.
        """
        logger.info(
            f"Closing session: id={session.id}, session_id={session.session_id}, "
            f"force={force}"
        )

        # Import command here to avoid circular import
        from .command import CloseSessionCommand

        # Create CloseSessionCommand
        command = CloseSessionCommand(session=session, force=force)

        # Submit command and wait for completion
        await self._submit_command_and_wait(session.mosaic_id, command, timeout)

        logger.info(
            f"Session closed successfully: id={session.id}, session_id={session.session_id}"
        )

    # ========== Command Submission Utilities ==========

    async def _submit_command_and_wait(
        self,
        mosaic_id: int,
        command: 'Command',
        timeout: float
    ) -> Any:
        """
        Submit a command to mosaic instance and wait for result.

        This is the core cross-thread communication mechanism.

        Steps:
        1. Get running mosaic instance and its event loop
        2. Create Future in main event loop
        3. Attach Future to command
        4. Submit command to worker thread via call_soon_threadsafe
        5. Wait for Future to be resolved (with timeout)

        Args:
            mosaic_id: Mosaic database ID
            command: Command object to execute
            timeout: Maximum wait time in seconds

        Returns:
            Command execution result (can be None)

        Raises:
            MosaicNotRunningError: If mosaic not running
            RuntimeInternalError: If event loop not found for thread
            RuntimeTimeoutError: If command doesn't complete in time
            Exception: Any exception raised during command execution

        Note:
            This method is used by all operations except start_mosaic.
        """
        # 1. Get running mosaic instance and its thread
        instance, thread = self._get_running_mosaic(mosaic_id)

        # Get the event loop for this thread
        with self._thread_loops_lock:
            loop = self._thread_loops.get(thread)

        if not loop:
            raise RuntimeInternalError(
                f"Event loop not found for thread: {thread.name}"
            )

        # 2. Create Future in main event loop
        future = asyncio.Future()

        # 3. Attach Future to command
        command.future = future

        # 4. Submit command to worker thread via call_soon_threadsafe
        loop.call_soon_threadsafe(instance.process_command, command)

        logger.debug(
            f"Command submitted: {command.__class__.__name__} "
            f"for mosaic_id={mosaic_id} in thread={thread.name}"
        )

        # 5. Wait for Future to be resolved (with timeout)
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            logger.debug(
                f"Command completed: {command.__class__.__name__} "
                f"for mosaic_id={mosaic_id}"
            )
            return result
        except asyncio.TimeoutError:
            logger.error(
                f"Command timeout: {command.__class__.__name__} "
                f"for mosaic_id={mosaic_id} after {timeout}s"
            )
            raise RuntimeTimeoutError(
                f"Command {command.__class__.__name__} timed out after {timeout}s"
            )

    def _submit_command_no_wait(self, mosaic_id: int, command: 'Command') -> None:
        """
        Submit a command without waiting for result (fire-and-forget).

        Used for operations that don't require acknowledgment (e.g., send_message).

        Args:
            mosaic_id: Mosaic database ID
            command: Command object to execute

        Raises:
            MosaicNotRunningError: If mosaic not running
            RuntimeInternalError: If event loop not found for thread
        """
        # Get running mosaic instance and its thread
        instance, thread = self._get_running_mosaic(mosaic_id)

        # Get the event loop for this thread
        with self._thread_loops_lock:
            loop = self._thread_loops.get(thread)

        if not loop:
            raise RuntimeInternalError(
                f"Event loop not found for thread: {thread.name}"
            )

        # Submit command to worker thread via call_soon_threadsafe (no waiting)
        loop.call_soon_threadsafe(instance.process_command, command)

        logger.debug(
            f"Command submitted (no-wait): {command.__class__.__name__} "
            f"for mosaic_id={mosaic_id} in thread={thread.name}"
        )

    # ========== Internal Helpers ==========

    def _get_running_mosaic(self, mosaic_id: int) -> tuple['MosaicInstance', threading.Thread]:
        """
        Get a running mosaic instance and its thread.

        Args:
            mosaic_id: Mosaic database ID

        Returns:
            Tuple of (MosaicInstance, Thread)

        Raises:
            MosaicNotRunningError: If mosaic not running
        """
        if mosaic_id not in self._mosaic_instances:
            raise MosaicNotRunningError(f"Mosaic with id={mosaic_id} is not running")

        return self._mosaic_instances[mosaic_id]

    def _select_thread(self) -> threading.Thread:
        """
        Select a worker thread using round-robin scheduling.

        Returns:
            Selected thread

        Raises:
            RuntimeInternalError: If no worker threads available

        Thread Safety:
            Uses _thread_loops_lock when accessing _thread_loops.
        """
        # Get all available threads with lock protection
        with self._thread_loops_lock:
            threads = list(self._thread_loops.keys())

        # Validate we have worker threads
        if not threads:
            raise RuntimeInternalError("No worker threads available")

        # Round-robin selection using modulo
        selected_thread = threads[self._next_thread_index % len(threads)]

        # Update index for next selection
        self._next_thread_index += 1

        logger.debug(
            f"Selected thread: {selected_thread.name} "
            f"(index={self._next_thread_index - 1}, total_threads={len(threads)})"
        )

        return selected_thread

    def _create_event_loop(self, ready_event: threading.Event) -> None:
        """
        Create and run an event loop in the current worker thread.

        This method runs in a worker thread (not main thread).

        Steps:
        1. Create new event loop
        2. Set as current thread's event loop
        3. Register in _thread_loops mapping (protected by _thread_loops_lock)
        4. Signal ready_event to main thread
        5. Run loop forever (blocks until loop.stop() is called)
        6. Clean up when loop stops (protected by _thread_loops_lock)

        Args:
            ready_event: Threading event to signal when loop is ready

        Thread Safety:
            Uses _thread_loops_lock when accessing shared _thread_loops dict.
        """
        # 1. Create new event loop
        loop = asyncio.new_event_loop()

        # 2. Set as current thread's event loop
        asyncio.set_event_loop(loop)

        # 3. Register in _thread_loops mapping (protected by _thread_loops_lock)
        current_thread = threading.current_thread()
        with self._thread_loops_lock:
            self._thread_loops[current_thread] = loop

        # 4. Signal ready_event to main thread
        ready_event.set()

        logger.info(f"Event loop created in worker thread: {current_thread.name}")

        # 5. Run loop forever (blocks until loop.stop() is called)
        try:
            loop.run_forever()
        finally:
            # 6. Clean up when loop stops (protected by _thread_loops_lock)
            logger.info(f"Event loop stopping in worker thread: {current_thread.name}")

            # Cancel all pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()

            # Wait for tasks to complete cancellation
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )

            # Close the loop
            loop.close()

            # Remove from mapping
            with self._thread_loops_lock:
                self._thread_loops.pop(current_thread, None)

            logger.info(f"Event loop stopped and cleaned up: {current_thread.name}")
