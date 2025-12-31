"""Message management schemas"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

from ..enum import MessageRole, MessageType


# ==================== Response Schemas ====================


class MessageOut(BaseModel):
    """Response schema for message data"""

    # Primary key and identifiers
    id: int = Field(..., description="Database primary key")
    message_id: str = Field(..., description="UUID for message")

    # References
    user_id: int = Field(..., description="Owner of this message")
    mosaic_id: int = Field(..., description="Mosaic instance")
    node_id: str = Field(..., description="Node that generated/received this message")
    session_id: str = Field(..., description="Session this message belongs to")

    # Message metadata
    role: MessageRole = Field(..., description="Message role (system/user/assistant)")
    message_type: MessageType = Field(..., description="Message type")

    # Payload (structure varies by message_type)
    payload: Any = Field(None, description="Message payload (JSON)")

    # Sequence
    sequence: int = Field(..., description="Message order in session (starts from 1)")

    # Timestamps
    created_at: datetime = Field(..., description="When message was created")

    class Config:
        from_attributes = True
