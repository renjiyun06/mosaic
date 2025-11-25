"""
SQLite Transport Backend for Mosaic

This package provides SQLite-based event transport with UDS signaling.

Features:
---------
- SQLite with WAL mode for event persistence
- Unix Domain Sockets for low-latency signaling
- At-least-once delivery semantics
- Recovery window for crash handling

Usage:
------
    from mosaic.transport.sqlite import (
        SQLiteTransportBackend,
        create_sqlite_transport,
    )
    
    # Using factory function (recommended)
    backend = create_sqlite_transport(mesh_id="dev-mesh")
    await backend.initialize()
    
    # Or using class directly
    from mosaic.transport.base import TransportConfig
    config = TransportConfig(mesh_id="dev-mesh")
    backend = SQLiteTransportBackend(config)
    await backend.initialize()

Internal Components:
--------------------
The following are internal implementation details and should NOT
be used directly by other modules:
- EventDatabase: SQLite database management
- EventRepository: Event CRUD operations
- SignalListener/SignalClient: UDS signaling
- SQLiteEventEnvelope: Envelope implementation
"""

from .backend import SQLiteTransportBackend, create_sqlite_transport

__all__ = [
    "SQLiteTransportBackend",
    "create_sqlite_transport",
]

