from datetime import datetime
from typing import Optional
from sqlmodel import Field, Column, JSON
from .base import BaseModel


class Event(BaseModel, table=True):
    """
    Event storage model for event monitoring and history

    Stores every event instance sent through the ZMQ bus.
    For events with multiple subscribers, each subscriber receives
    a separate event instance with a unique event_id.
    """
    __tablename__ = "events"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Event identity (UUID from runtime)
    event_id: str = Field(unique=True, index=True)

    # Ownership
    user_id: int = Field(foreign_key="users.id", index=True)
    mosaic_id: int = Field(foreign_key="mosaics.id", index=True)

    # Event routing
    source_node_id: int = Field(foreign_key="nodes.id", index=True)
    target_node_id: int = Field(foreign_key="nodes.id", index=True)

    # Event type (from EventType enum)
    event_type: str = Field(index=True)

    # Session tracking
    upstream_session_id: Optional[str] = Field(default=None, index=True)
    downstream_session_id: Optional[str] = Field(default=None, index=True)

    # Payload (JSON)
    payload: dict = Field(default={}, sa_column=Column(JSON))

    # Timestamp from event creation (not DB insertion)
    event_created_at: datetime
