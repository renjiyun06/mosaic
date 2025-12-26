"""Session model for Claude Code conversations"""

from sqlmodel import Field, Column, JSON
from datetime import datetime
from typing import Optional
from .base import BaseModel


class Session(BaseModel, table=True):
    """
    Session model - represents a Claude Code conversation session.

    A session is an interactive conversation context between a user and a Claude Code node.
    Each session maintains its own message history, token statistics, and configuration.
    """

    __tablename__ = "sessions"

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Unique identifier
    session_id: str = Field(
        index=True,
        unique=True,
        description="UUID for session, used in WebSocket and API"
    )

    # Foreign keys
    user_id: int = Field(
        foreign_key="users.id",
        index=True,
        description="Owner of this session"
    )
    mosaic_id: int = Field(
        foreign_key="mosaics.id",
        index=True,
        description="Mosaic instance this session belongs to"
    )
    node_id: int = Field(
        foreign_key="nodes.id",
        index=True,
        description="Claude Code node running this session"
    )

    # Session configuration
    mode: str = Field(
        default="background",
        description="Session mode: background (publish events) | program (node guidance, no events) | chat (interactive) - see SessionMode enum"
    )
    model: Optional[str] = Field(
        default=None,
        description="Claude model: sonnet | opus | haiku (see ClaudeModel enum, inherits from node config if not set)"
    )
    config: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Additional session configuration (MCP servers, hooks, etc.)"
    )

    # Status
    status: str = Field(
        default="active",
        description="Session status: active | closed | archived (see SessionStatus enum)"
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
    last_activity_at: datetime = Field(
        default_factory=datetime.now,
        description="Last time a message was sent or received"
    )
    closed_at: Optional[datetime] = Field(
        default=None,
        description="When the session was closed"
    )
