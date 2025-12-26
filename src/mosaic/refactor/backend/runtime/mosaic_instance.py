"""Mosaic instance runtime management"""
import asyncio
import logging
from typing import Dict, Optional
from pathlib import Path
from sqlmodel import Session as DBSession, select

from ..database import sync_engine
from ..models.node import Node
from ..config import get_instance_path
from .node import MosaicNode
from .nodes import NODE_REGISTRY
from .utils import get_node_workspace
from .commands import (
    Command,
    CommandType,
    SendMessageCommand,
    InterruptSessionCommand,
    CloseSessionCommand,
    StartNodeCommand,
    StopNodeCommand,
    RestartNodeCommand
)

logger = logging.getLogger(__name__)


class MosaicInstance:
    """
    Runtime instance of a mosaic.

    Runs in a dedicated thread's event loop.
    All nodes in this mosaic share the same event loop.
    """

    def __init__(self, mosaic):
        """
        Initialize mosaic instance.

        Args:
            mosaic: Mosaic database instance
        """
        self.mosaic = mosaic

        # Running nodes: {node_id: MosaicNode}
        self._running_nodes: Dict[str, MosaicNode] = {}

        # Command queue for cross-thread communication
        self._command_queue: asyncio.Queue = asyncio.Queue()

        # Session to node mapping for fast lookup
        # {session_id: node_id}
        self._session_node_map: Dict[str, str] = {}

        self._started = False

    async def start(self):
        """Start the mosaic instance"""
        if self._started:
            logger.warning(f"Mosaic {self.mosaic.id} already started")
            return

        logger.info(f"Starting mosaic instance {self.mosaic.id}")

        # Start command consumer loop
        asyncio.create_task(self._consume_commands())

        # Auto-start nodes marked as auto_start
        with DBSession(sync_engine) as db:
            stmt = select(Node).where(
                Node.mosaic_id == self.mosaic.id,
                Node.deleted_at.is_(None),
                Node.auto_start == True
            )
            nodes = db.exec(stmt).all()

            for node in nodes:
                try:
                    await self.start_node(node.node_id)
                except Exception as e:
                    logger.error(
                        f"Failed to auto-start node {node.node_id}: {e}",
                        exc_info=True
                    )

        self._started = True
        logger.info(f"Mosaic instance {self.mosaic.id} started")

    async def stop(self):
        """Stop the mosaic instance"""
        if not self._started:
            return

        logger.info(f"Stopping mosaic instance {self.mosaic.id}")

        # Stop all nodes
        for node_id in list(self._running_nodes.keys()):
            try:
                await self.stop_node(node_id)
            except Exception as e:
                logger.error(f"Error stopping node {node_id}: {e}", exc_info=True)

        self._started = False
        logger.info(f"Mosaic instance {self.mosaic.id} stopped")

    # ========== Node Lifecycle ==========

    async def start_node(self, node_id: str) -> MosaicNode:
        """
        Start a node.

        Args:
            node_id: Node ID (unique within mosaic)

        Returns:
            Started MosaicNode instance

        Raises:
            ValueError: If node already running or not found
        """
        if node_id in self._running_nodes:
            raise ValueError(f"Node {node_id} is already running")

        logger.info(f"Starting node {node_id} in mosaic {self.mosaic.id}")

        # Load node config from database
        with DBSession(sync_engine) as db:
            stmt = select(Node).where(
                Node.mosaic_id == self.mosaic.id,
                Node.node_id == node_id,
                Node.deleted_at.is_(None)
            )
            node = db.exec(stmt).first()

            if not node:
                raise ValueError(
                    f"Node {node_id} not found in mosaic {self.mosaic.id}"
                )

        # Get node class from registry
        node_cls = NODE_REGISTRY.get(node.node_type)
        if not node_cls:
            raise ValueError(f"Unknown node type: {node.node_type}")

        # Calculate node workspace
        instance_path = get_instance_path()
        workspace = get_node_workspace(node, instance_path)

        # Instantiate node with database Node instance and workspace
        mosaic_node = node_cls(
            node=node,
            workspace=workspace
        )

        # Start node
        await mosaic_node.start()

        # Cache running node
        self._running_nodes[node_id] = mosaic_node

        logger.info(f"Node {node_id} started in mosaic {self.mosaic.id}")
        return mosaic_node

    async def stop_node(self, node_id: str):
        """
        Stop a node.

        Args:
            node_id: Node ID

        Raises:
            ValueError: If node not running
        """
        mosaic_node = self._running_nodes.get(node_id)
        if not mosaic_node:
            raise ValueError(f"Node {node_id} is not running")

        logger.info(f"Stopping node {node_id} in mosaic {self.mosaic.id}")

        await mosaic_node.stop()
        del self._running_nodes[node_id]

        logger.info(f"Node {node_id} stopped in mosaic {self.mosaic.id}")

    async def restart_node(self, node_id: str) -> MosaicNode:
        """
        Restart a node.

        Args:
            node_id: Node ID

        Returns:
            Restarted MosaicNode instance
        """
        await self.stop_node(node_id)
        return await self.start_node(node_id)

    def get_node_status(self, node_id: str) -> str:
        """
        Get node status.

        Args:
            node_id: Node ID

        Returns:
            "running" or "stopped"
        """
        return "running" if node_id in self._running_nodes else "stopped"

    def get_node(self, node_id: str) -> Optional[MosaicNode]:
        """
        Get a running node instance.

        Args:
            node_id: Node ID

        Returns:
            MosaicNode instance or None if not running
        """
        return self._running_nodes.get(node_id)

    # ========== Command Processing ==========

    async def _consume_commands(self):
        """
        Command consumer loop.

        Runs in worker thread event loop.
        Processes commands from FastAPI main thread.
        """
        logger.info(f"Command consumer started for mosaic {self.mosaic.id}")

        while self._started:
            try:
                command = await self._command_queue.get()
                await self._process_command(command)
            except Exception as e:
                logger.error(
                    f"Error processing command in mosaic {self.mosaic.id}: {e}",
                    exc_info=True
                )

        logger.info(f"Command consumer stopped for mosaic {self.mosaic.id}")

    async def _process_command(self, command: Command):
        """
        Process a single command.

        Routes command to appropriate handler based on type.

        Args:
            command: Command to process
        """
        try:
            if command.type == CommandType.CREATE_SESSION:
                await self._handle_create_session(command)
            elif command.type == CommandType.SEND_MESSAGE:
                await self._handle_send_message(command)
            elif command.type == CommandType.INTERRUPT_SESSION:
                await self._handle_interrupt_session(command)
            elif command.type == CommandType.CLOSE_SESSION:
                await self._handle_close_session(command)
            elif command.type == CommandType.START_NODE:
                await self._handle_start_node(command)
            elif command.type == CommandType.STOP_NODE:
                await self._handle_stop_node(command)
            elif command.type == CommandType.RESTART_NODE:
                await self._handle_restart_node(command)
            else:
                logger.warning(f"Unknown command type: {command.type}")

            # Execute callback if provided
            if command.callback:
                await command.callback({"status": "success"})

        except Exception as e:
            logger.error(
                f"Command execution failed: {e}",
                exc_info=True
            )
            if command.callback:
                await command.callback({"status": "error", "error": str(e)})

    async def _handle_create_session(self, cmd):
        """
        Handle create session command.

        Creates a runtime session object and registers it for command routing.

        Args:
            cmd: CreateSessionCommand
        """
        from .commands import CreateSessionCommand
        from sqlmodel import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from ..models.node import Node
        from ..database import engine

        # Get node business ID from database ID
        async with AsyncSession(engine) as db:
            result = await db.execute(
                select(Node).where(
                    Node.id == cmd.node_id,
                    Node.deleted_at.is_(None)
                )
            )
            node_db = result.scalar_one_or_none()
            if not node_db:
                raise ValueError(f"Node {cmd.node_id} not found")

            node_business_id = node_db.node_id

        # Get running node
        node = self._running_nodes.get(node_business_id)
        if not node:
            raise ValueError(f"Node {node_business_id} not running")

        # Prepare config with user_id for ClaudeCodeNode
        config = cmd.config or {}
        config['user_id'] = cmd.user_id

        # Import user_broker for message callback
        from ..websocket.user_broker import user_broker

        # Add on_message callback to config for pushing messages to WebSocket
        def on_message_sync(msg: dict):
            """Synchronous wrapper for on_message callback"""
            # Add session_id to message
            msg['session_id'] = cmd.session_id
            # Push to user WebSocket via user_broker
            user_broker.push_from_worker(cmd.user_id, msg)

        config['on_message'] = on_message_sync

        # Create runtime session
        session = await node.create_session(cmd.session_id, config)

        # Register session for fast lookup
        self.register_session(cmd.session_id, node_business_id)

        logger.info(
            f"Created runtime session {cmd.session_id} for node {node_business_id}"
        )

    async def _handle_send_message(self, cmd: SendMessageCommand):
        """
        Handle send message command.

        Args:
            cmd: SendMessageCommand
        """
        # Fast lookup using session→node mapping
        node_id = self._session_node_map.get(cmd.session_id)
        if not node_id:
            raise ValueError(f"Session {cmd.session_id} not found in mosaic")

        node = self._running_nodes.get(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not running")

        session = node.get_session(cmd.session_id)
        if not session:
            raise ValueError(
                f"Session {cmd.session_id} not found in node {node_id}"
            )

        # Verify user ownership (defensive check)
        if hasattr(session, 'user_id') and session.user_id != cmd.user_id:
            raise PermissionError(
                f"User {cmd.user_id} does not own session {cmd.session_id}"
            )

        # Send message to session
        await session.send_user_message(cmd.message)

        logger.info(
            f"Message sent to session {cmd.session_id}: "
            f"{cmd.message[:50]}..."
        )

    async def _handle_interrupt_session(self, cmd: InterruptSessionCommand):
        """
        Handle interrupt session command.

        Args:
            cmd: InterruptSessionCommand
        """
        node_id = self._session_node_map.get(cmd.session_id)
        if not node_id:
            raise ValueError(f"Session {cmd.session_id} not found in mosaic")

        node = self._running_nodes.get(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not running")

        session = node.get_session(cmd.session_id)
        if not session:
            raise ValueError(
                f"Session {cmd.session_id} not found in node {node_id}"
            )

        # Interrupt session
        if hasattr(session, 'interrupt'):
            await session.interrupt()
            logger.info(f"Session {cmd.session_id} interrupted")
        else:
            logger.warning(
                f"Session {cmd.session_id} does not support interrupt"
            )

    async def _handle_close_session(self, cmd: CloseSessionCommand):
        """
        Handle close session command.

        Args:
            cmd: CloseSessionCommand
        """
        node_id = self._session_node_map.get(cmd.session_id)
        if not node_id:
            # Session may already be closed
            logger.warning(f"Session {cmd.session_id} not found in mosaic")
            return

        node = self._running_nodes.get(node_id)
        if not node:
            logger.warning(f"Node {node_id} not running")
            return

        # Close session
        await node.close_session(cmd.session_id, force=cmd.force)

        # Unregister session
        self.unregister_session(cmd.session_id)

        logger.info(f"Session {cmd.session_id} closed")

    async def _handle_start_node(self, cmd: StartNodeCommand):
        """
        Handle start node command.

        Args:
            cmd: StartNodeCommand
        """
        await self.start_node(cmd.node_id)

    async def _handle_stop_node(self, cmd: StopNodeCommand):
        """
        Handle stop node command.

        Args:
            cmd: StopNodeCommand
        """
        await self.stop_node(cmd.node_id)

    async def _handle_restart_node(self, cmd: RestartNodeCommand):
        """
        Handle restart node command.

        Args:
            cmd: RestartNodeCommand
        """
        await self.restart_node(cmd.node_id)

    # ========== Session Management ==========

    def register_session(self, session_id: str, node_id: str):
        """
        Register session for fast lookup.

        Should be called when a session is created.

        Args:
            session_id: Session UUID
            node_id: Node ID that owns the session
        """
        self._session_node_map[session_id] = node_id
        logger.debug(f"Registered session {session_id} → node {node_id}")

    def unregister_session(self, session_id: str):
        """
        Unregister session.

        Should be called when a session is closed.

        Args:
            session_id: Session UUID
        """
        if session_id in self._session_node_map:
            del self._session_node_map[session_id]
            logger.debug(f"Unregistered session {session_id}")
