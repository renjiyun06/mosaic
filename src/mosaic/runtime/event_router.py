"""
Mosaic Runtime - Event Router

This module provides event routing based on subscription relationships.
The EventRouter is responsible for determining which nodes should receive
an event when a node produces it.

Key Responsibilities:
1. Query subscription relationships (from storage)
2. Match events against subscription patterns
3. Create copies of events for each subscriber
4. Distinguish blocking vs non-blocking subscribers

Design Principles:
1. SENDER-SIDE DISPATCH: The sending node (via router) decides who receives
2. SUBSCRIPTION-DRIVEN: Routing is determined by subscription relationships
3. TRANSPARENT: Router doesn't interpret event payload or session info
4. STATELESS: Router queries subscriptions on-demand (no caching)

Note on Dependencies:
The EventRouter depends on storage repositories to query subscriptions.
It uses the Protocol pattern to define the required interface, allowing
for different storage implementations.
"""

import logging
from typing import Protocol, runtime_checkable

from mosaic.core.models import MeshEvent, Subscription
from mosaic.core.types import NodeId, MeshId, EventId


logger = logging.getLogger(__name__)


# =============================================================================
# Repository Protocol (for dependency injection)
# =============================================================================

@runtime_checkable
class SubscriptionRepositoryProtocol(Protocol):
    """
    Protocol defining the subscription query interface.
    
    This protocol defines what EventRouter needs from the storage layer.
    The actual implementation lives in mosaic.storage.repositories.
    
    Using Protocol enables:
    - Type checking without concrete dependencies
    - Easy testing with mock implementations
    - Clear interface boundaries
    """
    
    async def get_by_target(
        self,
        mesh_id: MeshId,
        target_id: NodeId,
    ) -> list[Subscription]:
        """
        Get all subscriptions where node is being subscribed to.
        
        Args:
            mesh_id: The mesh to query
            target_id: The node being subscribed to (produces events)
        
        Returns:
            List of subscriptions where target_id is the subscribed node
        """
        ...


# =============================================================================
# Routing Result
# =============================================================================

class RoutingResult:
    """
    Result of routing an event.
    
    Contains the lists of subscribers, separated by blocking vs non-blocking.
    Also holds the prepared event copies ready for delivery.
    
    Attributes:
        blocking_subscriptions: Subscriptions requiring sender to wait
        non_blocking_subscriptions: Fire-and-forget subscriptions
        routed_events: Events ready for delivery (target_id set)
    """
    
    def __init__(self) -> None:
        self.blocking_subscriptions: list[Subscription] = []
        self.non_blocking_subscriptions: list[Subscription] = []
        self.routed_events: list[MeshEvent] = []
    
    @property
    def has_blocking(self) -> bool:
        """Check if there are any blocking subscribers."""
        return len(self.blocking_subscriptions) > 0
    
    @property
    def blocking_count(self) -> int:
        """Number of blocking subscribers."""
        return len(self.blocking_subscriptions)
    
    @property
    def total_count(self) -> int:
        """Total number of subscribers."""
        return len(self.blocking_subscriptions) + len(self.non_blocking_subscriptions)
    
    def get_blocking_subscriber_ids(self) -> list[NodeId]:
        """Get list of blocking subscriber node IDs."""
        return [sub.source_id for sub in self.blocking_subscriptions]


# =============================================================================
# Event Router
# =============================================================================

class EventRouter:
    """
    Routes events to subscribers based on subscription relationships.
    
    The EventRouter is the core component that implements sender-side dispatch.
    When a node produces an event, the router:
    1. Queries all subscriptions where this node is the target
    2. Filters subscriptions by event type match
    3. Separates blocking and non-blocking subscriptions
    4. Creates event copies for each subscriber
    
    Important: The router does NOT send events. It only determines WHO should
    receive them. The actual sending is done by MeshOutbox.
    
    Usage:
        router = EventRouter(mesh_id, subscription_repo)
        
        event = MeshEvent(source_id="worker", event_type="PreToolUse", ...)
        result = await router.route(event)
        
        for routed_event in result.routed_events:
            await transport.send_event(routed_event)
        
        if result.has_blocking:
            # Need to wait for responses from blocking subscribers
            ...
    """
    
    def __init__(
        self,
        mesh_id: MeshId,
        subscription_repo: SubscriptionRepositoryProtocol,
    ) -> None:
        """
        Initialize the event router.
        
        Args:
            mesh_id: The mesh this router operates in
            subscription_repo: Repository for querying subscriptions
        """
        self.mesh_id = mesh_id
        self._subscription_repo = subscription_repo
        
        logger.debug(f"EventRouter initialized for mesh_id={mesh_id}")
    
    async def route(self, event: MeshEvent) -> RoutingResult:
        """
        Route an event to all matching subscribers.
        
        This method:
        1. Gets all subscriptions where source is target
        2. Filters by event type pattern
        3. Creates event copies with target_id set
        4. Returns routing result with blocking/non-blocking separation
        
        Args:
            event: The event to route (source_id must be set)
        
        Returns:
            RoutingResult with prepared events and subscription info
        """
        result = RoutingResult()
        
        # Get all subscriptions where this node is being subscribed to
        subscriptions = await self._subscription_repo.get_by_target(
            mesh_id=self.mesh_id,
            target_id=event.source_id,
        )
        
        logger.debug(
            f"EventRouter: found {len(subscriptions)} subscriptions for "
            f"source_id={event.source_id}, event_type={event.event_type}"
        )
        
        # Filter and categorize subscriptions
        for sub in subscriptions:
            if not sub.matches_event(event.event_type):
                continue
            
            # Create event copy with target_id set
            routed_event = self._create_routed_event(event, sub.source_id)
            result.routed_events.append(routed_event)
            
            # Categorize by blocking
            if sub.is_blocking():
                result.blocking_subscriptions.append(sub)
                logger.debug(
                    f"EventRouter: blocking subscriber {sub.source_id} "
                    f"for pattern {sub.event_pattern}"
                )
            else:
                result.non_blocking_subscriptions.append(sub)
                logger.debug(
                    f"EventRouter: non-blocking subscriber {sub.source_id} "
                    f"for pattern {sub.event_pattern}"
                )
        
        logger.debug(
            f"EventRouter: routing complete for event_id={event.event_id}, "
            f"blocking={result.blocking_count}, "
            f"non_blocking={len(result.non_blocking_subscriptions)}"
        )
        
        return result
    
    async def get_blocking_subscribers(
        self,
        source_id: NodeId,
        event_type: str,
    ) -> list[Subscription]:
        """
        Get blocking subscribers for an event type.
        
        This is a convenience method for checking if blocking waits are needed
        before actually creating the event.
        
        Args:
            source_id: The node that would produce the event
            event_type: The type of event
        
        Returns:
            List of blocking subscriptions that match
        """
        subscriptions = await self._subscription_repo.get_by_target(
            mesh_id=self.mesh_id,
            target_id=source_id,
        )
        
        return [
            sub for sub in subscriptions
            if sub.is_blocking() and sub.matches_event(event_type)
        ]
    
    async def has_blocking_subscribers(
        self,
        source_id: NodeId,
        event_type: str,
    ) -> bool:
        """
        Check if there are any blocking subscribers for an event type.
        
        Args:
            source_id: The node that would produce the event
            event_type: The type of event
        
        Returns:
            True if there are blocking subscribers
        """
        blocking = await self.get_blocking_subscribers(source_id, event_type)
        return len(blocking) > 0
    
    def _create_routed_event(
        self,
        original: MeshEvent,
        target_id: NodeId,
    ) -> MeshEvent:
        """
        Create a copy of an event with target_id set.
        
        We need to create copies because each subscriber gets their own
        event instance with different target_id.
        
        Args:
            original: The original event
            target_id: The subscriber node ID
        
        Returns:
            New MeshEvent with target_id set
        """
        # Use Pydantic's model_copy for efficient copying
        return original.model_copy(update={"target_id": target_id})

