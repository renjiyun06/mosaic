"""
SQLite Transport Backend Implementation

This module provides the SQLite-based transport backend for Mosaic.
It combines:
- SQLite database for event persistence (WAL mode)
- Unix Domain Sockets for inter-process signaling

Architecture:
-------------
                                    +------------------+
                                    |    Database      |
                                    |   events.db      |
                                    +--------+---------+
                                             |
          +----------------+                 |                 +----------------+
          |   Sender Node  |                 |                 | Receiver Node  |
          +-------+--------+                 |                 +--------+-------+
                  |                          |                          |
                  | 1. save_event()          |                          |
                  +------------------------->|                          |
                  |                          |                          |
                  | 2. notify() via UDS      |                          |
                  +---------------------------------------------------->|
                                             |                          |
                                             | 3. wake up               |
                                             |<-------------------------+
                                             |                          |
                                             | 4. fetch_pending()       |
                                             |<-------------------------+
                                             |                          |
                                             | 5. ack()                 |
                                             |<-------------------------+

Event Flow:
-----------
1. Sender calls send_event()
2. Event is persisted to SQLite with PENDING status
3. Sender notifies receiver via UDS
4. Receiver wakes up and fetches event (status -> PROCESSING)
5. Receiver processes and calls ack() (status -> COMPLETED)

Recovery:
---------
If receiver crashes while processing (status remains PROCESSING):
- After recovery_window_seconds, the event becomes visible again
- Event is redelivered with incremented delivery_count
- After max_delivery_attempts, event is marked FAILED
"""

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator, Optional

from mosaic.core.models import MeshEvent
from mosaic.core.types import MeshId, NodeId, EventId
from mosaic.core.exceptions import EventNotFoundError, TransportConnectionError

from mosaic.core.interfaces import EventEnvelope
from ..base import TransportBackend, TransportConfig
from .database import EventDatabase
from .repository import EventRepository
from .signal import SignalListener, SignalClient
from .envelope import SQLiteEventEnvelope


logger = logging.getLogger(__name__)


# Default polling interval when UDS signal fails
DEFAULT_POLL_INTERVAL_SECONDS = 1.0


class SQLiteTransportBackend(TransportBackend):
    """
    SQLite-based transport backend implementation.
    
    This backend uses:
    - SQLite with WAL mode for event persistence
    - Unix Domain Sockets for efficient signaling
    
    Features:
    ---------
    - At-least-once delivery semantics
    - Recovery window for crashed processors
    - Concurrent read access (WAL mode)
    - Low-latency signaling via UDS
    
    Usage:
        config = TransportConfig(mesh_id="dev-mesh")
        backend = SQLiteTransportBackend(config)
        await backend.initialize()
        
        try:
            # Send events
            await backend.send_event(event)
            
            # Receive events
            async for envelope in backend.receive_events("my-node"):
                process(envelope.event)
                await envelope.ack()
        finally:
            await backend.close()
    
    Thread Safety:
        This class is NOT thread-safe. Each process should have
        its own backend instance. SQLite WAL mode handles concurrent
        access from multiple processes.
    """
    
    def __init__(self, config: TransportConfig) -> None:
        """
        Initialize the SQLite transport backend.
        
        Args:
            config: Transport configuration
        """
        self._config = config
        self._mesh_id = config.mesh_id
        
        # Components (initialized in initialize())
        self._database: Optional[EventDatabase] = None
        self._repository: Optional[EventRepository] = None
        self._signal_client: Optional[SignalClient] = None
        
        # Active signal listeners (one per receive_events call)
        self._listeners: dict[NodeId, SignalListener] = {}
        
        self._initialized = False
    
    @property
    def mesh_id(self) -> MeshId:
        """The mesh this transport serves."""
        return self._mesh_id
    
    @property
    def config(self) -> TransportConfig:
        """Transport configuration."""
        return self._config
    
    async def initialize(self) -> None:
        """
        Initialize the transport backend.
        
        Creates the database, schema, and signal client.
        
        Raises:
            TransportConnectionError: If initialization fails
        """
        if self._initialized:
            return
        
        try:
            # Ensure directories exist
            self._config.mesh_dir.mkdir(parents=True, exist_ok=True)
            self._config.sockets_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize database
            self._database = EventDatabase(
                db_path=self._config.events_db_path,
                mesh_id=self._mesh_id,
            )
            await self._database.initialize()
            
            # Initialize repository
            self._repository = EventRepository(
                database=self._database,
                recovery_window_seconds=self._config.recovery_window_seconds,
                max_delivery_attempts=self._config.max_delivery_attempts,
            )
            
            # Initialize signal client
            self._signal_client = SignalClient(self._config.sockets_dir)
            
            self._initialized = True
            logger.info(f"SQLite transport initialized for mesh {self._mesh_id}")
        
        except Exception as e:
            raise TransportConnectionError(
                transport_type="sqlite",
                reason=str(e),
            ) from e
    
    async def close(self) -> None:
        """
        Close the transport backend.
        
        Stops all signal listeners and closes the database connection.
        """
        if not self._initialized:
            return
        
        # Stop all signal listeners
        for node_id, listener in list(self._listeners.items()):
            await listener.stop()
        self._listeners.clear()
        
        # Close database
        if self._database is not None:
            await self._database.close()
            self._database = None
        
        self._repository = None
        self._signal_client = None
        self._initialized = False
        
        logger.info(f"SQLite transport closed for mesh {self._mesh_id}")
    
    def _ensure_initialized(self) -> None:
        """Ensure the backend is initialized."""
        if not self._initialized:
            raise RuntimeError(
                "Transport not initialized. Call initialize() first."
            )
    
    async def send_event(self, event: MeshEvent) -> None:
        """
        Persist an event and notify the target node.
        
        Args:
            event: The event to send (target_id must be set)
        
        Raises:
            EventDeliveryError: If the event cannot be stored
        """
        self._ensure_initialized()
        assert self._repository is not None
        assert self._signal_client is not None
        
        # Validate event has target
        if not event.target_id:
            raise ValueError("Event must have target_id set")
        
        # Persist event
        await self._repository.save_event(event)
        logger.debug(
            f"Event {event.event_id} saved: "
            f"{event.source_id} -> {event.target_id} [{event.event_type}]"
        )
        
        # Notify target node (best effort)
        await self._signal_client.notify(event.target_id)
    
    def receive_events(self, node_id: NodeId) -> AsyncIterator[EventEnvelope]:
        """
        Create an async iterator for receiving events.
        
        This creates a signal listener for the node and yields
        events as they become available.
        
        Args:
            node_id: The node to receive events for
        
        Returns:
            Async iterator yielding EventEnvelope objects
        """
        self._ensure_initialized()
        return self._event_iterator(node_id)
    
    async def _event_iterator(
        self,
        node_id: NodeId,
    ) -> AsyncIterator[EventEnvelope]:
        """
        Internal async generator for event iteration.
        
        Yields events for the specified node, blocking when none
        are available and waiting for UDS signals.
        """
        assert self._repository is not None
        
        # Create and start signal listener
        socket_path = self._config.get_socket_path(node_id)
        listener = SignalListener(socket_path)
        await listener.start()
        self._listeners[node_id] = listener
        
        try:
            while True:
                # Try to fetch a pending event
                result = await self._repository.fetch_pending_event(node_id)
                
                if result is not None:
                    event, delivery_count = result
                    envelope = SQLiteEventEnvelope(
                        event=event,
                        delivery_count=delivery_count,
                        repository=self._repository,
                    )
                    yield envelope
                    continue
                
                # No events available - wait for signal or poll timeout
                signaled = await listener.wait_for_signal(
                    timeout=DEFAULT_POLL_INTERVAL_SECONDS
                )
                
                if not signaled:
                    # Timeout - check anyway (in case UDS failed)
                    logger.debug(
                        f"Poll timeout for node {node_id}, checking database"
                    )
        
        except asyncio.CancelledError:
            logger.debug(f"Event iterator cancelled for node {node_id}")
            raise
        
        finally:
            # Cleanup listener
            await listener.stop()
            self._listeners.pop(node_id, None)
    
    async def ack_event(self, event_id: EventId) -> None:
        """
        Acknowledge successful processing of an event.
        
        Args:
            event_id: The event to acknowledge
        
        Raises:
            EventNotFoundError: If the event doesn't exist
        """
        self._ensure_initialized()
        assert self._repository is not None
        
        success = await self._repository.mark_completed(event_id)
        if not success:
            raise EventNotFoundError(event_id)
    
    async def nack_event(self, event_id: EventId, requeue: bool = True) -> None:
        """
        Reject an event.
        
        Args:
            event_id: The event to reject
            requeue: If True, event returns to PENDING.
                    If False, event is marked as FAILED.
        
        Raises:
            EventNotFoundError: If the event doesn't exist
        """
        self._ensure_initialized()
        assert self._repository is not None
        
        if requeue:
            success = await self._repository.requeue(event_id)
        else:
            success = await self._repository.mark_failed(event_id)
        
        if not success:
            raise EventNotFoundError(event_id)
    
    async def get_event(self, event_id: EventId) -> Optional[MeshEvent]:
        """
        Get an event by ID.
        
        Args:
            event_id: The event to retrieve
        
        Returns:
            The event if found, None otherwise
        """
        self._ensure_initialized()
        assert self._repository is not None
        
        return await self._repository.get_event(event_id)
    
    async def get_pending_count(self, node_id: NodeId) -> int:
        """
        Get the count of pending events for a node.
        
        Args:
            node_id: The node to check
        
        Returns:
            Number of events in PENDING status
        """
        self._ensure_initialized()
        assert self._repository is not None
        
        return await self._repository.get_pending_count(node_id)
    
    async def cleanup_completed(
        self,
        older_than_seconds: int = 86400,
    ) -> int:
        """
        Remove completed events older than specified age.
        
        Args:
            older_than_seconds: Remove events older than this (default: 24h)
        
        Returns:
            Number of events removed
        """
        self._ensure_initialized()
        assert self._repository is not None
        
        count = await self._repository.cleanup_completed(older_than_seconds)
        logger.info(f"Cleaned up {count} completed events")
        return count
    
    async def cleanup_all(
        self,
        completed_older_than: int = 86400,
        failed_older_than: int = 604800,
    ) -> dict[str, int]:
        """
        Remove both completed and failed events.
        
        Args:
            completed_older_than: Age for completed events (default: 24h)
            failed_older_than: Age for failed events (default: 7 days)
        
        Returns:
            Dict with counts of removed events by status
        """
        self._ensure_initialized()
        assert self._repository is not None
        
        completed_count = await self._repository.cleanup_completed(
            completed_older_than
        )
        failed_count = await self._repository.cleanup_failed(
            failed_older_than
        )
        
        result = {
            "completed": completed_count,
            "failed": failed_count,
        }
        
        logger.info(f"Cleanup results: {result}")
        return result


# =============================================================================
# Factory Function
# =============================================================================

def create_sqlite_transport(
    mesh_id: MeshId,
    base_path: Optional[Path] = None,
    recovery_window_seconds: int = 300,
    max_delivery_attempts: int = 5,
) -> SQLiteTransportBackend:
    """
    Factory function to create a SQLite transport backend.
    
    Args:
        mesh_id: The mesh to create transport for
        base_path: Base directory (default: ~/.mosaic)
        recovery_window_seconds: Recovery window (default: 5 minutes)
        max_delivery_attempts: Max attempts (default: 5)
    
    Returns:
        Configured SQLiteTransportBackend (not yet initialized)
    
    Example:
        backend = create_sqlite_transport("dev-mesh")
        await backend.initialize()
    """
    config = TransportConfig(
        mesh_id=mesh_id,
        base_path=base_path,
        recovery_window_seconds=recovery_window_seconds,
        max_delivery_attempts=max_delivery_attempts,
    )
    return SQLiteTransportBackend(config)

