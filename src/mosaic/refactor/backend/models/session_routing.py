"""Session routing model for tracking session mappings between nodes"""
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, Index, Column

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

    id: Optional[int] = Field(default=None, primary_key=True)

    # Owner information
    user_id: int = Field(
        foreign_key="users.id",
        index=True,
        description="User who owns this routing"
    )
    mosaic_id: int = Field(
        foreign_key="mosaics.id",
        index=True,
        description="Mosaic instance this routing belongs to"
    )

    # Local side (the node that owns this routing record)
    local_node_id: int = Field(
        foreign_key="nodes.id",
        index=True,
        description="Local node ID (database ID)"
    )
    local_session_id: str = Field(
        max_length=100,
        index=True,
        description="Local session ID (UUID)"
    )

    # Remote side (the other node in this routing)
    remote_node_id: int = Field(
        foreign_key="nodes.id",
        index=True,
        description="Remote node ID (database ID)"
    )
    remote_session_id: str = Field(
        max_length=100,
        index=True,
        description="Remote session ID (UUID)"
    )

    __table_args__ = (
        Index(
            "idx_session_routing_unique",
            "mosaic_id",
            "local_node_id",
            "local_session_id",
            "remote_node_id",
            unique=True,
            sqlite_where=Column("deleted_at").is_(None),
        ),
        Index(
            "idx_session_routing_lookup",
            "mosaic_id",
            "local_node_id",
            "local_session_id",
            "remote_node_id",
        ),
    )
