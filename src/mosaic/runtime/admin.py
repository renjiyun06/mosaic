"""
Mosaic Runtime - MeshAdmin Implementation

This module implements MeshAdmin, the administrative interface for mesh
configuration. It provides methods to manage nodes, subscriptions, and
capabilities.

Key Responsibilities:
1. Node management: create, delete, update, list
2. Subscription management: subscribe, unsubscribe
3. Capability registration: declare produced/consumed events

Design Notes:
- MeshAdmin operates on the control plane database (via repositories)
- All operations are persisted immediately
- MeshAdmin is typically used by CLI, not by node runtime
"""

import logging
from typing import Protocol, Optional, runtime_checkable

from mosaic.core.interfaces import MeshAdmin
from mosaic.core.models import Node, Subscription, NodeCapabilities
from mosaic.core.types import NodeId, MeshId


logger = logging.getLogger(__name__)


# =============================================================================
# Repository Protocols (for dependency injection)
# =============================================================================

@runtime_checkable
class NodeRepositoryProtocol(Protocol):
    """Protocol for node repository operations."""
    
    async def create(self, node: Node) -> None:
        """Create a new node."""
        ...
    
    async def get(self, mesh_id: MeshId, node_id: NodeId) -> Optional[Node]:
        """Get a node by ID."""
        ...
    
    async def update(self, node: Node) -> None:
        """Update an existing node."""
        ...
    
    async def delete(self, mesh_id: MeshId, node_id: NodeId) -> None:
        """Delete a node."""
        ...
    
    async def list_by_mesh(self, mesh_id: MeshId) -> list[Node]:
        """List all nodes in a mesh."""
        ...
    
    async def exists(self, mesh_id: MeshId, node_id: NodeId) -> bool:
        """Check if a node exists."""
        ...


@runtime_checkable
class SubscriptionRepositoryProtocol(Protocol):
    """Protocol for subscription repository operations."""
    
    async def create(self, subscription: Subscription) -> None:
        """Create a new subscription."""
        ...
    
    async def delete(
        self,
        mesh_id: MeshId,
        source_id: NodeId,
        target_id: NodeId,
        event_pattern: str,
    ) -> None:
        """Delete a subscription."""
        ...
    
    async def get_by_source(
        self,
        mesh_id: MeshId,
        source_id: NodeId,
    ) -> list[Subscription]:
        """Get subscriptions where node is the subscriber."""
        ...
    
    async def get_by_target(
        self,
        mesh_id: MeshId,
        target_id: NodeId,
    ) -> list[Subscription]:
        """Get subscriptions where node is being subscribed to."""
        ...
    
    async def exists(
        self,
        mesh_id: MeshId,
        source_id: NodeId,
        target_id: NodeId,
        event_pattern: str,
    ) -> bool:
        """Check if a subscription exists."""
        ...
    
    async def delete_by_node(
        self,
        mesh_id: MeshId,
        node_id: NodeId,
    ) -> int:
        """Delete all subscriptions involving a node. Returns count deleted."""
        ...


@runtime_checkable
class CapabilityRepositoryProtocol(Protocol):
    """Protocol for capability repository operations."""
    
    async def register(self, mesh_id: MeshId, capabilities: NodeCapabilities) -> None:
        """Register capabilities for a node type."""
        ...
    
    async def get_all(self, mesh_id: MeshId) -> list[NodeCapabilities]:
        """Get all registered capabilities."""
        ...


# =============================================================================
# MeshAdmin Implementation
# =============================================================================

class MeshAdminImpl(MeshAdmin):
    """
    Implementation of MeshAdmin interface.
    
    MeshAdminImpl provides administrative operations on the control plane:
    
    1. NODE MANAGEMENT:
       - create_node(): Register a new node
       - get_node(): Look up a node
       - delete_node(): Remove a node and its subscriptions
       - list_nodes(): List all nodes in the mesh
    
    2. SUBSCRIPTION MANAGEMENT:
       - subscribe(): Create an event subscription
       - unsubscribe(): Remove an event subscription
       - get_subscriptions_by_source/target(): Query subscriptions
    
    3. CAPABILITY REGISTRATION:
       - register_capabilities(): Declare event semantics
    
    All operations are persisted to the control plane database via
    repository implementations.
    
    Usage:
        admin = MeshAdminImpl(mesh_id, node_repo, sub_repo, cap_repo)
        
        # Create a node
        await admin.create_node(Node(
            mesh_id="dev",
            node_id="worker",
            node_type=NodeType.CLAUDE_CODE,
            workspace="/path/to/workspace"
        ))
        
        # Create a subscription
        await admin.subscribe(Subscription(
            mesh_id="dev",
            source_id="auditor",
            target_id="worker",
            event_pattern="!PreToolUse"
        ))
    
    Attributes:
        mesh_id: The mesh this admin operates on
    """
    
    def __init__(
        self,
        mesh_id: MeshId,
        node_repo: NodeRepositoryProtocol,
        subscription_repo: SubscriptionRepositoryProtocol,
        capability_repo: CapabilityRepositoryProtocol | None = None,
    ) -> None:
        """
        Initialize the admin interface.
        
        Args:
            mesh_id: Mesh this admin operates on
            node_repo: Repository for node operations
            subscription_repo: Repository for subscription operations
            capability_repo: Repository for capability operations (optional)
        """
        self._mesh_id = mesh_id
        self._node_repo = node_repo
        self._subscription_repo = subscription_repo
        self._capability_repo = capability_repo
        
        logger.debug(f"MeshAdminImpl initialized: mesh_id={mesh_id}")
    
    @property
    def mesh_id(self) -> MeshId:
        """The mesh this admin operates on."""
        return self._mesh_id
    
    # =========================================================================
    # Node Management
    # =========================================================================
    
    async def create_node(self, node: Node) -> None:
        """
        Create a new node in the mesh.
        
        Args:
            node: Node definition (mesh_id should match this admin's mesh)
        
        Raises:
            NodeAlreadyExistsError: If node_id already exists
            ValueError: If mesh_id doesn't match
        """
        if node.mesh_id != self._mesh_id:
            raise ValueError(
                f"Node mesh_id ({node.mesh_id}) doesn't match admin mesh_id ({self._mesh_id})"
            )
        
        logger.debug(f"MeshAdminImpl.create_node: node_id={node.node_id}")
        
        # Check if already exists
        if await self._node_repo.exists(self._mesh_id, node.node_id):
            from mosaic.core.exceptions import NodeAlreadyExistsError
            raise NodeAlreadyExistsError(node.node_id, self._mesh_id)
        
        await self._node_repo.create(node)
        
        logger.info(f"Node created: {node.node_id} in mesh {self._mesh_id}")
    
    async def get_node(self, node_id: NodeId) -> Optional[Node]:
        """
        Get a node by ID.
        
        Args:
            node_id: The node to look up
        
        Returns:
            Node if found, None otherwise
        """
        logger.debug(f"MeshAdminImpl.get_node: node_id={node_id}")
        return await self._node_repo.get(self._mesh_id, node_id)
    
    async def delete_node(self, node_id: NodeId) -> None:
        """
        Delete a node from the mesh.
        
        This also deletes all subscriptions involving this node.
        
        Args:
            node_id: The node to delete
        
        Raises:
            NodeNotFoundError: If node doesn't exist
        """
        logger.debug(f"MeshAdminImpl.delete_node: node_id={node_id}")
        
        # Check if exists
        if not await self._node_repo.exists(self._mesh_id, node_id):
            from mosaic.core.exceptions import NodeNotFoundError
            raise NodeNotFoundError(node_id, self._mesh_id)
        
        # Delete all subscriptions involving this node
        deleted_subs = await self._subscription_repo.delete_by_node(
            self._mesh_id, node_id
        )
        if deleted_subs > 0:
            logger.info(f"Deleted {deleted_subs} subscriptions for node {node_id}")
        
        # Delete the node
        await self._node_repo.delete(self._mesh_id, node_id)
        
        logger.info(f"Node deleted: {node_id} from mesh {self._mesh_id}")
    
    async def list_nodes(self) -> list[Node]:
        """
        List all nodes in the mesh.
        
        Returns:
            List of all nodes
        """
        logger.debug(f"MeshAdminImpl.list_nodes: mesh_id={self._mesh_id}")
        return await self._node_repo.list_by_mesh(self._mesh_id)
    
    # =========================================================================
    # Subscription Management
    # =========================================================================
    
    async def subscribe(self, subscription: Subscription) -> None:
        """
        Create a subscription.
        
        Args:
            subscription: Subscription definition
        
        Raises:
            SubscriptionAlreadyExistsError: If subscription exists
            NodeNotFoundError: If source or target node doesn't exist
            ValueError: If mesh_id doesn't match
        """
        if subscription.mesh_id != self._mesh_id:
            raise ValueError(
                f"Subscription mesh_id ({subscription.mesh_id}) doesn't match "
                f"admin mesh_id ({self._mesh_id})"
            )
        
        logger.debug(
            f"MeshAdminImpl.subscribe: {subscription.source_id} -> "
            f"{subscription.target_id} [{subscription.event_pattern}]"
        )
        
        # Validate nodes exist
        from mosaic.core.exceptions import NodeNotFoundError
        
        if not await self._node_repo.exists(self._mesh_id, subscription.source_id):
            raise NodeNotFoundError(subscription.source_id, self._mesh_id)
        
        if not await self._node_repo.exists(self._mesh_id, subscription.target_id):
            raise NodeNotFoundError(subscription.target_id, self._mesh_id)
        
        # Check if subscription already exists
        if await self._subscription_repo.exists(
            self._mesh_id,
            subscription.source_id,
            subscription.target_id,
            subscription.event_pattern,
        ):
            from mosaic.core.exceptions import SubscriptionAlreadyExistsError
            raise SubscriptionAlreadyExistsError(
                subscription.source_id,
                subscription.target_id,
                subscription.event_pattern,
            )
        
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
        logger.debug(
            f"MeshAdminImpl.unsubscribe: {source_id} -> {target_id} [{event_pattern}]"
        )
        
        # Check if subscription exists
        if not await self._subscription_repo.exists(
            self._mesh_id, source_id, target_id, event_pattern
        ):
            from mosaic.core.exceptions import SubscriptionNotFoundError
            raise SubscriptionNotFoundError(source_id, target_id, event_pattern)
        
        await self._subscription_repo.delete(
            self._mesh_id, source_id, target_id, event_pattern
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
        
        Args:
            source_id: The subscribing node
        
        Returns:
            List of subscriptions where source_id is the subscriber
        """
        logger.debug(f"MeshAdminImpl.get_subscriptions_by_source: source_id={source_id}")
        return await self._subscription_repo.get_by_source(self._mesh_id, source_id)
    
    async def get_subscriptions_by_target(
        self,
        target_id: NodeId,
    ) -> list[Subscription]:
        """
        Get all subscriptions where node is being subscribed to.
        
        Args:
            target_id: The node being subscribed to
        
        Returns:
            List of subscriptions where target_id is the subscribed node
        """
        logger.debug(f"MeshAdminImpl.get_subscriptions_by_target: target_id={target_id}")
        return await self._subscription_repo.get_by_target(self._mesh_id, target_id)
    
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
        logger.debug(
            f"MeshAdminImpl.register_capabilities: node_type={capabilities.node_type}"
        )
        
        if self._capability_repo is None:
            logger.warning("MeshAdminImpl: no capability_repo, skipping registration")
            return
        
        await self._capability_repo.register(self._mesh_id, capabilities)
        
        logger.info(
            f"Capabilities registered for node type: {capabilities.node_type}, "
            f"produces={len(capabilities.produced_events)}, "
            f"consumes={len(capabilities.consumed_events)}"
        )

