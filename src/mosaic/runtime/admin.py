"""
Mosaic Runtime - MeshAdmin Implementation

This module provides the MeshAdmin implementation for mesh configuration
and management operations.

MeshAdmin is part of the "Control Plane" - it handles:
1. Node creation and deletion
2. Subscription management
3. Capability registration

Architecture:
=============

    ┌─────────────────────────────────────────────────────────────────┐
    │                         MeshAdminImpl                           │
    │                                                                 │
    │  ┌──────────────────────┐  ┌──────────────────────────────────┐ │
    │  │   Node Management    │  │   Subscription Management        │ │
    │  │                      │  │                                  │ │
    │  │  - create_node()     │  │  - subscribe()                   │ │
    │  │  - delete_node()     │  │  - unsubscribe()                 │ │
    │  │  - get_node()        │  │  - get_subscriptions_by_*()      │ │
    │  │  - list_nodes()      │  │                                  │ │
    │  └──────────────────────┘  └──────────────────────────────────┘ │
    │              │                              │                   │
    │              ▼                              ▼                   │
    │  ┌──────────────────────┐   ┌────────────────────────────────┐  │
    │  │    NodeRepository    │   │   SubscriptionRepository       │  │
    │  └──────────────────────┘   └────────────────────────────────┘  │
    │                                                                 │
    │  ┌──────────────────────────────────────────────────────────┐   │
    │  │              Capability Registration                     │   │
    │  │  - register_capabilities()                               │   │
    │  │  - get_capabilities()                                    │   │
    │  └──────────────────────────────────────────────────────────┘   │
    │                              │                                  │
    │                              ▼                                  │
    │  ┌──────────────────────────────────────────────────────────┐   │
    │  │                 CapabilityRepository                     │   │
    │  └──────────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────────┘

Usage:
======

    admin = MeshAdminImpl(
        mesh_id="dev",
        node_repo=node_repo,
        subscription_repo=sub_repo,
        capability_repo=cap_repo,
    )
    
    # Create nodes
    await admin.create_node(Node(
        mesh_id="dev",
        node_id="worker",
        node_type=NodeType.CLAUDE_CODE,
        workspace="/path/to/workspace"
    ))
    
    # Create subscriptions
    await admin.subscribe(Subscription(
        mesh_id="dev",
        source_id="auditor",
        target_id="worker",
        event_pattern="!PreToolUse"
    ))
    
    # Query
    nodes = await admin.list_nodes()
    subs = await admin.get_subscriptions_by_target("worker")

Design Principles:
==================
1. MeshAdmin only modifies control plane data
2. Does not start/stop node processes (that's Daemon's job)
3. Validates node existence before creating subscriptions
4. Cascading delete: node deletion removes related subscriptions
"""

import logging
from typing import Optional

from mosaic.core.interfaces import MeshAdmin
from mosaic.core.models import Node, Subscription, NodeCapabilities
from mosaic.core.types import NodeId, MeshId, NodeType
from mosaic.core.exceptions import (
    NodeNotFoundError,
    NodeAlreadyExistsError,
    SubscriptionNotFoundError,
)

from mosaic.storage import (
    NodeRepository,
    SubscriptionRepository,
    CapabilityRepository,
)


logger = logging.getLogger(__name__)


class MeshAdminImpl(MeshAdmin):
    """
    Implementation of MeshAdmin for mesh configuration.
    
    MeshAdminImpl provides administrative operations for managing
    the mesh network configuration. It operates on the control plane
    database through the repository pattern.
    
    Usage:
        admin = MeshAdminImpl(
            mesh_id="dev",
            node_repo=node_repo,
            subscription_repo=sub_repo,
            capability_repo=cap_repo,
        )
        
        # Create a node
        await admin.create_node(Node(...))
        
        # Create a subscription
        await admin.subscribe(Subscription(...))
    
    Validation:
        - Subscriptions require both source and target nodes to exist
        - Node deletion cascades to subscription deletion
        - Duplicate subscriptions are rejected
    
    Attributes:
        mesh_id: The mesh this admin manages
    """
    
    def __init__(
        self,
        mesh_id: MeshId,
        node_repo: NodeRepository,
        subscription_repo: SubscriptionRepository,
        capability_repo: CapabilityRepository,
    ) -> None:
        """
        Initialize the admin.
        
        Args:
            mesh_id: The mesh this admin manages
            node_repo: Repository for node operations
            subscription_repo: Repository for subscription operations
            capability_repo: Repository for capability operations
        """
        self._mesh_id = mesh_id
        self._node_repo = node_repo
        self._subscription_repo = subscription_repo
        self._capability_repo = capability_repo
        
        logger.debug(f"MeshAdminImpl created for mesh {mesh_id}")
    
    @property
    def mesh_id(self) -> MeshId:
        """The mesh this admin manages."""
        return self._mesh_id
    
    # =========================================================================
    # Node Management
    # =========================================================================
    
    async def create_node(self, node: Node) -> None:
        """
        Create a new node in the mesh.
        
        Args:
            node: Node definition (mesh_id must match admin's mesh_id)
        
        Raises:
            NodeAlreadyExistsError: If node_id already exists
            ValueError: If mesh_id doesn't match
        """
        # Validate mesh_id
        if node.mesh_id != self._mesh_id:
            raise ValueError(
                f"Node mesh_id ({node.mesh_id}) doesn't match "
                f"admin mesh_id ({self._mesh_id})"
            )
        
        await self._node_repo.create(node)
        
        logger.info(
            f"Node created: {node.node_id} "
            f"(type={node.node_type}, workspace={node.workspace})"
        )
    
    async def get_node(self, node_id: NodeId) -> Optional[Node]:
        """
        Get a node by ID.
        
        Args:
            node_id: The node to look up
        
        Returns:
            Node if found, None otherwise
        """
        return await self._node_repo.get(self._mesh_id, node_id)
    
    async def delete_node(self, node_id: NodeId) -> None:
        """
        Delete a node from the mesh.
        
        This also deletes all subscriptions involving this node
        (where node is either source or target).
        
        Args:
            node_id: The node to delete
        
        Raises:
            NodeNotFoundError: If node doesn't exist
        """
        # Check node exists
        node = await self.get_node(node_id)
        if node is None:
            raise NodeNotFoundError(node_id, self._mesh_id)
        
        # Delete subscriptions involving this node
        deleted_subs = await self._subscription_repo.delete_by_node(
            mesh_id=self._mesh_id,
            node_id=node_id,
        )
        
        # Delete the node
        await self._node_repo.delete(self._mesh_id, node_id)
        
        logger.info(
            f"Node deleted: {node_id} "
            f"(also deleted {deleted_subs} subscriptions)"
        )
    
    async def list_nodes(self) -> list[Node]:
        """
        List all nodes in the mesh.
        
        Returns:
            List of all nodes
        """
        return await self._node_repo.list_by_mesh(self._mesh_id)
    
    async def update_node(self, node: Node) -> None:
        """
        Update an existing node.
        
        Args:
            node: Updated node definition
        
        Raises:
            NodeNotFoundError: If node doesn't exist
        """
        existing = await self.get_node(node.node_id)
        if existing is None:
            raise NodeNotFoundError(node.node_id, self._mesh_id)
        
        await self._node_repo.update(node)
        
        logger.info(f"Node updated: {node.node_id}")
    
    # =========================================================================
    # Subscription Management
    # =========================================================================
    
    async def subscribe(self, subscription: Subscription) -> None:
        """
        Create a subscription.
        
        Validates that both source and target nodes exist before creating.
        
        Args:
            subscription: Subscription definition
        
        Raises:
            SubscriptionAlreadyExistsError: If subscription exists
            NodeNotFoundError: If source or target node doesn't exist
        """
        # Validate mesh_id
        if subscription.mesh_id != self._mesh_id:
            raise ValueError(
                f"Subscription mesh_id ({subscription.mesh_id}) doesn't match "
                f"admin mesh_id ({self._mesh_id})"
            )
        
        # Validate source node exists
        source = await self.get_node(subscription.source_id)
        if source is None:
            raise NodeNotFoundError(subscription.source_id, self._mesh_id)
        
        # Validate target node exists
        target = await self.get_node(subscription.target_id)
        if target is None:
            raise NodeNotFoundError(subscription.target_id, self._mesh_id)
        
        await self._subscription_repo.create(subscription)
        
        logger.info(
            f"Subscription created: {subscription.source_id} -> "
            f"{subscription.target_id} [{subscription.event_pattern}]"
        )
    
    async def unsubscribe(
        self,
        source_id: NodeId,
        target_id: NodeId,
        event_pattern: str,
    ) -> None:
        """
        Remove a subscription.
        
        Args:
            source_id: Subscribing node
            target_id: Subscribed node
            event_pattern: Event pattern to unsubscribe
        
        Raises:
            SubscriptionNotFoundError: If subscription doesn't exist
        """
        await self._subscription_repo.delete(
            mesh_id=self._mesh_id,
            source_id=source_id,
            target_id=target_id,
            event_pattern=event_pattern,
        )
        
        logger.info(
            f"Subscription removed: {source_id} -> {target_id} [{event_pattern}]"
        )
    
    async def get_subscriptions_by_source(
        self,
        source_id: NodeId,
    ) -> list[Subscription]:
        """
        Get all subscriptions where node is the subscriber.
        
        This answers: "What does this node subscribe to?"
        
        Args:
            source_id: The subscribing node
        
        Returns:
            List of subscriptions where source_id is the subscriber
        """
        return await self._subscription_repo.get_by_source(
            mesh_id=self._mesh_id,
            source_id=source_id,
        )
    
    async def get_subscriptions_by_target(
        self,
        target_id: NodeId,
    ) -> list[Subscription]:
        """
        Get all subscriptions where node is being subscribed to.
        
        This answers: "Who subscribes to this node?"
        
        Args:
            target_id: The node being subscribed to
        
        Returns:
            List of subscriptions where target_id is the subscribed node
        """
        return await self._subscription_repo.get_by_target(
            mesh_id=self._mesh_id,
            target_id=target_id,
        )
    
    async def list_subscriptions(self) -> list[Subscription]:
        """
        List all subscriptions in the mesh.
        
        Returns:
            List of all subscriptions
        """
        return await self._subscription_repo.list_by_mesh(self._mesh_id)
    
    # =========================================================================
    # Capability Registration
    # =========================================================================
    
    async def register_capabilities(
        self,
        capabilities: NodeCapabilities,
    ) -> None:
        """
        Register node type capabilities.
        
        This declares what events a node type can produce or consume,
        along with semantic descriptions for agent prompts.
        
        Args:
            capabilities: Capability declaration
        """
        await self._capability_repo.register(self._mesh_id, capabilities)
        
        logger.info(
            f"Capabilities registered for node type: {capabilities.node_type}"
        )
    
    async def get_capabilities(
        self,
        node_type: NodeType,
    ) -> Optional[NodeCapabilities]:
        """
        Get capabilities for a node type.
        
        Args:
            node_type: The node type to look up
        
        Returns:
            NodeCapabilities if found, None otherwise
        """
        return await self._capability_repo.get_by_node_type(self._mesh_id, node_type)
    
    async def list_all_capabilities(self) -> list[NodeCapabilities]:
        """
        List all registered capabilities.
        
        Returns:
            List of all capability declarations
        """
        return await self._capability_repo.get_all(self._mesh_id)

