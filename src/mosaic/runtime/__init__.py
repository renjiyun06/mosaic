"""
Mosaic Runtime Module

This module provides the runtime infrastructure for the Mosaic event system.
It implements the core interfaces defined in mosaic.core.interfaces and
coordinates with the transport layer.

Key Components:
===============

MeshClient (client.py)
    Main entry point for nodes to interact with the mesh.
    Assembles inbox, outbox, and context into a unified interface.
    
    Example:
        client = await create_mesh_client(
            node_id="worker",
            mesh_id="dev",
            transport=sqlite_transport,
            subscription_repo=sub_repo,
        )
        
        async for envelope in client.inbox:
            await process(envelope.event)
            await envelope.ack()

MeshInbox (inbox.py)
    Event input channel with reply interception.
    Automatically routes reply events to WaiterRegistry.

MeshOutbox (outbox.py)
    Event output channel with blocking support.
    - send(): Fire-and-persist
    - send_blocking(): Wait for responses from blocking subscribers
    - reply(): Respond to a blocking event

MeshContext (context.py)
    Query interface for topology and event semantics.
    Used by agent nodes for prompt generation.

MeshAdmin (admin.py)
    Administrative interface for mesh configuration.
    Node and subscription management.

WaiterRegistry (waiter.py)
    Manages blocking waits for events.
    Used internally by MeshOutbox for send_blocking().

EventRouter (event_router.py)
    Routes events to subscribers based on subscription relationships.
    Implements sender-side dispatch pattern.

Dependency Relationships:
========================

    nodes (uses)
        ↓
    MeshClient (assembles)
        ├── MeshInbox ←── TransportBackend + WaiterRegistry
        ├── MeshOutbox ←── TransportBackend + EventRouter + WaiterRegistry
        └── MeshContext ←── SubscriptionRepository + CapabilityRepository
        
    EventRouter ←── SubscriptionRepository
    MeshAdmin ←── NodeRepository + SubscriptionRepository + CapabilityRepository

Usage:
======

Creating a client:
    from mosaic.runtime import create_mesh_client
    
    client = await create_mesh_client(
        node_id="my-node",
        mesh_id="my-mesh",
        transport=my_transport,
        subscription_repo=my_sub_repo,
    )

Using admin:
    from mosaic.runtime import MeshAdminImpl
    
    admin = MeshAdminImpl(
        mesh_id="my-mesh",
        node_repo=my_node_repo,
        subscription_repo=my_sub_repo,
    )
    await admin.create_node(node)
    await admin.subscribe(subscription)
"""

# Client - main entry point
from .client import (
    MeshClientImpl,
    create_mesh_client,
)

# Channels
from .inbox import MeshInboxImpl
from .outbox import MeshOutboxImpl

# Context and Admin
from .context import MeshContextImpl
from .admin import MeshAdminImpl

# Infrastructure
from .waiter import (
    EventWaiter,
    WaiterRegistry,
    WaiterResponse,
)
from .event_router import (
    EventRouter,
    RoutingResult,
)

# Repository Protocols (for dependency injection)
from .event_router import SubscriptionRepositoryProtocol
from .admin import (
    NodeRepositoryProtocol,
    SubscriptionRepositoryProtocol as AdminSubscriptionProtocol,
    CapabilityRepositoryProtocol,
)
from .context import (
    SubscriptionQueryProtocol,
    CapabilityQueryProtocol,
)


__all__ = [
    # Main client
    "MeshClientImpl",
    "create_mesh_client",
    
    # Channel implementations
    "MeshInboxImpl",
    "MeshOutboxImpl",
    
    # Context and Admin
    "MeshContextImpl",
    "MeshAdminImpl",
    
    # Infrastructure
    "EventWaiter",
    "WaiterRegistry",
    "WaiterResponse",
    "EventRouter",
    "RoutingResult",
    
    # Protocols (for type hints and dependency injection)
    "SubscriptionRepositoryProtocol",
    "NodeRepositoryProtocol",
    "CapabilityRepositoryProtocol",
    "SubscriptionQueryProtocol",
    "CapabilityQueryProtocol",
]

