"""
Mosaic Runtime - Waiter Registry

This module provides the blocking wait mechanism for events that require
responses. It enables the send_blocking() pattern where a sender waits
for all blocking subscribers to reply.

Key Components:
- EventWaiter: A single wait point for one event (based on asyncio.Future)
- WaiterRegistry: Global registry managing event_id -> EventWaiter mappings

Design Principles:
1. DECOUPLING: Callers (Hook, Session) don't know who/how they wait
2. ASYNC-NATIVE: Uses asyncio.Future for efficient async waiting
3. TIMEOUT-AWARE: All waits have configurable timeouts
4. MULTI-RESPONSE: Supports waiting for multiple responses per event

Usage Example:
    # In Hook handler (sender side)
    waiter = registry.register(event_id, expected_count=2)
    await transport.send_event(event)
    try:
        responses = await waiter.wait(timeout=30.0)
    finally:
        registry.unregister(event_id)
    
    # In MCP tool handler (receiver side)
    registry.resolve(event_id, subscriber_id, response)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from mosaic.core.types import EventId, NodeId
from mosaic.core.exceptions import (
    WaiterNotFoundError,
    WaiterAlreadyExistsError,
    EventTimeoutError,
)


logger = logging.getLogger(__name__)


# =============================================================================
# Event Waiter
# =============================================================================

@dataclass
class WaiterResponse:
    """
    A single response from a blocking subscriber.
    
    Attributes:
        subscriber_id: The node that sent the response
        payload: Response data (interpretation depends on event type)
        received_at: When the response was received (monotonic time)
    """
    subscriber_id: NodeId
    payload: dict[str, Any]
    received_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class EventWaiter:
    """
    Wait point for a single blocking event.
    
    EventWaiter manages the async wait for one or more responses to a
    blocking event. It uses asyncio.Future internally for efficient
    non-polling waits.
    
    Lifecycle:
    1. Created when a blocking event is sent
    2. Receives responses via resolve()
    3. Completes when all expected responses arrive or timeout
    4. Cleaned up by the caller
    
    Thread Safety:
    This class is NOT thread-safe. All operations should be performed
    on the same event loop.
    
    Attributes:
        event_id: The event being waited on
        expected_count: Number of responses expected (blocking subscribers)
        responses: Collected responses so far
    """
    
    def __init__(self, event_id: EventId, expected_count: int = 1) -> None:
        """
        Initialize a new waiter.
        
        Args:
            event_id: The event to wait for responses to
            expected_count: Number of responses expected
        
        Raises:
            ValueError: If expected_count < 1
        """
        if expected_count < 1:
            raise ValueError(f"expected_count must be >= 1, got {expected_count}")
        
        self.event_id = event_id
        self.expected_count = expected_count
        self.responses: list[WaiterResponse] = []
        
        # Internal state
        self._future: asyncio.Future[list[WaiterResponse]] = asyncio.Future()
        self._lock = asyncio.Lock()
        self._completed = False
        
        logger.debug(
            f"EventWaiter created: event_id={event_id}, "
            f"expected_count={expected_count}"
        )
    
    async def wait(self, timeout: float = 30.0) -> list[WaiterResponse]:
        """
        Wait for all expected responses or until timeout.
        
        This method blocks until either:
        - All expected responses have been received
        - The timeout expires
        - An error occurs
        
        Args:
            timeout: Maximum seconds to wait
        
        Returns:
            List of all collected responses
        
        Raises:
            EventTimeoutError: If timeout expires before all responses
            asyncio.CancelledError: If the wait is cancelled
        """
        try:
            return await asyncio.wait_for(self._future, timeout=timeout)
        except asyncio.TimeoutError:
            # Collect information about who we're still waiting for
            received_from = [r.subscriber_id for r in self.responses]
            logger.warning(
                f"Timeout waiting for event {self.event_id}: "
                f"received {len(self.responses)}/{self.expected_count} responses"
            )
            raise EventTimeoutError(
                event_id=self.event_id,
                timeout_seconds=timeout,
                waiting_for=None,  # We don't know who we're waiting for
            )
    
    async def resolve(self, subscriber_id: NodeId, payload: dict[str, Any]) -> None:
        """
        Record a response from a subscriber.
        
        If this is the last expected response, the waiter completes
        and any wait() calls return.
        
        Args:
            subscriber_id: The node sending the response
            payload: Response data
        """
        async with self._lock:
            if self._completed:
                logger.warning(
                    f"Received response for already-completed waiter: "
                    f"event_id={self.event_id}, subscriber_id={subscriber_id}"
                )
                return
            
            response = WaiterResponse(
                subscriber_id=subscriber_id,
                payload=payload,
            )
            self.responses.append(response)
            
            logger.debug(
                f"EventWaiter received response: event_id={self.event_id}, "
                f"from={subscriber_id}, count={len(self.responses)}/{self.expected_count}"
            )
            
            # Check if we have all expected responses
            if len(self.responses) >= self.expected_count:
                self._completed = True
                self._future.set_result(self.responses)
                logger.debug(f"EventWaiter completed: event_id={self.event_id}")
    
    def reject(self, error: Exception) -> None:
        """
        Complete the waiter with an error.
        
        This causes any wait() calls to raise the given exception.
        
        Args:
            error: The exception to raise in wait()
        """
        if not self._completed:
            self._completed = True
            self._future.set_exception(error)
            logger.debug(f"EventWaiter rejected: event_id={self.event_id}, error={error}")
    
    @property
    def is_completed(self) -> bool:
        """Check if this waiter has completed (success or failure)."""
        return self._completed
    
    @property
    def response_count(self) -> int:
        """Number of responses received so far."""
        return len(self.responses)


# =============================================================================
# Waiter Registry
# =============================================================================

class WaiterRegistry:
    """
    Global registry for event waiters.
    
    WaiterRegistry manages the lifecycle of EventWaiter instances,
    providing a central place to register, resolve, and clean up waiters.
    
    Design Notes:
    - One registry per MeshClient (not truly global)
    - Handles multiple concurrent waiters
    - Automatic cleanup on unregister
    
    Thread Safety:
    This class uses asyncio.Lock for synchronization. All operations
    should be performed on the same event loop.
    """
    
    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._waiters: dict[EventId, EventWaiter] = {}
        self._lock = asyncio.Lock()
        logger.debug("WaiterRegistry initialized")
    
    async def register(
        self,
        event_id: EventId,
        expected_count: int = 1,
    ) -> EventWaiter:
        """
        Register a new waiter for an event.
        
        Args:
            event_id: The event to create a waiter for
            expected_count: Number of responses expected
        
        Returns:
            The created EventWaiter
        
        Raises:
            WaiterAlreadyExistsError: If a waiter already exists for this event
        """
        async with self._lock:
            if event_id in self._waiters:
                raise WaiterAlreadyExistsError(event_id)
            
            waiter = EventWaiter(event_id, expected_count)
            self._waiters[event_id] = waiter
            
            logger.debug(
                f"WaiterRegistry: registered waiter for event_id={event_id}, "
                f"expected_count={expected_count}"
            )
            return waiter
    
    async def get(self, event_id: EventId) -> Optional[EventWaiter]:
        """
        Get the waiter for an event.
        
        Args:
            event_id: The event to look up
        
        Returns:
            The EventWaiter if found, None otherwise
        """
        async with self._lock:
            return self._waiters.get(event_id)
    
    async def resolve(
        self,
        event_id: EventId,
        subscriber_id: NodeId,
        payload: dict[str, Any],
    ) -> bool:
        """
        Resolve a waiter with a response.
        
        This is called when a reply event is received for a blocking event.
        
        Args:
            event_id: The event being replied to
            subscriber_id: The node sending the reply
            payload: Reply payload
        
        Returns:
            True if a waiter was found and resolved, False otherwise
        """
        async with self._lock:
            waiter = self._waiters.get(event_id)
            if waiter is None:
                logger.debug(
                    f"WaiterRegistry: no waiter for event_id={event_id}, "
                    f"reply from {subscriber_id} ignored"
                )
                return False
        
        # Release lock before async operation
        await waiter.resolve(subscriber_id, payload)
        return True
    
    async def unregister(self, event_id: EventId) -> Optional[EventWaiter]:
        """
        Remove a waiter from the registry.
        
        This should be called after wait() completes to clean up resources.
        
        Args:
            event_id: The event to unregister
        
        Returns:
            The removed waiter, or None if not found
        """
        async with self._lock:
            waiter = self._waiters.pop(event_id, None)
            if waiter:
                logger.debug(f"WaiterRegistry: unregistered waiter for event_id={event_id}")
            return waiter
    
    async def reject_all(self, error: Exception) -> int:
        """
        Reject all pending waiters with an error.
        
        This is useful during shutdown to unblock all waiting operations.
        
        Args:
            error: The exception to raise in all waiters
        
        Returns:
            Number of waiters rejected
        """
        async with self._lock:
            count = 0
            for waiter in self._waiters.values():
                if not waiter.is_completed:
                    waiter.reject(error)
                    count += 1
            self._waiters.clear()
            logger.debug(f"WaiterRegistry: rejected {count} waiters with {error}")
            return count
    
    @property
    def pending_count(self) -> int:
        """Number of waiters currently registered."""
        return len(self._waiters)

