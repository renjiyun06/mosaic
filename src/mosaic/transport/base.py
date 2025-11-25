"""
Mosaic Transport Layer - Base Interfaces

This module defines the abstract interface for transport backends.
Transport backends are responsible for:
- Persisting events to storage
- Delivering events to nodes
- Managing event lifecycle (pending -> processing -> completed)
- Signaling nodes when new events arrive

Design Principles:
------------------
1. Transport is PLUGGABLE: SQLite, Kafka, Redis can all implement this interface
2. Transport is INTERNAL: Only runtime module uses transport directly
3. At-least-once delivery: Events are guaranteed to be delivered at least once
4. Recovery window: Processing events that exceed timeout become visible again

The transport layer does NOT:
- Route events (that's EventRouter in runtime)
- Wait for responses (that's WaiterRegistry in runtime)
- Interpret event content (it's opaque bytes to transport)
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import AsyncIterator, Optional

from mosaic.core.interfaces import EventEnvelope
from mosaic.core.models import MeshEvent
from mosaic.core.types import MeshId, NodeId, EventId, EventStatus


class TransportBackend(ABC):
    """
    Abstract interface for event transport backends.
    
    This is the core abstraction that enables pluggable transport
    implementations. Each backend (SQLite, Kafka, Redis) implements
    this interface with its own storage and delivery mechanisms.
    
    Lifecycle:
    ----------
    1. initialize(): Set up storage (create tables, connect to broker)
    2. send_event(): Store and signal delivery
    3. receive_events(): Iterate over pending events
    4. ack_event()/nack_event(): Complete or reject processing
    5. close(): Release resources
    
    Event Status Flow:
    ------------------
    PENDING -> PROCESSING -> COMPLETED
                  |
                  +-> FAILED (if nack with requeue=False)
                  +-> PENDING (if nack with requeue=True)
                  +-> PENDING (if recovery window exceeded)
    
    Mesh Isolation:
    ---------------
    Each mesh has its own event storage. The backend is instantiated
    per-mesh, so all operations are scoped to that mesh.
    """
    
    @property
    @abstractmethod
    def mesh_id(self) -> MeshId:
        """The mesh this transport serves."""
        pass
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the transport backend.
        
        This should:
        - Create storage if it doesn't exist
        - Establish connections
        - Perform any necessary migrations
        
        Raises:
            TransportConnectionError: If initialization fails
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """
        Close the transport backend.
        
        This should:
        - Release all resources
        - Close connections
        - Flush any buffered data
        """
        pass
    
    @abstractmethod
    async def send_event(self, event: MeshEvent) -> None:
        """
        Persist an event and notify the target node.
        
        This method:
        1. Stores the event with PENDING status
        2. Signals the target node that an event is waiting
        
        The event's target_id must be set before calling.
        
        Args:
            event: The event to send (target_id must be set)
        
        Raises:
            EventDeliveryError: If the event cannot be stored
        """
        pass
    
    @abstractmethod
    def receive_events(self, node_id: NodeId) -> AsyncIterator[EventEnvelope]:
        """
        Create an async iterator for receiving events.
        
        This returns an async iterator that:
        1. Yields events targeted at the specified node
        2. Marks events as PROCESSING when yielded
        3. Blocks when no events are available
        4. Respects the recovery window for stuck events
        
        Args:
            node_id: The node to receive events for
        
        Returns:
            Async iterator yielding EventEnvelope objects
        
        Example:
            async for envelope in backend.receive_events("my-node"):
                try:
                    process(envelope.event)
                    await envelope.ack()
                except Exception:
                    await envelope.nack(requeue=True)
        """
        pass
    
    @abstractmethod
    async def ack_event(self, event_id: EventId) -> None:
        """
        Acknowledge successful processing of an event.
        
        Marks the event as COMPLETED. The event will not be
        redelivered.
        
        Args:
            event_id: The event to acknowledge
        
        Raises:
            EventNotFoundError: If the event doesn't exist
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def get_event(self, event_id: EventId) -> Optional[MeshEvent]:
        """
        Get an event by ID.
        
        Args:
            event_id: The event to retrieve
        
        Returns:
            The event if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def get_pending_count(self, node_id: NodeId) -> int:
        """
        Get the count of pending events for a node.
        
        This is useful for monitoring and load balancing.
        
        Args:
            node_id: The node to check
        
        Returns:
            Number of events in PENDING status for this node
        """
        pass
    
    @abstractmethod
    async def cleanup_completed(
        self,
        older_than_seconds: int = 86400,
    ) -> int:
        """
        Remove completed events older than the specified age.
        
        This is a maintenance operation to prevent unbounded storage growth.
        
        Args:
            older_than_seconds: Remove events completed more than this many
                               seconds ago (default: 24 hours)
        
        Returns:
            Number of events removed
        """
        pass


class TransportConfig:
    """
    Configuration for transport backends.
    
    Each backend type may use different subsets of these settings.
    
    Attributes:
        mesh_id: The mesh this transport serves
        base_path: Base directory for file-based storage
        recovery_window_seconds: Time before stuck events become visible again
        max_delivery_attempts: Maximum redelivery attempts before marking FAILED
    """
    
    def __init__(
        self,
        mesh_id: MeshId,
        base_path: Optional[Path] = None,
        recovery_window_seconds: int = 300,  # 5 minutes
        max_delivery_attempts: int = 5,
    ) -> None:
        self.mesh_id = mesh_id
        self.base_path = base_path or Path.home() / ".mosaic"
        self.recovery_window_seconds = recovery_window_seconds
        self.max_delivery_attempts = max_delivery_attempts
    
    @property
    def mesh_dir(self) -> Path:
        """Directory for this mesh's runtime files."""
        return self.base_path / self.mesh_id
    
    @property
    def events_db_path(self) -> Path:
        """Path to the events database (SQLite backend)."""
        return self.mesh_dir / "events.db"
    
    @property
    def sockets_dir(self) -> Path:
        """Directory for UDS socket files."""
        return self.mesh_dir / "sockets"
    
    def get_socket_path(self, node_id: NodeId) -> Path:
        """Get the socket path for a specific node."""
        return self.sockets_dir / f"{node_id}.sock"

