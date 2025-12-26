"""Session API schemas"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

from ..enums import SessionMode, ClaudeModel


class SessionCreate(BaseModel):
    """Schema for creating a session"""

    mosaic_id: int = Field(description="Mosaic instance ID")
    node_id: int = Field(description="Claude Code node ID")
    mode: SessionMode = Field(
        default=SessionMode.CHAT,
        description="Session mode: background (publish events) | program (node guidance, no events) | chat (interactive)"
    )
    model: Optional[ClaudeModel] = Field(
        default=None,
        description="Claude model: sonnet | opus | haiku (see ClaudeModel enum)"
    )
    config: Optional[dict] = Field(
        default=None,
        description="Additional session configuration"
    )


class SessionResponse(BaseModel):
    """Schema for session response"""

    id: int
    session_id: str
    user_id: int
    mosaic_id: int
    node_id: int
    mode: str
    model: Optional[str]
    config: dict
    status: str
    message_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    created_at: datetime
    last_activity_at: datetime
    closed_at: Optional[datetime]

    # Additional fields from joins (optional)
    mosaic_name: Optional[str] = None
    node_name: Optional[str] = None

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Schema for session list response"""

    sessions: list[SessionResponse]
    total: int


class MessageResponse(BaseModel):
    """Schema for message response"""

    id: int
    message_id: str
    session_id: str
    role: str
    type: str
    content: str  # JSON string
    sequence: int
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """Schema for message list response"""

    messages: list[MessageResponse]
    total: int
