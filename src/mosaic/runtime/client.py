"""
Mosaic Runtime - MeshClient Implementation

This module implements MeshClient, the main entry point for nodes to interact
with the Mosaic mesh. MeshClient is an ASSEMBLER that combines lower-level
components (transport, waiter, router) into a unified interface.

Key Responsibilities:
1. Assemble inbox, outbox, and context components
2. Manage connection lifecycle
3. Provide unified interface for nodes

Design Notes:
- MeshClient is the ONLY interface nodes should use
- All complexity (transport, routing, waiting) is hidden behind this interface
- Dependencies are injected via constructor for testability
"""

import logging
from typing import Optional

from mosaic.core.interfaces import MeshClient, MeshInbox, MeshOutbox, MeshContext
from mosaic.core.types import NodeId, MeshId
from mosaic.transport.base import TransportBackend

from .waiter import WaiterRegistry
from .event_router import EventRouter, SubscriptionRepositoryProtocol
from .inbox import MeshInboxImpl
from .outbox import MeshOutboxImpl
from .context import (
    MeshContextImpl,
    SubscriptionQueryProtocol,
    CapabilityQueryProtocol,
)


logger = logging.getLogger(__name__)


class MeshClientImpl(MeshClient):
    """
    Implementation of MeshClient interface.
    
    MeshClientImpl is the main entry point for nodes to interact with the
    Mosaic mesh. It assembles and coordinates lower-level components:
    
    - TransportBackend: Event persistence and delivery
    - WaiterRegistry: Blocking wait management
    - EventRouter: Subscription-based routing
    - MeshInbox: Event input channel
    - MeshOutbox: Event output channel
    - MeshContext: Topology and semantics queries
    
    Lifecycle:
    1. Create: MeshClientImpl is instantiated with dependencies
    2. Connect: connect() initializes transport and starts inbox
    3. Use: Node uses inbox/outbox/context for event handling
    4. Disconnect: disconnect() releases all resources
    
    Usage:
        # Create client with dependencies
        client = MeshClientImpl(
            node_id="worker",
            mesh_id="dev",
            transport=sqlite_transport,
            subscription_repo=sub_repo,
            capability_repo=cap_repo,
        )
        
        # Connect and use
        await client.connect()
        
        try:
            async for envelope in client.inbox:
                await process(envelope.event)
                await envelope.ack()
        finally:
            await client.disconnect()
    
    Attributes:
        node_id: This node's identifier
        mesh_id: The mesh this client belongs to
        inbox: Event input channel
        outbox: Event output channel
        context: Topology and semantics queries
    """
    
    def __init__(
        self,
        node_id: NodeId,
        mesh_id: MeshId,
        transport: TransportBackend,
        subscription_repo: SubscriptionRepositoryProtocol,
        capability_repo: Optional[CapabilityQueryProtocol] = None,
    ) -> None:
        """
        Initialize the MeshClient.
        
        This constructor creates all internal components but does NOT
        connect to the transport. Call connect() to establish connections.
        
        Args:
            node_id: This node's identifier
            mesh_id: The mesh to connect to
            transport: Transport backend for event delivery
            subscription_repo: Repository for subscription queries
            capability_repo: Repository for capability queries (optional)
        """
        self._node_id = node_id
        self._mesh_id = mesh_id
        self._transport = transport
        self._subscription_repo = subscription_repo
        self._capability_repo = capability_repo
        
        # Connection state
        self._connected = False
        
        # Create shared components
        self._waiter_registry = WaiterRegistry()
        self._router = EventRouter(mesh_id, subscription_repo)
        
        # Create channel components (but don't activate until connect)
        self._inbox: Optional[MeshInboxImpl] = None
        self._outbox: Optional[MeshOutboxImpl] = None
        self._context: Optional[MeshContextImpl] = None
        
        logger.debug(
            f"MeshClientImpl created: node_id={node_id}, mesh_id={mesh_id}"
        )
    
    @property
    def node_id(self) -> NodeId:
        """This node's identifier."""
        return self._node_id
    
    @property
    def mesh_id(self) -> MeshId:
        """The mesh this client belongs to."""
        return self._mesh_id
    
    @property
    def inbox(self) -> MeshInbox:
        """
        Event input channel.
        
        Raises:
            RuntimeError: If client is not connected
        """
        if not self._connected or self._inbox is None:
            raise RuntimeError("MeshClient not connected. Call connect() first.")
        return self._inbox
    
    @property
    def outbox(self) -> MeshOutbox:
        """
        Event output channel.
        
        Raises:
            RuntimeError: If client is not connected
        """
        if not self._connected or self._outbox is None:
            raise RuntimeError("MeshClient not connected. Call connect() first.")
        return self._outbox
    
    @property
    def context(self) -> MeshContext:
        """
        Topology and semantics queries.
        
        Raises:
            RuntimeError: If client is not connected
        """
        if not self._connected or self._context is None:
            raise RuntimeError("MeshClient not connected. Call connect() first.")
        return self._context
    
    async def connect(self) -> None:
        """
        Connect to the mesh.
        
        This initializes the transport and creates all channel components.
        After connect(), inbox/outbox/context are ready for use.
        
        Raises:
            TransportConnectionError: If connection fails
            RuntimeError: If already connected
        """
        if self._connected:
            raise RuntimeError("MeshClient already connected")
        
        logger.info(f"MeshClient connecting: node_id={self._node_id}")
        
        # Initialize transport
        await self._transport.initialize()
        
        # Create inbox
        self._inbox = MeshInboxImpl(
            node_id=self._node_id,
            mesh_id=self._mesh_id,
            transport=self._transport,
            waiter_registry=self._waiter_registry,
        )
        
        # Create outbox
        self._outbox = MeshOutboxImpl(
            node_id=self._node_id,
            mesh_id=self._mesh_id,
            transport=self._transport,
            router=self._router,
            waiter_registry=self._waiter_registry,
        )
        
        # Create context
        # Note: subscription_repo satisfies both SubscriptionRepositoryProtocol
        # (for router) and SubscriptionQueryProtocol (for context) because
        # both protocols define the same methods
        self._context = MeshContextImpl(
            node_id=self._node_id,
            mesh_id=self._mesh_id,
            subscription_repo=self._subscription_repo,  # type: ignore
            capability_repo=self._capability_repo,
        )
        
        self._connected = True
        
        logger.info(f"MeshClient connected: node_id={self._node_id}")
    
    async def disconnect(self) -> None:
        """
        Disconnect from the mesh.
        
        This releases all resources and closes connections.
        After disconnect(), the client cannot be used.
        """
        if not self._connected:
            logger.debug("MeshClient.disconnect: already disconnected")
            return
        
        logger.info(f"MeshClient disconnecting: node_id={self._node_id}")
        
        # Close inbox
        if self._inbox is not None:
            await self._inbox.close()
            self._inbox = None
        
        # Reject all pending waiters
        from mosaic.core.exceptions import TransportUnavailableError
        await self._waiter_registry.reject_all(
            TransportUnavailableError("Client disconnected")
        )
        
        # Close transport
        await self._transport.close()
        
        # Clear references
        self._outbox = None
        self._context = None
        self._connected = False
        
        logger.info(f"MeshClient disconnected: node_id={self._node_id}")
    
    def is_connected(self) -> bool:
        """Check if the client is connected."""
        return self._connected
    
    # =========================================================================
    # Additional Helper Methods
    # =========================================================================
    
    @property
    def waiter_registry(self) -> WaiterRegistry:
        """
        Access to the internal waiter registry.
        
        This is primarily for testing and debugging. Normal node code
        should not need direct access.
        """
        return self._waiter_registry
    
    @property
    def router(self) -> EventRouter:
        """
        Access to the internal event router.
        
        This is primarily for testing and debugging.
        """
        return self._router
    
    async def get_pending_events_count(self) -> int:
        """
        Get the number of pending events for this node.
        
        Useful for monitoring and load balancing decisions.
        
        Returns:
            Number of events waiting to be processed
        """
        return await self._transport.get_pending_count(self._node_id)


# =============================================================================
# Factory Function
# =============================================================================

async def create_mesh_client(
    node_id: NodeId,
    mesh_id: MeshId,
    transport: TransportBackend,
    subscription_repo: SubscriptionRepositoryProtocol,
    capability_repo: Optional[CapabilityQueryProtocol] = None,
    auto_connect: bool = True,
) -> MeshClientImpl:
    """
    Factory function to create and optionally connect a MeshClient.
    
    This is the recommended way to create MeshClient instances.
    
    Args:
        node_id: This node's identifier
        mesh_id: The mesh to connect to
        transport: Transport backend for event delivery
        subscription_repo: Repository for subscription queries
        capability_repo: Repository for capability queries (optional)
        auto_connect: If True, connect before returning
    
    Returns:
        Configured MeshClientImpl instance
    
    Example:
        client = await create_mesh_client(
            node_id="worker",
            mesh_id="dev",
            transport=SQLiteTransportBackend(...),
            subscription_repo=SubscriptionRepository(...),
        )
        
        # Client is already connected, ready to use
        async for envelope in client.inbox:
            ...
    """
    client = MeshClientImpl(
        node_id=node_id,
        mesh_id=mesh_id,
        transport=transport,
        subscription_repo=subscription_repo,
        capability_repo=capability_repo,
    )
    
    if auto_connect:
        await client.connect()
    
    return client

