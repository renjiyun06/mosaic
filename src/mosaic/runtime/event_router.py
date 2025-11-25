"""
Mosaic Runtime - Event Router

This module provides event routing based on subscription relationships.
The EventRouter is responsible for:
1. Looking up subscribers for an event
2. Creating event copies for each subscriber
3. Sending events via the transport layer
4. Identifying blocking subscribers

Architecture:
=============

    ┌─────────────────────────────────────────────────────────────────┐
    │                        EventRouter                               │
    └─────────────────────────────────────────────────────────────────┘
                │                                      │
                │ Query subscriptions                  │ Send events
                ▼                                      ▼
    ┌─────────────────────┐                ┌─────────────────────────┐
    │  SubscriptionRepo   │                │   TransportBackend      │
    │  (storage module)   │                │  (transport module)     │
    └─────────────────────┘                └─────────────────────────┘

Event Flow:
===========

    1. Node produces event (e.g., PreToolUse from CC node)
                    │
                    ▼
    2. EventRouter.route_event(event)
                    │
                    ├──> Query SubscriptionRepository
                    │    "Who subscribes to this node for this event type?"
                    │
                    ├──> For each subscriber:
                    │    - Clone event
                    │    - Set target_id = subscriber
                    │    - Send via transport
                    │
                    ▼
    3. Events delivered to subscriber inboxes

Design Principles:
==================
1. Router only handles ROUTING - no waiting logic
2. Blocking/non-blocking determined by subscription, passed to caller
3. Router is stateless - all state in storage and transport
4. Router does NOT interpret session_scope - that's for agent nodes

Separation of Concerns:
=======================
- EventRouter: "Where should this event go?"
- WaiterRegistry: "How do we wait for replies?"
- MeshOutbox: Combines router + waiter for send_blocking()
"""

import logging
from typing import Optional

from mosaic.core.models import MeshEvent, Subscription
from mosaic.core.types import MeshId, NodeId, EventId
from mosaic.storage import SubscriptionRepository

from mosaic.transport import TransportBackend


logger = logging.getLogger(__name__)


class EventRouter:
    """
    Routes events to subscribers based on subscription relationships.
    
    EventRouter queries the subscription repository to find who should
    receive an event, then uses the transport backend to deliver it.
    
    Usage:
        router = EventRouter(
            mesh_id="dev",
            subscription_repo=sub_repo,
            transport=transport_backend,
        )
        
        # Route to all subscribers
        await router.route_event(event)
        
        # Get blocking subscribers (for send_blocking)
        blocking = await router.get_blocking_subscribers(
            source_id="worker",
            event_type="PreToolUse"
        )
    
    Attributes:
        mesh_id: The mesh this router serves
        subscription_repo: Repository for subscription queries
        transport: Transport backend for event delivery
    """
    
    def __init__(
        self,
        mesh_id: MeshId,
        subscription_repo: SubscriptionRepository,
        transport: TransportBackend,
    ) -> None:
        """
        Initialize the event router.
        
        Args:
            mesh_id: The mesh this router serves
            subscription_repo: Repository for subscription queries
            transport: Transport backend for event delivery
        """
        self._mesh_id = mesh_id
        self._subscription_repo = subscription_repo
        self._transport = transport
        
        logger.debug(f"EventRouter initialized for mesh {mesh_id}")
    
    @property
    def mesh_id(self) -> MeshId:
        """The mesh this router serves."""
        return self._mesh_id
    
    async def get_subscribers(
        self,
        source_id: NodeId,
        event_type: str,
    ) -> list[Subscription]:
        """
        Get all subscribers for a node's event type.
        
        This returns subscriptions where:
        - target_id = source_id (they subscribe to this node)
        - event_pattern matches the event_type (or is "*")
        
        Args:
            source_id: The node producing the event
            event_type: The type of event being produced
        
        Returns:
            List of matching subscriptions
        """
        # Get all subscriptions where this node is the target (being subscribed to)
        all_subs = await self._subscription_repo.get_by_target(
            mesh_id=self._mesh_id,
            target_id=source_id,
        )
        
        # Filter to subscriptions that match this event type
        matching = [
            sub for sub in all_subs
            if sub.matches_event(event_type)
        ]
        
        logger.debug(
            f"get_subscribers: source_id={source_id}, event_type={event_type}, "
            f"found={len(matching)} of {len(all_subs)} total"
        )
        
        return matching
    
    async def get_blocking_subscribers(
        self,
        source_id: NodeId,
        event_type: str,
    ) -> list[Subscription]:
        """
        Get subscribers with blocking subscriptions for an event.
        
        Blocking subscriptions use the "!" prefix in event_pattern
        (e.g., "!PreToolUse"). These require the sender to wait for
        a response.
        
        Args:
            source_id: The node producing the event
            event_type: The type of event being produced
        
        Returns:
            List of subscriptions that are blocking
        """
        all_subs = await self.get_subscribers(source_id, event_type)
        
        blocking = [sub for sub in all_subs if sub.is_blocking()]
        
        logger.debug(
            f"get_blocking_subscribers: source_id={source_id}, "
            f"event_type={event_type}, blocking={len(blocking)}"
        )
        
        return blocking
    
    async def get_non_blocking_subscribers(
        self,
        source_id: NodeId,
        event_type: str,
    ) -> list[Subscription]:
        """
        Get subscribers with non-blocking subscriptions for an event.
        
        Non-blocking subscriptions don't require waiting for a response.
        
        Args:
            source_id: The node producing the event
            event_type: The type of event being produced
        
        Returns:
            List of subscriptions that are non-blocking
        """
        all_subs = await self.get_subscribers(source_id, event_type)
        
        non_blocking = [sub for sub in all_subs if not sub.is_blocking()]
        
        logger.debug(
            f"get_non_blocking_subscribers: source_id={source_id}, "
            f"event_type={event_type}, non_blocking={len(non_blocking)}"
        )
        
        return non_blocking
    
    async def route_event(
        self,
        event: MeshEvent,
        subscriptions: Optional[list[Subscription]] = None,
    ) -> list[NodeId]:
        """
        Route an event to all matching subscribers.
        
        This method:
        1. Finds all matching subscriptions (if not provided)
        2. For each subscriber, creates a copy of the event with target_id set
        3. Sends each copy via the transport layer
        
        Args:
            event: The event to route (source_id must be set)
            subscriptions: Optional pre-queried subscriptions.
                          If None, queries based on event.source_id and event.event_type
        
        Returns:
            List of node IDs that received the event
        
        Raises:
            EventDeliveryError: If event delivery fails
        """
        # Get subscriptions if not provided
        if subscriptions is None:
            subscriptions = await self.get_subscribers(
                source_id=event.source_id,
                event_type=event.event_type,
            )
        
        if not subscriptions:
            logger.debug(
                f"No subscribers for event: source_id={event.source_id}, "
                f"event_type={event.event_type}"
            )
            return []
        
        # Route to each subscriber
        recipients: list[NodeId] = []
        
        for subscription in subscriptions:
            # Create a copy of the event with target_id set
            routed_event = MeshEvent(
                event_id=event.event_id,
                mesh_id=event.mesh_id,
                source_id=event.source_id,
                target_id=subscription.source_id,  # source_id in subscription is the subscriber
                event_type=event.event_type,
                timestamp=event.timestamp,
                session_trace=event.session_trace,
                reply_to=event.reply_to,
                payload=event.payload,
            )
            
            # Send via transport
            await self._transport.send_event(routed_event)
            recipients.append(subscription.source_id)
            
            logger.debug(
                f"Event routed: {event.event_id} -> {subscription.source_id} "
                f"[{subscription.event_pattern}]"
            )
        
        logger.info(
            f"Event {event.event_id} routed to {len(recipients)} subscribers: "
            f"{recipients}"
        )
        
        return recipients
    
    async def route_to_specific(
        self,
        event: MeshEvent,
        target_id: NodeId,
    ) -> None:
        """
        Route an event to a specific target node.
        
        This bypasses subscription lookup and sends directly to the target.
        Used for reply events where the target is known.
        
        Args:
            event: The event to send
            target_id: The target node ID
        
        Raises:
            EventDeliveryError: If delivery fails
        """
        # Create event with target set
        routed_event = MeshEvent(
            event_id=event.event_id,
            mesh_id=event.mesh_id,
            source_id=event.source_id,
            target_id=target_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            session_trace=event.session_trace,
            reply_to=event.reply_to,
            payload=event.payload,
        )
        
        # Send via transport
        await self._transport.send_event(routed_event)
        
        logger.debug(
            f"Event routed directly: {event.event_id} -> {target_id}"
        )
    
    async def route_reply(
        self,
        original_event: MeshEvent,
        reply_payload: dict,
        reply_event_id: EventId,
        reply_source_id: NodeId,
    ) -> None:
        """
        Route a reply event back to the original sender.
        
        This is a convenience method for creating and routing reply events.
        
        Args:
            original_event: The event being replied to
            reply_payload: The reply payload
            reply_event_id: ID for the reply event
            reply_source_id: Node sending the reply
        
        Raises:
            EventDeliveryError: If delivery fails
        """
        # Create reply event
        reply_event = MeshEvent(
            event_id=reply_event_id,
            mesh_id=original_event.mesh_id,
            source_id=reply_source_id,
            target_id=original_event.source_id,  # Reply goes back to original sender
            event_type="NodeMessage",
            reply_to=original_event.event_id,
            payload=reply_payload,
        )
        
        # Send via transport (direct to target)
        await self._transport.send_event(reply_event)
        
        logger.debug(
            f"Reply routed: {reply_event_id} -> {original_event.source_id} "
            f"(reply_to={original_event.event_id})"
        )


# =============================================================================
# Routing Result
# =============================================================================

class RoutingResult:
    """
    Result of an event routing operation.
    
    This provides detailed information about where an event was routed,
    including which subscribers are blocking vs non-blocking.
    
    Attributes:
        event_id: The routed event's ID
        blocking_subscribers: List of blocking subscription recipients
        non_blocking_subscribers: List of non-blocking subscription recipients
    """
    
    def __init__(
        self,
        event_id: EventId,
        blocking_subscribers: list[Subscription],
        non_blocking_subscribers: list[Subscription],
    ) -> None:
        """Initialize the routing result."""
        self.event_id = event_id
        self.blocking_subscribers = blocking_subscribers
        self.non_blocking_subscribers = non_blocking_subscribers
    
    @property
    def has_blocking(self) -> bool:
        """Check if there are any blocking subscribers."""
        return len(self.blocking_subscribers) > 0
    
    @property
    def blocking_node_ids(self) -> list[NodeId]:
        """Get IDs of blocking subscriber nodes."""
        return [sub.source_id for sub in self.blocking_subscribers]
    
    @property
    def all_recipients(self) -> list[NodeId]:
        """Get IDs of all recipients."""
        blocking = [sub.source_id for sub in self.blocking_subscribers]
        non_blocking = [sub.source_id for sub in self.non_blocking_subscribers]
        return blocking + non_blocking
    
    @property
    def total_recipients(self) -> int:
        """Get total number of recipients."""
        return len(self.blocking_subscribers) + len(self.non_blocking_subscribers)

