"""
Mosaic Runtime - MeshContext Implementation

This module implements MeshContext, the query interface for topology and
event semantics information. This information is used by nodes (especially
agent nodes) to understand their position in the mesh and generate prompts.

Key Responsibilities:
1. Provide topology information (who subscribes to whom)
2. Provide event semantics (descriptions for agent prompts)
3. Provide node capability information

Design Notes:
- MeshContext is READ-ONLY - it doesn't modify any data
- All data comes from the storage layer (repositories)
- Results may be cached for performance (future enhancement)
"""

import logging
from typing import Protocol, runtime_checkable

from mosaic.core.interfaces import MeshContext
from mosaic.core.models import (
    TopologyContext,
    EventSemantics,
    NodeCapabilities,
    Subscription,
)
from mosaic.core.types import NodeId, MeshId, NodeType


logger = logging.getLogger(__name__)


# =============================================================================
# Repository Protocols (for dependency injection)
# =============================================================================

@runtime_checkable
class SubscriptionQueryProtocol(Protocol):
    """Protocol for subscription queries needed by MeshContext."""
    
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


@runtime_checkable
class CapabilityQueryProtocol(Protocol):
    """Protocol for capability queries needed by MeshContext."""
    
    async def get_by_node_type(
        self,
        mesh_id: MeshId,
        node_type: NodeType,
    ) -> list[EventSemantics]:
        """Get event semantics for a node type."""
        ...
    
    async def get_all(
        self,
        mesh_id: MeshId,
    ) -> list[NodeCapabilities]:
        """Get all registered node capabilities."""
        ...


# =============================================================================
# MeshContext Implementation
# =============================================================================

class MeshContextImpl(MeshContext):
    """
    Implementation of MeshContext interface.
    
    MeshContextImpl provides read-only access to mesh information that
    nodes need for decision-making and prompt generation.
    
    Two Types of Information:
    1. TOPOLOGY: Who subscribes to whom
       - My subscriptions (who I subscribe to)
       - My subscribers (who subscribes to me)
       - Used for understanding event flow
    
    2. SEMANTICS: What events mean
       - Human-readable descriptions
       - Schema information
       - Used for agent prompt generation
    
    Usage:
        context = MeshContextImpl(node_id, mesh_id, sub_repo, cap_repo)
        
        # Get topology
        topology = await context.get_topology_context()
        for sub in topology.subscribers:
            print(f"{sub.source_id} subscribes to me for {sub.event_pattern}")
        
        # Get event semantics for prompt injection
        semantics = await context.get_event_semantics(["PreToolUse"])
        for event_type, info in semantics.items():
            print(f"{event_type}: {info.description}")
    
    Attributes:
        node_id: The node this context is for
        mesh_id: The mesh this context belongs to
    """
    
    def __init__(
        self,
        node_id: NodeId,
        mesh_id: MeshId,
        subscription_repo: SubscriptionQueryProtocol,
        capability_repo: CapabilityQueryProtocol | None = None,
    ) -> None:
        """
        Initialize the context.
        
        Args:
            node_id: Node this context is for
            mesh_id: Mesh this context belongs to
            subscription_repo: Repository for subscription queries
            capability_repo: Repository for capability queries (optional)
        """
        self._node_id = node_id
        self._mesh_id = mesh_id
        self._subscription_repo = subscription_repo
        self._capability_repo = capability_repo
        
        logger.debug(f"MeshContextImpl initialized: node_id={node_id}, mesh_id={mesh_id}")
    
    @property
    def node_id(self) -> NodeId:
        """The node this context is for."""
        return self._node_id
    
    @property
    def mesh_id(self) -> MeshId:
        """The mesh this context belongs to."""
        return self._mesh_id
    
    async def get_topology_context(self) -> TopologyContext:
        """
        Get topology information for this node.
        
        Returns a TopologyContext containing:
        - subscriptions: Who this node subscribes to (downstream of us)
        - subscribers: Who subscribes to this node (upstream of us)
        
        Returns:
            TopologyContext with subscription relationships
        """
        logger.debug(f"MeshContextImpl.get_topology_context: node_id={self._node_id}")
        
        # Get subscriptions where this node is the subscriber
        subscriptions = await self._subscription_repo.get_by_source(
            mesh_id=self._mesh_id,
            source_id=self._node_id,
        )
        
        # Get subscriptions where this node is being subscribed to
        subscribers = await self._subscription_repo.get_by_target(
            mesh_id=self._mesh_id,
            target_id=self._node_id,
        )
        
        topology = TopologyContext(
            node_id=self._node_id,
            mesh_id=self._mesh_id,
            subscriptions=subscriptions,
            subscribers=subscribers,
        )
        
        logger.debug(
            f"MeshContextImpl.get_topology_context: "
            f"subscriptions={len(subscriptions)}, subscribers={len(subscribers)}"
        )
        
        return topology
    
    async def get_event_semantics(
        self,
        event_types: list[str],
    ) -> dict[str, EventSemantics]:
        """
        Get semantic information for event types.
        
        This provides human-readable descriptions and schema information
        for event types. Agent nodes use this for prompt generation.
        
        Args:
            event_types: Event types to look up
        
        Returns:
            Dict mapping event type to its semantics
        """
        logger.debug(
            f"MeshContextImpl.get_event_semantics: event_types={event_types}"
        )
        
        result: dict[str, EventSemantics] = {}
        
        # If no capability repo, return empty result
        if self._capability_repo is None:
            logger.debug("MeshContextImpl: no capability_repo, returning empty semantics")
            return result
        
        # Get all capabilities
        all_capabilities = await self._capability_repo.get_all(self._mesh_id)
        
        # Extract semantics for requested event types
        for capabilities in all_capabilities:
            # Check produced events
            for semantics in capabilities.produced_events:
                if semantics.event_type in event_types:
                    result[semantics.event_type] = semantics
            
            # Check consumed events
            for semantics in capabilities.consumed_events:
                if semantics.event_type in event_types:
                    result[semantics.event_type] = semantics
        
        logger.debug(
            f"MeshContextImpl.get_event_semantics: found {len(result)} semantics"
        )
        
        return result
    
    async def get_all_node_capabilities(self) -> list[NodeCapabilities]:
        """
        Get capabilities of all registered node types.
        
        Returns:
            List of capability declarations
        """
        logger.debug("MeshContextImpl.get_all_node_capabilities")
        
        if self._capability_repo is None:
            logger.debug("MeshContextImpl: no capability_repo, returning empty list")
            return []
        
        capabilities = await self._capability_repo.get_all(self._mesh_id)
        
        logger.debug(
            f"MeshContextImpl.get_all_node_capabilities: found {len(capabilities)}"
        )
        
        return capabilities
    
    async def get_topology_summary(self) -> str:
        """
        Get a human-readable summary of topology for prompt injection.
        
        This generates a natural language description of the node's
        position in the mesh network.
        
        Returns:
            Human-readable topology summary
        """
        topology = await self.get_topology_context()
        
        lines = [
            f"Node '{self._node_id}' in mesh '{self._mesh_id}':",
            "",
        ]
        
        # Describe subscriptions (who we subscribe to)
        if topology.subscriptions:
            lines.append("You subscribe to:")
            for sub in topology.subscriptions:
                blocking = " (blocking)" if sub.is_blocking() else ""
                lines.append(f"  - {sub.target_id}: {sub.event_pattern}{blocking}")
        else:
            lines.append("You do not subscribe to any other nodes.")
        
        lines.append("")
        
        # Describe subscribers (who subscribes to us)
        if topology.subscribers:
            lines.append("Nodes subscribing to you:")
            for sub in topology.subscribers:
                blocking = " (blocking)" if sub.is_blocking() else ""
                lines.append(f"  - {sub.source_id}: {sub.event_pattern}{blocking}")
        else:
            lines.append("No other nodes subscribe to you.")
        
        return "\n".join(lines)

