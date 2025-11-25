"""
Mosaic Runtime - MeshInbox Implementation

This module provides the MeshInbox implementation that wraps the transport
layer and integrates with the waiter system for reply handling.

Architecture:
=============

    ┌────────────────────────────────────────────────────────────────┐
    │                         MeshInboxImpl                          │
    │                                                                │
    │  ┌──────────────┐    ┌──────────────┐    ┌─────────────────┐   │
    │  │   Transport  │───>│  Reply       │───>│  WaiterRegistry │   │
    │  │   Inbox      │    │  Handler     │    │                 │   │
    │  └──────────────┘    └──────────────┘    └─────────────────┘   │
    │         │                                                      │
    │         │ (non-reply events)                                   │
    │         ▼                                                      │
    │  ┌──────────────────────────────────────────────────────────┐  │
    │  │                    Async Iterator                        │  │
    │  │                  (yields EventEnvelope)                  │  │
    │  └──────────────────────────────────────────────────────────┘  │
    └────────────────────────────────────────────────────────────────┘

Event Flow:
===========

1. Transport delivers EventEnvelope to MeshInbox
2. MeshInbox checks if event is a reply (has reply_to field)
3. If reply:
   - Look up waiter in WaiterRegistry
   - Resolve waiter with payload
   - ACK the event (handled internally)
   - Do NOT yield to consumer
4. If not reply:
   - Yield to consumer as normal
   - Consumer processes and ACKs

Design Principles:
==================
1. Inbox wraps transport - adds reply handling logic
2. Reply events are handled transparently
3. Non-reply events flow through to consumer
4. WaiterRegistry integration is internal detail

Note on Reply Handling:
======================
When a reply event arrives (event.reply_to is set), we:
1. Find the original event's waiter
2. Resolve it with the reply payload
3. ACK the reply event automatically
4. Don't yield it to the consumer

This means the consumer only sees "real" events, not replies.
The sender's send_blocking() automatically gets the reply.
"""

import asyncio
import logging
from typing import AsyncIterator, Optional

from mosaic.core.interfaces import MeshInbox, EventEnvelope
from mosaic.core.models import MeshEvent
from mosaic.core.types import NodeId, MeshId

from mosaic.transport import TransportBackend

from .waiter import WaiterRegistry


logger = logging.getLogger(__name__)


class MeshInboxImpl(MeshInbox):
    """
    Implementation of MeshInbox that integrates transport and waiter handling.
    
    MeshInboxImpl wraps a TransportBackend's receive_events() and adds:
    - Automatic reply event handling (resolves waiters)
    - Transparent filtering of reply events from consumers
    
    Usage:
        inbox = MeshInboxImpl(
            node_id="worker",
            mesh_id="dev",
            transport=transport_backend,
            waiter_registry=registry,
        )
        
        async for envelope in inbox:
            # Only non-reply events are yielded here
            event = envelope.event
            await process(event)
            await envelope.ack()
    
    Attributes:
        node_id: The node this inbox belongs to
        mesh_id: The mesh this inbox is in
    """
    
    def __init__(
        self,
        node_id: NodeId,
        mesh_id: MeshId,
        transport: TransportBackend,
        waiter_registry: WaiterRegistry,
    ) -> None:
        """
        Initialize the inbox.
        
        Args:
            node_id: The node this inbox belongs to
            mesh_id: The mesh this inbox is in
            transport: Transport backend for receiving events
            waiter_registry: Registry for resolving reply waiters
        """
        self._node_id = node_id
        self._mesh_id = mesh_id
        self._transport = transport
        self._waiter_registry = waiter_registry
        
        # Internal state
        self._closed = False
        self._iterator: Optional[AsyncIterator[EventEnvelope]] = None
        
        logger.debug(f"MeshInboxImpl created for node {node_id}")
    
    @property
    def node_id(self) -> NodeId:
        """The node this inbox belongs to."""
        return self._node_id
    
    @property
    def mesh_id(self) -> MeshId:
        """The mesh this inbox is in."""
        return self._mesh_id
    
    @property
    def is_closed(self) -> bool:
        """Check if the inbox is closed."""
        return self._closed
    
    def __aiter__(self) -> AsyncIterator[EventEnvelope]:
        """Return self as async iterator."""
        return self
    
    async def __anext__(self) -> EventEnvelope:
        """
        Get the next event envelope.
        
        This filters out reply events (handling them internally)
        and only yields non-reply events to the consumer.
        
        Returns:
            EventEnvelope containing the next non-reply event
        
        Raises:
            StopAsyncIteration: When inbox is closed
        """
        if self._closed:
            raise StopAsyncIteration
        
        # Lazily create the transport iterator
        if self._iterator is None:
            self._iterator = self._transport.receive_events(self._node_id)
        
        while True:
            try:
                # Get next envelope from transport
                envelope = await self._iterator.__anext__()
                event = envelope.event
                
                # Check if this is a reply event
                if event.reply_to is not None:
                    # Handle reply internally
                    await self._handle_reply(envelope)
                    # Continue to get next event (don't yield reply)
                    continue
                
                # Non-reply event - yield to consumer
                logger.debug(
                    f"Inbox yielding event: {event.event_id} "
                    f"[{event.event_type}] from {event.source_id}"
                )
                return envelope
            
            except StopAsyncIteration:
                self._closed = True
                raise
    
    async def _handle_reply(self, envelope: EventEnvelope) -> None:
        """
        Handle a reply event by resolving its waiter.
        
        This:
        1. Looks up the waiter for the original event
        2. Resolves the waiter with the reply payload
        3. ACKs the reply event
        
        Args:
            envelope: The reply event envelope
        """
        event = envelope.event
        reply_to = event.reply_to
        
        logger.debug(
            f"Handling reply event: {event.event_id} "
            f"(reply_to={reply_to}) from {event.source_id}"
        )
        
        # Try to resolve waiter
        resolved = await self._waiter_registry.resolve(
            event_id=reply_to,
            result=event.payload,
            subscriber_id=event.source_id,
        )
        
        if resolved:
            logger.debug(f"Waiter resolved for event {reply_to}")
        else:
            logger.warning(
                f"No waiter found for reply: reply_to={reply_to}, "
                f"from={event.source_id}. The sender may have timed out."
            )
        
        # ACK the reply event
        await envelope.ack()
    
    async def close(self) -> None:
        """
        Close the inbox.
        
        After closing:
        - __anext__ will raise StopAsyncIteration
        - No more events will be delivered
        - Resources are released
        """
        if self._closed:
            return
        
        self._closed = True
        self._iterator = None
        
        logger.debug(f"MeshInboxImpl closed for node {self._node_id}")


class FilteredInbox(MeshInbox):
    """
    An inbox wrapper that filters events based on a predicate.
    
    This is useful for nodes that only want to receive certain
    event types, without modifying subscriptions.
    
    Usage:
        # Only receive PreToolUse events
        filtered = FilteredInbox(
            inner_inbox=inbox,
            predicate=lambda e: e.event_type == "PreToolUse"
        )
        
        async for envelope in filtered:
            # Only PreToolUse events here
            ...
    
    Note: Filtered-out events are still ACKed to prevent redelivery.
    """
    
    def __init__(
        self,
        inner_inbox: MeshInbox,
        predicate: callable,
        auto_ack_filtered: bool = True,
    ) -> None:
        """
        Initialize the filtered inbox.
        
        Args:
            inner_inbox: The underlying inbox
            predicate: Function that returns True for events to keep
            auto_ack_filtered: If True, ACK events that are filtered out
        """
        self._inner = inner_inbox
        self._predicate = predicate
        self._auto_ack = auto_ack_filtered
        self._closed = False
    
    def __aiter__(self) -> AsyncIterator[EventEnvelope]:
        """Return self as async iterator."""
        return self
    
    async def __anext__(self) -> EventEnvelope:
        """Get the next matching event envelope."""
        if self._closed:
            raise StopAsyncIteration
        
        while True:
            envelope = await self._inner.__anext__()
            
            if self._predicate(envelope.event):
                return envelope
            
            # Event filtered out
            logger.debug(
                f"Event filtered: {envelope.event.event_id} "
                f"[{envelope.event.event_type}]"
            )
            
            if self._auto_ack:
                await envelope.ack()
    
    async def close(self) -> None:
        """Close the inbox."""
        self._closed = True
        await self._inner.close()

