"""
Mosaic Storage Module

This module provides the control plane persistence layer for Mosaic.
It handles storage and retrieval of metadata: meshes, nodes, subscriptions,
and capabilities.

IMPORTANT: This module stores CONTROL PLANE data only.
Event data (DATA PLANE) is stored by the transport module.

Database Location:
- Control plane: ~/.mosaic/control.db
- Data plane: ~/.mosaic/<mesh_id>/events.db (managed by transport)

Key Components:
===============

DatabaseManager (database.py)
    Manages SQLite connections with WAL mode and schema initialization.
    
    Example:
        db = DatabaseManager()
        await db.initialize()
        
        async with db.connection() as conn:
            ...
        
        await db.close()

Repositories (repositories/)
    Data access layer using the Repository pattern.
    
    - MeshRepository: Mesh instances
    - NodeRepository: Node definitions
    - SubscriptionRepository: Event subscriptions
    - CapabilityRepository: Event semantics
    
    Example:
        mesh_repo = MeshRepository(db)
        node_repo = NodeRepository(db)
        
        await mesh_repo.create(Mesh(mesh_id="dev"))
        await node_repo.create(Node(mesh_id="dev", node_id="worker", ...))

Schema (schema.py)
    SQL schema definitions for the control plane.
    Schema versioning for migrations.

Usage Example:
==============

    from mosaic.storage import (
        DatabaseManager,
        MeshRepository,
        NodeRepository,
        SubscriptionRepository,
    )
    from mosaic.core.models import Mesh, Node, Subscription
    from mosaic.core.types import NodeType
    
    # Initialize database
    db = DatabaseManager()
    await db.initialize()
    
    # Create repositories
    mesh_repo = MeshRepository(db)
    node_repo = NodeRepository(db)
    sub_repo = SubscriptionRepository(db)
    
    # Create a mesh
    await mesh_repo.create(Mesh(mesh_id="dev"))
    
    # Create nodes
    await node_repo.create(Node(
        mesh_id="dev",
        node_id="worker",
        node_type=NodeType.CLAUDE_CODE,
        workspace="/path/to/workspace"
    ))
    
    await node_repo.create(Node(
        mesh_id="dev",
        node_id="auditor",
        node_type=NodeType.CLAUDE_CODE,
        workspace="/path/to/auditor"
    ))
    
    # Create subscription
    await sub_repo.create(Subscription(
        mesh_id="dev",
        source_id="auditor",
        target_id="worker",
        event_pattern="!PreToolUse"
    ))
    
    # Query
    nodes = await node_repo.list_by_mesh("dev")
    subs = await sub_repo.get_by_target("dev", "worker")
    
    # Cleanup
    await db.close()
"""

# Database management
from .database import (
    DatabaseManager,
    get_database,
    close_database,
    get_default_db_path,
)

# Schema
from .schema import (
    SCHEMA_VERSION,
    get_full_schema,
    get_table_names,
)

# Repositories
from .repositories import (
    BaseRepository,
    MeshRepository,
    NodeRepository,
    SubscriptionRepository,
    CapabilityRepository,
)


__all__ = [
    # Database
    "DatabaseManager",
    "get_database",
    "close_database",
    "get_default_db_path",
    
    # Schema
    "SCHEMA_VERSION",
    "get_full_schema",
    "get_table_names",
    
    # Repositories
    "BaseRepository",
    "MeshRepository",
    "NodeRepository",
    "SubscriptionRepository",
    "CapabilityRepository",
]

