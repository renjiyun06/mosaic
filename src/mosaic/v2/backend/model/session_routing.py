"""Session routing model for tracking session mappings between nodes"""
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, Index, Column
from sqlalchemy import text

from .base import BaseModel


class SessionRouting(BaseModel, table=True):
    """
    Session routing mapping between two nodes.

    This table maintains bidirectional mappings between sessions on different nodes.
    For each routing relationship, two records are stored:
    - (local=A, session=S1) ↔ (remote=B, session=S2)
    - (local=B, session=S2) ↔ (remote=A, session=S1)

    This allows efficient lookup in both directions.
    """
    __tablename__ = "session_routings"
    __table_args__ = (
        Index(
            "idx_session_routing_lookup",
            "mosaic_id",
            "local_node_id",
            "local_session_id",
            "remote_node_id",
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    # References
    user_id: int = Field(
        index=True,
        description="Reference to users.id - User who owns this routing"
    )
    mosaic_id: int = Field(
        index=True,
        description="Reference to mosaics.id - Mosaic instance this routing belongs to"
    )

    # Local side (the node that owns this routing record)
    local_node_id: str = Field(
        max_length=100,
        index=True,
        description="Reference to nodes.node_id - Local node"
    )
    local_session_id: str = Field(
        max_length=100,
        index=True,
        description="Reference to sessions.session_id - Local session (UUID)"
    )

    # Remote side (the other node in this routing)
    remote_node_id: str = Field(
        max_length=100,
        index=True,
        description="Reference to nodes.node_id - Remote node"
    )
    remote_session_id: str = Field(
        max_length=100,
        index=True,
        description="Reference to sessions.session_id - Remote session (UUID)"
    )
