"""Connection data model"""
from typing import Optional
from sqlmodel import Field, Index
from sqlalchemy import text
from .base import BaseModel
from ..enums import SessionAlignment


class Connection(BaseModel, table=True):
    """Connection between two nodes in a Mosaic instance

    Represents a directed connection from a source node to a target node.
    Each connection defines how sessions are aligned between the connected nodes.
    """

    __tablename__ = "connections"
    __table_args__ = (
        # Partial unique index: only enforce uniqueness for non-deleted records
        Index(
            "idx_active_connections_unique",
            "mosaic_id",
            "source_node_id",
            "target_node_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    user_id: int = Field(index=True, description="Reference to users.id")
    mosaic_id: int = Field(index=True, description="Reference to mosaics.id")
    source_node_id: str = Field(max_length=100, index=True, description="Reference to nodes.node_id")
    target_node_id: str = Field(max_length=100, index=True, description="Reference to nodes.node_id")
    session_alignment: SessionAlignment = Field(
        description="Session alignment strategy",
    )
    description: Optional[str] = Field(default=None, max_length=500)
