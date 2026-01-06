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
        - node_id specifies which node to create the session on
        - model defaults to SONNET if not provided
    """
    node_id: str = Field(
        ...,
        max_length=100,
        description="Node ID to create the session on"
    )
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
    last_activity_at: Optional[datetime] = Field(None, description="Last message activity time")
    closed_at: Optional[datetime] = Field(None, description="When session was closed")

    class Config:
        from_attributes = True


class SessionTopologyNode(BaseModel):
    """Session topology node (tree structure)"""

    # Basic session information
    session_id: str = Field(..., description="Session ID")
    node_id: str = Field(..., description="Node ID")
    status: SessionStatus = Field(..., description="Session status")

    # Tree structure
    parent_session_id: Optional[str] = Field(None, description="Parent session ID (null for root node)")
    children: list['SessionTopologyNode'] = Field(default_factory=list, description="List of child nodes")

    # Statistics
    depth: int = Field(..., description="Current node depth (0 for root node)")
    descendant_count: int = Field(..., description="Total number of descendants (all children and grandchildren)")

    # Timestamps
    created_at: datetime = Field(..., description="Session creation time")
    closed_at: Optional[datetime] = Field(None, description="Session close time")

    class Config:
        from_attributes = True


class SessionTopologyResponse(BaseModel):
    """Session topology response"""

    root_session: SessionTopologyNode = Field(..., description="Root session node (with complete tree structure)")
    total_nodes: int = Field(..., description="Total number of nodes (including root)")
    max_depth: int = Field(..., description="Maximum depth of the tree")

    class Config:
        from_attributes = True
