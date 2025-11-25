"""
Mosaic Storage - Mesh Repository

This module provides data access for Mesh entities.
A Mesh represents an isolated network of nodes.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from mosaic.core.models import Mesh
from mosaic.core.types import MeshId

from ..database import DatabaseManager
from .base import BaseRepository


logger = logging.getLogger(__name__)


class MeshRepository(BaseRepository[Mesh]):
    """
    Repository for Mesh entities.
    
    Provides CRUD operations for meshes in the control plane database.
    
    Usage:
        repo = MeshRepository(db)
        
        # Create
        mesh = Mesh(mesh_id="dev", config={"env": "development"})
        await repo.create(mesh)
        
        # Read
        mesh = await repo.get("dev")
        meshes = await repo.list_all()
        
        # Update
        mesh.config["version"] = "2.0"
        await repo.update(mesh)
        
        # Delete
        await repo.delete("dev")
    """
    
    _table_name = "meshes"
    
    def __init__(self, db: DatabaseManager) -> None:
        """Initialize the repository."""
        super().__init__(db)
    
    def _model_from_row(self, row: Any) -> Mesh:
        """Convert a database row to a Mesh model."""
        config = json.loads(row["config"]) if row["config"] else {}
        
        return Mesh(
            mesh_id=row["mesh_id"],
            config=config,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
        )
    
    def _model_to_row(self, model: Mesh) -> dict[str, Any]:
        """Convert a Mesh model to database column values."""
        return {
            "mesh_id": model.mesh_id,
            "config": json.dumps(model.config),
            "created_at": model.created_at.isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    async def create(self, mesh: Mesh) -> None:
        """
        Create a new mesh.
        
        Args:
            mesh: Mesh to create
        
        Raises:
            MeshAlreadyExistsError: If mesh_id already exists
        """
        logger.debug(f"MeshRepository.create: mesh_id={mesh.mesh_id}")
        
        if await self.exists(mesh.mesh_id):
            from mosaic.core.exceptions import MeshAlreadyExistsError
            raise MeshAlreadyExistsError(mesh.mesh_id)
        
        await self._insert(
            mesh,
            columns=["mesh_id", "config", "created_at", "updated_at"],
        )
        
        logger.info(f"Mesh created: {mesh.mesh_id}")
    
    async def get(self, mesh_id: MeshId) -> Optional[Mesh]:
        """
        Get a mesh by ID.
        
        Args:
            mesh_id: The mesh to look up
        
        Returns:
            Mesh if found, None otherwise
        """
        logger.debug(f"MeshRepository.get: mesh_id={mesh_id}")
        
        query = "SELECT * FROM meshes WHERE mesh_id = ?"
        return await self._fetch_one(query, (mesh_id,))
    
    async def list_all(self) -> list[Mesh]:
        """
        List all meshes.
        
        Returns:
            List of all meshes
        """
        logger.debug("MeshRepository.list_all")
        
        query = "SELECT * FROM meshes ORDER BY created_at"
        return await self._fetch_all(query)
    
    async def update(self, mesh: Mesh) -> None:
        """
        Update a mesh.
        
        Args:
            mesh: Mesh with updated values
        
        Raises:
            MeshNotFoundError: If mesh doesn't exist
        """
        logger.debug(f"MeshRepository.update: mesh_id={mesh.mesh_id}")
        
        if not await self.exists(mesh.mesh_id):
            from mosaic.core.exceptions import MeshNotFoundError
            raise MeshNotFoundError(mesh.mesh_id)
        
        await self._update(
            mesh,
            columns=["config", "updated_at"],
            where_clause="mesh_id = ?",
            where_params=(mesh.mesh_id,),
        )
        
        logger.info(f"Mesh updated: {mesh.mesh_id}")
    
    async def delete(self, mesh_id: MeshId) -> None:
        """
        Delete a mesh.
        
        This also cascades to delete all nodes and subscriptions in the mesh.
        
        Args:
            mesh_id: The mesh to delete
        
        Raises:
            MeshNotFoundError: If mesh doesn't exist
        """
        logger.debug(f"MeshRepository.delete: mesh_id={mesh_id}")
        
        if not await self.exists(mesh_id):
            from mosaic.core.exceptions import MeshNotFoundError
            raise MeshNotFoundError(mesh_id)
        
        deleted = await self._delete(
            where_clause="mesh_id = ?",
            where_params=(mesh_id,),
        )
        
        logger.info(f"Mesh deleted: {mesh_id} (cascade deleted related records)")
    
    async def exists(self, mesh_id: MeshId) -> bool:
        """
        Check if a mesh exists.
        
        Args:
            mesh_id: The mesh to check
        
        Returns:
            True if mesh exists
        """
        return await self._exists(
            where_clause="mesh_id = ?",
            where_params=(mesh_id,),
        )

