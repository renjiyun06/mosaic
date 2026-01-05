"""Scheduler node and session implementation"""
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..mosaic_node import MosaicNode
from ..mosaic_session import MosaicSession
from ...enum import EventType, SessionMode
from ...exception import SessionNotFoundError, SessionConflictError

if TYPE_CHECKING:
    from ...model.node import Node

logger = logging.getLogger(__name__)


class SchedulerNode(MosaicNode):
    """
    Scheduler node - manages scheduled tasks and event broadcasting.

    This node type provides:
    - APScheduler integration for cron-based scheduling
    - Event broadcasting to subscribed nodes
    - Singleton session pattern (one long-lived session per node)
    - Pure runtime (no database persistence)

    Architecture:
    - Node creates a single long-lived session on startup
    - APScheduler triggers send events through this session
    - Events are broadcast to all subscribers via Subscription table
    - Session lifecycle tied to node lifecycle
    """

    # Fixed session ID for the singleton scheduler session
    SCHEDULER_SESSION_ID = "scheduler_main"

    def __init__(
        self,
        node: 'Node',
        node_path: Path,
        mosaic_instance,
        async_session_factory,
        config: dict
    ):
        """
        Initialize Scheduler node.

        Args:
            node: Node model object from database
            node_path: Node working directory path
            mosaic_instance: Parent MosaicInstance reference
            async_session_factory: AsyncSession factory for database access
            config: System configuration dict (must contain 'zmq')

        Note:
            Scheduler-specific configuration (cron, message) is read from node.config
        """
        super().__init__(node, node_path, mosaic_instance, async_session_factory, config)

        # Extract scheduler configuration from node.config (not system config)
        self._cron = self.node.config.get("cron")
        self._message = self.node.config.get("message", "Scheduled task triggered")

        # APScheduler instance (initialized in _on_start)
        self._scheduler: Optional[AsyncIOScheduler] = None

        logger.info(
            f"Initialized SchedulerNode: node_id={node.node_id}, "
            f"cron={self._cron}, message_preview={self._message[:50] if self._message else 'None'}..."
        )

    # ========== Lifecycle Hooks ==========

    async def _on_start(self) -> None:
        """
        Node startup hook.

        Steps:
        1. Validate cron configuration
        2. Create and start APScheduler
        3. Register scheduled task
        4. Create singleton scheduler session (directly, avoiding command queue deadlock)

        Raises:
            RuntimeConfigError: If cron configuration is missing or invalid

        Note:
            Session is created directly instead of via CreateSessionCommand to avoid deadlock.
            _on_start is called from command loop, cannot wait for another command.
        """
        logger.info(f"SchedulerNode {self.node.node_id} starting...")

        # 1. Validate cron configuration
        if not self._cron:
            from ...exception import RuntimeConfigError
            raise RuntimeConfigError(
                f"Missing required configuration 'cron' for scheduler node {self.node.node_id}"
            )

        logger.info(
            f"Scheduler configuration validated: node_id={self.node.node_id}, "
            f"cron='{self._cron}', message='{self._message}'"
        )

        # 2. Create and start APScheduler
        self._scheduler = AsyncIOScheduler()
        self._scheduler.start()
        logger.info(f"APScheduler started for node {self.node.node_id}")

        # 3. Register scheduled task
        try:
            trigger = CronTrigger.from_crontab(self._cron)
            self._scheduler.add_job(
                self._send_scheduled_message,
                trigger=trigger,
                id=f"scheduler_{self.node.node_id}",
                name=f"Scheduler task for {self.node.node_id}"
            )
            logger.info(
                f"Scheduled task registered: node_id={self.node.node_id}, "
                f"cron='{self._cron}', next_run={self._scheduler.get_job(f'scheduler_{self.node.node_id}').next_run_time}"
            )
        except Exception as e:
            logger.error(
                f"Failed to register scheduled task: node_id={self.node.node_id}, "
                f"cron='{self._cron}', error={e}",
                exc_info=True
            )
            raise

        # 4. Create singleton scheduler session (directly, not via command queue)
        # Note: Cannot use CreateSessionCommand here as it would cause deadlock
        # (_on_start is called from command loop, cannot wait for another command)
        logger.info(
            f"Creating singleton scheduler session: node_id={self.node.node_id}, "
            f"session_id={self.SCHEDULER_SESSION_ID}"
        )

        # Create session instance directly
        session = SchedulerSession(
            session_id=self.SCHEDULER_SESSION_ID,
            node=self,
            async_session_factory=self.async_session_factory,
            config={"mode": SessionMode.BACKGROUND}
        )

        # Register in session map
        self._sessions[self.SCHEDULER_SESSION_ID] = session
        logger.debug(
            f"Scheduler session registered: session_id={self.SCHEDULER_SESSION_ID}, "
            f"node_id={self.node.node_id}"
        )

        # Initialize session (starts worker task)
        await session.initialize()
        logger.info(
            f"Singleton scheduler session created successfully: "
            f"node_id={self.node.node_id}, session_id={self.SCHEDULER_SESSION_ID}"
        )

        logger.info(
            f"SchedulerNode {self.node.node_id} started successfully, "
            f"scheduler running with cron '{self._cron}'"
        )

    async def _on_stop(self) -> None:
        """
        Node cleanup hook.

        Steps:
        1. Shutdown APScheduler (wait for running jobs to complete)
        2. Singleton session will be cleaned up by base class _cleanup_all_sessions

        Note:
            APScheduler shutdown waits for all running jobs to complete gracefully.
        """
        logger.info(f"SchedulerNode {self.node.node_id} stopping...")

        # Shutdown APScheduler
        if self._scheduler:
            try:
                logger.info(
                    f"Shutting down APScheduler for node {self.node.node_id}, "
                    f"waiting for running jobs to complete..."
                )
                self._scheduler.shutdown(wait=True)
                logger.info(f"APScheduler shut down successfully for node {self.node.node_id}")
            except Exception as e:
                logger.error(
                    f"Error shutting down APScheduler: node_id={self.node.node_id}, error={e}",
                    exc_info=True
                )
            self._scheduler = None

        logger.info(f"SchedulerNode {self.node.node_id} stopped")

    # ========== Scheduled Task Handler ==========

    async def _send_scheduled_message(self):
        """
        Scheduled task trigger handler.

        Called by APScheduler when cron trigger fires.
        Broadcasts SCHEDULER_MESSAGE event to all subscribers via the singleton session.

        Note:
            Uses send_event with target_node_id=None for broadcast mode.
            Subscription table is automatically queried for subscriber list.
        """
        logger.info(
            f"Scheduled task triggered: node_id={self.node.node_id}, "
            f"cron='{self._cron}', message='{self._message}'"
        )

        # Check if singleton session exists
        if self.SCHEDULER_SESSION_ID not in self._sessions:
            logger.error(
                f"Singleton scheduler session not found during task trigger: "
                f"node_id={self.node.node_id}, session_id={self.SCHEDULER_SESSION_ID}"
            )
            return

        try:
            # Broadcast event via singleton session (target_node_id=None)
            await self.send_event(
                source_session_id=self.SCHEDULER_SESSION_ID,
                event_type=EventType.SCHEDULER_MESSAGE,
                payload={"message": self._message}
                # target_node_id=None for broadcast (default)
            )

            logger.info(
                f"Scheduled message broadcasted successfully: "
                f"node_id={self.node.node_id}, event_type={EventType.SCHEDULER_MESSAGE}, "
                f"message='{self._message}'"
            )

        except Exception as e:
            logger.error(
                f"Failed to broadcast scheduled message: "
                f"node_id={self.node.node_id}, error={e}",
                exc_info=True
            )

    # ========== Session Management ==========

    async def create_session(
        self,
        session_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> 'MosaicSession':
        """
        Create a scheduler session (pure runtime, no database).

        This is a runtime-only node, so sessions are NOT persisted to database.

        Strategy:
        1. Check runtime conflict (self._sessions)
        2. Create runtime session instance
        3. Register in self._sessions
        4. Initialize session (starts worker task)

        Args:
            session_id: Session identifier (required)
            config: Session configuration (optional)

        Returns:
            SchedulerSession instance

        Raises:
            SessionConflictError: If session already exists in runtime

        Note:
            Does NOT create database Session record (scheduler is runtime-only).
        """
        logger.info(
            f"Creating Scheduler session: session_id={session_id}, "
            f"node_id={self.node.node_id}"
        )

        # 1. Check if session already exists in runtime
        if session_id in self._sessions:
            raise SessionConflictError(
                f"Session {session_id} already exists in runtime for node {self.node.node_id}"
            )

        # 2. Create runtime session instance
        session = SchedulerSession(
            session_id=session_id,
            node=self,
            async_session_factory=self.async_session_factory,
            config=config or {}
        )

        # 3. Register in session map
        self._sessions[session_id] = session
        logger.debug(
            f"Scheduler session registered in session map: session_id={session_id}, "
            f"node_id={self.node.node_id}"
        )

        # 4. Initialize session (starts worker task)
        await session.initialize()
        logger.info(
            f"Scheduler session created and initialized: session_id={session_id}, "
            f"node_id={self.node.node_id}"
        )

        return session

    async def close_session(self, session_id: str) -> None:
        """
        Close a scheduler session.

        Runtime cleanup only (no database updates).

        Args:
            session_id: Session identifier

        Raises:
            SessionNotFoundError: If session not found

        Note:
            Does NOT update database Session record (scheduler is runtime-only).
        """
        logger.info(
            f"Closing Scheduler session: session_id={session_id}, "
            f"node_id={self.node.node_id}"
        )

        # Get session from map
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(
                f"Session {session_id} not found in node {self.node.node_id}"
            )

        # Call session cleanup (stops worker, calls _on_close hook)
        await session.close()
        logger.debug(f"Scheduler session closed: session_id={session_id}")

        # Unregister from session map
        self._sessions.pop(session_id, None)
        logger.info(
            f"Scheduler session unregistered from session map: session_id={session_id}, "
            f"node_id={self.node.node_id}"
        )


class SchedulerSession(MosaicSession):
    """
    Scheduler session - minimal runtime session for event broadcasting.

    Key features:
    - Pure runtime (no database persistence)
    - Does not process incoming events (only sends events)
    - Never auto-closes (long-lived, tied to node lifecycle)
    - Minimal lifecycle hooks (no special initialization/cleanup)

    Session lifecycle:
    1. Creation: __init__ (runtime flags initialized)
    2. Initialization: _on_initialize (no-op for scheduler)
    3. Event loop: _handle_event (warns and ignores unexpected events)
    4. Auto-close: _should_close_after_event (always returns False)
    5. Cleanup: _on_close (no-op for scheduler)
    """

    def __init__(
        self,
        session_id: str,
        node: SchedulerNode,
        async_session_factory,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Scheduler session.

        Args:
            session_id: Session identifier (typically SCHEDULER_SESSION_ID)
            node: Parent SchedulerNode reference
            async_session_factory: AsyncSession factory for database access
            config: Session configuration (optional)
        """
        super().__init__(session_id, node, async_session_factory, config)

        logger.debug(
            f"Initialized SchedulerSession: session_id={session_id}, "
            f"node_id={node.node.node_id}"
        )

    # ========== Lifecycle Hooks ==========

    async def _on_initialize(self):
        """
        Session initialization hook (no-op for scheduler).

        Scheduler sessions have no special resources to initialize.
        Worker task is started by base class.
        """
        logger.debug(
            f"SchedulerSession initialization (no-op): session_id={self.session_id}, "
            f"node_id={self.node.node.node_id}"
        )

    async def _on_close(self):
        """
        Session cleanup hook (no-op for scheduler).

        Scheduler sessions have no special resources to cleanup.
        Worker task is stopped by base class.
        """
        logger.debug(
            f"SchedulerSession cleanup (no-op): session_id={self.session_id}, "
            f"node_id={self.node.node.node_id}"
        )

    async def _on_event_loop_started(self):
        """
        Event loop started hook.

        Called when the session worker task starts processing events.
        """
        logger.info(
            f"SchedulerSession event loop started: session_id={self.session_id}, "
            f"node_id={self.node.node.node_id}"
        )

    async def _on_event_loop_exited(self):
        """
        Event loop exited hook.

        Called when the session worker task exits (on session close or cancellation).
        """
        logger.info(
            f"SchedulerSession event loop exited: session_id={self.session_id}, "
            f"node_id={self.node.node.node_id}"
        )

    # ========== Event Processing ==========

    async def _handle_event(self, event: dict) -> None:
        """
        Handle an incoming event.

        Scheduler sessions do not process incoming events (they only send events).
        Any received event is logged as a warning and ignored.

        Args:
            event: Event data dict

        Note:
            This is not an error condition - it's just unexpected.
            Events may arrive due to misconfiguration or testing.
        """
        event_type = event.get('event_type', 'UNKNOWN')
        event_id = event.get('event_id', 'UNKNOWN')

        logger.warning(
            f"SchedulerSession received unexpected event (ignoring): "
            f"session_id={self.session_id}, node_id={self.node.node.node_id}, "
            f"event_type={event_type}, event_id={event_id}"
        )

        # Ignore the event (no processing logic)

    async def _should_close_after_event(self, event: dict) -> bool:
        """
        Determine if session should close after processing an event.

        Scheduler sessions are long-lived and never auto-close.
        They remain active until the node is stopped.

        Args:
            event: The event that was just processed

        Returns:
            Always False (never auto-close)
        """
        logger.debug(
            f"SchedulerSession auto-close check (always False): "
            f"session_id={self.session_id}, node_id={self.node.node.node_id}"
        )
        return False
