"""
Mosaic Runtime - Event Waiter System

This module provides the blocking wait mechanism for the Mosaic event system.
It enables send_blocking() semantics where senders wait for responses from
subscribers.

Architecture:
=============

    ┌─────────────┐                      ┌─────────────┐
    │   Sender    │                      │  Receiver   │
    └──────┬──────┘                      └──────┬──────┘
           │                                    │
           │ 1. send_blocking(event)            │
           │    - Register waiter               │
           │    - Send event                    │
           │    - Block on future               │
           │                                    │
           │ ─────── event ────────────────────>│
           │                                    │
           │                           2. Process event
           │                              - Decide allow/deny
           │                              - Call reply()
           │                                    │
           │ <─────── reply ────────────────────│
           │                                    │
           │ 3. Waiter receives reply           │
           │    - Resolve future                │
           │    - Return decision               │
           │                                    │

Components:
===========

EventWaiter:
    Individual wait point backed by asyncio.Future.
    Supports timeout, resolution, and rejection.

WaiterRegistry:
    Thread-safe registry managing all active waiters.
    Maps event_id -> EventWaiter for lookup during reply processing.

Multi-Subscriber Support:
    When multiple subscribers have blocking subscriptions to the same event,
    we create a waiter for each subscriber and aggregate responses.

Design Principles:
==================
1. High-level code (Hook, Session) just calls send_blocking() - no waiter details
2. Inbox automatically routes replies to resolve waiters
3. WaiterRegistry is thread-safe for concurrent access
4. Waiters are cleaned up automatically on completion/timeout/error
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from mosaic.core.types import EventId, NodeId
from mosaic.core.models import AggregatedDecision, BlockingReply
from mosaic.core.exceptions import (
    WaiterError,
    WaiterNotFoundError,
    WaiterAlreadyExistsError,
    EventTimeoutError,
)


logger = logging.getLogger(__name__)


# =============================================================================
# Waiter State
# =============================================================================

class WaiterState(str, Enum):
    """State of an EventWaiter."""
    
    PENDING = "pending"      # Waiting for resolution
    RESOLVED = "resolved"    # Successfully resolved with result
    REJECTED = "rejected"    # Rejected with error
    TIMED_OUT = "timed_out"  # Timed out waiting


# =============================================================================
# Event Waiter
# =============================================================================

@dataclass
class EventWaiter:
    """
    Represents a single wait point for a blocking event.
    
    EventWaiter wraps an asyncio.Future to provide a clean interface
    for waiting on event responses. It supports:
    - Blocking wait with timeout
    - Resolution with a result value
    - Rejection with an error
    - State tracking for debugging
    
    Usage:
        waiter = EventWaiter(event_id="evt-123")
        
        # In one coroutine: wait for result
        try:
            result = await waiter.wait(timeout=30.0)
        except EventTimeoutError:
            # Handle timeout
            pass
        
        # In another coroutine: resolve the waiter
        waiter.resolve({"decision": "allow"})
    
    Thread Safety:
        EventWaiter is safe to use from multiple coroutines within
        the same event loop, but not across different event loops.
    
    Attributes:
        event_id: The event this waiter is waiting for
        subscriber_id: Optional ID of the subscriber we're waiting for
        state: Current state of the waiter
    """
    
    event_id: EventId
    subscriber_id: Optional[NodeId] = None
    state: WaiterState = field(default=WaiterState.PENDING, init=False)
    
    # Internal future (created on first access)
    _future: Optional[asyncio.Future] = field(
        default=None, init=False, repr=False
    )
    _result: Any = field(default=None, init=False, repr=False)
    _error: Optional[Exception] = field(default=None, init=False, repr=False)
    
    def __post_init__(self) -> None:
        """Initialize the internal future."""
        self._future = asyncio.get_event_loop().create_future()
    
    @property
    def is_pending(self) -> bool:
        """Check if waiter is still waiting."""
        return self.state == WaiterState.PENDING
    
    @property
    def is_done(self) -> bool:
        """Check if waiter has completed (resolved, rejected, or timed out)."""
        return self.state != WaiterState.PENDING
    
    async def wait(self, timeout: Optional[float] = None) -> Any:
        """
        Wait for the waiter to be resolved.
        
        Blocks until:
        - resolve() is called -> returns the result
        - reject() is called -> raises the error
        - timeout expires -> raises EventTimeoutError
        
        Args:
            timeout: Maximum seconds to wait (None for indefinite)
        
        Returns:
            The value passed to resolve()
        
        Raises:
            EventTimeoutError: If timeout expires
            WaiterError: If waiter was rejected
        """
        if self._future is None:
            raise WaiterError("Waiter future not initialized")
        
        try:
            if timeout is not None:
                result = await asyncio.wait_for(self._future, timeout=timeout)
            else:
                result = await self._future
            
            return result
        
        except asyncio.TimeoutError:
            self.state = WaiterState.TIMED_OUT
            logger.warning(
                f"Waiter timed out: event_id={self.event_id}, "
                f"subscriber_id={self.subscriber_id}, timeout={timeout}s"
            )
            raise EventTimeoutError(
                event_id=self.event_id,
                timeout_seconds=timeout or 0,
                waiting_for=[self.subscriber_id] if self.subscriber_id else None,
            )
        
        except asyncio.CancelledError:
            self.state = WaiterState.REJECTED
            logger.debug(f"Waiter cancelled: event_id={self.event_id}")
            raise
    
    def resolve(self, result: Any) -> None:
        """
        Resolve the waiter with a result.
        
        This wakes up any coroutine waiting via wait().
        
        Args:
            result: The value to return from wait()
        
        Raises:
            WaiterError: If waiter is already done
        """
        if self._future is None:
            raise WaiterError("Waiter future not initialized")
        
        if self.is_done:
            logger.warning(
                f"Attempted to resolve already-done waiter: "
                f"event_id={self.event_id}, state={self.state}"
            )
            return
        
        self.state = WaiterState.RESOLVED
        self._result = result
        
        if not self._future.done():
            self._future.set_result(result)
        
        logger.debug(
            f"Waiter resolved: event_id={self.event_id}, "
            f"subscriber_id={self.subscriber_id}"
        )
    
    def reject(self, error: Exception) -> None:
        """
        Reject the waiter with an error.
        
        This wakes up any coroutine waiting via wait() with an exception.
        
        Args:
            error: The exception to raise from wait()
        
        Raises:
            WaiterError: If waiter is already done
        """
        if self._future is None:
            raise WaiterError("Waiter future not initialized")
        
        if self.is_done:
            logger.warning(
                f"Attempted to reject already-done waiter: "
                f"event_id={self.event_id}, state={self.state}"
            )
            return
        
        self.state = WaiterState.REJECTED
        self._error = error
        
        if not self._future.done():
            self._future.set_exception(error)
        
        logger.debug(
            f"Waiter rejected: event_id={self.event_id}, error={error}"
        )
    
    def cancel(self) -> None:
        """
        Cancel the waiter.
        
        This is equivalent to reject(CancelledError()).
        """
        if self._future is not None and not self._future.done():
            self._future.cancel()
        self.state = WaiterState.REJECTED


# =============================================================================
# Multi-Subscriber Waiter
# =============================================================================

@dataclass
class MultiSubscriberWaiter:
    """
    Waiter that collects responses from multiple subscribers.
    
    When a blocking event has multiple subscribers (e.g., multiple auditors),
    we need to wait for all of them and aggregate their decisions.
    
    Aggregation Rule (one-vote-veto):
        - Any DENY -> final DENY
        - Any ASK (no DENY) -> final ASK
        - All ALLOW -> final ALLOW
        - Timeout for any subscriber -> treat as DENY
    
    Usage:
        waiter = MultiSubscriberWaiter(
            event_id="evt-123",
            subscriber_ids=["auditor-1", "auditor-2"]
        )
        
        # Wait for all subscribers
        decision = await waiter.wait(timeout=30.0)
        
        # Individual subscribers resolve via:
        waiter.resolve_for("auditor-1", {"decision": "allow"})
        waiter.resolve_for("auditor-2", {"decision": "deny", "reason": "..."})
    
    Attributes:
        event_id: The event we're waiting for responses to
        subscriber_ids: List of subscriber node IDs to wait for
    """
    
    event_id: EventId
    subscriber_ids: list[NodeId]
    
    # Individual waiters for each subscriber
    _waiters: dict[NodeId, EventWaiter] = field(
        default_factory=dict, init=False, repr=False
    )
    _replies: dict[NodeId, BlockingReply] = field(
        default_factory=dict, init=False, repr=False
    )
    _completion_event: Optional[asyncio.Event] = field(
        default=None, init=False, repr=False
    )
    
    def __post_init__(self) -> None:
        """Initialize individual waiters for each subscriber."""
        self._completion_event = asyncio.Event()
        
        for subscriber_id in self.subscriber_ids:
            self._waiters[subscriber_id] = EventWaiter(
                event_id=self.event_id,
                subscriber_id=subscriber_id,
            )
    
    @property
    def pending_subscribers(self) -> list[NodeId]:
        """Get list of subscribers that haven't responded yet."""
        return [
            sub_id for sub_id, waiter in self._waiters.items()
            if waiter.is_pending
        ]
    
    @property
    def is_complete(self) -> bool:
        """Check if all subscribers have responded."""
        return len(self.pending_subscribers) == 0
    
    def get_waiter_for(self, subscriber_id: NodeId) -> Optional[EventWaiter]:
        """Get the waiter for a specific subscriber."""
        return self._waiters.get(subscriber_id)
    
    def resolve_for(self, subscriber_id: NodeId, payload: dict[str, Any]) -> None:
        """
        Record a response from a specific subscriber.
        
        Args:
            subscriber_id: The subscriber sending the response
            payload: The response payload
        
        Raises:
            WaiterNotFoundError: If subscriber is not expected
        """
        waiter = self._waiters.get(subscriber_id)
        if waiter is None:
            raise WaiterNotFoundError(
                f"Unexpected subscriber {subscriber_id} for event {self.event_id}"
            )
        
        # Store the reply
        self._replies[subscriber_id] = BlockingReply(
            event_id=self.event_id,
            subscriber_id=subscriber_id,
            payload=payload,
        )
        
        # Resolve individual waiter
        waiter.resolve(payload)
        
        # Check if all subscribers have responded
        if self.is_complete:
            self._completion_event.set()
        
        logger.debug(
            f"MultiSubscriberWaiter received reply: event_id={self.event_id}, "
            f"subscriber_id={subscriber_id}, pending={len(self.pending_subscribers)}"
        )
    
    async def wait(self, timeout: Optional[float] = None) -> AggregatedDecision:
        """
        Wait for all subscribers to respond and aggregate decisions.
        
        Args:
            timeout: Maximum seconds to wait for all responses
        
        Returns:
            AggregatedDecision with final decision and individual replies
        
        Raises:
            EventTimeoutError: If timeout expires before all responses
        """
        try:
            if timeout is not None:
                await asyncio.wait_for(
                    self._completion_event.wait(),
                    timeout=timeout,
                )
            else:
                await self._completion_event.wait()
        
        except asyncio.TimeoutError:
            # Mark remaining waiters as timed out
            timed_out = self.pending_subscribers
            for sub_id in timed_out:
                self._waiters[sub_id].state = WaiterState.TIMED_OUT
            
            logger.warning(
                f"MultiSubscriberWaiter timed out: event_id={self.event_id}, "
                f"timed_out={timed_out}"
            )
        
        # Aggregate decisions
        return self._aggregate_decisions()
    
    def _aggregate_decisions(self) -> AggregatedDecision:
        """
        Aggregate decisions from all subscribers using one-vote-veto.
        
        Rules:
            - Any DENY -> final DENY
            - Any ASK (no DENY) -> final ASK
            - All ALLOW -> final ALLOW
            - Timeout -> treat as DENY
        
        Returns:
            AggregatedDecision with final_decision and individual_replies
        """
        individual_replies: list[BlockingReply] = []
        reasons: list[str] = []
        timed_out: list[NodeId] = []
        
        has_deny = False
        has_ask = False
        
        for subscriber_id in self.subscriber_ids:
            waiter = self._waiters[subscriber_id]
            
            if waiter.state == WaiterState.TIMED_OUT:
                # Timeout treated as DENY
                timed_out.append(subscriber_id)
                has_deny = True
                reasons.append(f"Subscriber {subscriber_id} timed out")
                continue
            
            reply = self._replies.get(subscriber_id)
            if reply is not None:
                individual_replies.append(reply)
                
                # Extract decision from payload
                decision = reply.payload.get("decision", "allow").lower()
                reason = reply.payload.get("reason", "")
                
                if decision == "deny":
                    has_deny = True
                    if reason:
                        reasons.append(f"{subscriber_id}: {reason}")
                elif decision == "ask":
                    has_ask = True
                    if reason:
                        reasons.append(f"{subscriber_id}: {reason}")
        
        # Determine final decision
        if has_deny:
            final_decision = "deny"
        elif has_ask:
            final_decision = "ask"
        else:
            final_decision = "allow"
        
        return AggregatedDecision(
            final_decision=final_decision,
            individual_replies=individual_replies,
            reasons=reasons,
            timed_out_subscribers=timed_out,
        )
    
    def cancel(self) -> None:
        """Cancel all pending waiters."""
        for waiter in self._waiters.values():
            if waiter.is_pending:
                waiter.cancel()


# =============================================================================
# Waiter Registry
# =============================================================================

class WaiterRegistry:
    """
    Global registry for managing active event waiters.
    
    WaiterRegistry provides a central place to register and resolve waiters.
    When a reply event arrives, the Inbox looks up the corresponding waiter
    and resolves it.
    
    Usage:
        registry = WaiterRegistry()
        
        # Register a waiter when sending blocking event
        waiter = registry.register(event_id="evt-123")
        
        # Later, when reply arrives
        registry.resolve(event_id="evt-123", result={"decision": "allow"})
        
        # For multi-subscriber events
        multi_waiter = registry.register_multi(
            event_id="evt-456",
            subscriber_ids=["auditor-1", "auditor-2"]
        )
    
    Thread Safety:
        All operations use asyncio.Lock for safety within the event loop.
        Not safe across different event loops.
    
    Cleanup:
        Waiters are automatically removed when:
        - resolve() or reject() is called
        - unregister() is explicitly called
        - cleanup_expired() is called for old waiters
    """
    
    def __init__(self) -> None:
        """Initialize the registry."""
        # Simple waiters (single subscriber or no subscriber tracking)
        self._waiters: dict[EventId, EventWaiter] = {}
        
        # Multi-subscriber waiters
        self._multi_waiters: dict[EventId, MultiSubscriberWaiter] = {}
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        logger.debug("WaiterRegistry initialized")
    
    async def register(
        self,
        event_id: EventId,
        subscriber_id: Optional[NodeId] = None,
    ) -> EventWaiter:
        """
        Register a new waiter for an event.
        
        Args:
            event_id: The event to wait for
            subscriber_id: Optional subscriber ID (for logging/debugging)
        
        Returns:
            The created EventWaiter
        
        Raises:
            WaiterAlreadyExistsError: If a waiter already exists for this event
        """
        async with self._lock:
            if event_id in self._waiters or event_id in self._multi_waiters:
                raise WaiterAlreadyExistsError(event_id)
            
            waiter = EventWaiter(
                event_id=event_id,
                subscriber_id=subscriber_id,
            )
            self._waiters[event_id] = waiter
            
            logger.debug(
                f"Waiter registered: event_id={event_id}, "
                f"subscriber_id={subscriber_id}"
            )
            
            return waiter
    
    async def register_multi(
        self,
        event_id: EventId,
        subscriber_ids: list[NodeId],
    ) -> MultiSubscriberWaiter:
        """
        Register a multi-subscriber waiter.
        
        Args:
            event_id: The event to wait for
            subscriber_ids: List of subscriber node IDs to wait for
        
        Returns:
            The created MultiSubscriberWaiter
        
        Raises:
            WaiterAlreadyExistsError: If a waiter already exists for this event
        """
        async with self._lock:
            if event_id in self._waiters or event_id in self._multi_waiters:
                raise WaiterAlreadyExistsError(event_id)
            
            waiter = MultiSubscriberWaiter(
                event_id=event_id,
                subscriber_ids=subscriber_ids,
            )
            self._multi_waiters[event_id] = waiter
            
            logger.debug(
                f"MultiSubscriberWaiter registered: event_id={event_id}, "
                f"subscribers={subscriber_ids}"
            )
            
            return waiter
    
    async def get(self, event_id: EventId) -> Optional[EventWaiter]:
        """
        Get a simple waiter by event ID.
        
        Args:
            event_id: The event to look up
        
        Returns:
            The EventWaiter if found, None otherwise
        """
        async with self._lock:
            return self._waiters.get(event_id)
    
    async def get_multi(self, event_id: EventId) -> Optional[MultiSubscriberWaiter]:
        """
        Get a multi-subscriber waiter by event ID.
        
        Args:
            event_id: The event to look up
        
        Returns:
            The MultiSubscriberWaiter if found, None otherwise
        """
        async with self._lock:
            return self._multi_waiters.get(event_id)
    
    async def resolve(
        self,
        event_id: EventId,
        result: Any,
        subscriber_id: Optional[NodeId] = None,
    ) -> bool:
        """
        Resolve a waiter with a result.
        
        This handles both simple and multi-subscriber waiters:
        - Simple waiter: directly resolved
        - Multi-subscriber: resolves the specific subscriber's slot
        
        Args:
            event_id: The event being replied to
            result: The reply payload
            subscriber_id: For multi-subscriber, which subscriber is replying
        
        Returns:
            True if waiter was found and resolved
        """
        async with self._lock:
            # Check simple waiter first
            if event_id in self._waiters:
                waiter = self._waiters[event_id]
                waiter.resolve(result)
                # Remove from registry
                del self._waiters[event_id]
                logger.debug(f"Simple waiter resolved and removed: {event_id}")
                return True
            
            # Check multi-subscriber waiter
            if event_id in self._multi_waiters:
                multi_waiter = self._multi_waiters[event_id]
                
                if subscriber_id is None:
                    logger.warning(
                        f"MultiSubscriberWaiter resolve without subscriber_id: "
                        f"event_id={event_id}"
                    )
                    return False
                
                try:
                    multi_waiter.resolve_for(subscriber_id, result)
                except WaiterNotFoundError:
                    logger.warning(
                        f"Unknown subscriber for multi-waiter: "
                        f"event_id={event_id}, subscriber_id={subscriber_id}"
                    )
                    return False
                
                # If all subscribers responded, remove from registry
                if multi_waiter.is_complete:
                    del self._multi_waiters[event_id]
                    logger.debug(
                        f"MultiSubscriberWaiter completed and removed: {event_id}"
                    )
                
                return True
            
            # No waiter found
            logger.debug(f"No waiter found for event: {event_id}")
            return False
    
    async def reject(
        self,
        event_id: EventId,
        error: Exception,
    ) -> bool:
        """
        Reject a waiter with an error.
        
        Args:
            event_id: The event to reject
            error: The error to raise
        
        Returns:
            True if waiter was found and rejected
        """
        async with self._lock:
            if event_id in self._waiters:
                waiter = self._waiters[event_id]
                waiter.reject(error)
                del self._waiters[event_id]
                return True
            
            if event_id in self._multi_waiters:
                multi_waiter = self._multi_waiters[event_id]
                multi_waiter.cancel()
                del self._multi_waiters[event_id]
                return True
            
            return False
    
    async def unregister(self, event_id: EventId) -> bool:
        """
        Remove a waiter from the registry.
        
        This cancels the waiter if it's still pending.
        
        Args:
            event_id: The event to unregister
        
        Returns:
            True if waiter was found and removed
        """
        async with self._lock:
            if event_id in self._waiters:
                waiter = self._waiters.pop(event_id)
                waiter.cancel()
                logger.debug(f"Waiter unregistered: {event_id}")
                return True
            
            if event_id in self._multi_waiters:
                multi_waiter = self._multi_waiters.pop(event_id)
                multi_waiter.cancel()
                logger.debug(f"MultiSubscriberWaiter unregistered: {event_id}")
                return True
            
            return False
    
    async def pending_count(self) -> int:
        """Get the number of pending waiters."""
        async with self._lock:
            simple_pending = sum(
                1 for w in self._waiters.values() if w.is_pending
            )
            multi_pending = sum(
                1 for w in self._multi_waiters.values() if not w.is_complete
            )
            return simple_pending + multi_pending
    
    async def clear(self) -> None:
        """
        Clear all waiters.
        
        This cancels all pending waiters. Use with caution.
        """
        async with self._lock:
            for waiter in self._waiters.values():
                waiter.cancel()
            self._waiters.clear()
            
            for multi_waiter in self._multi_waiters.values():
                multi_waiter.cancel()
            self._multi_waiters.clear()
            
            logger.info("WaiterRegistry cleared")

