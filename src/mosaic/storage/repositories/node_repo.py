"""
Mosaic Storage - Node Repository

This module provides data access for Node entities.
Nodes are the basic units of the Mosaic mesh.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from mosaic.core.models import Node
from mosaic.core.types import MeshId, NodeId, NodeType, RestartPolicy

from ..database import DatabaseManager
from .base import BaseRepository


logger = logging.getLogger(__name__)


class NodeRepository(BaseRepository[Node]):
    """
    Repository for Node entities.
    
    Provides CRUD operations for nodes in the control plane database.
    All operations are scoped to a mesh_id.
    
    Usage:
        repo = NodeRepository(db)
        
        # Create
        node = Node(
            mesh_id="dev",
            node_id="worker",
            node_type=NodeType.CLAUDE_CODE,
            workspace="/path/to/workspace"
        )
        await repo.create(node)
        
        # Read
        node = await repo.get("dev", "worker")
        nodes = await repo.list_by_mesh("dev")
        
        # Update
        node.config["key"] = "value"
        await repo.update(node)
        
        # Delete
        await repo.delete("dev", "worker")
    """
    
    _table_name = "nodes"
    
    def __init__(self, db: DatabaseManager) -> None:
        """Initialize the repository."""
        super().__init__(db)
    
    def _model_from_row(self, row: Any) -> Node:
        """Convert a database row to a Node model."""
        config = json.loads(row["config"]) if row["config"] else {}
        
        return Node(
            mesh_id=row["mesh_id"],
            node_id=row["node_id"],
            node_type=NodeType(row["node_type"]),
            workspace=row["workspace"],
            config=config,
            restart_policy=RestartPolicy(row["restart_policy"]),
            max_retries=row["max_retries"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
        )
    
    def _model_to_row(self, model: Node) -> dict[str, Any]:
        """Convert a Node model to database column values."""
        return {
            "mesh_id": model.mesh_id,
            "node_id": model.node_id,
            "node_type": model.node_type.value,
            "workspace": model.workspace,
            "config": json.dumps(model.config),
            "restart_policy": model.restart_policy.value,
            "max_retries": model.max_retries,
            "created_at": model.created_at.isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    async def create(self, node: Node) -> None:
        """
        Create a new node.
        
        Args:
            node: Node to create
        
        Raises:
            NodeAlreadyExistsError: If node_id already exists in the mesh
        """
        logger.debug(f"NodeRepository.create: mesh_id={node.mesh_id}, node_id={node.node_id}")
        
        if await self.exists(node.mesh_id, node.node_id):
            from mosaic.core.exceptions import NodeAlreadyExistsError
            raise NodeAlreadyExistsError(node.node_id, node.mesh_id)
        
        await self._insert(
            node,
            columns=[
                "mesh_id", "node_id", "node_type", "workspace",
                "config", "restart_policy", "max_retries",
                "created_at", "updated_at"
            ],
        )
        
        logger.info(f"Node created: {node.node_id} in mesh {node.mesh_id}")
    
    async def get(self, mesh_id: MeshId, node_id: NodeId) -> Optional[Node]:
        """
        Get a node by ID.
        
        Args:
            mesh_id: The mesh to look in
            node_id: The node to look up
        
        Returns:
            Node if found, None otherwise
        """
        logger.debug(f"NodeRepository.get: mesh_id={mesh_id}, node_id={node_id}")
        
        query = "SELECT * FROM nodes WHERE mesh_id = ? AND node_id = ?"
        return await self._fetch_one(query, (mesh_id, node_id))
    
    async def list_by_mesh(self, mesh_id: MeshId) -> list[Node]:
        """
        List all nodes in a mesh.
        
        Args:
            mesh_id: The mesh to list nodes for
        
        Returns:
            List of nodes in the mesh
        """
        logger.debug(f"NodeRepository.list_by_mesh: mesh_id={mesh_id}")
        
        query = "SELECT * FROM nodes WHERE mesh_id = ? ORDER BY node_id"
        return await self._fetch_all(query, (mesh_id,))
    
    async def list_by_type(self, mesh_id: MeshId, node_type: NodeType) -> list[Node]:
        """
        List all nodes of a specific type in a mesh.
        
        Args:
            mesh_id: The mesh to list nodes for
            node_type: The node type to filter by
        
        Returns:
            List of nodes of the specified type
        """
        logger.debug(f"NodeRepository.list_by_type: mesh_id={mesh_id}, node_type={node_type}")
        
        query = "SELECT * FROM nodes WHERE mesh_id = ? AND node_type = ? ORDER BY node_id"
        return await self._fetch_all(query, (mesh_id, node_type.value))
    
    async def update(self, node: Node) -> None:
        """
        Update a node.
        
        Args:
            node: Node with updated values
        
        Raises:
            NodeNotFoundError: If node doesn't exist
        """
        logger.debug(f"NodeRepository.update: mesh_id={node.mesh_id}, node_id={node.node_id}")
        
        if not await self.exists(node.mesh_id, node.node_id):
            from mosaic.core.exceptions import NodeNotFoundError
            raise NodeNotFoundError(node.node_id, node.mesh_id)
        
        await self._update(
            node,
            columns=[
                "workspace", "config", "restart_policy",
                "max_retries", "updated_at"
            ],
            where_clause="mesh_id = ? AND node_id = ?",
            where_params=(node.mesh_id, node.node_id),
        )
        
        logger.info(f"Node updated: {node.node_id} in mesh {node.mesh_id}")
    
    async def delete(self, mesh_id: MeshId, node_id: NodeId) -> None:
        """
        Delete a node.
        
        Note: This does NOT cascade delete subscriptions. Use the
        admin interface for that (it handles subscription cleanup).
        
        Args:
            mesh_id: The mesh containing the node
            node_id: The node to delete
        
        Raises:
            NodeNotFoundError: If node doesn't exist
        """
        logger.debug(f"NodeRepository.delete: mesh_id={mesh_id}, node_id={node_id}")
        
        if not await self.exists(mesh_id, node_id):
            from mosaic.core.exceptions import NodeNotFoundError
            raise NodeNotFoundError(node_id, mesh_id)
        
        await self._delete(
            where_clause="mesh_id = ? AND node_id = ?",
            where_params=(mesh_id, node_id),
        )
        
        logger.info(f"Node deleted: {node_id} from mesh {mesh_id}")
    
    async def exists(self, mesh_id: MeshId, node_id: NodeId) -> bool:
        """
        Check if a node exists.
        
        Args:
            mesh_id: The mesh to check in
            node_id: The node to check
        
        Returns:
            True if node exists
        """
        return await self._exists(
            where_clause="mesh_id = ? AND node_id = ?",
            where_params=(mesh_id, node_id),
        )
    
    async def count_by_mesh(self, mesh_id: MeshId) -> int:
        """
        Count nodes in a mesh.
        
        Args:
            mesh_id: The mesh to count nodes in
        
        Returns:
            Number of nodes
        """
        return await self._count(
            where_clause="mesh_id = ?",
            where_params=(mesh_id,),
        )

