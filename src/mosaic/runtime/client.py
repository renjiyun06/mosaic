"""
Mosaic Runtime - MeshClient Implementation

This module provides the MeshClient implementation that assembles all
runtime components into a unified interface for nodes.

MeshClient is the main entry point for nodes to interact with the
Mosaic event system. It combines:
- MeshInbox: For receiving events
- MeshOutbox: For sending events
- MeshContext: For topology and semantics queries

Architecture:
=============

    ┌─────────────────────────────────────────────────────────────────┐
    │                        MeshClientImpl                           │
    │                                                                 │
    │  ┌──────────────────────────────────────────────────────────┐   │
    │  │                    Shared Components                      │   │
    │  │                                                          │   │
    │  │  ┌────────────────┐  ┌────────────────┐                  │   │
    │  │  │ WaiterRegistry │  │  EventRouter   │                  │   │
    │  │  └────────────────┘  └────────────────┘                  │   │
    │  └──────────────────────────────────────────────────────────┘   │
    │                                                                 │
    │  ┌────────────────────────────────────────────────────────────┐ │
    │  │                      User-Facing APIs                       │ │
    │  │                                                            │ │
    │  │  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐ │ │
    │  │  │   Inbox      │  │   Outbox     │  │     Context       │ │ │
    │  │  │ (receive)    │  │  (send)      │  │  (query)          │ │ │
    │  │  └──────────────┘  └──────────────┘  └───────────────────┘ │ │
    │  └────────────────────────────────────────────────────────────┘ │
    │                                                                 │
    │  ┌────────────────────────────────────────────────────────────┐ │
    │  │                   External Dependencies                     │ │
    │  │                                                            │ │
    │  │  ┌────────────────┐  ┌────────────────────────────────────┐ │ │
    │  │  │ Transport      │  │      Storage Repositories          │ │ │
    │  │  │ Backend        │  │  (Subscription, Node, Capability)  │ │ │
    │  │  └────────────────┘  └────────────────────────────────────┘ │ │
    │  └────────────────────────────────────────────────────────────┘ │
    └─────────────────────────────────────────────────────────────────┘

Lifecycle:
==========

    1. Create: MeshClientImpl is created with dependencies
    2. Connect: connect() initializes all components
    3. Use: Node uses inbox/outbox/context for event handling
    4. Disconnect: disconnect() releases resources

    client = await create_mesh_client(mesh_id="dev", node_id="worker")
    await client.connect()
    
    try:
        async for envelope in client.inbox:
            await process(envelope.event)
            await envelope.ack()
    finally:
        await client.disconnect()

Factory Function:
=================

The recommended way to create a MeshClient is via the factory function:

    client = await create_mesh_client(
        mesh_id="dev",
        node_id="worker",
        transport=sqlite_transport,  # Optional: uses default SQLite
        storage_db=database_manager,  # Optional: uses default DB
    )

This handles all the dependency injection and component wiring.
"""

import logging
from typing import Optional

from mosaic.core.interfaces import MeshClient, MeshInbox, MeshOutbox, MeshContext
from mosaic.core.types import NodeId, MeshId
from mosaic.core.exceptions import TransportConnectionError

from mosaic.transport import TransportBackend
from mosaic.transport.sqlite import create_sqlite_transport
from mosaic.storage import (
    DatabaseManager,
    get_database,
    NodeRepository,
    SubscriptionRepository,
    CapabilityRepository,
)

from .waiter import WaiterRegistry
from .event_router import EventRouter
from .inbox import MeshInboxImpl
from .outbox import MeshOutboxImpl
from .context import MeshContextImpl


logger = logging.getLogger(__name__)


class MeshClientImpl(MeshClient):
    """
    Implementation of MeshClient that assembles all runtime components.
    
    MeshClientImpl is the main entry point for nodes to interact with
    the Mosaic event system. It provides:
    - inbox: For receiving events (with automatic reply handling)
    - outbox: For sending events (with blocking support)
    - context: For topology and semantics queries
    
    Usage:
        client = MeshClientImpl(
            node_id="worker",
            mesh_id="dev",
            transport=transport_backend,
            subscription_repo=sub_repo,
            capability_repo=cap_repo,
        )
        await client.connect()
        
        try:
            async for envelope in client.inbox:
                event = envelope.event
                await process(event)
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
        subscription_repo: SubscriptionRepository,
        capability_repo: CapabilityRepository,
    ) -> None:
        """
        Initialize the client.
        
        Note: This creates the client but does not connect it.
        Call connect() before using inbox/outbox.
        
        Args:
            node_id: This node's identifier
            mesh_id: The mesh this client belongs to
            transport: Transport backend for event delivery
            subscription_repo: Repository for subscription queries
            capability_repo: Repository for capability queries
        """
        self._node_id = node_id
        self._mesh_id = mesh_id
        self._transport = transport
        self._subscription_repo = subscription_repo
        self._capability_repo = capability_repo
        
        # Shared components (created on connect)
        self._waiter_registry: Optional[WaiterRegistry] = None
        self._router: Optional[EventRouter] = None
        
        # User-facing components (created on connect)
        self._inbox: Optional[MeshInboxImpl] = None
        self._outbox: Optional[MeshOutboxImpl] = None
        self._context: Optional[MeshContextImpl] = None
        
        self._connected = False
        
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
        """Event input channel."""
        if self._inbox is None:
            raise RuntimeError("Client not connected. Call connect() first.")
        return self._inbox
    
    @property
    def outbox(self) -> MeshOutbox:
        """Event output channel."""
        if self._outbox is None:
            raise RuntimeError("Client not connected. Call connect() first.")
        return self._outbox
    
    @property
    def context(self) -> MeshContext:
        """Topology and semantics queries."""
        if self._context is None:
            raise RuntimeError("Client not connected. Call connect() first.")
        return self._context
    
    async def connect(self) -> None:
        """
        Connect to the mesh.
        
        This initializes all components and prepares the client
        for event handling.
        
        Raises:
            TransportConnectionError: If connection fails
        """
        if self._connected:
            logger.debug(f"Client {self._node_id} already connected")
            return
        
        logger.info(f"Connecting client: {self._node_id}")
        
        try:
            # Initialize transport if needed
            await self._transport.initialize()
            
            # Create shared components
            self._waiter_registry = WaiterRegistry()
            
            self._router = EventRouter(
                mesh_id=self._mesh_id,
                subscription_repo=self._subscription_repo,
                transport=self._transport,
            )
            
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
            self._context = MeshContextImpl(
                node_id=self._node_id,
                mesh_id=self._mesh_id,
                subscription_repo=self._subscription_repo,
                capability_repo=self._capability_repo,
            )
            
            self._connected = True
            
            logger.info(f"Client connected: {self._node_id}")
        
        except Exception as e:
            logger.error(f"Failed to connect client {self._node_id}: {e}")
            raise TransportConnectionError(
                transport_type="mesh",
                reason=str(e),
            ) from e
    
    async def disconnect(self) -> None:
        """
        Disconnect from the mesh.
        
        This releases transport resources and closes channels.
        After disconnect, the client cannot be used.
        """
        if not self._connected:
            return
        
        logger.info(f"Disconnecting client: {self._node_id}")
        
        # Close inbox
        if self._inbox is not None:
            await self._inbox.close()
        
        # Clear any pending waiters
        if self._waiter_registry is not None:
            await self._waiter_registry.clear()
        
        # Note: We don't close the transport here because it may be shared
        # The transport should be closed by whoever created it
        
        self._inbox = None
        self._outbox = None
        self._context = None
        self._router = None
        self._waiter_registry = None
        self._connected = False
        
        logger.info(f"Client disconnected: {self._node_id}")
    
    def is_connected(self) -> bool:
        """Check if the client is connected."""
        return self._connected
    
    # =========================================================================
    # Context Manager Protocol
    # =========================================================================
    
    async def __aenter__(self) -> "MeshClientImpl":
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()


# =============================================================================
# Factory Function
# =============================================================================

async def create_mesh_client(
    mesh_id: MeshId,
    node_id: NodeId,
    transport: Optional[TransportBackend] = None,
    storage_db: Optional[DatabaseManager] = None,
    auto_connect: bool = True,
) -> MeshClientImpl:
    """
    Factory function to create a configured MeshClient.
    
    This is the recommended way to create a MeshClient. It handles
    all dependency injection and component wiring.
    
    Args:
        mesh_id: The mesh to connect to
        node_id: This node's identifier
        transport: Transport backend (default: creates SQLite transport)
        storage_db: Storage database manager (default: uses global DB)
        auto_connect: If True, connect() is called automatically
    
    Returns:
        Configured MeshClientImpl (connected if auto_connect=True)
    
    Example:
        # Simple usage with defaults
        client = await create_mesh_client(mesh_id="dev", node_id="worker")
        
        try:
            async for envelope in client.inbox:
                await process(envelope.event)
                await envelope.ack()
        finally:
            await client.disconnect()
        
        # Or with context manager
        async with await create_mesh_client("dev", "worker") as client:
            async for envelope in client.inbox:
                ...
    """
    logger.debug(
        f"Creating mesh client: mesh_id={mesh_id}, node_id={node_id}"
    )
    
    # Get or create transport
    if transport is None:
        transport = create_sqlite_transport(mesh_id)
    
    # Get or create storage DB
    if storage_db is None:
        storage_db = await get_database()
    
    # Create repositories
    subscription_repo = SubscriptionRepository(storage_db)
    capability_repo = CapabilityRepository(storage_db)
    
    # Create client
    client = MeshClientImpl(
        node_id=node_id,
        mesh_id=mesh_id,
        transport=transport,
        subscription_repo=subscription_repo,
        capability_repo=capability_repo,
    )
    
    # Auto-connect if requested
    if auto_connect:
        await client.connect()
    
    return client

