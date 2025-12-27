"""Subscription model for event subscriptions"""
from sqlalchemy import Index, text
from sqlmodel import Field
from typing import Optional

from .base import BaseModel
from ..enums import EventType


class Subscription(BaseModel, table=True):
    """Subscription model represents event subscriptions on top of connections.

    A subscription defines which event types should be transmitted
    from source node to target node. A connection must exist first
    before creating subscriptions.

    Key Design:
        - Subscriptions are built ON TOP OF connections (connection_id references connections.id)
        - Session alignment strategy is defined at the connection level, NOT at subscription level
        - This means all events flowing through the same connection use the same session alignment
        - source_node_id and target_node_id are denormalized for query efficiency and table completeness

    Attributes:
        user_id: Foreign key to user who owns this subscription
        mosaic_id: Foreign key to mosaic instance
        connection_id: Foreign key to the connection this subscription is based on
        source_node_id: Source node that emits events (denormalized from connection)
        target_node_id: Target node that receives events (denormalized from connection)
        event_type: Type of event to subscribe to (EventType enum value)
        description: Optional description of this subscription
    """

    __tablename__ = "subscriptions"
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

    # References
    user_id: int = Field(nullable=False, index=True, description="Reference to users.id")
    mosaic_id: int = Field(nullable=False, index=True, description="Reference to mosaics.id")
    connection_id: int = Field(
        nullable=False, index=True, description="Reference to connections.id - Subscription must be based on an existing connection"
    )

    # Node references (denormalized for query convenience and table completeness)
    source_node_id: str = Field(
        max_length=100, nullable=False, index=True, description="Reference to nodes.node_id - Source node that emits events"
    )
    target_node_id: str = Field(
        max_length=100, nullable=False, index=True, description="Reference to nodes.node_id - Target node that receives events"
    )
    event_type: EventType = Field(
        nullable=False, description="Type of event to subscribe to"
    )

    # Optional fields
    description: Optional[str] = Field(
        default=None, max_length=500, description="Description of this subscription"
    )
