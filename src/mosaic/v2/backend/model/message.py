"""Message model for session chat messages"""

from typing import Any
from sqlmodel import Field, Column, JSON
from .base import BaseModel
from ..enum import MessageRole, MessageType


class Message(BaseModel, table=True):
    """
    Message model - stores all session messages.

    The message_type field determines the structure of the payload.
    Payload can be any valid JSON value (dict, list, str, int, float, bool, or None).

    Example message types and their payload structures:
    - user_message: {"message": "user input text"}
    - assistant_text: {"message": "assistant response text"}
    - assistant_thinking: {"message": "thinking process text"}
    - assistant_tool_use: {"tool_name": "ToolName", "tool_input": {...}}
    - assistant_result: {
        "message": "result summary",
        "total_cost_usd": 0.05,
        "total_input_tokens": 1000,
        "total_output_tokens": 500,
        "cost_usd": 0.02,
        "usage": {"input_tokens": 200, "output_tokens": 100}
      }
    - system_message: {"message": "system notification"}

    Note: Actual MessageType enum values to be defined during implementation.
    """

    __tablename__ = "messages"

    # Unique identifier
    message_id: str = Field(
        index=True,
        unique=True,
        description="UUID for message"
    )

    # References
    user_id: int = Field(
        index=True,
        description="Reference to users.id"
    )
    mosaic_id: int = Field(
        index=True,
        description="Reference to mosaics.id"
    )
    node_id: str = Field(
        max_length=100,
        index=True,
        description="Reference to nodes.node_id"
    )
    session_id: str = Field(
        index=True,
        description="Reference to sessions.session_id - Parent session this message belongs to"
    )

    # Message metadata
    role: MessageRole = Field(
        description="Message role"
    )
    message_type: MessageType = Field(
        description="Message type"
    )

    # Payload (JSON value determined by message_type)
    # Can be any valid JSON value: dict, list, str, int, float, bool, or None
    payload: Any = Field(
        default=None,
        sa_column=Column(JSON),
        description="Message payload (structure determined by message_type)"
    )

    # Sequence number (maintained by application, not database auto-increment)
    sequence: int = Field(
        description="Message order in session (application-managed sequence, starts from 1)"
    )
