"""
Mosaic Runtime - MeshOutbox Implementation

This module implements MeshOutbox, the event output channel for nodes.
It provides three sending modes:

1. send(): Fire-and-persist (non-blocking)
2. send_blocking(): Send and wait for responses
3. reply(): Respond to a blocking event

Key Responsibilities:
1. Route events to subscribers (using EventRouter)
2. Manage blocking waits (using WaiterRegistry)
3. Aggregate responses from multiple blocking subscribers
4. Create and send reply events

Design Notes:
- send() routes via EventRouter and sends via TransportBackend
- send_blocking() adds WaiterRegistry coordination
- reply() creates a reply event and triggers sender's waiter
- Aggregation uses one-vote-veto rule
"""

import logging
from typing import Any

from mosaic.core.interfaces import MeshOutbox
from mosaic.core.models import (
    MeshEvent,
    AggregatedDecision,
    BlockingReply,
)
from mosaic.core.types import NodeId, MeshId, EventId, PermissionDecision
from mosaic.core.exceptions import EventTimeoutError, EventNotFoundError
from mosaic.transport.base import TransportBackend
from mosaic.utils.id_generator import generate_event_id

from .event_router import EventRouter
from .waiter import WaiterRegistry, WaiterResponse


logger = logging.getLogger(__name__)


class MeshOutboxImpl(MeshOutbox):
    """
    Implementation of MeshOutbox interface.
    
    MeshOutboxImpl provides the sending capabilities for nodes:
    
    1. FIRE-AND-PERSIST: send() routes and persists events without waiting
    
    2. BLOCKING SEND: send_blocking() waits for all blocking subscribers
       to respond, then aggregates their responses
    
    3. REPLY: reply() creates and sends a response to a blocking event
    
    The outbox coordinates multiple components:
    - EventRouter: Determines who receives events
    - TransportBackend: Persists and delivers events
    - WaiterRegistry: Manages blocking waits
    
    Usage:
        outbox = MeshOutboxImpl(
            node_id, mesh_id, transport, router, waiter_registry
        )
        
        # Fire-and-forget
        await outbox.send(event)
        
        # Wait for responses
        decision = await outbox.send_blocking(event, timeout=30.0)
        
        # Reply to blocking event
        await outbox.reply(event_id, {"decision": "allow"})
    
    Attributes:
        node_id: The node this outbox sends events from
        mesh_id: The mesh this outbox belongs to
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
            node_id: Node this outbox sends events from
            mesh_id: Mesh this outbox belongs to
            transport: Transport backend for sending events
            router: Event router for determining subscribers
            waiter_registry: Registry for managing blocking waits
        """
        self._node_id = node_id
        self._mesh_id = mesh_id
        self._transport = transport
        self._router = router
        self._waiter_registry = waiter_registry
        
        logger.debug(f"MeshOutboxImpl initialized: node_id={node_id}, mesh_id={mesh_id}")
    
    @property
    def node_id(self) -> NodeId:
        """The node this outbox sends events from."""
        return self._node_id
    
    @property
    def mesh_id(self) -> MeshId:
        """The mesh this outbox belongs to."""
        return self._mesh_id
    
    async def send(self, event: MeshEvent) -> None:
        """
        Send an event to all subscribers (fire-and-persist).
        
        The event is routed to all matching subscribers and persisted.
        This method returns immediately without waiting for processing.
        
        Args:
            event: The event to send (source_id should match this outbox)
        
        Raises:
            EventDeliveryError: If event cannot be persisted
        """
        logger.debug(
            f"MeshOutboxImpl.send: event_id={event.event_id}, "
            f"type={event.event_type}"
        )
        
        # Route event to find all subscribers
        routing_result = await self._router.route(event)
        
        if routing_result.total_count == 0:
            logger.debug(f"MeshOutboxImpl.send: no subscribers for event {event.event_id}")
            return
        
        # Send to all subscribers via transport
        for routed_event in routing_result.routed_events:
            logger.debug(
                f"MeshOutboxImpl.send: delivering to {routed_event.target_id}"
            )
            await self._transport.send_event(routed_event)
        
        logger.debug(
            f"MeshOutboxImpl.send: completed event_id={event.event_id}, "
            f"delivered to {routing_result.total_count} subscribers"
        )
    
    async def send_blocking(
        self,
        event: MeshEvent,
        timeout: float = 30.0,
    ) -> AggregatedDecision:
        """
        Send an event and wait for all blocking subscribers to respond.
        
        This method:
        1. Routes event to find all subscribers
        2. Sends to non-blocking subscribers immediately
        3. Registers waiter for blocking subscribers
        4. Sends to blocking subscribers
        5. Waits for all blocking responses (or timeout)
        6. Aggregates responses using one-vote-veto
        
        Args:
            event: The event to send
            timeout: Maximum seconds to wait for all responses
        
        Returns:
            AggregatedDecision with final decision and individual replies
        
        Raises:
            EventTimeoutError: If timeout expires before all responses
        """
        logger.debug(
            f"MeshOutboxImpl.send_blocking: event_id={event.event_id}, "
            f"type={event.event_type}, timeout={timeout}"
        )
        
        # Route event
        routing_result = await self._router.route(event)
        
        # If no blocking subscribers, just send normally
        if not routing_result.has_blocking:
            logger.debug(
                f"MeshOutboxImpl.send_blocking: no blocking subscribers, "
                f"falling back to normal send"
            )
            await self.send(event)
            return AggregatedDecision(
                final_decision=PermissionDecision.ALLOW.value,
                individual_replies=[],
                reasons=[],
            )
        
        # Send to non-blocking subscribers first (they don't need waiter)
        for routed_event in routing_result.routed_events:
            is_blocking = any(
                sub.source_id == routed_event.target_id
                for sub in routing_result.blocking_subscriptions
            )
            if not is_blocking:
                logger.debug(
                    f"MeshOutboxImpl.send_blocking: sending to non-blocking "
                    f"subscriber {routed_event.target_id}"
                )
                await self._transport.send_event(routed_event)
        
        # Register waiter for blocking subscribers
        waiter = await self._waiter_registry.register(
            event_id=event.event_id,
            expected_count=routing_result.blocking_count,
        )
        
        try:
            # Send to blocking subscribers
            for routed_event in routing_result.routed_events:
                is_blocking = any(
                    sub.source_id == routed_event.target_id
                    for sub in routing_result.blocking_subscriptions
                )
                if is_blocking:
                    logger.debug(
                        f"MeshOutboxImpl.send_blocking: sending to blocking "
                        f"subscriber {routed_event.target_id}"
                    )
                    await self._transport.send_event(routed_event)
            
            # Wait for responses
            responses = await waiter.wait(timeout=timeout)
            
            # Aggregate responses
            return self._aggregate_responses(event.event_id, responses)
            
        except EventTimeoutError:
            # Some subscribers didn't respond in time
            # Aggregate what we have, treating timeouts as DENY
            return self._aggregate_responses(
                event.event_id,
                waiter.responses,
                timed_out=routing_result.get_blocking_subscriber_ids(),
            )
        finally:
            # Always clean up waiter
            await self._waiter_registry.unregister(event.event_id)
    
    async def reply(
        self,
        event_id: EventId,
        payload: dict[str, Any],
    ) -> None:
        """
        Reply to a blocking event.
        
        Creates a reply event and sends it to the original sender.
        The reply will trigger the sender's waiter.
        
        Args:
            event_id: The event being replied to
            payload: Reply data (format depends on event type)
        
        Raises:
            EventNotFoundError: If the event doesn't exist
        """
        logger.debug(
            f"MeshOutboxImpl.reply: replying to event_id={event_id}"
        )
        
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
            reply_to=event_id,
            payload=payload,
        )
        
        # Send reply directly (no routing needed)
        await self._transport.send_event(reply_event)
        
        logger.debug(
            f"MeshOutboxImpl.reply: sent reply {reply_event.event_id} "
            f"to {original_event.source_id} for event {event_id}"
        )
    
    def _aggregate_responses(
        self,
        event_id: EventId,
        responses: list[WaiterResponse],
        timed_out: list[NodeId] | None = None,
    ) -> AggregatedDecision:
        """
        Aggregate responses from multiple blocking subscribers.
        
        Uses one-vote-veto rule:
        - Any DENY -> final DENY
        - Any ASK (no DENY) -> final ASK
        - All ALLOW -> final ALLOW
        - Timeout subscribers count as DENY
        
        Args:
            event_id: The event that was sent
            responses: Responses received
            timed_out: List of subscribers that timed out
        
        Returns:
            AggregatedDecision with final decision
        """
        timed_out = timed_out or []
        
        # Convert responses to BlockingReply objects
        individual_replies = [
            BlockingReply(
                event_id=event_id,
                subscriber_id=resp.subscriber_id,
                payload=resp.payload,
            )
            for resp in responses
        ]
        
        # Collect all decisions and reasons
        decisions = []
        reasons = []
        
        for resp in responses:
            decision = resp.payload.get("decision", PermissionDecision.ALLOW.value)
            decisions.append(decision)
            
            reason = resp.payload.get("reason")
            if reason:
                reasons.append(f"[{resp.subscriber_id}] {reason}")
        
        # Add timeout entries as DENY
        for node_id in timed_out:
            if node_id not in [r.subscriber_id for r in responses]:
                decisions.append(PermissionDecision.DENY.value)
                reasons.append(f"[{node_id}] Timed out waiting for response")
        
        # Apply one-vote-veto aggregation
        final_decision = self._one_vote_veto(decisions)
        
        logger.debug(
            f"MeshOutboxImpl._aggregate_responses: event_id={event_id}, "
            f"decisions={decisions}, final={final_decision}"
        )
        
        return AggregatedDecision(
            final_decision=final_decision,
            individual_replies=individual_replies,
            reasons=reasons,
            timed_out_subscribers=timed_out,
        )
    
    def _one_vote_veto(self, decisions: list[str]) -> str:
        """
        Apply one-vote-veto aggregation rule.
        
        Args:
            decisions: List of decision strings
        
        Returns:
            Aggregated decision string
        """
        if not decisions:
            return PermissionDecision.ALLOW.value
        
        # Any DENY -> final DENY
        if any(d == PermissionDecision.DENY.value for d in decisions):
            return PermissionDecision.DENY.value
        
        # Any ASK -> final ASK
        if any(d == PermissionDecision.ASK.value for d in decisions):
            return PermissionDecision.ASK.value
        
        # All ALLOW -> final ALLOW
        return PermissionDecision.ALLOW.value

