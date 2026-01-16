"""Session model for Claude Code conversations"""

from sqlmodel import Field, Column, JSON
from datetime import datetime
from typing import Optional
from .base import BaseModel
from ..enum import SessionMode, SessionStatus, LLMModel, RuntimeStatus


class Session(BaseModel, table=True):
    """
    Session model - represents a Claude Code conversation session.

    A session is an interactive conversation context between a user and a Claude Code node.
    Each session maintains its own message history, token statistics, and configuration.
    """

    __tablename__ = "sessions"

    # Unique identifier
    session_id: str = Field(
        index=True,
        unique=True,
        description="UUID for session, used in WebSocket and API"
    )

    # References
    user_id: int = Field(
        index=True,
        description="Reference to users.id - Owner of this session"
    )
    mosaic_id: int = Field(
        index=True,
        description="Reference to mosaics.id - Mosaic instance this session belongs to"
    )
    node_id: str = Field(
        max_length=100,
        index=True,
        description="Reference to nodes.node_id - Claude Code node running this session"
    )

    # Session configuration
    mode: SessionMode = Field(
        description="Session mode: background (publish events) | program (node guidance, no events) | chat (interactive)"
    )
    model: Optional[LLMModel] = Field(
        default=None,
        description="LLM model for this session"
    )

    # Status
    status: SessionStatus = Field(
        description="Session status"
    )
    runtime_status: RuntimeStatus = Field(
        default=RuntimeStatus.IDLE,
        description="Runtime processing status (idle/busy)"
    )

    # Session metadata
    topic: Optional[str] = Field(
        default=None,
        max_length=80,
        index=True,
        description="Auto-generated session topic/title (maximum 80 characters)"
    )

    # Statistics
    message_count: int = Field(
        default=0,
        description="Total number of messages in this session"
    )
    total_input_tokens: int = Field(
        default=0,
        description="Cumulative input tokens consumed"
    )
    total_output_tokens: int = Field(
        default=0,
        description="Cumulative output tokens generated"
    )
    total_cost_usd: float = Field(
        default=0.0,
        description="Cumulative cost in USD"
    )

    # Additional timestamps (beyond BaseModel's created_at, updated_at, deleted_at)
    last_activity_at: Optional[datetime] = Field(
        default=None,
        description="Last time a message was sent or received"
    )
    closed_at: Optional[datetime] = Field(
        default=None,
        description="When the session was closed"
    )
