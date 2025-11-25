"""
Mosaic Storage - Capability Repository

This module provides data access for NodeCapabilities entities.
Capabilities declare what events a node type can produce or consume.
"""

import json
import logging
from typing import Any, Optional

from mosaic.core.models import NodeCapabilities, EventSemantics
from mosaic.core.types import MeshId, NodeType

from ..database import DatabaseManager
from .base import BaseRepository


logger = logging.getLogger(__name__)


class CapabilityRepository(BaseRepository[NodeCapabilities]):
    """
    Repository for NodeCapabilities entities.
    
    Capabilities are stored differently from other entities:
    - Each capability record represents one (node_type, event_type, direction)
    - When queried, records are aggregated into NodeCapabilities objects
    
    The table structure is:
    | node_type | event_type | direction | description | schema | examples |
    |-----------|------------|-----------|-------------|--------|----------|
    | cc        | PreToolUse | produce   | "..."       | {...}  | [...]    |
    | cc        | PreToolUse | consume   | "..."       | {...}  | [...]    |
    
    Usage:
        repo = CapabilityRepository(db)
        
        # Register capabilities
        capabilities = NodeCapabilities(
            node_type=NodeType.CLAUDE_CODE,
            produced_events=[...],
            consumed_events=[...]
        )
        await repo.register("dev", capabilities)
        
        # Query
        caps = await repo.get_all("dev")
        caps = await repo.get_by_node_type("dev", NodeType.CLAUDE_CODE)
    """
    
    _table_name = "node_capabilities"
    
    def __init__(self, db: DatabaseManager) -> None:
        """Initialize the repository."""
        super().__init__(db)
    
    def _model_from_row(self, row: Any) -> NodeCapabilities:
        """
        Convert a database row to a partial NodeCapabilities.
        
        Note: This creates a NodeCapabilities with only one event.
        The full capabilities object is assembled by aggregating
        multiple rows in get_by_node_type().
        """
        schema_def = json.loads(row["schema_def"]) if row["schema_def"] else None
        examples = json.loads(row["examples"]) if row["examples"] else []
        
        semantics = EventSemantics(
            event_type=row["event_type"],
            description=row["description"] or "",
            schema_def=schema_def,
            examples=examples,
        )
        
        node_type = NodeType(row["node_type"])
        direction = row["direction"]
        
        if direction == "produce":
            return NodeCapabilities(
                node_type=node_type,
                produced_events=[semantics],
                consumed_events=[],
            )
        else:
            return NodeCapabilities(
                node_type=node_type,
                produced_events=[],
                consumed_events=[semantics],
            )
    
    def _model_to_row(self, model: NodeCapabilities) -> dict[str, Any]:
        """
        Convert a NodeCapabilities model to database values.
        
        Note: This is not used directly since capabilities
        are stored as multiple rows (one per event).
        """
        raise NotImplementedError(
            "Use register() instead - capabilities are stored as multiple rows"
        )
    
    async def register(
        self,
        mesh_id: MeshId,
        capabilities: NodeCapabilities,
    ) -> None:
        """
        Register capabilities for a node type.
        
        This replaces any existing capabilities for the node type.
        
        Args:
            mesh_id: The mesh to register in
            capabilities: Capability declaration
        """
        logger.debug(
            f"CapabilityRepository.register: mesh_id={mesh_id}, "
            f"node_type={capabilities.node_type}"
        )
        
        # Delete existing capabilities for this node type
        await self._delete(
            where_clause="mesh_id = ? AND node_type = ?",
            where_params=(mesh_id, capabilities.node_type.value),
        )
        
        # Insert produced events
        for semantics in capabilities.produced_events:
            await self._insert_semantics(
                mesh_id=mesh_id,
                node_type=capabilities.node_type,
                semantics=semantics,
                direction="produce",
            )
        
        # Insert consumed events
        for semantics in capabilities.consumed_events:
            await self._insert_semantics(
                mesh_id=mesh_id,
                node_type=capabilities.node_type,
                semantics=semantics,
                direction="consume",
            )
        
        logger.info(
            f"Capabilities registered: {capabilities.node_type}, "
            f"produces={len(capabilities.produced_events)}, "
            f"consumes={len(capabilities.consumed_events)}"
        )
    
    async def _insert_semantics(
        self,
        mesh_id: MeshId,
        node_type: NodeType,
        semantics: EventSemantics,
        direction: str,
    ) -> None:
        """Insert a single event semantics record."""
        query = """
            INSERT INTO node_capabilities 
            (mesh_id, node_type, event_type, direction, description, schema_def, examples)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        schema_json = json.dumps(semantics.schema_def) if semantics.schema_def else None
        examples_json = json.dumps(semantics.examples)
        
        async with self._db.connection() as conn:
            await conn.execute(
                query,
                (
                    mesh_id,
                    node_type.value,
                    semantics.event_type,
                    direction,
                    semantics.description,
                    schema_json,
                    examples_json,
                ),
            )
            await conn.commit()
    
    async def get_by_node_type(
        self,
        mesh_id: MeshId,
        node_type: NodeType,
    ) -> Optional[NodeCapabilities]:
        """
        Get capabilities for a node type.
        
        Args:
            mesh_id: The mesh to query
            node_type: The node type to get capabilities for
        
        Returns:
            NodeCapabilities if found, None otherwise
        """
        logger.debug(
            f"CapabilityRepository.get_by_node_type: "
            f"mesh_id={mesh_id}, node_type={node_type}"
        )
        
        query = """
            SELECT * FROM node_capabilities 
            WHERE mesh_id = ? AND node_type = ?
            ORDER BY direction, event_type
        """
        rows = await self._db.fetch_all(query, (mesh_id, node_type.value))
        
        if not rows:
            return None
        
        return self._aggregate_capabilities(node_type, rows)
    
    async def get_all(self, mesh_id: MeshId) -> list[NodeCapabilities]:
        """
        Get all registered capabilities.
        
        Args:
            mesh_id: The mesh to query
        
        Returns:
            List of NodeCapabilities for all registered node types
        """
        logger.debug(f"CapabilityRepository.get_all: mesh_id={mesh_id}")
        
        query = """
            SELECT * FROM node_capabilities 
            WHERE mesh_id = ?
            ORDER BY node_type, direction, event_type
        """
        rows = await self._db.fetch_all(query, (mesh_id,))
        
        if not rows:
            return []
        
        # Group by node_type and aggregate
        by_type: dict[str, list[Any]] = {}
        for row in rows:
            type_str = row["node_type"]
            if type_str not in by_type:
                by_type[type_str] = []
            by_type[type_str].append(row)
        
        return [
            self._aggregate_capabilities(NodeType(type_str), type_rows)
            for type_str, type_rows in by_type.items()
        ]
    
    def _aggregate_capabilities(
        self,
        node_type: NodeType,
        rows: list[Any],
    ) -> NodeCapabilities:
        """Aggregate database rows into a NodeCapabilities object."""
        produced = []
        consumed = []
        
        for row in rows:
            schema_def = json.loads(row["schema_def"]) if row["schema_def"] else None
            examples = json.loads(row["examples"]) if row["examples"] else []
            
            semantics = EventSemantics(
                event_type=row["event_type"],
                description=row["description"] or "",
                schema_def=schema_def,
                examples=examples,
            )
            
            if row["direction"] == "produce":
                produced.append(semantics)
            else:
                consumed.append(semantics)
        
        return NodeCapabilities(
            node_type=node_type,
            produced_events=produced,
            consumed_events=consumed,
        )
    
    async def get_event_semantics(
        self,
        mesh_id: MeshId,
        event_types: list[str],
    ) -> dict[str, EventSemantics]:
        """
        Get semantics for specific event types.
        
        Args:
            mesh_id: The mesh to query
            event_types: Event types to look up
        
        Returns:
            Dict mapping event type to its semantics
        """
        logger.debug(
            f"CapabilityRepository.get_event_semantics: event_types={event_types}"
        )
        
        if not event_types:
            return {}
        
        # Build query with placeholders
        placeholders = ", ".join(["?"] * len(event_types))
        query = f"""
            SELECT DISTINCT event_type, description, schema_def, examples
            FROM node_capabilities 
            WHERE mesh_id = ? AND event_type IN ({placeholders})
        """
        
        params = (mesh_id, *event_types)
        rows = await self._db.fetch_all(query, params)
        
        result = {}
        for row in rows:
            schema_def = json.loads(row["schema_def"]) if row["schema_def"] else None
            examples = json.loads(row["examples"]) if row["examples"] else []
            
            result[row["event_type"]] = EventSemantics(
                event_type=row["event_type"],
                description=row["description"] or "",
                schema_def=schema_def,
                examples=examples,
            )
        
        return result
    
    async def delete_by_node_type(
        self,
        mesh_id: MeshId,
        node_type: NodeType,
    ) -> int:
        """
        Delete all capabilities for a node type.
        
        Args:
            mesh_id: The mesh to delete from
            node_type: The node type to delete capabilities for
        
        Returns:
            Number of records deleted
        """
        logger.debug(
            f"CapabilityRepository.delete_by_node_type: "
            f"mesh_id={mesh_id}, node_type={node_type}"
        )
        
        return await self._delete(
            where_clause="mesh_id = ? AND node_type = ?",
            where_params=(mesh_id, node_type.value),
        )

