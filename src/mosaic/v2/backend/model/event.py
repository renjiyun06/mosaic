from typing import Any
from sqlmodel import Field, Column, JSON
from .base import BaseModel
from ..enum import EventType


class Event(BaseModel, table=True):
    """
    Event storage model for event monitoring and history

    Stores every event instance sent through the ZMQ bus.
    For events with multiple subscribers, each subscriber receives
    a separate event instance with a unique event_id.
    """
    __tablename__ = "events"

    # Event identity (UUID from runtime)
    event_id: str = Field(unique=True, index=True)

    # References
    user_id: int = Field(index=True, description="Reference to users.id")
    mosaic_id: int = Field(index=True, description="Reference to mosaics.id")

    # Event type
    event_type: EventType = Field(index=True)

    # Event routing: source (node + session) -> target (node + session)
    # Note: node_id is technically redundant (derivable from session_id),
    # but kept for clearer business semantics and direct querying
    source_node_id: str = Field(max_length=100, index=True, description="Reference to nodes.node_id - Source node")
    source_session_id: str = Field(index=True, description="Reference to sessions.session_id - Source session")
    target_node_id: str = Field(max_length=100, index=True, description="Reference to nodes.node_id - Target node")
    target_session_id: str = Field(index=True, description="Reference to sessions.session_id - Target session")

    # Payload (JSON value determined by event_type)
    # Can be any valid JSON value: dict, list, str, int, float, bool, or None
    payload: Any = Field(default=None, sa_column=Column(JSON))
