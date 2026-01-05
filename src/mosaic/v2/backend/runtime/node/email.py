"""Email node and session implementation"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING

from email_threads import EmailAccount, EmailSender

from ..mosaic_node import MosaicNode
from ..mosaic_session import MosaicSession
from ...enum import EventType, SessionMode, SessionAlignment
from ...exception import (
    SessionNotFoundError,
    SessionConflictError,
    RuntimeConfigError
)

if TYPE_CHECKING:
    from ...model.node import Node

logger = logging.getLogger(__name__)


class EmailNode(MosaicNode):
    """
    Email node - manages email sending sessions.

    This node type provides:
    - Email sending capability via EmailSender (email_threads library)
    - Event-driven email sending (EMAIL_MESSAGE events)
    - Multiple concurrent sessions (runtime-only, no database)
    - Session alignment support (TASKING/MIRRORING)

    Architecture:
    - Node initializes a single EmailSender shared by all sessions
    - Each EMAIL_MESSAGE event triggers session creation (auto-create)
    - Sessions send email and close based on session_alignment strategy
    - No database persistence (pure runtime)
    """

    def __init__(
        self,
        node: 'Node',
        node_path: Path,
        mosaic_instance,
        async_session_factory,
        config: dict
    ):
        """
        Initialize Email node.

        Args:
            node: Node model object from database
            node_path: Node working directory path
            mosaic_instance: Parent MosaicInstance reference
            async_session_factory: AsyncSession factory for database access
            config: System configuration dict (must contain 'zmq')

        Note:
            Email-specific configuration (email, password, smtp_server, smtp_port)
            is read from node.config
        """
        super().__init__(node, node_path, mosaic_instance, async_session_factory, config)

        # Email sender instance (initialized in _on_start)
        self._email_sender: Optional[EmailSender] = None

        # Extract email configuration from node.config (will be validated in _on_start)
        self._email_config = self.node.config or {}

        logger.info(
            f"Initialized EmailNode: node_id={node.node_id}, "
            f"email={self._email_config.get('email', 'NOT_SET')}"
        )

    # ========== Lifecycle Hooks ==========

    async def _on_start(self) -> None:
        """
        Node startup hook.

        Steps:
        1. Validate email configuration (email, password, smtp_server required)
        2. Create EmailAccount from configuration
        3. Initialize EmailSender instance

        Raises:
            RuntimeConfigError: If required email configuration is missing
        """
        logger.info(f"EmailNode {self.node.node_id} starting...")

        # 1. Validate email configuration
        required_fields = ['email', 'password', 'smtp_server']
        missing_fields = [f for f in required_fields if not self._email_config.get(f)]

        if missing_fields:
            raise RuntimeConfigError(
                f"Missing required email configuration fields for node {self.node.node_id}: "
                f"{', '.join(missing_fields)}"
            )

        email = self._email_config['email']
        password = self._email_config['password']
        smtp_server = self._email_config['smtp_server']
        smtp_port = self._email_config['smtp_port']
        imap_server = self._email_config['imap_server']

        logger.info(
            f"Email configuration validated: node_id={self.node.node_id}, "
            f"email={email}, smtp_server={smtp_server}, smtp_port={smtp_port}"
        )

        # 2. Create EmailAccount
        try:
            email_account = EmailAccount(
                email=email,
                password=password,
                imap_server=imap_server,
                smtp_server=smtp_server,
                smtp_port=smtp_port
            )
            logger.debug(f"EmailAccount created: email={email}")

        except Exception as e:
            logger.error(
                f"Failed to create EmailAccount: node_id={self.node.node_id}, error={e}",
                exc_info=True
            )
            raise RuntimeConfigError(f"Failed to create EmailAccount: {e}") from e

        # 3. Initialize EmailSender
        try:
            self._email_sender = EmailSender(email_account)
            logger.info(f"EmailSender initialized for node {self.node.node_id}")

        except Exception as e:
            logger.error(
                f"Failed to initialize EmailSender: node_id={self.node.node_id}, error={e}",
                exc_info=True
            )
            raise RuntimeConfigError(f"Failed to initialize EmailSender: {e}") from e

        logger.info(
            f"EmailNode {self.node.node_id} started successfully, "
            f"ready to send emails from {email}"
        )

    async def _on_stop(self) -> None:
        """
        Node cleanup hook.

        Steps:
        1. Cleanup EmailSender resources (if any)

        Note:
            EmailSender cleanup is minimal - just reset the reference.
            All sessions are already cleaned up by base class.
        """
        logger.info(f"EmailNode {self.node.node_id} stopping...")

        # Cleanup EmailSender
        if self._email_sender:
            logger.debug(f"Cleaning up EmailSender for node {self.node.node_id}")
            self._email_sender = None

        logger.info(f"EmailNode {self.node.node_id} stopped")

    # ========== Email Sending Helper ==========

    def send_email(
        self,
        to: str,
        subject: str,
        text: str
    ) -> None:
        """
        Send an email using the configured EmailSender.

        Called by EmailSession to actually send the email.

        Args:
            to: Recipient email address
            subject: Email subject line
            text: Email body text

        Raises:
            RuntimeError: If EmailSender is not initialized
            Exception: Any email sending errors from EmailSender

        Note:
            This is a synchronous method that uses EmailSender.send().
            EmailSender handles SMTP connection internally.
        """
        if not self._email_sender:
            raise RuntimeError(
                f"EmailSender not initialized for node {self.node.node_id}"
            )

        logger.info(
            f"Sending email: node_id={self.node.node_id}, to={to}, subject='{subject}'"
        )

        try:
            self._email_sender.send(
                to=to,
                subject=subject,
                text=text
            )
            logger.info(
                f"Email sent successfully: node_id={self.node.node_id}, to={to}"
            )

        except Exception as e:
            logger.error(
                f"Failed to send email: node_id={self.node.node_id}, "
                f"to={to}, subject='{subject}', error={e}",
                exc_info=True
            )
            raise

    # ========== Session Management ==========

    async def create_session(
        self,
        session_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> 'MosaicSession':
        """
        Create an email session (pure runtime, no database).

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
            EmailSession instance

        Raises:
            SessionConflictError: If session already exists in runtime

        Note:
            Does NOT create database Session record (email is runtime-only).
        """
        logger.info(
            f"Creating Email session: session_id={session_id}, "
            f"node_id={self.node.node_id}"
        )

        # 1. Check if session already exists in runtime
        if session_id in self._sessions:
            raise SessionConflictError(
                f"Session {session_id} already exists in runtime for node {self.node.node_id}"
            )

        # 2. Create runtime session instance
        session = EmailSession(
            session_id=session_id,
            node=self,
            async_session_factory=self.async_session_factory,
            config=config or {}
        )

        # 3. Register in session map
        self._sessions[session_id] = session
        logger.debug(
            f"Email session registered in session map: session_id={session_id}, "
            f"node_id={self.node.node_id}"
        )

        # 4. Initialize session (starts worker task)
        await session.initialize()
        logger.info(
            f"Email session created and initialized: session_id={session_id}, "
            f"node_id={self.node.node_id}"
        )

        return session

    async def close_session(self, session_id: str) -> None:
        """
        Close an email session.

        Runtime cleanup only (no database updates).

        Args:
            session_id: Session identifier

        Raises:
            SessionNotFoundError: If session not found

        Note:
            Does NOT update database Session record (email is runtime-only).
        """
        logger.info(
            f"Closing Email session: session_id={session_id}, "
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
        logger.debug(f"Email session closed: session_id={session_id}")

        # Unregister from session map
        self._sessions.pop(session_id, None)
        logger.info(
            f"Email session unregistered from session map: session_id={session_id}, "
            f"node_id={self.node.node_id}"
        )


class EmailSession(MosaicSession):
    """
    Email session - event-driven email sending with session alignment support.

    Key features:
    - Pure runtime (no database persistence)
    - Processes EMAIL_MESSAGE events to send emails
    - Auto-closes based on session_alignment strategy (TASKING/MIRRORING)
    - Minimal lifecycle hooks (no special initialization/cleanup)

    Session lifecycle:
    1. Creation: __init__ (runtime flags initialized)
    2. Initialization: _on_initialize (no-op for email)
    3. Event processing: _handle_event (sends email via node.send_email)
    4. Auto-close decision: _should_close_after_event (based on session_alignment)
    5. Cleanup: _on_close (no-op for email)

    Session alignment behavior:
    - TASKING: Close immediately after sending email (one session per email)
    - MIRRORING: Keep session alive until upstream session ends (SESSION_END event)
    """

    def __init__(
        self,
        session_id: str,
        node: EmailNode,
        async_session_factory,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Email session.

        Args:
            session_id: Session identifier
            node: Parent EmailNode reference
            async_session_factory: AsyncSession factory for database access
            config: Session configuration (optional)
        """
        super().__init__(session_id, node, async_session_factory, config)

        logger.debug(
            f"Initialized EmailSession: session_id={session_id}, "
            f"node_id={node.node.node_id}"
        )

    # ========== Lifecycle Hooks ==========

    async def _on_initialize(self):
        """
        Session initialization hook (no-op for email).

        Email sessions have no special resources to initialize.
        Worker task is started by base class.
        """
        logger.debug(
            f"EmailSession initialization (no-op): session_id={self.session_id}, "
            f"node_id={self.node.node.node_id}"
        )

    async def _on_close(self):
        """
        Session cleanup hook (no-op for email).

        Email sessions have no special resources to cleanup.
        Worker task is stopped by base class.
        """
        logger.debug(
            f"EmailSession cleanup (no-op): session_id={self.session_id}, "
            f"node_id={self.node.node.node_id}"
        )

    async def _on_event_loop_started(self):
        """
        Event loop started hook.

        Called when the session worker task starts processing events.
        """
        logger.info(
            f"EmailSession event loop started: session_id={self.session_id}, "
            f"node_id={self.node.node.node_id}"
        )

    async def _on_event_loop_exited(self):
        """
        Event loop exited hook.

        Called when the session worker task exits (on session close or cancellation).
        """
        logger.info(
            f"EmailSession event loop exited: session_id={self.session_id}, "
            f"node_id={self.node.node.node_id}"
        )

    # ========== Event Processing ==========

    async def _handle_event(self, event: dict) -> None:
        """
        Handle an incoming event.

        Event processing:
        1. Extract event_type and payload
        2. If EMAIL_MESSAGE: extract to, subject, text and send email
        3. Log success or warning for unexpected event types

        Args:
            event: Event data dict containing:
                - event_type (str): Event type (required)
                - event_id (str): Unique event identifier
                - source_node_id (str): Source node
                - source_session_id (str): Source session
                - payload (dict): Event-specific data
                    - to (str): Recipient email address
                    - subject (str): Email subject line
                    - text (str): Email body text

        Note:
            Exceptions from email sending are logged but not caught here.
            They will be caught by the base class event loop.
        """
        event_type = event.get('event_type', 'UNKNOWN')
        event_id = event.get('event_id', 'UNKNOWN')
        source_node_id = event.get('source_node_id', 'UNKNOWN')
        source_session_id = event.get('source_session_id', 'UNKNOWN')

        logger.debug(
            f"Handling event: session_id={self.session_id}, event_type={event_type}, "
            f"event_id={event_id}, source={source_node_id}/{source_session_id}"
        )

        if event_type == EventType.EMAIL_MESSAGE:
            # Extract email parameters from payload
            payload = event.get('payload', {})
            to = payload.get('to')
            subject = payload.get('subject')
            text = payload.get('text')

            # Validate required fields
            if not to or not subject or not text:
                logger.error(
                    f"Invalid EMAIL_MESSAGE event: missing required fields "
                    f"(to={to}, subject={subject is not None}, text={text is not None}), "
                    f"session_id={self.session_id}, event_id={event_id}"
                )
                return

            # Send email via node
            logger.info(
                f"Processing EMAIL_MESSAGE event: session_id={self.session_id}, "
                f"to={to}, subject='{subject}'"
            )

            self.node.send_email(to=to, subject=subject, text=text)

            logger.info(
                f"Email sent successfully for event: session_id={self.session_id}, "
                f"event_id={event_id}, to={to}"
            )

        else:
            # Unexpected event type (not an error, just log warning)
            logger.warning(
                f"EmailSession received unexpected event type (ignoring): "
                f"session_id={self.session_id}, node_id={self.node.node.node_id}, "
                f"event_type={event_type}, event_id={event_id}"
            )

    async def _should_close_after_event(self, event: dict) -> bool:
        """
        Determine if session should close after processing an event.

        Auto-close logic (mirrors ClaudeCodeSession behavior):
        - Always check session_alignment strategy from Connection table
        - If TASKING: Close after each event (one session per email)
        - If MIRRORING: Close only when upstream session ends (SESSION_END event)
        - If no connection or unknown strategy: Don't close (keep session alive)

        Args:
            event: The event that was just processed

        Returns:
            True if session should close, False to continue

        Note:
            This logic is copied from ClaudeCodeSession._should_close_after_event
            to ensure consistent session alignment behavior across node types.
        """
        event_type = event.get('event_type')

        # Get source_node_id from event
        source_node_id = event.get('source_node_id')
        if not source_node_id:
            logger.warning(
                f"Network event missing source_node_id: event_type={event_type}, "
                f"session {self.session_id} will not auto-close"
            )
            return False

        # Query connection from source_node to current node
        from ...model.connection import Connection
        from sqlmodel import select

        async with self.async_session_factory() as db_session:
            stmt = select(Connection).where(
                Connection.mosaic_id == self.node.mosaic_instance.mosaic.id,
                Connection.source_node_id == source_node_id,
                Connection.target_node_id == self.node.node.node_id,
                Connection.deleted_at.is_(None)
            )
            result = await db_session.execute(stmt)
            connection = result.scalar_one_or_none()

        # If no connection exists, don't auto-close
        if not connection:
            logger.debug(
                f"No connection found from {source_node_id} to {self.node.node.node_id}, "
                f"session {self.session_id} will not auto-close"
            )
            return False

        # Check session alignment strategy
        if connection.session_alignment == SessionAlignment.TASKING:
            # TASKING: Close after each event (one session per email)
            logger.info(
                f"TASKING session {self.session_id} completed event, will auto-close"
            )
            return True

        elif connection.session_alignment == SessionAlignment.MIRRORING:
            # MIRRORING: Close only when upstream session ends
            should_close = (event_type == EventType.SESSION_END)

            if should_close:
                logger.info(
                    f"MIRRORING session {self.session_id} received SESSION_END, will auto-close"
                )

            return should_close

        # Unknown alignment strategy, don't auto-close
        logger.warning(
            f"Unknown session_alignment {connection.session_alignment} for connection "
            f"{source_node_id} -> {self.node.node.node_id}, session {self.session_id} will not auto-close"
        )
        return False
