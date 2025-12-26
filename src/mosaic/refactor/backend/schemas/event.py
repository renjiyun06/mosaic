from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class EventResponse(BaseModel):
    """Event response for frontend"""
    id: int
    event_id: str
    mosaic_id: int
    source_node_id: int
    target_node_id: int
    event_type: str
    upstream_session_id: Optional[str]
    downstream_session_id: Optional[str]
    payload: dict
    event_created_at: datetime
    created_at: datetime


class EventListResponse(BaseModel):
    """Paginated event list"""
    events: list[EventResponse]
    total: int
    limit: int
    offset: int
