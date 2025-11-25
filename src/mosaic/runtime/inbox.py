"""
Mosaic Runtime - MeshInbox Implementation

This module implements MeshInbox, the event input channel for nodes.
It adapts the transport layer's receive_events() to the MeshInbox interface,
adding reply detection and automatic waiter resolution.

Key Responsibilities:
1. Receive events from transport layer
2. Detect and handle reply events (trigger WaiterRegistry)
3. Provide async iterator interface to nodes

Design Notes:
- MeshInbox wraps TransportBackend.receive_events()
- Reply events are intercepted and routed to WaiterRegistry
- Non-reply events are passed through to the node
- The inbox maintains the connection to transport layer
"""

import asyncio
import logging
from typing import AsyncIterator, Optional

from mosaic.core.interfaces import MeshInbox, EventEnvelope
from mosaic.core.models import MeshEvent
from mosaic.core.types import NodeId, MeshId
from mosaic.transport.base import TransportBackend

from .waiter import WaiterRegistry


logger = logging.getLogger(__name__)


class MeshInboxImpl(MeshInbox):
    """
    Implementation of MeshInbox interface.
    
    MeshInboxImpl adapts the transport layer's event stream to the
    MeshInbox interface. It adds value beyond raw transport by:
    
    1. REPLY INTERCEPTION: Reply events are detected and routed to
       WaiterRegistry, waking up send_blocking() calls.
    
    2. CLEAN INTERFACE: Nodes only see non-reply events through the
       iterator; replies are handled transparently.
    
    3. LIFECYCLE MANAGEMENT: Properly closes the transport stream
       when the inbox is closed.
    
    Usage:
        inbox = MeshInboxImpl(node_id, mesh_id, transport, waiter_registry)
        
        async for envelope in inbox:
            # This only yields non-reply events
            # Replies are automatically routed to waiters
            await process(envelope.event)
            await envelope.ack()
        
        await inbox.close()
    
    Attributes:
        node_id: The node this inbox receives events for
        mesh_id: The mesh this inbox belongs to
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
            node_id: Node to receive events for
            mesh_id: Mesh this inbox belongs to
            transport: Transport backend for receiving events
            waiter_registry: Registry for resolving blocking waiters
        """
        self._node_id = node_id
        self._mesh_id = mesh_id
        self._transport = transport
        self._waiter_registry = waiter_registry
        
        # Stream state
        self._event_stream: Optional[AsyncIterator[EventEnvelope]] = None
        self._closed = False
        self._closing_lock = asyncio.Lock()
        
        logger.debug(f"MeshInboxImpl initialized: node_id={node_id}, mesh_id={mesh_id}")
    
    @property
    def node_id(self) -> NodeId:
        """The node this inbox receives events for."""
        return self._node_id
    
    @property
    def mesh_id(self) -> MeshId:
        """The mesh this inbox belongs to."""
        return self._mesh_id
    
    def __aiter__(self) -> AsyncIterator[EventEnvelope]:
        """Return self as async iterator."""
        return self
    
    async def __anext__(self) -> EventEnvelope:
        """
        Get the next event envelope.
        
        This method:
        1. Gets events from transport
        2. Intercepts reply events and routes to waiters
        3. Returns non-reply events to caller
        
        Reply events are ACKed automatically after routing to waiter.
        
        Returns:
            EventEnvelope containing the next non-reply event
        
        Raises:
            StopAsyncIteration: When inbox is closed
        """
        if self._closed:
            raise StopAsyncIteration
        
        # Lazily create event stream
        if self._event_stream is None:
            self._event_stream = self._transport.receive_events(self._node_id)
        
        # Loop until we get a non-reply event or stream ends
        while True:
            try:
                envelope = await self._event_stream.__anext__()
            except StopAsyncIteration:
                logger.debug(f"MeshInboxImpl: transport stream ended for {self._node_id}")
                raise
            
            event = envelope.event
            
            # Check if this is a reply event
            if event.is_reply():
                logger.debug(
                    f"MeshInboxImpl: intercepted reply event "
                    f"event_id={event.event_id} reply_to={event.reply_to}"
                )
                await self._handle_reply(envelope)
                # Continue to next event (don't yield replies)
                continue
            
            # Non-reply event - yield to caller
            logger.debug(
                f"MeshInboxImpl: yielding event_id={event.event_id}, "
                f"type={event.event_type}, from={event.source_id}"
            )
            return envelope
    
    async def _handle_reply(self, envelope: EventEnvelope) -> None:
        """
        Handle a reply event by routing to WaiterRegistry.
        
        Reply events are not passed to the node's event loop. Instead,
        they are routed to the WaiterRegistry which wakes up the
        corresponding send_blocking() call.
        
        Args:
            envelope: The reply event envelope
        """
        event = envelope.event
        
        # Route to waiter
        resolved = await self._waiter_registry.resolve(
            event_id=event.reply_to,  # The event being replied to
            subscriber_id=event.source_id,  # Who sent the reply
            payload=event.payload,
        )
        
        if not resolved:
            logger.warning(
                f"MeshInboxImpl: no waiter for reply event "
                f"reply_to={event.reply_to}, discarding"
            )
        
        # ACK the reply event since we've handled it
        await envelope.ack()
    
    async def close(self) -> None:
        """
        Close the inbox.
        
        After closing:
        - __anext__ will raise StopAsyncIteration
        - No more events will be delivered
        - Resources are released
        """
        async with self._closing_lock:
            if self._closed:
                return
            
            self._closed = True
            
            # Note: We don't need to explicitly close the transport stream
            # as it's just an async generator. The transport itself is
            # managed by MeshClient.
            
            logger.debug(f"MeshInboxImpl closed: node_id={self._node_id}")

