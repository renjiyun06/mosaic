"""Aggregator node implementation

Aggregator node collects events and batches them for downstream processing.
"""
import logging
from typing import Optional, Dict, Any, TYPE_CHECKING
from pathlib import Path

from ..mosaic_node import MosaicNode
from ..mosaic_session import MosaicSession
from ...exception import SessionNotFoundError

if TYPE_CHECKING:
    from ...model.node import Node
    from ..mosaic_instance import MosaicInstance

logger = logging.getLogger(__name__)


class AggregatorNode(MosaicNode):
    """
    Aggregator node for collecting and batching events.

    This node:
    - Receives events from subscribed sources
    - Collects events within sessions
    - Batches events and emits EVENT_BATCH events

    Session characteristics:
    - Runtime-only (no database persistence)
    - Each session collects events independently
    """

    def __init__(
        self,
        node: 'Node',
        node_path: Path,
        mosaic_instance: 'MosaicInstance',
        async_session_factory,
        config: dict
    ):
        """
        Initialize aggregator node.

        Args:
            node: Node model object from database
            node_path: Node working directory path
            mosaic_instance: Parent MosaicInstance reference
            async_session_factory: AsyncSession factory for database access
            config: Configuration dict
        """
        super().__init__(
            node=node,
            node_path=node_path,
            mosaic_instance=mosaic_instance,
            async_session_factory=async_session_factory,
            config=config
        )

        logger.info(f"AggregatorNode initialized: node_id={node.node_id}")

    # ========== Lifecycle Hooks ==========

    async def _on_start(self) -> None:
        """
        Initialize aggregator-specific resources before accepting events.
        """
        logger.info(f"AggregatorNode started: node_id={self.node.node_id}")

    async def _on_stop(self) -> None:
        """
        Cleanup aggregator-specific resources after all sessions stopped.
        """
        logger.info(f"AggregatorNode stopped: node_id={self.node.node_id}")

    # ========== Session Management ==========

    async def create_session(
        self,
        session_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> 'AggregatorSession':
        """
        Create an aggregator session.

        Args:
            session_id: Session identifier
            config: Session configuration (optional)

        Returns:
            AggregatorSession: The created session instance
        """
        # Generate session_id if not provided
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
            logger.debug(f"Generated session_id: {session_id}")

        # Create AggregatorSession instance
        session = AggregatorSession(
            session_id=session_id,
            node=self,
            async_session_factory=self.async_session_factory,
            config=config
        )

        # Register in parent class session map
        self._sessions[session_id] = session

        logger.info(
            f"AggregatorSession created and registered: "
            f"session_id={session_id}, node_id={self.node.node_id}"
        )

        # Initialize session
        await session.initialize()

        return session

    async def close_session(self, session_id: str) -> None:
        """
        Close an aggregator session.

        Args:
            session_id: Session identifier

        Raises:
            SessionNotFoundError: If session not found
        """
        # Get session from map
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(
                f"Session not found: session_id={session_id}, node_id={self.node.node_id}"
            )

        # Close session
        await session.close()

        # Unregister from session map
        del self._sessions[session_id]

        logger.info(
            f"AggregatorSession closed and unregistered: "
            f"session_id={session_id}, node_id={self.node.node_id}"
        )


class AggregatorSession(MosaicSession):
    """
    Aggregator session for collecting and batching events.

    Each session:
    - Collects incoming events
    - Batches them according to configured strategy
    - Emits EVENT_BATCH events

    Runtime-only session (no database persistence).
    """

    def __init__(
        self,
        session_id: str,
        node: AggregatorNode,
        async_session_factory,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize aggregator session.

        Args:
            session_id: Session identifier
            node: Parent AggregatorNode reference
            async_session_factory: AsyncSession factory for database access
            config: Session configuration (optional)
        """
        super().__init__(
            session_id=session_id,
            node=node,
            async_session_factory=async_session_factory,
            config=config
        )

        # Event collector for batching
        self._event_buffer: list = []

        logger.info(
            f"AggregatorSession created: session_id={session_id}, "
            f"node_id={node.node.node_id}"
        )

    # ========== Lifecycle Hooks ==========

    async def _on_initialize(self):
        """
        Initialize session-specific resources.
        """
        logger.info(f"AggregatorSession initialized: session_id={self.session_id}")

    async def _on_close(self):
        """
        Cleanup session-specific resources.

        Sends all collected events as EVENT_BATCH before closing.
        """
        # Send collected events if buffer is not empty
        if self._event_buffer:
            logger.info(
                f"Sending EVENT_BATCH on close: session_id={self.session_id}, "
                f"event_count={len(self._event_buffer)}"
            )

            # Import EventType
            from ...enum import EventType

            # Send EVENT_BATCH event with all collected events
            await self.node.send_event(
                source_session_id=self.session_id,
                event_type=EventType.EVENT_BATCH,
                payload={
                    "events": self._event_buffer
                }
            )

            # Clear the buffer
            self._event_buffer.clear()

        logger.info(f"AggregatorSession closed: session_id={self.session_id}")

    async def _on_event_loop_started(self):
        """
        Called when event processing loop starts.
        """
        logger.info(f"AggregatorSession event loop started: session_id={self.session_id}")

    async def _on_event_loop_exited(self):
        """
        Called when event processing loop exits.
        """
        logger.info(f"AggregatorSession event loop exited: session_id={self.session_id}")

    # ========== Event Processing ==========

    async def _handle_event(self, event: dict) -> None:
        """
        Handle an incoming event.

        Args:
            event: Event data dict containing:
                - event_id (str): Unique event identifier
                - event_type (str): Event type
                - source_node_id (str): Source node
                - source_session_id (str): Source session
                - target_node_id (str): Target node (this node)
                - target_session_id (str): Target session (this session)
                - payload (dict, optional): Event-specific data
        """
        # Add event to buffer
        self._event_buffer.append(event)

        logger.debug(
            f"Event added to buffer: session_id={self.session_id}, "
            f"event_id={event.get('event_id', 'UNKNOWN')}, "
            f"buffer_size={len(self._event_buffer)}"
        )

    async def _should_close_after_event(self, event: dict) -> bool:
        """
        Determine if session should close after processing an event.

        Args:
            event: The event that was just processed

        Returns:
            True if session should close (when SESSION_END received), False otherwise
        """
        from ...enum import EventType

        # Close session if SESSION_END event is received
        event_type = event.get('event_type')
        return event_type == EventType.SESSION_END
