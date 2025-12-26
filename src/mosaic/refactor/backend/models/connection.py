"""Connection data model"""
from typing import Optional
from sqlmodel import Field, Index
from sqlalchemy import text
from .base import BaseModel


class Connection(BaseModel, table=True):
    """Connection between two nodes in a Mosaic instance

    Represents a directed connection from a source node to a target node.
    Each connection defines how sessions are aligned between the connected nodes.
    """

    __tablename__ = "connections"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    mosaic_id: int = Field(foreign_key="mosaics.id", index=True)
    source_node_id: int = Field(foreign_key="nodes.id", index=True)
    target_node_id: int = Field(foreign_key="nodes.id", index=True)
    session_alignment: str = Field(
        default="tasking",
        max_length=20,
        description="Session alignment strategy: 'mirroring' or 'tasking'",
    )
    description: Optional[str] = Field(default=None, max_length=500)

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
