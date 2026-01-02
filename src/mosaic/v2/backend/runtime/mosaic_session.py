"""Base class for runtime session representations"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .mosaic_node import MosaicNode

logger = logging.getLogger(__name__)


class MosaicSession(ABC):
    """
    Base class for all runtime session types.

    Architecture:
    - Session manages its own queue and worker task
    - Session has simple runtime flags: initialized, should_close
    - When session decides to close, it marks should_close and submits CloseSessionCommand
    - Worker loop continues running, only processing special events when should_close is True
    - External close via CloseSessionCommand removes session from node's maps

    Different session types:
    - Agent sessions: Use database Session model (subclass stores in self.session)
    - Scheduler/Email sessions: Runtime-only (no database)

    State Management:
        Runtime flags (managed by session):
        - _initialized: False after creation, True after initialize() completes
        - _should_close: False normally, True when session decides to close
        - Worker task: None before initialize(), running after initialize(), None after close()

        Database states (for agent sessions only, managed by subclass):
        - Agent sessions can manage their own database status (PENDING, ACTIVE, CLOSED, ARCHIVED)
        - Runtime-only sessions don't use database

    Lifecycle:
    1. Creation: MosaicNode creates instance (_initialized=False)
    2. Initialization: Call initialize() to set up resources and start worker (_initialized=True)
    3. Processing: Worker task processes events from queue
    4. Auto-close decision: Session sets _should_close=True, submits CloseSessionCommand
    5. Special events: Worker continues processing special events when _should_close=True
    6. External close: Command handler calls close() (stops worker)

    Subclasses must implement:
    - _on_initialize(): Initialize session-specific resources
    - _handle_event(): Process a single event
    - _should_close_after_event(): Decide if session should close after event
    - _on_close(): Clean up session-specific resources
    """

    def __init__(
        self,
        session_id: str,
        node: 'MosaicNode',
        async_session_factory,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize session.

        Args:
            session_id: Session identifier (required)
            node: Parent MosaicNode reference (required)
            async_session_factory: AsyncSession factory for database access (required)
            config: Session configuration (optional, subclass-specific)

        Note:
            Does NOT initialize resources or start worker.
            Call initialize() to begin operation.
            Subclasses that use database should accept Session object in their own __init__.
        """
        self.session_id = session_id
        self.node = node
        self.async_session_factory = async_session_factory
        self.config = config

        # State flags
        self._initialized = False
        self._should_close = False

        # Queue and worker management (owned by session)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

        logger.info(
            f"MosaicSession created: session_id={self.session_id}, "
            f"node_id={self.node.node.node_id}"
        )

    # ========== Lifecycle Methods ==========

    async def initialize(self):
        """
        Initialize session resources and start worker task.

        Called once by MosaicNode when session is created.
        This method:
        1. Calls subclass initialization hook (_on_initialize)
        2. Sets _initialized flag to True
        3. Starts the worker task for event processing

        Note:
            Database state management is handled by subclass (for agent sessions).
            After this method completes, session is fully operational.

        Idempotent: safe to call multiple times (skips if already initialized).

        Raises:
            Exception: Any exception from _on_initialize() will propagate
        """
        if self._initialized:
            logger.debug(f"Session already initialized: {self.session_id}")
            return

        if self._worker_task is not None:
            logger.warning(f"Worker already running for session: {self.session_id}")
            return

        logger.info(f"Initializing session: {self.session_id}")

        try:
            # 1. Call subclass initialization
            await self._on_initialize()

            # 2. Mark as initialized
            self._initialized = True

            # 3. Start worker task
            self._worker_task = asyncio.create_task(
                self._event_loop(),
                name=f"session-worker-{self.session_id}"
            )

            logger.info(
                f"Session initialized and worker started: session_id={self.session_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to initialize session {self.session_id}: {e}",
                exc_info=True
            )
            raise

    def enqueue_event(self, event: dict):
        """
        Enqueue an event for processing.

        This is called by MosaicNode when an event is routed to this session.

        Args:
            event: Event data dict

        Note:
            Non-blocking. Events are processed asynchronously by the worker task.
            If _should_close is True, non-special events will be ignored by worker.
        """
        self._queue.put_nowait(event)

        logger.debug(
            f"Event enqueued: session_id={self.session_id}, "
            f"event_type={event.get('event_type', 'UNKNOWN')}, "
            f"queue_size={self._queue.qsize()}"
        )

    async def close(self):
        """
        Close session and release resources.

        This is called externally by MosaicNode (via command handler) to close the session.

        Steps:
        1. Cancel worker task (if running)
        2. Call subclass close hook (only if session was initialized)
        3. Reset state flags

        Note:
            Database state management is handled by subclass (for agent sessions).
            Should not raise exceptions. Log errors and continue cleanup.

        Idempotent: safe to call multiple times.
        """
        logger.info(f"Closing session: {self.session_id}")

        # 1. Cancel worker task (if running)
        if self._worker_task is not None and not self._worker_task.done():
            logger.debug(f"Cancelling worker task: {self.session_id}")
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass  # Expected
            except Exception as e:
                logger.error(
                    f"Error waiting for worker cancellation: {self.session_id}, {e}",
                    exc_info=True
                )
            self._worker_task = None

        # 2. Call subclass close hook (only if session was initialized)
        if self._initialized:
            try:
                await self._on_close()
            except Exception as e:
                logger.error(
                    f"Error during session close: session_id={self.session_id}, "
                    f"error={e}",
                    exc_info=True
                )
                # Don't raise - close should always succeed

        # 3. Reset state flags
        self._initialized = False
        self._should_close = False

        logger.info(f"Session closed: {self.session_id}")

    # ========== Event Processing ==========

    async def _event_loop(self):
        """
        Event processing loop (runs as background task).

        Continuously:
        - Fetches events from queue (blocking)
        - Processes events based on current flags
        - When _should_close is False: processes all events
        - When _should_close is True: only processes special events
        - Loop only exits on cancellation or exception

        Note:
            When session decides to close (_should_close_after_event returns True):
            1. Set _should_close flag to True
            2. Submit CloseSessionCommand to MosaicInstance
            3. Continue loop (do NOT break)
            4. Only process special events from this point

            CancelledError is caught and not re-raised (cancellation is normal).
        """
        await self._on_event_loop_started()
        logger.info(f"Session worker loop started: {self.session_id}")

        try:
            while True:
                # Fetch next event (blocking)
                event = await self._queue.get()

                event_id = event.get('event_id', 'UNKNOWN')
                event_type = event.get('event_type', 'UNKNOWN')

                # Should close: only process special events
                if self._should_close:
                    if not self._is_special_event(event):
                        logger.debug(
                            f"Ignoring non-special event (should_close=True): "
                            f"session_id={self.session_id}, event_type={event_type}"
                        )
                        self._queue.task_done()
                        continue

                logger.info(
                    f"Processing event: session_id={self.session_id}, "
                    f"event_id={event_id}, event_type={event_type}"
                )

                try:
                    # Process event (sequential within this session)
                    await self._handle_event(event)

                    logger.debug(
                        f"Event processed: session_id={self.session_id}, "
                        f"event_id={event_id}, event_type={event_type}"
                    )

                    # Check if session should close after this event (only when not already closing)
                    if not self._should_close and await self._should_close_after_event(event):
                        logger.info(
                            f"Session should close after event: session_id={self.session_id}, "
                            f"event_type={event_type}"
                        )

                        # Mark should close flag
                        self._should_close = True

                        # Submit close command immediately
                        self._submit_close_command()

                        # Do NOT break - continue loop to process special events

                except Exception as e:
                    logger.error(
                        f"Error processing event: session_id={self.session_id}, "
                        f"event_id={event_id}, error={e}",
                        exc_info=True
                    )
                    # Continue to next event (don't close session on error)

                finally:
                    self._queue.task_done()

        except asyncio.CancelledError:
            logger.info(f"Session worker cancelled: {self.session_id}")

        finally:
            await self._on_event_loop_exited()
            logger.info(f"Session worker exited: {self.session_id}")

    def _submit_close_command(self):
        """
        Submit CloseSessionCommand to MosaicInstance for external close.

        This is called when the session decides it should close (auto-close logic).
        The command triggers external close: session.close() and removal from node's maps.

        Uses MosaicInstance.process_command() for immediate submission.

        Note:
            Does not raise exceptions - logs errors and continues.
        """
        try:
            from .command import CloseSessionCommand

            command = CloseSessionCommand(
                node=self.node.node,
                session_id=self.session_id
            )

            # Submit command via MosaicInstance.process_command()
            self.node.mosaic_instance.process_command(command)

            logger.info(
                f"Close command submitted for session: session_id={self.session_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to submit close command: session_id={self.session_id}, "
                f"error={e}",
                exc_info=True
            )
            # Don't raise - session can still be closed externally

    def _is_special_event(self, event: dict) -> bool:
        """
        Determine if an event is "special" (should be processed when _should_close is True).

        Special events are those that are critical for cleanup or shutdown,
        and must be processed even when the session is marked for closure.

        Args:
            event: Event data dict

        Returns:
            True if event is special, False otherwise

        Default behavior:
            Returns False for all events. Most session types don't have special events.
            Agent session subclasses can override to define their own special events
            (e.g., force_close, cleanup, final_message).

        Note:
            This is NOT an abstract method - default implementation returns False.
            Subclasses only need to override if they have special event handling.
        """
        return False

    # ========== Abstract Methods (Must be implemented by subclasses) ==========

    @abstractmethod
    async def _on_initialize(self):
        """
        Subclass initialization hook.

        Called once during initialize() before starting worker task.
        Subclasses should set up their specific resources here.

        Examples:
        - Agent sessions: Initialize Claude SDK client, load system prompt
        - Email sessions: Connect to SMTP server
        - Scheduler sessions: Load schedule configuration

        Raises:
            Exception: Any exception will cause initialization to fail
        """
        pass

    @abstractmethod
    async def _handle_event(self, event: dict) -> None:
        """
        Handle an event (subclass-specific logic).

        Called by _event_loop() for each queued event.

        Args:
            event: Event data dict containing:
                - event_id (str): Unique event identifier
                - event_type (str): Event type
                - source_node_id (str): Source node
                - source_session_id (str): Source session
                - target_node_id (str): Target node (this node)
                - target_session_id (str): Target session (this session)
                - payload (dict, optional): Event-specific data

        Examples:
        - Agent sessions: Route to Claude SDK based on event type
        - Email sessions: Send email
        - Scheduler sessions: Execute scheduled task

        Note:
            Should not raise exceptions for recoverable errors.
            Exceptions are caught and logged by the worker loop.
        """
        pass

    @abstractmethod
    async def _should_close_after_event(self, event: dict) -> bool:
        """
        Determine if session should close after processing an event.

        This method is called by the worker loop after each event is successfully
        processed (only when not already closing). Subclasses must implement their
        closure logic here.

        Args:
            event: The event that was just processed

        Returns:
            True if session should close (marks SHOULD_CLOSE, submits command, continues loop)
            False to continue processing events normally

        Note:
            Returning True triggers:
            1. Runtime flag _should_close set to True
            2. CloseSessionCommand submitted to MosaicInstance
            3. Worker loop continues (processes special events only)

            Actual close happens externally via command handler.

            This method is async to support database queries (e.g., checking Connection table).
        """
        pass

    @abstractmethod
    async def _on_close(self):
        """
        Subclass close hook.

        Called during close() after worker task has been cancelled.
        Subclasses should release their specific resources here.

        Examples:
        - Agent sessions: Close Claude SDK client, flush message buffers
        - Email sessions: Disconnect from SMTP server
        - Scheduler sessions: Cancel pending timers

        Note:
            Should not raise exceptions. Log errors and continue cleanup.
            Worker task is already stopped when this is called.
        """
        pass

    @abstractmethod
    async def _on_event_loop_started(self):
        pass

    @abstractmethod
    async def _on_event_loop_exited(self):
        pass

    # ========== Optional Methods ==========

    async def interrupt(self) -> None:
        """
        Interrupt the session (only for sessions that support interruption).

        This method is called to interrupt an ongoing operation in the session.
        For example, agent sessions can interrupt Claude SDK requests.

        Default implementation raises NotImplementedError.
        Subclasses that support interruption should override this method.

        Raises:
            NotImplementedError: If this session type doesn't support interruption

        Note:
            This is typically implemented by enqueuing an interrupt event
            or calling an interrupt API (e.g., Claude SDK interrupt).
        """
        raise NotImplementedError(
            f"Session type {self.__class__.__name__} does not support interrupt"
        )

    # ========== State Properties ==========

    @property
    def is_initialized(self) -> bool:
        """Check if session is initialized"""
        return self._initialized
