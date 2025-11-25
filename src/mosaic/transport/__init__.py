"""
Mosaic Transport Layer

This package provides pluggable event transport backends for the Mosaic
event system. Transport backends handle:
- Event persistence
- Event delivery to target nodes
- At-least-once delivery semantics
- Recovery from failures

Available Backends:
-------------------
- SQLite: File-based storage with UDS signaling (default, recommended for
          single-machine deployments and development)
- Kafka: Distributed message broker (future, for multi-machine deployments)
- Redis: In-memory with persistence (future, for low-latency requirements)

Usage:
------
    # Using SQLite backend (recommended)
    from mosaic.transport.sqlite import create_sqlite_transport
    
    backend = create_sqlite_transport(mesh_id="dev-mesh")
    await backend.initialize()
    
    # Send events
    await backend.send_event(event)
    
    # Receive events
    async for envelope in backend.receive_events("my-node"):
        process(envelope.event)
        await envelope.ack()

Integration with Runtime:
-------------------------
Transport backends are NOT used directly by nodes. Instead:
1. Runtime module creates a TransportBackend instance
2. Runtime wraps it with MeshClient/MeshInbox/MeshOutbox
3. Nodes use the runtime abstractions

This separation allows:
- Transport to focus on delivery mechanics
- Runtime to add routing, waiting, and aggregation
- Nodes to work with high-level abstractions
"""

from .base import (
    TransportBackend,
    TransportConfig,
)

__all__ = [
    # Base abstractions
    "TransportBackend",
    "TransportConfig",
]

