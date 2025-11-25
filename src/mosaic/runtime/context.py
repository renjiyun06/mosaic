"""
Mosaic Runtime - MeshContext Implementation

This module provides the MeshContext implementation for topology and
event semantics queries.

MeshContext is part of the "Context Plane" - it provides read-only
information about the mesh network that nodes can use for:
1. Understanding their position in the topology
2. Generating agent prompts with event semantics
3. Making routing decisions

Architecture:
=============

    ┌─────────────────────────────────────────────────────────────────┐
    │                        MeshContextImpl                          │
    │                                                                 │
    │  ┌──────────────────────────┐   ┌────────────────────────────┐  │
    │  │   Topology Queries       │   │   Semantics Queries        │  │
    │  │                          │   │                            │  │
    │  │  - Who do I subscribe to?│   │  - What does PreToolUse    │  │
    │  │  - Who subscribes to me? │   │    mean?                   │  │
    │  │  - Blocking subscribers? │   │  - What's the payload      │  │
    │  │                          │   │    schema?                 │  │
    │  └──────────────────────────┘   └────────────────────────────┘  │
    │              │                              │                   │
    │              ▼                              ▼                   │
    │  ┌──────────────────────────┐   ┌────────────────────────────┐  │
    │  │  SubscriptionRepository  │   │   CapabilityRepository     │  │
    │  └──────────────────────────┘   └────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────────┘

Use Cases:
==========

1. Agent Prompt Generation:
   - Get topology to explain "who am I in this network?"
   - Get event semantics to explain "what events might I receive?"

2. Session Routing (in agent nodes):
   - Query subscriptions to get session_scope configuration
   - (The context just provides data; interpretation is node-specific)

3. Debugging/Monitoring:
   - Inspect network topology
   - Understand event flow

Design Principles:
==================
1. Read-only - context never modifies state
2. Caches topology for efficiency (refresh on request)
3. Event semantics are registered per node type
"""

import logging
from typing import Optional

from mosaic.core.interfaces import MeshContext
from mosaic.core.models import (
    TopologyContext,
    EventSemantics,
    NodeCapabilities,
    Subscription,
)
from mosaic.core.types import NodeId, MeshId

from mosaic.storage import (
    SubscriptionRepository,
    CapabilityRepository,
)


logger = logging.getLogger(__name__)


class MeshContextImpl(MeshContext):
    """
    Implementation of MeshContext for topology and semantics queries.
    
    MeshContextImpl provides nodes with information about:
    - Their subscription relationships (who they subscribe to, who subscribes to them)
    - Event type semantics (descriptions, schemas)
    - Node type capabilities (what events each type can produce/consume)
    
    Usage:
        context = MeshContextImpl(
            node_id="worker",
            mesh_id="dev",
            subscription_repo=sub_repo,
            capability_repo=cap_repo,
        )
        
        # Get topology
        topology = await context.get_topology_context()
        for sub in topology.subscribers:
            print(f"{sub.source_id} subscribes to me for {sub.event_pattern}")
        
        # Get event semantics
        semantics = await context.get_event_semantics(["PreToolUse", "PostToolUse"])
        for event_type, info in semantics.items():
            print(f"{event_type}: {info.description}")
    
    Caching:
        Topology is cached and refreshed on explicit request.
        Event semantics are always fetched fresh.
    
    Attributes:
        node_id: The node this context is for
        mesh_id: The mesh this context is in
    """
    
    def __init__(
        self,
        node_id: NodeId,
        mesh_id: MeshId,
        subscription_repo: SubscriptionRepository,
        capability_repo: CapabilityRepository,
    ) -> None:
        """
        Initialize the context.
        
        Args:
            node_id: The node this context is for
            mesh_id: The mesh this context is in
            subscription_repo: Repository for subscription queries
            capability_repo: Repository for capability queries
        """
        self._node_id = node_id
        self._mesh_id = mesh_id
        self._subscription_repo = subscription_repo
        self._capability_repo = capability_repo
        
        # Cached topology (refreshed on request)
        self._topology_cache: Optional[TopologyContext] = None
        
        logger.debug(f"MeshContextImpl created for node {node_id}")
    
    @property
    def node_id(self) -> NodeId:
        """The node this context is for."""
        return self._node_id
    
    @property
    def mesh_id(self) -> MeshId:
        """The mesh this context is in."""
        return self._mesh_id
    
    async def get_topology_context(self) -> TopologyContext:
        """
        Get topology information for this node.
        
        This returns:
        - subscriptions: Who this node subscribes to (downstream of us)
        - subscribers: Who subscribes to this node (upstream of us)
        
        Returns:
            TopologyContext with subscription relationships
        """
        # Query subscriptions where this node is the subscriber
        subscriptions = await self._subscription_repo.get_by_source(
            mesh_id=self._mesh_id,
            source_id=self._node_id,
        )
        
        # Query subscriptions where this node is being subscribed to
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
        
        # Cache for efficiency
        self._topology_cache = topology
        
        logger.debug(
            f"Topology for {self._node_id}: "
            f"subscriptions={len(subscriptions)}, subscribers={len(subscribers)}"
        )
        
        return topology
    
    async def get_event_semantics(
        self,
        event_types: list[str],
    ) -> dict[str, EventSemantics]:
        """
        Get semantic information for event types.
        
        This retrieves descriptions and schema information for
        the specified event types. Used for agent prompt generation.
        
        Args:
            event_types: Event types to look up
        
        Returns:
            Dict mapping event type to its semantics
        """
        result: dict[str, EventSemantics] = {}
        
        # Get all capabilities
        all_capabilities = await self._capability_repo.get_all(self._mesh_id)
        
        # Build event type -> semantics mapping
        for cap in all_capabilities:
            for event_sem in cap.produced_events:
                if event_sem.event_type in event_types:
                    result[event_sem.event_type] = event_sem
            
            for event_sem in cap.consumed_events:
                if event_sem.event_type in event_types:
                    # Prefer produced over consumed if both exist
                    if event_sem.event_type not in result:
                        result[event_sem.event_type] = event_sem
        
        # For any event types not found, create default semantics
        for event_type in event_types:
            if event_type not in result:
                result[event_type] = EventSemantics(
                    event_type=event_type,
                    description=f"Event type: {event_type} (no description registered)",
                )
        
        logger.debug(
            f"Event semantics for {event_types}: found {len(result)}"
        )
        
        return result
    
    async def get_all_node_capabilities(self) -> list[NodeCapabilities]:
        """
        Get capabilities of all registered node types.
        
        This returns what events each node type can produce or consume,
        along with semantic descriptions.
        
        Returns:
            List of capability declarations
        """
        capabilities = await self._capability_repo.get_all(self._mesh_id)
        
        logger.debug(f"Retrieved {len(capabilities)} node type capabilities")
        
        return capabilities
    
    async def get_blocking_subscribers_for_event(
        self,
        event_type: str,
    ) -> list[Subscription]:
        """
        Get subscribers with blocking subscriptions for an event type.
        
        This is a convenience method that filters the cached topology.
        
        Args:
            event_type: The event type to check
        
        Returns:
            List of blocking subscriptions
        """
        # Ensure topology is loaded
        if self._topology_cache is None:
            await self.get_topology_context()
        
        return self._topology_cache.get_blocking_subscribers(event_type)
    
    async def refresh(self) -> None:
        """
        Force refresh of cached topology.
        
        Call this if subscriptions may have changed.
        """
        self._topology_cache = None
        await self.get_topology_context()
        logger.debug(f"Context refreshed for node {self._node_id}")
    
    def generate_topology_prompt(self) -> str:
        """
        Generate a natural language description of this node's topology.
        
        This can be injected into agent system prompts to help them
        understand their position in the network.
        
        Returns:
            Human-readable topology description
        
        Raises:
            RuntimeError: If topology hasn't been loaded
        """
        if self._topology_cache is None:
            raise RuntimeError(
                "Topology not loaded. Call get_topology_context() first."
            )
        
        lines = [
            f"You are node '{self._node_id}' in mesh '{self._mesh_id}'.",
            "",
        ]
        
        # Describe subscriptions (who we subscribe to)
        if self._topology_cache.subscriptions:
            lines.append("You subscribe to the following nodes:")
            for sub in self._topology_cache.subscriptions:
                blocking = " (BLOCKING - you must reply)" if sub.is_blocking() else ""
                lines.append(
                    f"  - {sub.target_id}: events matching '{sub.event_pattern}'{blocking}"
                )
            lines.append("")
        else:
            lines.append("You do not subscribe to any other nodes.")
            lines.append("")
        
        # Describe subscribers (who subscribes to us)
        if self._topology_cache.subscribers:
            lines.append("The following nodes subscribe to your events:")
            for sub in self._topology_cache.subscribers:
                blocking = " (BLOCKING - sender waits for your reply)" if sub.is_blocking() else ""
                lines.append(
                    f"  - {sub.source_id}: listens for '{sub.event_pattern}'{blocking}"
                )
        else:
            lines.append("No other nodes subscribe to your events.")
        
        return "\n".join(lines)

