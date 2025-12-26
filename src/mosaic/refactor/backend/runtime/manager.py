"""Runtime manager for all mosaic instances"""
import asyncio
import threading
import logging
from typing import Dict, Optional, Callable, Awaitable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .mosaic_instance import MosaicInstance
from .zmq_layer import ZmqServer
from .nodes.claude_code import ClaudeCodeNode, ClaudeCodeSession
from ..config import settings
from ..database import sync_engine
from ..models.mosaic import Mosaic
from sqlmodel import Session as DBSession, select

logger = logging.getLogger(__name__)


class RuntimeManager:
    """
    Global runtime manager for all mosaic instances.

    Responsibilities:
    - Manage global ZMQ server
    - Manage thread pool for running mosaics
    - Schedule mosaics to threads
    - Provide thread-safe interface for API layer
    """

    _instance: Optional['RuntimeManager'] = None
    _lock = threading.Lock()

    def __init__(self, max_threads: Optional[int] = None):
        """
        Initialize runtime manager.

        Args:
            max_threads: Maximum number of worker threads for mosaics
                        (defaults to settings.runtime_max_threads)
        """
        self.max_threads = max_threads if max_threads is not None else settings.runtime_max_threads

        # Thread pool
        self._executor: Optional[ThreadPoolExecutor] = None

        # Thread -> Event loop mapping
        self._thread_loops: Dict[threading.Thread, asyncio.AbstractEventLoop] = {}

        # Event for signaling event loop readiness
        self._thread_ready_events: Dict[int, threading.Event] = {}

        # Mosaic instances: {mosaic_id: (MosaicInstance, thread)}
        self._mosaic_instances: Dict[int, tuple[MosaicInstance, threading.Thread]] = {}

        # Claude Code nodes: {(mosaic_id, node_id): ClaudeCodeNode}
        self._claude_nodes: Dict[tuple[int, int], ClaudeCodeNode] = {}

        # Session to mosaic mapping for fast command routing
        # {session_id: mosaic_id}
        self._session_mosaic_map: Dict[str, int] = {}

        # Round-robin index for scheduling
        self._next_thread_index = 0

        # Global ZMQ server (runs in main event loop)
        self._zmq_server: Optional[ZmqServer] = None

        self._started = False

    @classmethod
    def get_instance(cls) -> 'RuntimeManager':
        """Get or create the singleton instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    async def start(self):
        """Start the runtime manager (called from main event loop)"""
        if self._started:
            logger.warning("RuntimeManager already started")
            return

        logger.info("Starting RuntimeManager")

        # Start global ZMQ server with database URL for event storage
        self._zmq_server = await ZmqServer.get_instance(db_url=settings.database_url)

        # Create thread pool
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_threads,
            thread_name_prefix="mosaic-worker-"
        )

        # Pre-create event loops in threads
        for i in range(self.max_threads):
            ready_event = threading.Event()
            self._thread_ready_events[i] = ready_event
            self._executor.submit(self._create_event_loop, ready_event)

        # Wait for all event loops to be ready (NOT for them to finish)
        for i, event in self._thread_ready_events.items():
            event.wait()
            logger.debug(f"Worker thread {i} event loop ready")

        self._started = True
        logger.info(
            f"RuntimeManager started with {self.max_threads} worker threads"
        )

    async def stop(self):
        """Stop all mosaic instances and the runtime manager"""
        if not self._started:
            return

        logger.info("Stopping RuntimeManager")

        # Stop all mosaics
        for mosaic_id in list(self._mosaic_instances.keys()):
            try:
                await self.stop_mosaic(mosaic_id)
            except Exception as e:
                logger.error(f"Error stopping mosaic {mosaic_id}: {e}", exc_info=True)

        # Stop event loops in all threads
        for thread, loop in self._thread_loops.items():
            # Schedule loop.stop() in the target loop
            loop.call_soon_threadsafe(loop.stop)

        # Shutdown thread pool
        if self._executor:
            self._executor.shutdown(wait=True)

        # Stop ZMQ server
        if self._zmq_server:
            await self._zmq_server.stop()

        self._started = False
        logger.info("RuntimeManager stopped")

    # ========== Mosaic Lifecycle ==========

    async def start_mosaic(self, mosaic_id: int) -> MosaicInstance:
        """
        Start a mosaic instance.

        Args:
            mosaic_id: Mosaic ID from database

        Returns:
            Started MosaicInstance

        Raises:
            ValueError: If mosaic already running or not found
        """
        if mosaic_id in self._mosaic_instances:
            raise ValueError(f"Mosaic {mosaic_id} is already running")

        logger.info(f"Starting mosaic {mosaic_id}")

        # Get Mosaic object from database
        with DBSession(sync_engine) as db:
            mosaic = db.get(Mosaic, mosaic_id)
            if not mosaic or mosaic.deleted_at is not None:
                raise ValueError(f"Mosaic {mosaic_id} not found")

        # Select a thread using round-robin
        thread = self._select_thread()
        loop = self._thread_loops[thread]

        # Create mosaic instance with Mosaic object
        instance = MosaicInstance(mosaic=mosaic)

        # Start mosaic in the selected thread's event loop
        future = asyncio.run_coroutine_threadsafe(instance.start(), loop)
        future.result()  # Wait for startup to complete

        # Cache instance
        self._mosaic_instances[mosaic_id] = (instance, thread)

        logger.info(f"Mosaic {mosaic_id} started on {thread.name}")
        return instance

    async def stop_mosaic(self, mosaic_id: int):
        """
        Stop a mosaic instance.

        This will:
        1. Close all active sessions in database (status: active → closed)
        2. Disconnect all WebSocket connections for this mosaic
        3. Stop all nodes (which closes their runtime sessions)
        4. Stop the mosaic instance

        Args:
            mosaic_id: Mosaic ID

        Raises:
            ValueError: If mosaic not running
        """
        if mosaic_id not in self._mosaic_instances:
            raise ValueError(f"Mosaic {mosaic_id} is not running")

        logger.info(f"Stopping mosaic {mosaic_id}")

        # 1. Close all active sessions in database
        from ..services.session_service import SessionService
        from sqlalchemy.ext.asyncio import AsyncSession
        from ..database import engine

        async with AsyncSession(engine) as db:
            await SessionService.close_mosaic_sessions(db, mosaic_id)

        # 2. Disconnect all WebSockets for this mosaic
        from ..websocket.manager import ws_manager
        await ws_manager.disconnect_by_mosaic(mosaic_id)

        # 3. Stop mosaic instance (which stops all nodes)
        instance, thread = self._mosaic_instances[mosaic_id]
        loop = self._thread_loops[thread]

        future = asyncio.run_coroutine_threadsafe(instance.stop(), loop)
        future.result()  # Wait for shutdown to complete

        # Remove from cache
        del self._mosaic_instances[mosaic_id]

        logger.info(f"Mosaic {mosaic_id} stopped")

    async def restart_mosaic(self, mosaic_id: int) -> MosaicInstance:
        """
        Restart a mosaic instance.

        Args:
            mosaic_id: Mosaic ID

        Returns:
            Restarted MosaicInstance
        """
        await self.stop_mosaic(mosaic_id)
        return await self.start_mosaic(mosaic_id)

    def get_mosaic_status(self, mosaic_id: int) -> str:
        """
        Get mosaic status.

        Args:
            mosaic_id: Mosaic ID

        Returns:
            "running" or "stopped"
        """
        return "running" if mosaic_id in self._mosaic_instances else "stopped"

    # ========== Node Lifecycle (Proxied to MosaicInstance) ==========

    async def start_node(self, mosaic_id: int, node_id: str):
        """
        Start a node in a mosaic.

        Args:
            mosaic_id: Mosaic ID
            node_id: Node ID

        Raises:
            ValueError: If mosaic not running
        """
        instance, thread = self._get_running_mosaic(mosaic_id)
        loop = self._thread_loops[thread]

        # Call instance.start_node() in its thread
        future = asyncio.run_coroutine_threadsafe(
            instance.start_node(node_id), loop
        )
        future.result()

    async def stop_node(self, mosaic_id: int, node_id: str):
        """
        Stop a node in a mosaic.

        This will:
        1. Close all active sessions in database (status: active → closed)
        2. Disconnect all WebSocket connections for this node
        3. Stop the node runtime (closes all runtime sessions)

        Args:
            mosaic_id: Mosaic ID
            node_id: Node ID (business identifier, e.g., "node-1")

        Raises:
            ValueError: If mosaic not running
        """
        instance, thread = self._get_running_mosaic(mosaic_id)
        loop = self._thread_loops[thread]

        # Get node database ID from business ID
        from ..websocket.manager import ws_manager
        from ..services.session_service import SessionService
        from sqlalchemy.ext.asyncio import AsyncSession
        from ..database import engine
        from ..models.node import Node

        node_db_id = None
        async with AsyncSession(engine) as db:
            result = await db.execute(
                select(Node).where(
                    Node.mosaic_id == mosaic_id,
                    Node.node_id == node_id,
                    Node.deleted_at.is_(None)
                )
            )
            node = result.scalar_one_or_none()
            if node:
                # Store node database ID before session closes
                node_db_id = node.id

                # 1. Close all active sessions in database
                await SessionService.close_node_sessions(db, node_db_id)

        # 2. Disconnect all WebSockets for this node (outside session context)
        if node_db_id is not None:
            await ws_manager.disconnect_by_node(node_db_id)
            logger.info(
                f"Closed sessions and disconnected WebSockets for node {node_id} (db_id={node_db_id})"
            )

        # 3. Stop the node runtime
        future = asyncio.run_coroutine_threadsafe(
            instance.stop_node(node_id), loop
        )
        future.result()

    async def restart_node(self, mosaic_id: int, node_id: str):
        """
        Restart a node in a mosaic.

        Args:
            mosaic_id: Mosaic ID
            node_id: Node ID

        Raises:
            ValueError: If mosaic not running
        """
        instance, thread = self._get_running_mosaic(mosaic_id)
        loop = self._thread_loops[thread]

        future = asyncio.run_coroutine_threadsafe(
            instance.restart_node(node_id), loop
        )
        future.result()

    def get_node_status(self, mosaic_id: int, node_id: str) -> str:
        """
        Get node status.

        Args:
            mosaic_id: Mosaic ID
            node_id: Node ID

        Returns:
            "running", "stopped", or "mosaic_not_running"
        """
        if mosaic_id not in self._mosaic_instances:
            return "mosaic_not_running"

        instance, thread = self._mosaic_instances[mosaic_id]
        loop = self._thread_loops[thread]

        # Call instance.get_node_status() in its thread
        future = asyncio.run_coroutine_threadsafe(
            self._get_node_status_async(instance, node_id), loop
        )
        return future.result()

    async def _get_node_status_async(
        self, instance: MosaicInstance, node_id: str
    ) -> str:
        """Helper to get node status asynchronously"""
        return instance.get_node_status(node_id)

    # ========== Command Submission Interface ==========

    def submit_create_session(
        self,
        mosaic_id: int,
        node_id: int,
        session_id: str,
        user_id: int,
        config: dict,
        callback: Optional[Callable[[dict], Awaitable[None]]] = None
    ):
        """
        Submit a create session command to the appropriate mosaic instance.

        Thread-safe method that enqueues command into worker thread.

        Args:
            mosaic_id: Mosaic ID
            node_id: Node database ID
            session_id: Session UUID
            user_id: User ID
            config: Session configuration
            callback: Optional callback for command result

        Raises:
            ValueError: If mosaic not running
        """
        from .commands import CreateSessionCommand

        instance, thread = self._get_running_mosaic(mosaic_id)
        loop = self._thread_loops[thread]

        command = CreateSessionCommand(
            mosaic_id=mosaic_id,
            node_id=node_id,
            session_id=session_id,
            user_id=user_id,
            config=config,
            callback=callback
        )

        # Thread-safe command submission
        loop.call_soon_threadsafe(
            instance._command_queue.put_nowait, command
        )

        logger.debug(
            f"Submitted create_session command: session={session_id}, "
            f"request_id={command.request_id}"
        )

    def submit_send_message(
        self,
        session_id: str,
        message: str,
        user_id: int,
        callback: Optional[Callable[[dict], Awaitable[None]]] = None
    ):
        """
        Submit a send message command to the appropriate mosaic instance.

        Thread-safe method that enqueues command into worker thread.

        Args:
            session_id: Session UUID
            message: User message
            user_id: User ID (for permission verification)
            callback: Optional callback for command result

        Raises:
            ValueError: If session not found
        """
        from .commands import SendMessageCommand

        mosaic_id = self._session_mosaic_map.get(session_id)
        if not mosaic_id:
            raise ValueError(f"Session {session_id} not found")

        instance, thread = self._get_running_mosaic(mosaic_id)
        loop = self._thread_loops[thread]

        command = SendMessageCommand(
            mosaic_id=mosaic_id,
            session_id=session_id,
            message=message,
            user_id=user_id,
            callback=callback
        )

        # Thread-safe command submission
        loop.call_soon_threadsafe(
            instance._command_queue.put_nowait, command
        )

        logger.debug(
            f"Submitted send_message command: session={session_id}, "
            f"request_id={command.request_id}"
        )

    def submit_interrupt_session(
        self,
        session_id: str,
        user_id: int,
        callback: Optional[Callable[[dict], Awaitable[None]]] = None
    ):
        """
        Submit an interrupt session command.

        Args:
            session_id: Session UUID
            user_id: User ID
            callback: Optional callback for command result

        Raises:
            ValueError: If session not found
        """
        from .commands import InterruptSessionCommand

        mosaic_id = self._session_mosaic_map.get(session_id)
        if not mosaic_id:
            raise ValueError(f"Session {session_id} not found")

        instance, thread = self._get_running_mosaic(mosaic_id)
        loop = self._thread_loops[thread]

        command = InterruptSessionCommand(
            mosaic_id=mosaic_id,
            session_id=session_id,
            user_id=user_id,
            callback=callback
        )

        loop.call_soon_threadsafe(
            instance._command_queue.put_nowait, command
        )

        logger.debug(f"Submitted interrupt_session command: session={session_id}")

    def submit_close_session(
        self,
        session_id: str,
        node_id: int,
        user_id: int,
        force: bool = False,
        callback: Optional[Callable[[dict], Awaitable[None]]] = None
    ):
        """
        Submit a close session command.

        Note: Database status should be updated before calling this method.

        Args:
            session_id: Session UUID
            node_id: Node database ID
            user_id: User ID
            force: Force close even if session is busy
            callback: Optional callback for command result

        Raises:
            ValueError: If session not found
        """
        from .commands import CloseSessionCommand

        mosaic_id = self._session_mosaic_map.get(session_id)
        if not mosaic_id:
            # Session may already be closed
            logger.warning(f"Session {session_id} not found in mapping")
            return

        instance, thread = self._mosaic_instances.get(mosaic_id, (None, None))
        if not instance:
            logger.warning(f"Mosaic {mosaic_id} not running")
            return

        loop = self._thread_loops[thread]

        command = CloseSessionCommand(
            mosaic_id=mosaic_id,
            session_id=session_id,
            node_id=node_id,
            user_id=user_id,
            force=force,
            callback=callback
        )

        loop.call_soon_threadsafe(
            instance._command_queue.put_nowait, command
        )

        logger.debug(f"Submitted close_session command: session={session_id}")

    def submit_start_node(
        self,
        mosaic_id: int,
        node_id: str,
        callback: Optional[Callable[[dict], Awaitable[None]]] = None
    ):
        """
        Submit a start node command.

        Args:
            mosaic_id: Mosaic ID
            node_id: Node business ID
            callback: Optional callback for command result

        Raises:
            ValueError: If mosaic not running
        """
        from .commands import StartNodeCommand

        instance, thread = self._get_running_mosaic(mosaic_id)
        loop = self._thread_loops[thread]

        command = StartNodeCommand(
            mosaic_id=mosaic_id,
            node_id=node_id,
            callback=callback
        )

        loop.call_soon_threadsafe(
            instance._command_queue.put_nowait, command
        )

        logger.debug(f"Submitted start_node command: mosaic={mosaic_id}, node={node_id}")

    def submit_stop_node(
        self,
        mosaic_id: int,
        node_id: str,
        callback: Optional[Callable[[dict], Awaitable[None]]] = None
    ):
        """
        Submit a stop node command.

        Note: Session cleanup should be done before calling this method.

        Args:
            mosaic_id: Mosaic ID
            node_id: Node business ID
            callback: Optional callback for command result

        Raises:
            ValueError: If mosaic not running
        """
        from .commands import StopNodeCommand

        instance, thread = self._get_running_mosaic(mosaic_id)
        loop = self._thread_loops[thread]

        command = StopNodeCommand(
            mosaic_id=mosaic_id,
            node_id=node_id,
            callback=callback
        )

        loop.call_soon_threadsafe(
            instance._command_queue.put_nowait, command
        )

        logger.debug(f"Submitted stop_node command: mosaic={mosaic_id}, node={node_id}")

    def submit_restart_node(
        self,
        mosaic_id: int,
        node_id: str,
        callback: Optional[Callable[[dict], Awaitable[None]]] = None
    ):
        """
        Submit a restart node command.

        Args:
            mosaic_id: Mosaic ID
            node_id: Node business ID
            callback: Optional callback for command result

        Raises:
            ValueError: If mosaic not running
        """
        from .commands import RestartNodeCommand

        instance, thread = self._get_running_mosaic(mosaic_id)
        loop = self._thread_loops[thread]

        command = RestartNodeCommand(
            mosaic_id=mosaic_id,
            node_id=node_id,
            callback=callback
        )

        loop.call_soon_threadsafe(
            instance._command_queue.put_nowait, command
        )

        logger.debug(f"Submitted restart_node command: mosaic={mosaic_id}, node={node_id}")

    # ========== Session Registration ==========

    def register_session(self, session_id: str, mosaic_id: int):
        """
        Register session for command routing.

        Should be called when a session is created.

        Args:
            session_id: Session UUID
            mosaic_id: Mosaic ID that owns the session
        """
        self._session_mosaic_map[session_id] = mosaic_id
        logger.debug(f"Registered session {session_id} → mosaic {mosaic_id}")

    def unregister_session(self, session_id: str):
        """
        Unregister session.

        Should be called when a session is closed.

        Args:
            session_id: Session UUID
        """
        if session_id in self._session_mosaic_map:
            del self._session_mosaic_map[session_id]
            logger.debug(f"Unregistered session {session_id}")

    # ========== Helper Methods ==========

    def _get_running_mosaic(
        self, mosaic_id: int
    ) -> tuple[MosaicInstance, threading.Thread]:
        """Get a running mosaic or raise error"""
        if mosaic_id not in self._mosaic_instances:
            raise ValueError(f"Mosaic {mosaic_id} is not running")
        return self._mosaic_instances[mosaic_id]

    def _select_thread(self) -> threading.Thread:
        """Select a thread using round-robin scheduling"""
        threads = list(self._thread_loops.keys())
        if not threads:
            raise RuntimeError("No worker threads available")

        thread = threads[self._next_thread_index % len(threads)]
        self._next_thread_index += 1
        return thread

    def _create_event_loop(self, ready_event: threading.Event):
        """
        Create an event loop in the current thread.

        Args:
            ready_event: Event to signal when loop is ready

        This method runs in a worker thread.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Register this thread's loop
        current_thread = threading.current_thread()
        self._thread_loops[current_thread] = loop

        logger.info(f"Event loop created in {current_thread.name}")

        # Signal that the event loop is ready
        ready_event.set()

        # Run the event loop forever (blocks until loop.stop() is called)
        try:
            loop.run_forever()
        finally:
            loop.close()
            logger.info(f"Event loop closed in {current_thread.name}")

    # ========== Node Session Management (Unified for all node types) ==========

    async def get_or_create_node(
        self,
        mosaic_id: int,
        node_db_id: int
    ):
        """
        Get or create a node instance (uses MosaicInstance if mosaic is running).

        This method provides unified access to nodes across all types.
        For nodes in running mosaics, delegates to MosaicInstance.
        For standalone nodes (like Claude Code for WebSocket), creates directly.

        Args:
            mosaic_id: Mosaic instance ID
            node_db_id: Node database ID (primary key)

        Returns:
            Node instance (MosaicNode subclass)
        """
        # Check if mosaic is running
        if mosaic_id in self._mosaic_instances:
            instance, thread = self._mosaic_instances[mosaic_id]

            # Get node from running mosaic
            from sqlmodel import select
            from sqlalchemy.ext.asyncio import AsyncSession
            from ..models.node import Node
            from ..database import engine

            async with AsyncSession(engine) as db:
                result = await db.execute(
                    select(Node).where(
                        Node.id == node_db_id,
                        Node.mosaic_id == mosaic_id,
                        Node.deleted_at.is_(None)
                    )
                )
                node = result.scalar_one_or_none()

                if not node:
                    raise ValueError(f"Node {node_db_id} not found in mosaic {mosaic_id}")

            # Get from running instance
            loop = self._thread_loops[thread]
            future = asyncio.run_coroutine_threadsafe(
                self._get_node_from_instance(instance, node.node_id), loop
            )
            mosaic_node = future.result()

            if not mosaic_node:
                # Start the node if not running
                future = asyncio.run_coroutine_threadsafe(
                    instance.start_node(node.node_id), loop
                )
                mosaic_node = future.result()

            return mosaic_node

        else:
            # Mosaic not running, create standalone node (for WebSocket sessions)
            # This path is primarily for Claude Code nodes accessed via WebSocket
            return await self._create_standalone_claude_node(mosaic_id, node_db_id)

    async def _get_node_from_instance(self, instance, node_id: str):
        """Helper to get node from MosaicInstance"""
        return instance.get_node(node_id)

    async def _create_standalone_claude_node(
        self,
        mosaic_id: int,
        node_db_id: int
    ) -> ClaudeCodeNode:
        """
        Create a standalone Claude Code node (for WebSocket access).

        This is used when accessing Claude Code via WebSocket without
        starting the full mosaic instance.

        Args:
            mosaic_id: Mosaic instance ID
            node_db_id: Node database ID

        Returns:
            ClaudeCodeNode instance
        """
        key = (mosaic_id, node_db_id)

        if key in self._claude_nodes:
            return self._claude_nodes[key]

        # Get node from database
        from sqlmodel import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from ..models.node import Node
        from ..database import engine
        from ..config import get_instance_path
        from .utils import get_node_workspace

        async with AsyncSession(engine) as db:
            result = await db.execute(
                select(Node).where(
                    Node.id == node_db_id,
                    Node.mosaic_id == mosaic_id,
                    Node.deleted_at.is_(None)
                )
            )
            node = result.scalar_one_or_none()

            if not node:
                raise ValueError(f"Node {node_db_id} not found in mosaic {mosaic_id}")

            if node.node_type != "cc":
                raise ValueError(
                    f"Node {node_db_id} is not a Claude Code node (type: {node.node_type})"
                )

        # Calculate workspace
        instance_path = get_instance_path()
        workspace = get_node_workspace(node, instance_path)

        # Create Claude Code node
        claude_node = ClaudeCodeNode(
            node=node,
            workspace=workspace
        )

        await claude_node.start()
        self._claude_nodes[key] = claude_node

        logger.info(
            f"Created standalone Claude Code node: mosaic={mosaic_id}, node={node_db_id}"
        )

        return claude_node

    async def get_or_create_claude_session(
        self,
        mosaic_id: int,
        node_id: int,
        session_id: str,
        config: dict,
        on_message: Callable[[dict], Awaitable[None]]
    ) -> ClaudeCodeSession:
        """
        Get or create a Claude Code session.

        This is a convenience method for WebSocket layer.
        It uses the unified node management infrastructure.

        Args:
            mosaic_id: Mosaic instance ID
            node_id: Node ID (database primary key)
            session_id: Session UUID
            config: Session configuration
            on_message: Callback for sending messages to WebSocket

        Returns:
            ClaudeCodeSession instance
        """
        # Get or create the node (uses unified infrastructure)
        node = await self.get_or_create_node(mosaic_id, node_id)

        # Verify it's a Claude Code node
        if not isinstance(node, ClaudeCodeNode):
            raise ValueError(f"Node {node_id} is not a Claude Code node")

        # Try to get existing session first
        session = node.get_session(session_id)
        if session:
            # Update on_message callback for reconnection
            config['on_message'] = on_message
            session.on_message = on_message
            logger.info(f"Reusing existing session {session_id} for node {node_id}")
            return session

        # Session doesn't exist, create new one
        config['on_message'] = on_message
        session = await node.create_session(session_id, config)

        return session

    async def close_claude_session(
        self,
        mosaic_id: int,
        node_id: int,
        session_id: str
    ):
        """
        Close a Claude Code session.

        This uses the unified node management infrastructure.

        Args:
            mosaic_id: Mosaic instance ID
            node_id: Node ID (database primary key)
            session_id: Session UUID
        """
        # Try standalone nodes first
        key = (mosaic_id, node_id)

        if key in self._claude_nodes:
            node = self._claude_nodes[key]
            await node.close_session(session_id)
            logger.info(
                f"Closed Claude session: mosaic={mosaic_id}, "
                f"node={node_id}, session={session_id}"
            )
            return

        # Check if mosaic is running
        if mosaic_id in self._mosaic_instances:
            instance, thread = self._mosaic_instances[mosaic_id]

            # Get node business ID
            from sqlmodel import select
            from sqlalchemy.ext.asyncio import AsyncSession
            from ..models.node import Node
            from ..database import engine

            async with AsyncSession(engine) as db:
                result = await db.execute(
                    select(Node).where(
                        Node.id == node_id,
                        Node.deleted_at.is_(None)
                    )
                )
                node = result.scalar_one_or_none()

                if not node:
                    logger.warning(f"Node {node_id} not found")
                    return

            loop = self._thread_loops[thread]
            future = asyncio.run_coroutine_threadsafe(
                self._close_node_session(instance, node.node_id, session_id), loop
            )
            future.result()

            logger.info(
                f"Closed session in running mosaic: mosaic={mosaic_id}, "
                f"node={node_id}, session={session_id}"
            )
        else:
            logger.warning(
                f"Node not found: mosaic={mosaic_id}, node={node_id}"
            )

    async def _close_node_session(self, instance, node_id: str, session_id: str):
        """Helper to close session in running mosaic"""
        node = instance.get_node(node_id)
        if node:
            await node.close_session(session_id)

    async def stop_claude_node(
        self,
        mosaic_id: int,
        node_id: int
    ):
        """
        Stop a standalone Claude Code node (closes all sessions).

        This only applies to standalone nodes (not in running mosaics).
        For nodes in running mosaics, use stop_node via MosaicInstance.

        Args:
            mosaic_id: Mosaic instance ID
            node_id: Node ID (database primary key)
        """
        key = (mosaic_id, node_id)

        if key not in self._claude_nodes:
            return

        node = self._claude_nodes[key]
        await node.stop()
        del self._claude_nodes[key]

        logger.info(
            f"Stopped standalone Claude node: mosaic={mosaic_id}, node={node_id}"
        )
