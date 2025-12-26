"""Subscription model for event subscriptions"""
from sqlalchemy import Index, text
from sqlmodel import Field
from typing import Optional

from .base import BaseModel


class Subscription(BaseModel, table=True):
    """Subscription model represents event subscriptions on top of connections.

    A subscription defines which event types should be transmitted
    from source node to target node. A connection must exist first
    before creating subscriptions.

    Attributes:
        user_id: Foreign key to user who owns this subscription
        mosaic_id: Foreign key to mosaic instance
        source_node_id: Source node that emits events
        target_node_id: Target node that receives events
        event_type: Type of event to subscribe to (EventType enum value)
        description: Optional description of this subscription
    """

    __tablename__ = "subscriptions"

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Foreign keys
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    mosaic_id: int = Field(foreign_key="mosaics.id", nullable=False, index=True)

    # Core fields (foreign keys to nodes table)
    source_node_id: int = Field(
        foreign_key="nodes.id", nullable=False, index=True, description="Source node that emits events"
    )
    target_node_id: int = Field(
        foreign_key="nodes.id", nullable=False, index=True, description="Target node that receives events"
    )
    event_type: str = Field(
        nullable=False, max_length=50, description="Type of event to subscribe to"
    )

    # Optional fields
    description: Optional[str] = Field(
        default=None, max_length=500, description="Description of this subscription"
    )

    __table_args__ = (
        # Partial unique index for active subscriptions only
        # Prevents duplicate subscriptions: same source, same target, same event type
        Index(
            "idx_active_subscriptions_unique",
            "mosaic_id",
            "source_node_id",
            "target_node_id",
            "event_type",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
