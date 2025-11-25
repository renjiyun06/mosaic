"""
Mosaic Runtime - MeshOutbox Implementation

This module provides the MeshOutbox implementation that combines event
routing with the waiter system for blocking semantics.

Architecture:
=============

    ┌─────────────────────────────────────────────────────────────────┐
    │                         MeshOutboxImpl                          │
    │                                                                 │
    │  ┌─────────────────────────────────────────────────────────────┐│
    │  │                       send()                                 ││
    │  │  1. EventRouter.route_event() -> all subscribers            ││
    │  │  2. Return immediately (fire-and-persist)                   ││
    │  └─────────────────────────────────────────────────────────────┘│
    │                                                                 │
    │  ┌─────────────────────────────────────────────────────────────┐│
    │  │                   send_blocking()                            ││
    │  │  1. Get blocking subscribers from EventRouter               ││
    │  │  2. Register MultiSubscriberWaiter                          ││
    │  │  3. Route event to all subscribers                          ││
    │  │  4. Wait for all blocking responses                         ││
    │  │  5. Return AggregatedDecision                               ││
    │  └─────────────────────────────────────────────────────────────┘│
    │                                                                 │
    │  ┌─────────────────────────────────────────────────────────────┐│
    │  │                       reply()                                ││
    │  │  1. Create reply event with reply_to field                  ││
    │  │  2. Route directly to original sender                       ││
    │  │  3. (Sender's inbox will resolve their waiter)              ││
    │  └─────────────────────────────────────────────────────────────┘│
    └─────────────────────────────────────────────────────────────────┘

send_blocking Flow:
===================

    Sender                    Registry                 Subscribers
      │                          │                          │
      │ 1. send_blocking(event)  │                          │
      │────────────────────────>│                          │
      │                          │                          │
      │ 2. register_multi()      │                          │
      │<────────────────────────│                          │
      │                          │                          │
      │ 3. route_event() ─────────────────────────────────>│
      │                          │                          │
      │ 4. waiter.wait() ────────┤                          │
      │     (blocked)            │                          │
      │                          │ 5. Subscribers process   │
      │                          │    and call reply()      │
      │                          │<────────────────────────│
      │                          │                          │
      │ 6. waiter resolved       │                          │
      │<────────────────────────│                          │
      │                          │                          │
      │ 7. Return AggregatedDecision                        │
      │                          │                          │

Design Principles:
==================
1. send() is fire-and-persist - no waiting
2. send_blocking() combines routing + waiting + aggregation
3. reply() is a convenience for subscribers
4. All complexity is hidden behind simple interfaces
"""

import logging
from datetime import datetime
from typing import Any

from mosaic.core.interfaces import MeshOutbox
from mosaic.core.models import MeshEvent, AggregatedDecision
from mosaic.core.types import NodeId, MeshId, EventId
from mosaic.core.exceptions import EventNotFoundError

from mosaic.transport import TransportBackend

from .event_router import EventRouter
from .waiter import WaiterRegistry

from mosaic.utils.id_generator import generate_event_id


logger = logging.getLogger(__name__)


class MeshOutboxImpl(MeshOutbox):
    """
    Implementation of MeshOutbox with routing and blocking support.
    
    MeshOutboxImpl provides three sending modes:
    
    1. send(): Fire-and-persist to all subscribers
       - Routes to all matching subscribers
       - Returns immediately
       - No response expected
    
    2. send_blocking(): Send and wait for blocking subscribers
       - Routes to all subscribers
       - Waits for blocking subscribers to reply
       - Aggregates responses (one-vote-veto)
       - Returns AggregatedDecision
    
    3. reply(): Respond to a received event
       - Sends reply directly to original sender
       - Triggers sender's waiter
    
    Usage:
        outbox = MeshOutboxImpl(
            node_id="worker",
            mesh_id="dev",
            transport=transport_backend,
            router=event_router,
            waiter_registry=registry,
        )
        
        # Fire-and-persist
        await outbox.send(event)
        
        # Wait for blocking subscribers
        decision = await outbox.send_blocking(event, timeout=30.0)
        
        # Reply to an event
        await outbox.reply(event_id="evt-123", payload={"decision": "allow"})
    
    Attributes:
        node_id: The node this outbox belongs to
        mesh_id: The mesh this outbox is in
    """
    
    def __init__(
        self,
        node_id: NodeId,
        mesh_id: MeshId,
        transport: TransportBackend,
        router: EventRouter,
        waiter_registry: WaiterRegistry,
    ) -> None:
        """
        Initialize the outbox.
        
        Args:
            node_id: The node this outbox belongs to
            mesh_id: The mesh this outbox is in
            transport: Transport backend for event delivery
            router: Event router for subscription-based routing
            waiter_registry: Registry for managing blocking waiters
        """
        self._node_id = node_id
        self._mesh_id = mesh_id
        self._transport = transport
        self._router = router
        self._waiter_registry = waiter_registry
        
        logger.debug(f"MeshOutboxImpl created for node {node_id}")
    
    @property
    def node_id(self) -> NodeId:
        """The node this outbox belongs to."""
        return self._node_id
    
    @property
    def mesh_id(self) -> MeshId:
        """The mesh this outbox is in."""
        return self._mesh_id
    
    async def send(self, event: MeshEvent) -> None:
        """
        Send an event to all subscribers (fire-and-persist).
        
        The event is persisted and routed to all matching subscribers.
        This method returns immediately without waiting for processing.
        
        Args:
            event: The event to send (source_id should be set)
        
        Raises:
            EventDeliveryError: If event cannot be persisted
        """
        # Ensure event has correct mesh_id and source_id
        if event.source_id != self._node_id:
            logger.warning(
                f"Event source_id ({event.source_id}) doesn't match "
                f"outbox node_id ({self._node_id}). Sending anyway."
            )
        
        # Route to all subscribers
        recipients = await self._router.route_event(event)
        
        logger.debug(
            f"Event sent: {event.event_id} [{event.event_type}] "
            f"to {len(recipients)} subscribers"
        )
    
    async def send_blocking(
        self,
        event: MeshEvent,
        timeout: float = 30.0,
    ) -> AggregatedDecision:
        """
        Send an event and wait for all blocking subscribers to respond.
        
        This method:
        1. Finds all blocking subscribers
        2. Sends the event to ALL subscribers (blocking and non-blocking)
        3. Waits for all BLOCKING subscribers to respond (or timeout)
        4. Aggregates responses using one-vote-veto
        
        Aggregation Rule (one-vote-veto):
            - Any DENY -> final DENY
            - Any ASK (no DENY) -> final ASK
            - All ALLOW -> final ALLOW
            - Timeout -> treat as DENY
        
        Args:
            event: The event to send
            timeout: Maximum seconds to wait for all responses
        
        Returns:
            AggregatedDecision with final decision and individual replies
        
        Raises:
            EventDeliveryError: If event cannot be delivered
        """
        # Get all subscribers
        all_subs = await self._router.get_subscribers(
            source_id=event.source_id,
            event_type=event.event_type,
        )
        
        # Separate blocking and non-blocking
        blocking_subs = [s for s in all_subs if s.is_blocking()]
        non_blocking_subs = [s for s in all_subs if not s.is_blocking()]
        
        logger.debug(
            f"send_blocking: event={event.event_id}, "
            f"blocking={len(blocking_subs)}, non_blocking={len(non_blocking_subs)}"
        )
        
        # If no blocking subscribers, just send and return ALLOW
        if not blocking_subs:
            # Route to non-blocking subscribers
            await self._router.route_event(event, subscriptions=non_blocking_subs)
            
            return AggregatedDecision(
                final_decision="allow",
                individual_replies=[],
                reasons=[],
                timed_out_subscribers=[],
            )
        
        # Register multi-subscriber waiter
        blocking_ids = [s.source_id for s in blocking_subs]
        waiter = await self._waiter_registry.register_multi(
            event_id=event.event_id,
            subscriber_ids=blocking_ids,
        )
        
        try:
            # Route to ALL subscribers (blocking and non-blocking)
            await self._router.route_event(event, subscriptions=all_subs)
            
            # Wait for blocking subscribers
            decision = await waiter.wait(timeout=timeout)
            
            logger.info(
                f"Blocking event completed: {event.event_id}, "
                f"decision={decision.final_decision}"
            )
            
            return decision
        
        except Exception as e:
            # Ensure waiter is cleaned up on error
            await self._waiter_registry.unregister(event.event_id)
            raise
    
    async def reply(
        self,
        event_id: EventId,
        payload: dict[str, Any],
    ) -> None:
        """
        Reply to a blocking event.
        
        When a node receives a blocking event (!EventName), it should
        send a reply. This method:
        1. Looks up the original event to find the sender
        2. Creates a reply event with reply_to field set
        3. Sends it directly to the original sender
        4. The sender's inbox will resolve their waiter
        
        Args:
            event_id: The event being replied to
            payload: Reply data (format depends on event type)
                     For PreToolUse: {"decision": "allow/deny/ask", "reason": "..."}
        
        Raises:
            EventNotFoundError: If the event_id doesn't exist
            EventDeliveryError: If reply cannot be delivered
        """
        # Get the original event to find the sender
        original_event = await self._transport.get_event(event_id)
        
        if original_event is None:
            raise EventNotFoundError(event_id)
        
        # Create reply event
        reply_event = MeshEvent(
            event_id=generate_event_id(),
            mesh_id=self._mesh_id,
            source_id=self._node_id,
            target_id=original_event.source_id,  # Reply to original sender
            event_type="NodeMessage",
            timestamp=datetime.utcnow(),
            reply_to=event_id,
            payload=payload,
        )
        
        # Send directly to original sender (bypass subscription routing)
        await self._transport.send_event(reply_event)
        
        logger.debug(
            f"Reply sent: {reply_event.event_id} -> {original_event.source_id} "
            f"(reply_to={event_id})"
        )
    
    async def send_to(
        self,
        target_id: NodeId,
        event_type: str,
        payload: dict[str, Any],
        event_id: Optional[EventId] = None,
    ) -> MeshEvent:
        """
        Send an event directly to a specific node (bypassing subscriptions).
        
        This is useful for direct node-to-node communication without
        relying on subscription relationships.
        
        Args:
            target_id: The target node ID
            event_type: The event type
            payload: Event payload
            event_id: Optional event ID (generated if not provided)
        
        Returns:
            The sent event
        
        Raises:
            EventDeliveryError: If delivery fails
        """
        event = MeshEvent(
            event_id=event_id or generate_event_id(),
            mesh_id=self._mesh_id,
            source_id=self._node_id,
            target_id=target_id,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            payload=payload,
        )
        
        # Send directly via transport
        await self._transport.send_event(event)
        
        logger.debug(
            f"Direct event sent: {event.event_id} -> {target_id} [{event_type}]"
        )
        
        return event

