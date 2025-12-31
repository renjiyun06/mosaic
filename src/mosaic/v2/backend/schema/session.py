"""Session management schemas"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from ..enum import SessionMode, SessionStatus, LLMModel


# ==================== Request Schemas ====================


class CreateSessionRequest(BaseModel):
    """Request schema for creating a new session

    Note:
        - Only 'program' and 'chat' modes are allowed (background sessions are event-triggered)
        - node_id is specified in the URL path parameter
        - model defaults to SONNET if not provided
    """
    mode: SessionMode = Field(
        ...,
        description="Session mode: 'program' (instruction/guidance) or 'chat' (interactive)"
    )
    model: Optional[LLMModel] = Field(
        default=LLMModel.SONNET,
        description="LLM model for this session (defaults to SONNET)"
    )

    @field_validator('mode')
    @classmethod
    def validate_mode(cls, value: SessionMode) -> SessionMode:
        """Validate that mode is either PROGRAM or CHAT (BACKGROUND not allowed)"""
        if value not in (SessionMode.PROGRAM, SessionMode.CHAT):
            raise ValueError(
                f"Invalid session mode '{value}'. "
                "Only 'program' and 'chat' modes can be created manually. "
                "Background sessions are created automatically by event triggers."
            )
        return value


class ListSessionsRequest(BaseModel):
    """Query parameters for listing sessions

    Supports filtering by session_id, node_id, and status, with pagination
    """
    session_id: Optional[str] = Field(
        default=None,
        description="Filter by specific session ID (exact match)"
    )
    node_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Filter by node ID (exact match)"
    )
    status: Optional[SessionStatus] = Field(
        default=None,
        description="Filter by session status (active/closed/archived)"
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (starts from 1)"
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page (1-100)"
    )


# ==================== Response Schemas ====================


class SessionOut(BaseModel):
    """Response schema for session data"""

    # Primary key and identifiers
    id: int = Field(..., description="Database primary key")
    session_id: str = Field(..., description="UUID for session")

    # References
    user_id: int = Field(..., description="Owner of this session")
    mosaic_id: int = Field(..., description="Mosaic instance this session belongs to")
    node_id: str = Field(..., description="Node running this session")

    # Configuration
    mode: SessionMode = Field(..., description="Session mode")
    model: Optional[LLMModel] = Field(None, description="LLM model used")

    # Status
    status: SessionStatus = Field(..., description="Session status")

    # Statistics
    message_count: int = Field(..., description="Total number of messages")
    total_input_tokens: int = Field(..., description="Cumulative input tokens")
    total_output_tokens: int = Field(..., description="Cumulative output tokens")
    total_cost_usd: float = Field(..., description="Cumulative cost in USD")

    # Timestamps
    created_at: datetime = Field(..., description="When session was created")
    updated_at: datetime = Field(..., description="Last modification time")
    last_activity_at: datetime = Field(..., description="Last message activity time")
    closed_at: Optional[datetime] = Field(None, description="When session was closed")

    class Config:
        from_attributes = True
