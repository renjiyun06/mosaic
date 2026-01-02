"""Base class for runtime node representations"""
import asyncio
import logging
import json
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Set, TYPE_CHECKING, List
from pathlib import Path
from datetime import datetime, timezone

from sqlmodel import select

from ..enum import NodeStatus, SessionMode, EventType
from ..exception import (
    RuntimeInternalError,
    RuntimeConfigError,
    NodeAlreadyRunningError,
    SessionNotFoundError,
    SessionConflictError,
)

if TYPE_CHECKING:
    from ..model.node import Node
    from ..model.session import Session
    from .mosaic_instance import MosaicInstance
    from .mosaic_session import MosaicSession
    from .zmq import ZmqClient

logger = logging.getLogger(__name__)


class MosaicNode(ABC):
    """
    Base class for all runtime node types.

    This is an abstract base class that provides common functionality for all nodes:
    - ZMQ client lifecycle management
    - Event receiving loop
    - Status tracking
    - Node path resolution

    Subclasses must implement:
    - _on_start(): Custom initialization logic
    - _on_stop(): Custom cleanup logic
    - create_session(): Create a new session (fully implemented by subclass)
    - close_session(): Close a session

    Optional methods for agent nodes:
    - send_message(): Send message to a session
    - interrupt_session(): Interrupt a running session

    Architecture:
    - Each node runs in the same event loop as its parent MosaicInstance
    - ZMQ client connects to global ZmqServer
    - Event receiving happens in a background task (_event_loop)
    - All operations are async and non-blocking
    - Session map (self._sessions) is directly accessible to subclasses
    - create_session() and close_session() are called only from command loop (serialized, no lock needed)
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
        Initialize node instance.

        Args:
            node: Node model object from database
            node_path: Node working directory path
            mosaic_instance: Parent MosaicInstance reference
            async_session_factory: AsyncSession factory for database access
            config: Configuration dict (must contain 'zmq')

        Note:
            Does NOT start the node. Call start() to begin operation.
        """
        self.node = node
        self.node_path = node_path
        self.mosaic_instance = mosaic_instance
        self.async_session_factory = async_session_factory
        self.config = config

        # Initialize state
        self._status = NodeStatus.STOPPED
        self._zmq_client: Optional['ZmqClient'] = None

        # Session management (accessed only from command loop - no lock needed)
        self._sessions: Dict[str, 'MosaicSession'] = {}       # session_id -> MosaicSession

        logger.info(
            f"MosaicNode initialized: node_id={node.node_id}, "
            f"node_type={node.node_type}, path={node_path}"
        )

    # ========== Lifecycle Methods ==========

    async def start(self) -> None:
        """
        Start the node.

        Steps:
        1. Validate current status (must be STOPPED)
        2. Call subclass _on_start() hook (prepare resources BEFORE accepting events)
        3. Create and connect ZMQ client (start accepting events)
        4. Set status to RUNNING

        Raises:
            NodeAlreadyRunningError: If node is already running
            RuntimeConfigError: If required ZMQ configuration is missing
            RuntimeInternalError: If startup fails

        Note:
            This is a template method that calls _on_start() for subclass customization.
            Subclass resources MUST be ready before ZMQ starts receiving events.
        """
        if self._status != NodeStatus.STOPPED:
            raise NodeAlreadyRunningError(
                f"Node {self.node.node_id} is already running"
            )

        logger.info(
            f"Starting node: node_id={self.node.node_id}, node_type={self.node.node_type}"
        )

        try:
            # 1. Call subclass initialization hook FIRST (prepare resources)
            await self._on_start()
            logger.debug(f"Subclass initialization complete for node: {self.node.node_id}")

            # 2. Create and connect ZMQ client (start accepting events)
            from .zmq import ZmqClient

            # Get ZMQ server configuration (no defaults - must be provided)
            zmq_config = self.config.get('zmq')
            if not zmq_config:
                raise RuntimeConfigError("Missing required configuration: [zmq]")

            server_host = zmq_config.get('host')
            server_pull_port = zmq_config.get('pull_port')
            server_pub_port = zmq_config.get('pub_port')

            if not all([server_host, server_pull_port, server_pub_port]):
                raise RuntimeConfigError(
                    "Missing required ZMQ configuration fields: host, pull_port, pub_port"
                )

            self._zmq_client = ZmqClient(
                mosaic_id=self.mosaic_instance.mosaic.id,
                node_id=self.node.node_id,
                server_host=server_host,
                server_pull_port=server_pull_port,
                server_pub_port=server_pub_port,
                on_event=self._on_event_received  # Register event callback
            )
            self._zmq_client.connect()
            logger.debug(f"ZMQ client connected for node: {self.node.node_id}")

            # 3. Set status to RUNNING
            self._status = NodeStatus.RUNNING

            logger.info(
                f"Node started successfully: node_id={self.node.node_id}"
            )

        except Exception as e:
            logger.error(f"Failed to start node {self.node.node_id}: {e}")
            # Cleanup on failure
            await self._cleanup()
            raise RuntimeInternalError(f"Node startup failed: {e}") from e

    async def stop(self) -> None:
        """
        Stop the node.

        Steps:
        1. Check if already stopped (idempotent)
        2. Set status to STOPPED (prevent new operations from API)
        3. Cleanup ZMQ and sessions (via _cleanup)
        4. Call subclass _on_stop() hook (cleanup resources after all sessions stopped)

        Note:
            This is a template method that calls _on_stop() for subclass customization.
            Does not raise exceptions - used during cleanup.
            Sessions are cleaned BEFORE _on_stop() because session workers may still need
            subclass resources (e.g., Claude client) to process queued events.
        """
        if self._status == NodeStatus.STOPPED:
            logger.info(f"Node {self.node.node_id} already stopped")
            return

        logger.info(f"Stopping node: node_id={self.node.node_id}")

        # 1. Set status to STOPPED (prevents new operations from API)
        self._status = NodeStatus.STOPPED

        # 2. Cleanup ZMQ and sessions (via _cleanup)
        await self._cleanup()

        # 3. Call subclass cleanup hook (safe to cleanup resources now)
        try:
            await self._on_stop()
        except Exception as e:
            logger.error(
                f"Error in _on_stop() for node {self.node.node_id}: {e}",
                exc_info=True
            )

        logger.info(f"Node stopped: node_id={self.node.node_id}")

    async def _cleanup(self) -> None:
        """
        Cleanup base class resources (ZMQ client and sessions).

        Called by:
        - stop(): After setting status to STOPPED, before calling _on_stop()
        - start() exception handler: When startup fails

        Steps:
        1. Clean up all sessions (cancel worker tasks)
        2. Disconnect ZMQ client (if connected)

        Note:
            This method does NOT call _on_stop(). Subclass resource cleanup is handled separately:
            - In stop(): _on_stop() is called AFTER _cleanup()
            - In start() failure: Subclasses should use try-finally in _on_start() to cleanup
              their own resources, or ensure partial initialization is safe.

            This method is idempotent and safe to call multiple times.
        """
        # 1. Clean up all sessions (idempotent)
        await self._cleanup_all_sessions()

        # 2. Disconnect ZMQ client (idempotent)
        if self._zmq_client:
            try:
                self._zmq_client.disconnect()
                logger.debug(f"ZMQ client disconnected for node: {self.node.node_id}")
            except Exception as e:
                logger.error(f"Error disconnecting ZMQ client: {e}")
            self._zmq_client = None

        logger.debug(f"Cleanup complete for node: {self.node.node_id}")

    # ========== Event Processing ==========

    async def _on_event_received(self, event_data: Dict[str, Any]) -> None:
        """
        Event callback invoked by ZmqClient when an event is received.

        This is called by the ZmqClient's internal receive loop (sequential).
        Routes event to the target session's queue (non-blocking).

        Responsibilities:
        1. Check node status (drop if not RUNNING)
        2. Parse target_session_id from event
        3. Ensure session exists (create if needed via create_session)
        4. Enqueue event to session's queue (non-blocking)
        5. Return immediately (never blocks ZMQ receive loop)

        Args:
            event_data: Event data dict from ZMQ
        """
        try:
            # 1. Defensive check: drop events if node is not running
            if self._status != NodeStatus.RUNNING:
                logger.warning(
                    f"Received event while node not running (status={self._status}), dropping: "
                    f"node_id={self.node.node_id}, event_id={event_data.get('event_id', 'UNKNOWN')}"
                )
                return

            target_session_id = event_data.get('target_session_id')
            event_type = event_data.get('event_type', 'UNKNOWN')
            event_id = event_data.get('event_id', 'UNKNOWN')

            if not target_session_id:
                logger.warning(
                    f"Event missing target_session_id, dropping: "
                    f"event_id={event_id}, event_type={event_type}"
                )
                return

            logger.debug(
                f"Routing event: node_id={self.node.node_id}, "
                f"session_id={target_session_id}, event_type={event_type}"
            )

            # Ensure session exists (create via command if needed)
            # All management operations must go through command queue for serialization
            if target_session_id not in self._sessions:
                logger.info(
                    f"Auto-creating session for incoming event: "
                    f"session_id={target_session_id}, event_type={event_type}"
                )

                # Import here to avoid circular dependency
                from .command import CreateSessionCommand

                # Get default session config from subclass
                default_config = self.get_default_session_config()

                # Create command with future for synchronization
                command = CreateSessionCommand(
                    node=self.node,
                    session_id=target_session_id,
                    config=default_config,  # Use subclass-provided defaults
                    future=asyncio.Future()
                )

                # Submit to command queue (non-blocking)
                self.mosaic_instance.process_command(command)

                # Wait for command completion (blocks until session created)
                try:
                    await command.future
                    logger.debug(
                        f"Session created via command: session_id={target_session_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to create session via command: "
                        f"session_id={target_session_id}, error={e}"
                    )
                    return

            # Get session (should exist after command completion)
            session = self._sessions.get(target_session_id)
            if not session:
                logger.error(
                    f"Session not found after creation: session_id={target_session_id}"
                )
                return

            # Enqueue event to session (non-blocking, session manages its own queue)
            session.enqueue_event(event_data)
            logger.debug(
                f"Event enqueued to session: session_id={target_session_id}, "
                f"event_id={event_id}, event_type={event_type}"
            )

        except Exception as e:
            logger.error(
                f"Error routing event in node {self.node.node_id}: {e}",
                exc_info=True
            )
            # Don't re-raise - prevent crashing the ZmqClient's receive loop

    async def send_event(
        self,
        source_session_id: str,
        event_type: EventType,
        payload: Optional[Dict[str, Any]] = None,
        target_node_id: Optional[str] = None
    ) -> None:
        """
        Send an event from a session to target node(s).

        This method is used by MosaicSession instances to emit events through the event mesh.
        All events in the system are generated by sessions and consumed by sessions.

        Event Routing:
            1. Unicast mode (target_node_id provided):
               - Validates that a Connection exists from this node to target_node_id
               - If no connection found, the event is dropped (logged as WARNING)
               - Uses SessionRouting table to determine target_session_id
               - If no routing exists, generates new target_session_id and creates bidirectional routing

            2. Broadcast mode (target_node_id is None):
               - Queries Subscription table to find all subscribers for this event_type
               - Sends event to each subscribed node
               - For each target, uses SessionRouting to determine target_session_id

        SessionRouting lookup and creation:
            - Query: (local_node_id=self.node.node_id, local_session_id=source_session_id, remote_node_id=target_node_id)
            - Returns: remote_session_id (target_session_id)
            - If not found:
              * Generates new target_session_id (UUID)
              * Inserts TWO SessionRouting records (bidirectional binding):
                - (local=A, session=S1, remote=B, session=S2)
                - (local=B, session=S2, remote=A, session=S1)
              * This creates a persistent session pair for bidirectional communication

        Target session creation:
            - SessionRouting insertion does NOT create the actual session instance
            - Target session is auto-created when target node receives the event (_on_event_received)
            - This separates routing (logical mapping) from runtime (actual session instance)

        Args:
            source_session_id: Session ID that is emitting this event
            event_type: Event type identifier (from EventType enum)
            payload: Optional event-specific data (JSON-serializable dict)
            target_node_id: Optional target node ID. If None, broadcast to all subscribers.

        Raises:
            RuntimeInternalError: If ZMQ client is not connected
            SessionNotFoundError: If source_session_id is not found in this node

        Business Logic:
            - Only events within the same mosaic_id are allowed (no cross-mosaic events)
            - Unicast mode requires an active Connection (no connection = no send, logged as WARNING)
            - Broadcast mode uses Subscriptions to find targets (no subscribers = no send, logged as DEBUG)
            - Event persistence is handled by ZmqServer (events are logged to database)
            - SessionRouting is created bidirectionally for session pair binding

        Database Models Used:
            - Connection: Validates node-to-node connections (unicast mode)
            - Subscription: Defines which nodes subscribe to which event types (broadcast mode)
            - SessionRouting: Maps session pairs between nodes
        """
        # 1. Validate ZMQ client is connected
        if not self._zmq_client:
            raise RuntimeInternalError(
                f"Cannot send event: ZMQ client not connected for node {self.node.node_id}"
            )

        # 2. Validate source session exists
        if source_session_id not in self._sessions:
            raise SessionNotFoundError(
                f"Source session not found: session_id={source_session_id}, node_id={self.node.node_id}"
            )

        logger.debug(
            f"Sending event: source_node={self.node.node_id}, source_session={source_session_id}, "
            f"event_type={event_type}, target_node={target_node_id or 'BROADCAST'}"
        )

        # 3. Determine target node list
        target_nodes: List[str] = []
        if target_node_id:
            # Unicast mode: Verify connection exists
            from ..model.connection import Connection

            async with self.async_session_factory() as db_session:
                stmt = select(Connection).where(
                    Connection.mosaic_id == self.mosaic_instance.mosaic.id,
                    Connection.source_node_id == self.node.node_id,
                    Connection.target_node_id == target_node_id,
                    Connection.deleted_at.is_(None)
                )
                result = await db_session.execute(stmt)
                connection = result.scalar_one_or_none()

            if not connection:
                logger.warning(
                    f"No connection found from {self.node.node_id} to {target_node_id}, "
                    f"event will not be sent: event_type={event_type}, source_session={source_session_id}"
                )
                return

            target_nodes = [target_node_id]
        else:
            # Broadcast mode: query subscriptions
            from ..model.subscription import Subscription

            async with self.async_session_factory() as db_session:
                stmt = select(Subscription.target_node_id).where(
                    Subscription.mosaic_id == self.mosaic_instance.mosaic.id,
                    Subscription.source_node_id == self.node.node_id,
                    Subscription.event_type == event_type,
                    Subscription.deleted_at.is_(None)
                ).distinct()
                result = await db_session.execute(stmt)
                target_nodes = list(result.scalars().all())

            if not target_nodes:
                logger.debug(
                    f"No subscribers found for broadcast: event_type={event_type}, "
                    f"source_node={self.node.node_id}"
                )
                return

            logger.info(
                f"Broadcasting event to {len(target_nodes)} subscribers: "
                f"event_type={event_type}, targets={target_nodes}"
            )

        # 4. For each target node, resolve target_session_id and send event
        from ..model.session_routing import SessionRouting

        for target_node in target_nodes:
            try:
                # 4.1 Query SessionRouting to find or create target_session_id
                async with self.async_session_factory() as db_session:
                    # Query existing routing
                    stmt = select(SessionRouting).where(
                        SessionRouting.mosaic_id == self.mosaic_instance.mosaic.id,
                        SessionRouting.local_node_id == self.node.node_id,
                        SessionRouting.local_session_id == source_session_id,
                        SessionRouting.remote_node_id == target_node,
                        SessionRouting.deleted_at.is_(None)
                    )
                    result = await db_session.execute(stmt)
                    routing = result.scalar_one_or_none()

                    if routing:
                        # Use existing routing
                        target_session_id = routing.remote_session_id
                        logger.debug(
                            f"Using existing session routing: {self.node.node_id}/{source_session_id} -> "
                            f"{target_node}/{target_session_id}"
                        )
                    else:
                        # Create new routing (bidirectional)
                        target_session_id = str(uuid.uuid4())
                        now = datetime.now(timezone.utc)

                        # Create both directions of the routing
                        routing_forward = SessionRouting(
                            user_id=self.mosaic_instance.mosaic.user_id,
                            mosaic_id=self.mosaic_instance.mosaic.id,
                            local_node_id=self.node.node_id,
                            local_session_id=source_session_id,
                            remote_node_id=target_node,
                            remote_session_id=target_session_id,
                            created_at=now,
                            updated_at=now
                        )
                        routing_backward = SessionRouting(
                            user_id=self.mosaic_instance.mosaic.user_id,
                            mosaic_id=self.mosaic_instance.mosaic.id,
                            local_node_id=target_node,
                            local_session_id=target_session_id,
                            remote_node_id=self.node.node_id,
                            remote_session_id=source_session_id,
                            created_at=now,
                            updated_at=now
                        )

                        db_session.add(routing_forward)
                        db_session.add(routing_backward)
                        await db_session.commit()

                        logger.info(
                            f"Created bidirectional session routing: {self.node.node_id}/{source_session_id} <-> "
                            f"{target_node}/{target_session_id}"
                        )

                # 4.2 Construct event dict
                event_id = str(uuid.uuid4())
                event_data = {
                    "event_id": event_id,
                    "event_type": event_type,
                    "source_node_id": self.node.node_id,
                    "source_session_id": source_session_id,
                    "target_node_id": target_node,
                    "target_session_id": target_session_id,
                    "payload": payload
                }

                # 4.3 Send event via ZMQ
                await self._zmq_client.send(
                    target_mosaic_id=self.mosaic_instance.mosaic.id,
                    target_node_id=target_node,
                    event=event_data
                )

                logger.debug(
                    f"Event sent: event_id={event_id}, {self.node.node_id}/{source_session_id} -> "
                    f"{target_node}/{target_session_id}, event_type={event_type}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to send event to target {target_node}: {e}",
                    exc_info=True
                )
                # Continue sending to other targets in broadcast mode
                if len(target_nodes) > 1:
                    continue
                else:
                    raise

    # ========== Session Configuration ==========

    def get_default_session_config(self) -> Optional[Dict[str, Any]]:
        """
        Get default configuration for session creation.

        This method is called when a session is auto-created due to incoming event
        (without explicit config provided).

        Default behavior:
        - Reads all configuration from node.config (from database)
        - Ensures 'mode' is set to BACKGROUND if not specified
        - Returns the merged configuration

        Subclasses can override to add node-type-specific defaults
        (e.g., default model for agent nodes).

        Returns:
            Dict with default session configuration

        Examples:
            # Override to add node-type-specific defaults
            def get_default_session_config(self):
                config = super().get_default_session_config()
                config.setdefault("model", LLMModel.SONNET)
                return config
        """
        # Get config from database node model
        node_config = self.node.config or {}

        # Copy to avoid modifying the original
        config = node_config.copy()

        # Ensure mode is always set to BACKGROUND for auto-created sessions
        config.setdefault("mode", SessionMode.BACKGROUND)

        return config

    # ========== Abstract Methods (Must be implemented by subclasses) ==========

    @abstractmethod
    async def _on_start(self) -> None:
        """
        Subclass initialization hook.

        Called BEFORE ZMQ client connects (ensures resources ready before events arrive).
        Subclasses should implement their custom initialization logic here.

        Examples:
        - Agent nodes: Initialize Claude SDK, load system prompts
        - Scheduler nodes: Load schedule configuration, start timers
        - Email nodes: Connect to email server

        Resource cleanup on failure:
            If initialization fails, subclasses should cleanup their own resources using
            try-finally pattern:

            async def _on_start(self):
                self.claude_client = None
                try:
                    self.claude_client = Anthropic(api_key=...)
                    self.system_prompt = await load_prompt(...)
                except Exception:
                    # Cleanup on failure
                    if self.claude_client:
                        await self.claude_client.close()
                    raise

            Alternatively, ensure partial initialization is safe (resources set to None
            and checked before use).

        Raises:
            Exception: Any exception will cause node startup to fail and trigger cleanup
        """
        pass

    @abstractmethod
    async def _on_stop(self) -> None:
        """
        Subclass cleanup hook.

        Called AFTER ZMQ disconnects and all sessions are cleaned up.
        All session workers have stopped, so it's safe to cleanup shared resources.

        Subclasses should implement their custom cleanup logic here.

        Examples:
        - Agent nodes: Cleanup SDK resources (close Claude client)
        - Scheduler nodes: Cancel all scheduled tasks
        - Email nodes: Disconnect from email server

        Resource cleanup:
            async def _on_stop(self):
                # Safe to cleanup now - no sessions are using these resources
                if self.claude_client:
                    await self.claude_client.close()
                    self.claude_client = None

        Note:
            Should not raise exceptions - log errors and continue cleanup.
            This hook is NOT called if _on_start() fails during node startup.
        """
        pass

    async def _cleanup_all_sessions(self):
        """
        Clean up all running sessions.

        Called by _cleanup() to gracefully shut down all sessions.

        Steps:
        1. Get all session IDs from registry
        2. For each session:
           - Call self.close_session() (delegates to subclass implementation)

        Note:
            Delegates to subclass close_session() for consistent cleanup logic.
            No lock needed - invoked from _cleanup() which runs in the event loop
            (either from stop() or start() exception handler, serialized execution).
        """
        session_ids = list(self._sessions.keys())

        if not session_ids:
            return

        logger.info(
            f"Cleaning up {len(session_ids)} sessions for node {self.node.node_id}"
        )

        for session_id in session_ids:
            try:
                # Delegate to subclass close_session() implementation
                # Subclass handles:
                # - Calling session.close() (worker cancellation, _on_close hook)
                # - Database updates (for agent sessions)
                # - Unregistering from session map
                await self.close_session(session_id)
            except Exception as e:
                logger.error(
                    f"Error closing session: session_id={session_id}, error={e}",
                    exc_info=True
                )

        logger.info(f"All sessions cleaned up for node {self.node.node_id}")


    @abstractmethod
    async def create_session(
        self,
        session_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> 'MosaicSession':
        """
        Create a session (fully implemented by subclass).

        Different node types have fundamentally different session characteristics:
        - Agent nodes: Use database storage, config contains mode/model
        - Scheduler nodes: Runtime-only, config contains schedule settings
        - Email nodes: Runtime-only, config contains email settings

        Args:
            session_id: Session identifier (required)
            config: Session configuration (optional, subclass-specific)

        Returns:
            MosaicSession: The created session instance

        Raises:
            SessionConflictError: If session_id already exists (optional, subclass decision)
            Exception: Any subclass-specific creation errors

        Important:
            - Called ONLY from command loop (no lock needed, serialized by command queue)
            - Must register created session in self._sessions map
            - Subclasses decide when to call session.initialize() and when to register
            - Access self.async_session_factory for database operations (if needed)
        """
        pass

    async def send_message(self, session_id: str, message: str) -> None:
        """
        Send a message to a session (only for agent nodes).

        Args:
            session_id: Session identifier
            message: User message content

        Raises:
            SessionNotFoundError: If session not found
            NotImplementedError: If this node type doesn't support messages

        Note:
            This is typically implemented by creating and enqueuing a "user_message" event.
            Default implementation raises NotImplementedError.
        """
        raise NotImplementedError(
            f"Node type {self.node.node_type} does not support send_message"
        )

    async def interrupt_session(self, session_id: str) -> None:
        """
        Interrupt a running session.

        Delegates to the session's interrupt() method.
        If the session type doesn't support interruption, it will raise NotImplementedError.

        Args:
            session_id: Session identifier

        Raises:
            SessionNotFoundError: If session not found
            NotImplementedError: If session type doesn't support interruption

        Note:
            This method has a default implementation that delegates to the session.
            Subclasses typically don't need to override this.
        """
        mosaic_session = self._sessions.get(session_id)
        if mosaic_session is None:
            raise SessionNotFoundError(
                f"Session not found: session_id={session_id}"
            )

        await mosaic_session.interrupt()

    @abstractmethod
    async def close_session(self, session_id: str) -> None:
        """
        Close a session (fully implemented by subclass).

        Different node types may have different close strategies:
        - Agent nodes: Update database status, cleanup session resources
        - Scheduler nodes: Cancel timers, cleanup runtime-only state
        - Email nodes: Cleanup connections, runtime-only state

        Args:
            session_id: Session identifier

        Raises:
            SessionNotFoundError: If session not found

        Important:
            - Called ONLY from command loop (no lock needed, serialized by command queue)
            - Must call session.close() to stop worker and cleanup resources
            - Must unregister from self._sessions map after session cleanup
            - Access self.async_session_factory for database operations (if needed)
        """
        pass

    # ========== State Properties ==========

    @property
    def status(self) -> NodeStatus:
        """Get current node status"""
        return self._status

    def is_running(self) -> bool:
        """Check if node is running"""
        return self._status == NodeStatus.RUNNING
