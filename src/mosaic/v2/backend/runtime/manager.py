"""Runtime manager for all mosaic instances"""
import asyncio
import threading
import logging
from typing import Dict, Optional, Any, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..enum import MosaicStatus, NodeStatus, SessionMode, LLMModel
from ..exception import (
    RuntimeConfigError,
    RuntimeAlreadyStartedError,
    RuntimeNotStartedError,
    MosaicAlreadyRunningError,
    MosaicStartingError,
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

        # Thread safety locks
        self._thread_loops_lock = threading.Lock()  # Protects _thread_loops
        self._mosaic_instances_lock = threading.Lock()  # Protects _mosaic_instances

        # Starting counter for graceful shutdown coordination
        # Note: No lock needed - all async methods run in same event loop
        self._starting_count = 0  # Number of mosaics currently starting
        self._all_started_event: Optional[asyncio.Event] = None  # Set in start()

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

        # Create the event for tracking startup completion
        self._all_started_event = asyncio.Event()
        self._all_started_event.set()  # Initially set (no startups in progress)

        self._started = True
        logger.info(
            f"RuntimeManager started successfully with {max_threads} worker threads"
        )

    async def stop(self):
        """
        Stop the runtime manager.

        This must be called from the main event loop (FastAPI shutdown).

        Steps:
        1. Wait for all in-progress mosaic startups to complete (graceful shutdown)
        2. Stop all running mosaic instances (via command queue)
        3. Stop all worker thread event loops
        4. Shutdown thread pool (wait for all threads to finish)
        5. Stop global ZMQ server

        Note:
            All mosaic stop operations use command queue for consistency.
            The starting counter mechanism ensures no orphaned instances are created.
            This method blocks until all in-progress startups complete (usually brief).
        """
        if not self._started:
            logger.warning("RuntimeManager is not started, nothing to stop")
            return

        logger.info("Stopping RuntimeManager...")

        # Wait for all in-progress mosaic startups to complete
        # This ensures no orphaned instances are created
        if self._all_started_event:
            logger.info("Waiting for all in-progress mosaic startups to complete...")
            await self._all_started_event.wait()
            logger.info("All mosaic startups completed")

        try:
            # 1. Stop all running mosaic instances (parallel)
            # Defensive check: filter out placeholders (should not exist after wait)
            with self._mosaic_instances_lock:
                mosaic_items = []
                for mosaic_id, (instance, thread) in self._mosaic_instances.items():
                    if instance is not None:
                        mosaic_items.append((mosaic_id, instance, thread))
                    else:
                        # This should never happen after waiting for all startups to complete
                        logger.warning(
                            f"Found placeholder for mosaic_id={mosaic_id} after startup "
                            f"completion wait - this indicates a bug in synchronization logic"
                        )

            if mosaic_items:
                logger.info(f"Stopping {len(mosaic_items)} running mosaic instances...")

                # Import command here to avoid circular import
                from .command import StopMosaicCommand

                # Create stop tasks for all mosaics
                stop_tasks = []
                for mosaic_id, instance, thread in mosaic_items:
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

                # Clear the instances map (with lock protection)
                with self._mosaic_instances_lock:
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
            self._starting_count = 0  # Reset counter
            self._all_started_event = None  # Clear event

            logger.info("RuntimeManager stopped successfully")

        except Exception as e:
            logger.error(f"Error during RuntimeManager shutdown: {e}")
            # Reset state even on error to allow restart
            self._starting_count = 0
            self._all_started_event = None
            raise

    # ========== Mosaic Lifecycle ==========

    async def start_mosaic(
        self,
        mosaic: 'Mosaic',
        mosaic_path: Path,
        timeout: float = 30.0
    ) -> None:
        """
        Start a mosaic instance.

        This is the ONLY operation that uses run_coroutine_threadsafe for direct
        coroutine invocation. All other operations use the command queue mechanism
        (call_soon_threadsafe + Future) for cross-thread communication.

        Steps:
        1. Increment starting counter (for graceful shutdown coordination)
        2. Check and reserve slot (with lock protection to prevent race condition)
        3. Select a worker thread using round-robin
        4. Create MosaicInstance with mosaic model object and path
        5. Start instance in worker thread (run_coroutine_threadsafe)
        6. Create background task to wait for startup completion
        7. Wait for background task with timeout
        8. If task completes: get result; if timeout: raise error (task continues)

        Args:
            mosaic: Mosaic model object (validated by FastAPI layer)
            mosaic_path: Mosaic working directory path (computed by API layer)
            timeout: Maximum wait time in seconds

        Raises:
            MosaicStartingError: If mosaic is already starting (concurrent start attempt)
            MosaicAlreadyRunningError: If mosaic is already running
            RuntimeInternalError: If no worker threads available
            RuntimeTimeoutError: If startup times out

        Note:
            Uses starting counter to coordinate with stop() method for graceful shutdown.
            The stop() method waits for all in-progress startups to complete.
            Uses placeholder (None, None) during startup to prevent race conditions.
            Multiple concurrent start requests for the same mosaic will be rejected.
            Counter decrement is ALWAYS handled by background task (in its finally block).
            FastAPI layer must validate mosaic existence and permissions before calling.
            FastAPI layer must also compute and provide mosaic_path.
        """
        logger.info(
            f"Starting mosaic: id={mosaic.id}, name={mosaic.name}, "
            f"path={mosaic_path}"
        )

        # 1. Increment starting counter (for graceful shutdown coordination)
        # No lock needed - all operations run in same event loop (no await yet)
        self._starting_count += 1
        if self._all_started_event:
            self._all_started_event.clear()
        logger.debug(
            f"Incremented starting counter: {self._starting_count} "
            f"(mosaic id={mosaic.id})"
        )

        # 2. Check and reserve slot (atomic operation with lock)
        with self._mosaic_instances_lock:
            if mosaic.id in self._mosaic_instances:
                instance, _ = self._mosaic_instances[mosaic.id]
                if instance is None:
                    # Placeholder exists - another request is starting this mosaic
                    # Decrement counter before raising
                    self._decrement_starting_counter(mosaic.id)
                    raise MosaicStartingError(
                        f"Mosaic with id={mosaic.id} is already starting, please wait"
                    )
                else:
                    # Real instance exists - mosaic is already running
                    # Decrement counter before raising
                    self._decrement_starting_counter(mosaic.id)
                    raise MosaicAlreadyRunningError(
                        f"Mosaic with id={mosaic.id} is already running"
                    )

            # Reserve slot with placeholder to prevent concurrent starts
            self._mosaic_instances[mosaic.id] = (None, None)
            logger.debug(f"Reserved slot for mosaic id={mosaic.id} (placeholder)")

        # 3. Select a worker thread using round-robin
        thread = self._select_thread()

        # Get the event loop for the selected thread
        with self._thread_loops_lock:
            loop = self._thread_loops.get(thread)

        if not loop:
            # Cleanup placeholder and decrement counter before raising
            with self._mosaic_instances_lock:
                self._mosaic_instances.pop(mosaic.id, None)
            self._decrement_starting_counter(mosaic.id)
            raise RuntimeInternalError(
                f"Event loop not found for thread: {thread.name}"
            )

        # 4. Create MosaicInstance with mosaic model object and path
        from .mosaic_instance import MosaicInstance

        mosaic_instance = MosaicInstance(
            mosaic=mosaic,
            mosaic_path=mosaic_path,
            async_session_factory=self.async_session_factory,
            config=self.config
        )

        logger.debug(
            f"Created MosaicInstance for mosaic name={mosaic.name} "
            f"in thread={thread.name}, path={mosaic_path}"
        )

        # 5. Start instance in worker thread (run_coroutine_threadsafe)
        # This is the ONLY operation that uses run_coroutine_threadsafe
        future = asyncio.run_coroutine_threadsafe(mosaic_instance.start(), loop)

        # 6. Create background task to wait for startup completion
        # This task will handle counter decrement in its finally block
        startup_task = asyncio.create_task(
            self._wait_for_startup_completion(mosaic.id, mosaic_instance, future, thread)
        )

        # 7. Wait for background task with timeout
        done, pending = await asyncio.wait([startup_task], timeout=timeout)

        # 8. Check result
        if startup_task in done:
            # Task completed - check if it succeeded or failed
            # This will re-raise any exception from the background task
            await startup_task
            logger.info(
                f"Mosaic started successfully: id={mosaic.id}, name={mosaic.name} "
                f"in thread={thread.name}"
            )
        else:
            # Timeout - task is still running in background
            logger.error(
                f"Mosaic startup timeout: id={mosaic.id}, name={mosaic.name} "
                f"after {timeout}s. Background task will continue and handle completion."
            )
            raise RuntimeTimeoutError(
                f"Mosaic startup timed out after {timeout}s"
            )

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
        logger.info(f"Stopping mosaic: id={mosaic.id}, name={mosaic.name}")

        # Import command here to avoid circular import
        from .command import StopMosaicCommand

        # 1. Create StopMosaicCommand
        command = StopMosaicCommand(mosaic=mosaic)

        # 2. Submit command and wait for completion
        await self._submit_command_and_wait(mosaic.id, command, timeout)

        # 3. Remove instance from _mosaic_instances cache (with lock protection)
        with self._mosaic_instances_lock:
            self._mosaic_instances.pop(mosaic.id, None)

        logger.info(f"Mosaic stopped successfully: id={mosaic.id}, name={mosaic.name}")

    async def get_mosaic_status(self, mosaic: 'Mosaic') -> MosaicStatus:
        """
        Get mosaic runtime status.

        Args:
            mosaic: Mosaic model object (validated by FastAPI layer)

        Returns:
            MosaicStatus.STARTING if placeholder exists (being initialized)
            MosaicStatus.RUNNING if actual instance exists
            MosaicStatus.STOPPED if not in cache

        Note:
            FastAPI layer must validate mosaic existence and permissions before calling.
            Uses lock protection to ensure consistent read of instance state.
        """
        with self._mosaic_instances_lock:
            if mosaic.id not in self._mosaic_instances:
                return MosaicStatus.STOPPED

            instance, _ = self._mosaic_instances[mosaic.id]
            if instance is None:
                # Placeholder exists - mosaic is starting
                return MosaicStatus.STARTING
            else:
                # Real instance exists - mosaic is running
                return MosaicStatus.RUNNING

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

    async def get_node_status(self, node: 'Node') -> NodeStatus:
        """
        Get node runtime status.

        Args:
            node: Node model object (validated by FastAPI layer)

        Returns:
            NodeStatus.RUNNING or NodeStatus.STOPPED

        Raises:
            MosaicNotRunningError: If mosaic not running
            MosaicStartingError: If mosaic is starting but not ready yet
            RuntimeTimeoutError: If query times out

        Note:
            FastAPI layer must validate node existence and permissions before calling.
            If mosaic is not running or still starting, returns NodeStatus.STOPPED.
        """
        # Check if mosaic is running (with lock protection)
        with self._mosaic_instances_lock:
            if node.mosaic_id not in self._mosaic_instances:
                return NodeStatus.STOPPED

            instance, _ = self._mosaic_instances[node.mosaic_id]
            # If mosaic is starting (placeholder), nodes are not ready yet
            if instance is None:
                return NodeStatus.STOPPED

        # Import command here to avoid circular import
        from .command import GetNodeStatusCommand

        # Create GetNodeStatusCommand
        command = GetNodeStatusCommand(node=node)

        # Submit command and wait for result (with short timeout for query)
        status = await self._submit_command_and_wait(
            node.mosaic_id, command, timeout=30.0
        )
        return status

    # ========== Session Operations ==========

    async def create_session(
        self,
        node: 'Node',
        mode: 'SessionMode',
        model: 'LLMModel',
        token_threshold_enabled: bool = False,
        token_threshold: int = 60000,
        inherit_threshold: bool = True,
        timeout: float = 10.0
    ) -> str:
        """
        Create a runtime session in an agent node.

        Uses command queue with Future for async wait.

        This method is ONLY for agent sessions (PROGRAM or CHAT mode).
        Background sessions are automatically created by the runtime when events arrive.

        Steps:
        1. Generate a unique session_id
        2. Create CreateSessionCommand with node, session_id, config
        3. Submit command and wait for completion

        Args:
            node: Node model object (validated by FastAPI layer)
            mode: Session mode (PROGRAM or CHAT)
            model: LLM model to use (SONNET, OPUS, or HAIKU)
            token_threshold_enabled: Enable token threshold monitoring (default: False)
            token_threshold: Token count threshold (default: 60000)
            inherit_threshold: Whether child sessions inherit threshold config (default: True)
            timeout: Maximum wait time in seconds

        Returns:
            Generated session_id string

        Raises:
            MosaicNotRunningError: If mosaic not running
            NodeNotFoundError: If node not found
            RuntimeTimeoutError: If operation times out

        Note:
            FastAPI layer must validate node existence and permissions before calling.
            FastAPI layer must ensure mode is PROGRAM or CHAT (not BACKGROUND).
            The session_id is auto-generated using UUID.
        """
        # Generate unique session_id
        import uuid
        session_id = str(uuid.uuid4())

        logger.info(
            f"Creating session: session_id={session_id}, "
            f"node_id={node.node_id}, mosaic_id={node.mosaic_id}, "
            f"mode={mode.value}, model={model.value}, "
            f"token_threshold_enabled={token_threshold_enabled}, "
            f"token_threshold={token_threshold}, "
            f"inherit_threshold={inherit_threshold}"
        )

        # Import command here to avoid circular import
        from .command import CreateSessionCommand

        # Build config dictionary for agent session
        config = {
            'mode': mode,
            'model': model,
            'token_threshold_enabled': token_threshold_enabled,
            'token_threshold': token_threshold,
            'inherit_threshold': inherit_threshold
        }

        # Add mcp_servers from node config if present
        if node.config and 'mcp_servers' in node.config:
            config['mcp_servers'] = node.config['mcp_servers']

        # Create CreateSessionCommand
        command = CreateSessionCommand(
            node=node,
            session_id=session_id,
            config=config
        )

        # Submit command and wait for completion
        await self._submit_command_and_wait(node.mosaic_id, command, timeout)

        logger.info(
            f"Session created successfully: session_id={session_id}, node_id={node.node_id}"
        )

        return session_id

    def submit_send_message(self, node: 'Node', session: 'Session', message: str) -> None:
        """
        Submit a send message command (fire-and-forget).

        Does NOT wait for completion. Message sending is asynchronous.

        Args:
            node: Node model object (validated by FastAPI layer)
            session: Session model object (validated by FastAPI layer)
            message: User message content

        Raises:
            MosaicNotRunningError: If mosaic not running

        Note:
            This is a non-blocking operation. Use this for user message submission.
            FastAPI layer must validate node and session existence/permissions before calling.
        """
        logger.debug(
            f"Submitting message for session: session_id={session.session_id}, "
            f"node_id={node.node_id}, message_length={len(message)}"
        )

        # Import command here to avoid circular import
        from .command import SendMessageCommand

        # Create SendMessageCommand (no future needed, fire-and-forget)
        command = SendMessageCommand(
            node=node,
            session=session,
            message=message,
            future=None  # Don't wait for result
        )

        # Submit command without waiting (fire-and-forget)
        self._submit_command_no_wait(node.mosaic_id, command)

        logger.debug(
            f"Message submitted for session: session_id={session.session_id}, node_id={node.node_id}"
        )

    async def interrupt_session(self, node: 'Node', session: 'Session', timeout: float = 5.0) -> None:
        """
        Interrupt a running session.

        Uses command queue with Future for async wait.

        Args:
            node: Node model object (validated by FastAPI layer)
            session: Session model object (validated by FastAPI layer)
            timeout: Maximum wait time in seconds

        Raises:
            MosaicNotRunningError: If mosaic not running
            SessionNotFoundError: If session not found
            RuntimeTimeoutError: If operation times out

        Note:
            FastAPI layer must validate node and session existence/permissions before calling.
        """
        logger.info(
            f"Interrupting session: session_id={session.session_id}, node_id={node.node_id}"
        )

        # Import command here to avoid circular import
        from .command import InterruptSessionCommand

        # Create InterruptSessionCommand
        command = InterruptSessionCommand(
            node=node,
            session=session
        )

        # Submit command and wait for completion
        await self._submit_command_and_wait(node.mosaic_id, command, timeout)

        logger.info(
            f"Session interrupted successfully: session_id={session.session_id}, node_id={node.node_id}"
        )

    async def close_session(
        self,
        node: 'Node',
        session: 'Session',
        timeout: float = 10.0
    ) -> None:
        """
        Close a runtime session.

        Uses command queue with Future for async wait.

        Steps:
        1. Create CloseSessionCommand
        2. Submit command and wait for completion

        Args:
            node: Node model object (validated by FastAPI layer)
            session: Session model object (validated by FastAPI layer)
            timeout: Maximum wait time in seconds

        Raises:
            MosaicNotRunningError: If mosaic not running
            SessionNotFoundError: If session not found
            RuntimeTimeoutError: If operation times out

        Note:
            Database status should be updated BEFORE calling this method.
            FastAPI layer must validate node and session existence/permissions before calling.
        """
        logger.info(
            f"Closing session: session_id={session.session_id}, node_id={node.node_id}"
        )

        # Import command here to avoid circular import
        from .command import CloseSessionCommand

        # Create CloseSessionCommand
        command = CloseSessionCommand(
            node=node,
            session_id=session.session_id
        )

        # Submit command and wait for completion
        await self._submit_command_and_wait(node.mosaic_id, command, timeout)

        logger.info(
            f"Session closed successfully: session_id={session.session_id}, node_id={node.node_id}"
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
        # Use shield() to protect future from cancellation on timeout.
        # The worker thread task should continue running even if we stop waiting.
        try:
            result = await asyncio.wait_for(
                asyncio.shield(future),
                timeout=timeout
            )
            logger.debug(
                f"Command completed: {command.__class__.__name__} "
                f"for mosaic_id={mosaic_id}"
            )
            return result
        except asyncio.TimeoutError:
            # Timeout occurred, but the worker thread task is still running (shielded).
            # We simply stop waiting and let the task complete on its own.
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

    async def _wait_for_startup_completion(
        self,
        mosaic_id: int,
        mosaic_instance: 'MosaicInstance',
        future: 'asyncio.Future',
        thread: threading.Thread
    ) -> None:
        """
        Background task to wait for mosaic startup completion and manage counter.

        This task is created immediately when start_mosaic begins the startup process.
        It waits for the actual startup to complete (without timeout) and handles cleanup.
        The starting counter is ALWAYS decremented in this task's finally block.

        Philosophy:
        - User timeout: User stops waiting and receives error (start_mosaic returns)
        - Startup process: Continues running, never times out internally
        - This task: Waits indefinitely for completion, handles result, manages counter

        Steps:
        1. Wait for startup to complete (no timeout, let it finish naturally)
        2. If success: Replace placeholder with actual instance
        3. If failure: Remove placeholder and re-raise exception
        4. Always decrement starting counter (in finally block)

        Args:
            mosaic_id: Mosaic database ID
            mosaic_instance: The MosaicInstance being started
            future: The concurrent.futures.Future from run_coroutine_threadsafe
            thread: The worker thread running the instance

        Raises:
            Exception: Re-raises any exception from the startup process

        Note:
            This task runs for ALL startup attempts (not just timeouts).
            Counter management is centralized here to avoid race conditions.
        """
        try:
            logger.debug(
                f"Background task waiting for mosaic startup completion: id={mosaic_id}"
            )

            # Wait for the startup to complete (no timeout - let it finish naturally)
            await asyncio.wrap_future(future)

            # Startup succeeded! Replace placeholder with actual instance
            with self._mosaic_instances_lock:
                self._mosaic_instances[mosaic_id] = (mosaic_instance, thread)

            logger.debug(
                f"Mosaic startup completed successfully: id={mosaic_id}"
            )

        except Exception as e:
            # Startup failed, remove placeholder
            with self._mosaic_instances_lock:
                self._mosaic_instances.pop(mosaic_id, None)

            logger.error(
                f"Mosaic startup failed: id={mosaic_id}, error: {e}"
            )
            # Re-raise to propagate to start_mosaic caller
            raise

        finally:
            # Always decrement starting counter (success, failure, or timeout)
            self._decrement_starting_counter(mosaic_id)
            logger.debug(
                f"Background task completed for mosaic startup: id={mosaic_id}"
            )

    def _decrement_starting_counter(self, mosaic_id: int) -> None:
        """
        Decrement the starting counter and signal completion if all startups are done.

        This method is called when a mosaic startup completes (success or failure).
        When the counter reaches 0, it signals _all_started_event to allow graceful shutdown.

        Args:
            mosaic_id: Mosaic database ID (for logging purposes)

        Note:
            No lock needed - all async operations run in same event loop.
            This method should only be called from async methods in the main event loop.
        """
        self._starting_count -= 1
        logger.debug(
            f"Decremented starting counter: {self._starting_count} "
            f"(mosaic id={mosaic_id})"
        )

        # If all startups are complete, signal the event
        if self._starting_count == 0 and self._all_started_event:
            self._all_started_event.set()
            logger.info("All mosaic startups completed - ready for graceful shutdown")

    def _get_running_mosaic(self, mosaic_id: int) -> tuple['MosaicInstance', threading.Thread]:
        """
        Get a running mosaic instance and its thread.

        Args:
            mosaic_id: Mosaic database ID

        Returns:
            Tuple of (MosaicInstance, Thread)

        Raises:
            MosaicNotRunningError: If mosaic not running
            MosaicStartingError: If mosaic is starting but not ready yet

        Note:
            This method rejects placeholder entries (mosaic is starting but not ready).
            Callers should wait for startup to complete before submitting commands.
        """
        if mosaic_id not in self._mosaic_instances:
            raise MosaicNotRunningError(f"Mosaic with id={mosaic_id} is not running")

        instance, thread = self._mosaic_instances[mosaic_id]

        # Check for placeholder (mosaic is starting)
        if instance is None:
            raise MosaicStartingError(
                f"Mosaic with id={mosaic_id} is currently starting, please retry later"
            )

        return instance, thread

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
