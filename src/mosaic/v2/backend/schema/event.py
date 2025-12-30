"""Event-related schemas for API input/output"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

from ..enum import EventType


# ==================== Output Schemas ====================

class EventListOut(BaseModel):
    """Event list output schema (brief information for list view)"""

    event_id: str = Field(..., description="Event unique identifier (UUID)")
    event_type: EventType = Field(..., description="Event type")
    source_node_id: str = Field(..., description="Source node identifier")
    source_session_id: str = Field(..., description="Source session identifier")
    target_node_id: str = Field(..., description="Target node identifier")
    target_session_id: str = Field(..., description="Target session identifier")
    created_at: datetime = Field(..., description="Event creation time")

    class Config:
        from_attributes = True  # Enable ORM mode


class EventDetailOut(BaseModel):
    """Event detail output schema (complete information including payload)"""

    event_id: str = Field(..., description="Event unique identifier (UUID)")
    event_type: EventType = Field(..., description="Event type")
    source_node_id: str = Field(..., description="Source node identifier")
    source_session_id: str = Field(..., description="Source session identifier")
    target_node_id: str = Field(..., description="Target node identifier")
    target_session_id: str = Field(..., description="Target session identifier")
    payload: Any = Field(None, description="Event payload (JSON data)")
    created_at: datetime = Field(..., description="Event creation time")

    class Config:
        from_attributes = True  # Enable ORM mode
