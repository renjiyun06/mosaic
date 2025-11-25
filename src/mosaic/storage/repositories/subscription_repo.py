"""
Mosaic Storage - Subscription Repository

This module provides data access for Subscription entities.
Subscriptions define event flow between nodes in the mesh.
"""

import logging
from typing import Any, Optional

from mosaic.core.models import Subscription
from mosaic.core.types import MeshId, NodeId, SessionScope, SessionFilter

from ..database import DatabaseManager
from .base import BaseRepository


logger = logging.getLogger(__name__)


class SubscriptionRepository(BaseRepository[Subscription]):
    """
    Repository for Subscription entities.
    
    Provides CRUD operations for subscriptions in the control plane database.
    All operations are scoped to a mesh_id.
    
    Terminology Reminder:
    - source_id: The SUBSCRIBER (downstream node, receives events)
    - target_id: The SUBSCRIBED (upstream node, produces events)
    
    Usage:
        repo = SubscriptionRepository(db)
        
        # Create
        sub = Subscription(
            mesh_id="dev",
            source_id="auditor",
            target_id="worker",
            event_pattern="!PreToolUse"
        )
        await repo.create(sub)
        
        # Query
        subs = await repo.get_by_source("dev", "auditor")  # Who auditor subscribes to
        subs = await repo.get_by_target("dev", "worker")   # Who subscribes to worker
        
        # Delete
        await repo.delete("dev", "auditor", "worker", "!PreToolUse")
    """
    
    _table_name = "subscriptions"
    
    def __init__(self, db: DatabaseManager) -> None:
        """Initialize the repository."""
        super().__init__(db)
    
    def _model_from_row(self, row: Any) -> Subscription:
        """Convert a database row to a Subscription model."""
        return Subscription(
            mesh_id=row["mesh_id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            event_pattern=row["event_pattern"],
            session_scope=SessionScope(row["session_scope"]),
            session_filter=SessionFilter(row["session_filter"]),
            session_profile=row["session_profile"],
            min_sessions=row["min_sessions"],
            max_sessions=row["max_sessions"],
        )
    
    def _model_to_row(self, model: Subscription) -> dict[str, Any]:
        """Convert a Subscription model to database column values."""
        return {
            "mesh_id": model.mesh_id,
            "source_id": model.source_id,
            "target_id": model.target_id,
            "event_pattern": model.event_pattern,
            "session_scope": model.session_scope.value,
            "session_filter": model.session_filter.value,
            "session_profile": model.session_profile,
            "min_sessions": model.min_sessions,
            "max_sessions": model.max_sessions,
        }
    
    async def create(self, subscription: Subscription) -> None:
        """
        Create a new subscription.
        
        Args:
            subscription: Subscription to create
        
        Raises:
            SubscriptionAlreadyExistsError: If subscription already exists
        """
        logger.debug(
            f"SubscriptionRepository.create: {subscription.source_id} -> "
            f"{subscription.target_id} [{subscription.event_pattern}]"
        )
        
        if await self.exists(
            subscription.mesh_id,
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
        
        await self._insert(
            subscription,
            columns=[
                "mesh_id", "source_id", "target_id", "event_pattern",
                "session_scope", "session_filter", "session_profile",
                "min_sessions", "max_sessions"
            ],
        )
        
        logger.info(
            f"Subscription created: {subscription.source_id} -> "
            f"{subscription.target_id} [{subscription.event_pattern}]"
        )
    
    async def get_by_source(
        self,
        mesh_id: MeshId,
        source_id: NodeId,
    ) -> list[Subscription]:
        """
        Get all subscriptions where node is the subscriber.
        
        This answers: "What does this node subscribe to?"
        
        Args:
            mesh_id: The mesh to query
            source_id: The subscribing node
        
        Returns:
            List of subscriptions where source_id is the subscriber
        """
        logger.debug(f"SubscriptionRepository.get_by_source: source_id={source_id}")
        
        query = """
            SELECT * FROM subscriptions 
            WHERE mesh_id = ? AND source_id = ?
            ORDER BY target_id, event_pattern
        """
        return await self._fetch_all(query, (mesh_id, source_id))
    
    async def get_by_target(
        self,
        mesh_id: MeshId,
        target_id: NodeId,
    ) -> list[Subscription]:
        """
        Get all subscriptions where node is being subscribed to.
        
        This answers: "Who subscribes to this node?"
        
        Args:
            mesh_id: The mesh to query
            target_id: The node being subscribed to
        
        Returns:
            List of subscriptions where target_id is the subscribed node
        """
        logger.debug(f"SubscriptionRepository.get_by_target: target_id={target_id}")
        
        query = """
            SELECT * FROM subscriptions 
            WHERE mesh_id = ? AND target_id = ?
            ORDER BY source_id, event_pattern
        """
        return await self._fetch_all(query, (mesh_id, target_id))
    
    async def get_blocking_subscribers(
        self,
        mesh_id: MeshId,
        target_id: NodeId,
        event_type: str,
    ) -> list[NodeId]:
        """
        Get blocking subscribers for a specific event type.
        
        This answers: "Who has blocking subscriptions to this event?"
        
        Args:
            mesh_id: The mesh to query
            target_id: The node producing the event
            event_type: The event type to check
        
        Returns:
            List of subscriber node IDs with blocking subscriptions
        """
        logger.debug(
            f"SubscriptionRepository.get_blocking_subscribers: "
            f"target_id={target_id}, event_type={event_type}"
        )
        
        # Get all subscriptions for this target
        subscriptions = await self.get_by_target(mesh_id, target_id)
        
        # Filter to blocking subscriptions that match the event type
        blocking_subscribers = []
        for sub in subscriptions:
            if sub.is_blocking() and sub.matches_event(event_type):
                blocking_subscribers.append(sub.source_id)
        
        return blocking_subscribers
    
    async def list_by_mesh(self, mesh_id: MeshId) -> list[Subscription]:
        """
        List all subscriptions in a mesh.
        
        Args:
            mesh_id: The mesh to list subscriptions for
        
        Returns:
            List of all subscriptions in the mesh
        """
        logger.debug(f"SubscriptionRepository.list_by_mesh: mesh_id={mesh_id}")
        
        query = """
            SELECT * FROM subscriptions 
            WHERE mesh_id = ?
            ORDER BY source_id, target_id, event_pattern
        """
        return await self._fetch_all(query, (mesh_id,))
    
    async def delete(
        self,
        mesh_id: MeshId,
        source_id: NodeId,
        target_id: NodeId,
        event_pattern: str,
    ) -> None:
        """
        Delete a subscription.
        
        Args:
            mesh_id: The mesh containing the subscription
            source_id: The subscribing node
            target_id: The subscribed node
            event_pattern: The event pattern
        
        Raises:
            SubscriptionNotFoundError: If subscription doesn't exist
        """
        logger.debug(
            f"SubscriptionRepository.delete: {source_id} -> "
            f"{target_id} [{event_pattern}]"
        )
        
        if not await self.exists(mesh_id, source_id, target_id, event_pattern):
            from mosaic.core.exceptions import SubscriptionNotFoundError
            raise SubscriptionNotFoundError(source_id, target_id, event_pattern)
        
        await self._delete(
            where_clause="mesh_id = ? AND source_id = ? AND target_id = ? AND event_pattern = ?",
            where_params=(mesh_id, source_id, target_id, event_pattern),
        )
        
        logger.info(
            f"Subscription deleted: {source_id} -> {target_id} [{event_pattern}]"
        )
    
    async def delete_by_node(
        self,
        mesh_id: MeshId,
        node_id: NodeId,
    ) -> int:
        """
        Delete all subscriptions involving a node.
        
        This deletes subscriptions where the node is either:
        - The subscriber (source_id)
        - The subscribed (target_id)
        
        Args:
            mesh_id: The mesh containing the subscriptions
            node_id: The node to remove subscriptions for
        
        Returns:
            Number of subscriptions deleted
        """
        logger.debug(f"SubscriptionRepository.delete_by_node: node_id={node_id}")
        
        query = """
            DELETE FROM subscriptions 
            WHERE mesh_id = ? AND (source_id = ? OR target_id = ?)
        """
        
        async with self._db.connection() as conn:
            cursor = await conn.execute(query, (mesh_id, node_id, node_id))
            await conn.commit()
            count = cursor.rowcount
        
        logger.info(f"Deleted {count} subscriptions for node {node_id}")
        return count
    
    async def exists(
        self,
        mesh_id: MeshId,
        source_id: NodeId,
        target_id: NodeId,
        event_pattern: str,
    ) -> bool:
        """
        Check if a subscription exists.
        
        Args:
            mesh_id: The mesh to check in
            source_id: The subscribing node
            target_id: The subscribed node
            event_pattern: The event pattern
        
        Returns:
            True if subscription exists
        """
        return await self._exists(
            where_clause="mesh_id = ? AND source_id = ? AND target_id = ? AND event_pattern = ?",
            where_params=(mesh_id, source_id, target_id, event_pattern),
        )
    
    async def count_by_mesh(self, mesh_id: MeshId) -> int:
        """
        Count subscriptions in a mesh.
        
        Args:
            mesh_id: The mesh to count subscriptions in
        
        Returns:
            Number of subscriptions
        """
        return await self._count(
            where_clause="mesh_id = ?",
            where_params=(mesh_id,),
        )

