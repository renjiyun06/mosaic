"""
SQLite Event Envelope Implementation

This module provides the EventEnvelope implementation for SQLite transport.
The envelope wraps a MeshEvent and provides ACK/NACK operations.

Design:
-------
The envelope holds a reference to the repository, allowing it to
perform status updates when ack() or nack() is called.

Thread Safety:
--------------
Each envelope should only be acked/nacked once. Calling ack/nack
multiple times is idempotent (subsequent calls are no-ops).
"""

import logging
from typing import TYPE_CHECKING

from mosaic.core.interfaces import EventEnvelope
from mosaic.core.models import MeshEvent
from mosaic.core.types import EventId

if TYPE_CHECKING:
    from .repository import EventRepository


logger = logging.getLogger(__name__)


class SQLiteEventEnvelope(EventEnvelope):
    """
    EventEnvelope implementation for SQLite transport.
    
    This envelope wraps a MeshEvent and provides methods to
    acknowledge or reject the event. The underlying repository
    is used to update event status in the database.
    
    Usage:
        envelope = SQLiteEventEnvelope(event, delivery_count, repository)
        
        try:
            # Process the event
            process(envelope.event)
            # Acknowledge success
            await envelope.ack()
        except Exception:
            # Requeue for retry
            await envelope.nack(requeue=True)
    
    Idempotency:
        ack() and nack() can safely be called multiple times.
        Only the first call has effect; subsequent calls are no-ops.
    """
    
    def __init__(
        self,
        event: MeshEvent,
        delivery_count: int,
        repository: "EventRepository",
    ) -> None:
        """
        Initialize the envelope.
        
        Args:
            event: The wrapped event
            delivery_count: Number of times this event has been delivered
            repository: Repository for status updates
        """
        self._event = event
        self._delivery_count = delivery_count
        self._repository = repository
        self._acknowledged = False
    
    @property
    def event(self) -> MeshEvent:
        """The wrapped event."""
        return self._event
    
    @property
    def event_id(self) -> EventId:
        """The event's unique identifier."""
        return self._event.event_id
    
    @property
    def delivery_count(self) -> int:
        """
        Number of times this event has been delivered.
        
        A count > 1 indicates redelivery after failure or timeout.
        Nodes should implement idempotent processing.
        """
        return self._delivery_count
    
    @property
    def is_redelivery(self) -> bool:
        """Check if this is a redelivery (delivery_count > 1)."""
        return self._delivery_count > 1
    
    @property
    def is_acknowledged(self) -> bool:
        """Check if this envelope has been acked or nacked."""
        return self._acknowledged
    
    async def ack(self) -> None:
        """
        Acknowledge successful processing.
        
        Marks the event as COMPLETED in the database.
        The event will not be redelivered.
        
        This method is idempotent - calling it multiple times
        has no additional effect after the first call.
        """
        if self._acknowledged:
            logger.debug(f"Event {self.event_id} already acknowledged, skipping")
            return
        
        success = await self._repository.mark_completed(self.event_id)
        
        if success:
            logger.debug(f"Event {self.event_id} marked as completed")
        else:
            logger.warning(
                f"Failed to mark event {self.event_id} as completed "
                "(may have been processed by another handler)"
            )
        
        self._acknowledged = True
    
    async def nack(self, requeue: bool = True) -> None:
        """
        Reject the event.
        
        Args:
            requeue: If True, event returns to PENDING for redelivery.
                    If False, event is marked as FAILED permanently.
        
        Use Cases:
            - requeue=True: Temporary failure, retry later
            - requeue=False: Permanent failure, don't retry
        
        This method is idempotent - calling it multiple times
        has no additional effect after the first call.
        """
        if self._acknowledged:
            logger.debug(f"Event {self.event_id} already acknowledged, skipping nack")
            return
        
        if requeue:
            success = await self._repository.requeue(self.event_id)
            status_msg = "requeued for retry"
        else:
            success = await self._repository.mark_failed(self.event_id)
            status_msg = "marked as failed"
        
        if success:
            logger.debug(f"Event {self.event_id} {status_msg}")
        else:
            logger.warning(
                f"Failed to {status_msg.replace('ed', '')} event {self.event_id} "
                "(may have been processed by another handler)"
            )
        
        self._acknowledged = True
    
    def __repr__(self) -> str:
        return (
            f"SQLiteEventEnvelope("
            f"event_id={self.event_id!r}, "
            f"event_type={self._event.event_type!r}, "
            f"delivery_count={self._delivery_count}, "
            f"acknowledged={self._acknowledged}"
            f")"
        )

