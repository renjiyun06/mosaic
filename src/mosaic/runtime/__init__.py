"""
Mosaic Runtime Module

This module provides the runtime infrastructure that bridges the transport
layer and nodes. It implements the core Mosaic interfaces defined in
mosaic.core.interfaces.

Module Responsibilities:
========================

The runtime module is responsible for:
1. Implementing MeshClient, MeshInbox, MeshOutbox, MeshContext, MeshAdmin
2. Providing the blocking wait mechanism (WaiterRegistry)
3. Routing events based on subscriptions (EventRouter)
4. Assembling components for node usage (create_mesh_client)

Architecture Position:
======================

    ┌──────────────────────────────────────────────────────────────────┐
    │                            nodes                                  │
    │               (CC, Scheduler, Webhook implementations)           │
    └────────────────────────────────┬─────────────────────────────────┘
                                     │ uses
                                     ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │                           runtime                                 │
    │                                                                   │
    │  ┌────────────────┐  ┌───────────────┐  ┌──────────────────────┐ │
    │  │  MeshClient    │  │ WaiterRegistry │  │    EventRouter      │ │
    │  │  (assembler)   │  │  (blocking)    │  │    (routing)        │ │
    │  └────────────────┘  └───────────────┘  └──────────────────────┘ │
    │  ┌────────────────┐  ┌───────────────┐  ┌──────────────────────┐ │
    │  │   MeshInbox    │  │   MeshOutbox  │  │    MeshContext       │ │
    │  │   MeshAdmin    │  │               │  │                      │ │
    │  └────────────────┘  └───────────────┘  └──────────────────────┘ │
    └────────────────────────────────┬─────────────────────────────────┘
                                     │ uses
                                     ▼
    ┌─────────────────────────────────┬────────────────────────────────┐
    │           transport              │           storage             │
    │    (event delivery)              │    (control plane data)       │
    └─────────────────────────────────┴────────────────────────────────┘

Key Components:
===============

WaiterRegistry (waiter.py):
    Manages blocking wait points for send_blocking() semantics.
    - EventWaiter: Individual wait point (asyncio.Future based)
    - MultiSubscriberWaiter: Aggregates responses from multiple subscribers
    - WaiterRegistry: Global registry for waiter lookup

EventRouter (event_router.py):
    Routes events based on subscription relationships.
    - Queries SubscriptionRepository
    - Creates event copies for each subscriber
    - Identifies blocking vs non-blocking subscribers

MeshInboxImpl (inbox.py):
    Wraps transport receive_events() with reply handling.
    - Automatically resolves waiters when replies arrive
    - Filters reply events from consumer iteration

MeshOutboxImpl (outbox.py):
    Combines routing with blocking support.
    - send(): Fire-and-persist routing
    - send_blocking(): Route + wait + aggregate
    - reply(): Direct reply to sender

MeshContextImpl (context.py):
    Provides topology and semantics queries.
    - Subscription relationships
    - Event type semantics
    - Topology prompt generation

MeshAdminImpl (admin.py):
    Administrative operations for mesh configuration.
    - Node CRUD
    - Subscription management
    - Capability registration

MeshClientImpl (client.py):
    Assembles all components into unified interface.
    - Factory: create_mesh_client()
    - Properties: inbox, outbox, context
    - Lifecycle: connect(), disconnect()

Usage:
======

    from mosaic.runtime import create_mesh_client
    
    # Create and connect client
    client = await create_mesh_client(mesh_id="dev", node_id="worker")
    
    try:
        # Receive events
        async for envelope in client.inbox:
            event = envelope.event
            
            # Process event
            if event.event_type == "PreToolUse":
                decision = await analyze_tool_use(event)
                await client.outbox.reply(event.event_id, decision)
            
            await envelope.ack()
    finally:
        await client.disconnect()

Dependency Injection:
=====================

Runtime components use dependency injection for flexibility:

    # Custom transport
    from mosaic.transport.kafka import create_kafka_transport
    transport = create_kafka_transport(...)
    client = await create_mesh_client(
        mesh_id="prod",
        node_id="worker",
        transport=transport,
    )

For most use cases, the factory function with defaults is sufficient.
"""

# Waiter components
from .waiter import (
    EventWaiter,
    MultiSubscriberWaiter,
    WaiterRegistry,
    WaiterState,
)

# Event routing
from .event_router import (
    EventRouter,
    RoutingResult,
)

# Core interfaces implementation
from .inbox import (
    MeshInboxImpl,
    FilteredInbox,
)

from .outbox import (
    MeshOutboxImpl,
)

from .context import (
    MeshContextImpl,
)

from .admin import (
    MeshAdminImpl,
)

from .client import (
    MeshClientImpl,
    create_mesh_client,
)


__all__ = [
    # Waiter components
    "EventWaiter",
    "MultiSubscriberWaiter",
    "WaiterRegistry",
    "WaiterState",
    
    # Event routing
    "EventRouter",
    "RoutingResult",
    
    # Core interface implementations
    "MeshInboxImpl",
    "FilteredInbox",
    "MeshOutboxImpl",
    "MeshContextImpl",
    "MeshAdminImpl",
    "MeshClientImpl",
    
    # Factory function (main entry point)
    "create_mesh_client",
]

