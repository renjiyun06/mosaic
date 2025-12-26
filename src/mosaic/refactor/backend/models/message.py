"""Message model for session chat messages"""

from sqlmodel import Field, Column, Text
from typing import Optional
from .base import BaseModel


class Message(BaseModel, table=True):
    """
    Message model - stores all session messages.

    Each message is stored as a JSON string in the content field.
    The message type determines the structure of the JSON content.

    Message types and their content structure:
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
    """

    __tablename__ = "messages"

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Unique identifier
    message_id: str = Field(
        index=True,
        unique=True,
        description="UUID for message"
    )

    # Foreign key
    session_id: str = Field(
        foreign_key="sessions.session_id",
        index=True,
        description="Parent session this message belongs to"
    )

    # Message metadata
    role: str = Field(
        description="Message role: user | assistant | system"
    )
    type: str = Field(
        description="Message type: user_message | assistant_text | assistant_thinking | assistant_tool_use | assistant_result | system_message"
    )

    # Message content (JSON string)
    content: str = Field(
        sa_column=Column(Text),
        description="JSON string containing message data (structure depends on type)"
    )

    # Sequence number
    sequence: int = Field(
        description="Message order in session (auto-increment per session, starts from 1)"
    )
