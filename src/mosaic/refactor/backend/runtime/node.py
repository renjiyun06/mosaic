"""Mosaic node base class"""
import uuid
import json
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, TYPE_CHECKING

from .zmq_layer import ZmqClient
from .session import MosaicSession
from .event import MosaicEvent, EVENTS
from jsonschema import validate
from ..logger import get_logger

if TYPE_CHECKING:
    from ..models.node import Node

logger = get_logger(__name__)


class MosaicNode(ABC):
    """
    Base class for all mosaic nodes.

    Each node runs in its parent mosaic's event loop and communicates
    via the global ZMQ message broker.
    """

    def __init__(
        self,
        node: 'Node',
        workspace: Path
    ):
        """
        Initialize a node.

        Args:
            node: Database Node instance (contains all metadata)
            workspace: Node working directory
        """
        # Store full node model (single source of truth)
        self.node = node
        self.workspace = workspace

        # ZMQ client (will be created on start)
        self._zmq_client: Optional[ZmqClient] = None

        # Node status
        self._status = "stopped"

        # Sessions managed by this node: {session_id: MosaicSession}
        self._sessions: Dict[str, MosaicSession] = {}

    async def start(self):
        """Start the node"""
        if self._status == "running":
            logger.warning(f"Node {self.node.node_id} already running")
            return

        logger.info(f"Starting node {self.node.mosaic_id}#{self.node.node_id}")

        # Create and connect ZMQ client (convert IDs to strings for ZMQ topics)
        self._zmq_client = ZmqClient(
            mosaic_id=str(self.node.mosaic_id),
            node_id=str(self.node.id),  # Use database ID for routing
            on_event=self.process_event
        )
        self._zmq_client.connect()

        # Call subclass-specific startup logic
        await self.on_start()

        self._status = "running"
        logger.info(f"Node {self.node.mosaic_id}#{self.node.node_id} started")

    async def stop(self):
        """Stop the node"""
        if self._status == "stopped":
            logger.warning(f"Node {self.node.node_id} already stopped")
            return

        logger.info(f"Stopping node {self.node.mosaic_id}#{self.node.node_id}")

        # Close all sessions
        for session_id in list(self._sessions.keys()):
            await self.close_session(session_id, force=True)

        # Disconnect ZMQ client
        if self._zmq_client:
            self._zmq_client.disconnect()
            self._zmq_client = None

        # Call subclass-specific cleanup logic
        await self.on_stop()

        self._status = "stopped"
        logger.info(f"Node {self.node.mosaic_id}#{self.node.node_id} stopped")

    # ========== Subclass Hooks ==========

    @abstractmethod
    async def on_start(self):
        """
        Subclass-specific startup logic.

        Override this to initialize resources (e.g., start schedulers,
        connect to external services).
        """
        ...

    @abstractmethod
    async def on_stop(self):
        """
        Subclass-specific cleanup logic.

        Override this to clean up resources.
        """
        ...

    @abstractmethod
    async def start_mosaic_session(
        self,
        session_id: str,
        config: Dict[str, Any] | None = None
    ) -> MosaicSession:
        """
        Create and start a session instance.

        Args:
            session_id: Session identifier
            config: Session-specific configuration

        Returns:
            Started session instance
        """
        ...

    # ========== Event Processing ==========

    async def process_event(self, event: Dict[str, Any]):
        """
        Process an incoming event.

        This is called by ZmqClient when a message is received.

        Args:
            event: Event data (JSON dict)
        """
        logger.info(
            f"[NODE_PROCESS] Received event in node {self.node.id} ({self.node.node_id}): "
            f"event_id={event.get('event_id')}, event_type={event.get('event_type')}, "
            f"source_id={event.get('source_id')}, target_id={event.get('target_id')}"
        )

        event_type = event.get("event_type")
        event_cls = EVENTS.get(event_type)

        if not event_cls:
            logger.warning(f"[NODE_PROCESS] Unknown event type: {event_type}")
            return

        # Validate payload schema
        payload = event.get("payload")
        payload_schema = event_cls.payload_schema()
        if payload_schema:
            try:
                validate(payload, payload_schema)
                logger.debug(f"[NODE_PROCESS] Payload validation passed for {event_type}")
            except Exception as e:
                logger.error(f"[NODE_PROCESS] Payload validation failed: {e}")
                return

        # Parse event
        mosaic_event: MosaicEvent = event_cls.model_validate(event)

        logger.info(
            f"[NODE_PROCESS] Processing event {event_type} from "
            f"source={mosaic_event.source_id}, upstream_session={mosaic_event.upstream_session_id}, "
            f"downstream_session={mosaic_event.downstream_session_id}"
        )

        # Verify target (event target_id is string, node.id is int)
        if str(self.node.id) != mosaic_event.target_id:
            logger.error(
                f"[NODE_PROCESS] Event target mismatch: expected {self.node.id} (str: {str(self.node.id)}), "
                f"got {mosaic_event.target_id} (type: {type(mosaic_event.target_id)})"
            )
            return

        logger.debug(f"[NODE_PROCESS] Target verification passed: {mosaic_event.target_id} == {str(self.node.id)}")

        # Get or create session
        downstream_session_id = mosaic_event.downstream_session_id
        downstream_session = self._sessions.get(downstream_session_id)

        if not downstream_session:
            # TODO: Check connection config to decide whether to auto-create session
            # For now, always create a new session
            logger.info(
                f"[NODE_PROCESS] Session {downstream_session_id} not found, creating new session"
            )
            try:
                downstream_session = await self.create_session(
                    session_id=downstream_session_id
                )
                logger.info(
                    f"[NODE_PROCESS] Successfully created session {downstream_session_id}"
                )
            except Exception as e:
                logger.error(
                    f"[NODE_PROCESS] Failed to create session {downstream_session_id}: {e}",
                    exc_info=True
                )
                return
        else:
            logger.info(
                f"[NODE_PROCESS] Using existing session {downstream_session_id}"
            )

        # Dispatch to session
        try:
            logger.info(
                f"[NODE_PROCESS] Dispatching event {event.get('event_id')} "
                f"to session {downstream_session_id}"
            )
            future = await downstream_session.process_event(mosaic_event)
            if future:
                await future
            logger.info(
                f"[NODE_PROCESS] Successfully processed event {event.get('event_id')} "
                f"in session {downstream_session_id}"
            )
        except Exception as e:
            logger.error(
                f"[NODE_PROCESS] Error processing event in session {downstream_session_id}: {e}",
                exc_info=True
            )

        # Handle session alignment (tasking vs mirroring)
        # Import here to avoid circular dependency
        from sqlmodel.ext.asyncio.session import AsyncSession as AsyncSessionType
        from sqlmodel import select
        from ..models.connection import Connection
        from ..database import engine

        async with AsyncSessionType(engine) as db:
            # Query connection to get session_alignment
            result = await db.execute(
                select(Connection).where(
                    Connection.mosaic_id == self.node.mosaic_id,
                    Connection.source_node_id == int(mosaic_event.source_id),
                    Connection.target_node_id == self.node.id,
                    Connection.deleted_at.is_(None)
                )
            )
            connection = result.scalar_one_or_none()

            if connection:
                session_alignment = connection.session_alignment
                logger.debug(
                    f"[NODE_PROCESS] Session alignment: {session_alignment}"
                )

                if session_alignment == "tasking":
                    # Tasking mode: Close session after processing
                    logger.info(
                        f"[NODE_PROCESS] Tasking mode: Closing session {downstream_session_id}"
                    )
                    await self.close_session(downstream_session_id)
                elif mosaic_event.event_type == "session_end":
                    # Always close on session_end event
                    logger.info(
                        f"[NODE_PROCESS] Received session_end: Closing session {downstream_session_id}"
                    )
                    await self.close_session(downstream_session_id)
            else:
                logger.warning(
                    f"[NODE_PROCESS] No connection found from {mosaic_event.source_id} to {self.node.id}"
                )

    # ========== Event Publishing ==========

    async def publish_event(
        self,
        session_id: str,
        event_type: str,
        payload: Dict[str, Any],
        target_mosaic_id: str,
        target_node_id: str,
        downstream_session_id: Optional[str] = None
    ):
        """
        Publish an event to a target node.

        Args:
            session_id: Source session ID
            event_type: Event type
            payload: Event payload
            target_mosaic_id: Target mosaic ID
            target_node_id: Target node ID
            downstream_session_id: Target session ID (auto-generated if None)
        """
        if not self._zmq_client:
            raise RuntimeError("Node not started")

        # Generate downstream session ID if not provided
        if downstream_session_id is None:
            downstream_session_id = str(uuid.uuid4())

        # Construct event (use database IDs for routing)
        event = {
            "event_id": str(uuid.uuid4()),
            "source_id": str(self.node.id),
            "target_id": target_node_id,
            "event_type": event_type,
            "upstream_session_id": session_id,
            "downstream_session_id": downstream_session_id,
            "payload": payload,
            "created_at": datetime.now().isoformat()
        }

        # Send via ZMQ
        await self._zmq_client.send(target_mosaic_id, target_node_id, event)

        logger.debug(
            f"Published event {event_type} to "
            f"{target_mosaic_id}#{target_node_id}"
        )

    # ========== Session Management ==========

    async def create_session(
        self,
        session_id: str,
        config: Dict[str, Any] | None = None
    ) -> MosaicSession:
        """
        Create and start a session.

        Args:
            session_id: Session identifier
            config: Session-specific configuration

        Returns:
            Started session instance
        """
        if session_id in self._sessions:
            raise ValueError(f"Session {session_id} already exists")

        logger.info(f"Creating session {session_id} for node {self.node.node_id}")

        # Call subclass to create session
        session = await self.start_mosaic_session(session_id, config)

        # Start session
        await session.start()

        # Cache session
        self._sessions[session_id] = session

        return session

    async def close_session(self, session_id: str, force: bool = False):
        """
        Close a session.

        Args:
            session_id: Session identifier
            force: If True, forcefully close without cleanup
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found")
            return

        logger.info(f"Closing session {session_id} for node {self.node.node_id}")

        # Close session
        await session.close(force=force)

        # Remove from cache
        del self._sessions[session_id]

    def get_session(self, session_id: str) -> Optional[MosaicSession]:
        """Get a session by ID"""
        return self._sessions.get(session_id)
