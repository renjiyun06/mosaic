"""
Mosaic Storage - Repositories

This module exports all repository classes for the control plane.

Repositories provide data access for:
- Meshes: Network instances
- Nodes: Processing units in a mesh
- Subscriptions: Event flow relationships
- Capabilities: Event semantics declarations

Usage:
    from mosaic.storage.repositories import (
        MeshRepository,
        NodeRepository,
        SubscriptionRepository,
        CapabilityRepository,
    )
    
    # Create with database manager
    db = DatabaseManager()
    await db.initialize()
    
    mesh_repo = MeshRepository(db)
    node_repo = NodeRepository(db)
    sub_repo = SubscriptionRepository(db)
    cap_repo = CapabilityRepository(db)
"""

from .base import BaseRepository
from .mesh_repo import MeshRepository
from .node_repo import NodeRepository
from .subscription_repo import SubscriptionRepository
from .capability_repo import CapabilityRepository


__all__ = [
    "BaseRepository",
    "MeshRepository",
    "NodeRepository",
    "SubscriptionRepository",
    "CapabilityRepository",
]

