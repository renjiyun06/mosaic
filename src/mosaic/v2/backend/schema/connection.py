"""Connection-related schemas for API input/output"""

from datetime import datetime
from pydantic import BaseModel, Field

from ..enum import SessionAlignment


# ==================== Input Schemas ====================

class CreateConnectionRequest(BaseModel):
    """Create connection request"""

    source_node_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Source node identifier (event emitter)",
        examples=["scheduler_1", "claude_node"]
    )
    target_node_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Target node identifier (event receiver)",
        examples=["aggregator", "email_node"]
    )
    session_alignment: SessionAlignment = Field(
        ...,
        description="Session alignment strategy (mirroring or tasking)",
        examples=[SessionAlignment.MIRRORING, SessionAlignment.TASKING]
    )
    description: str | None = Field(
        None,
        max_length=500,
        description="Connection description",
        examples=["Routes scheduler events to aggregator"]
    )


class UpdateConnectionRequest(BaseModel):
    """Update connection request (all fields optional, at least one required)"""

    session_alignment: SessionAlignment | None = Field(
        None,
        description="New session alignment strategy",
        examples=[SessionAlignment.MIRRORING, SessionAlignment.TASKING]
    )
    description: str | None = Field(
        None,
        max_length=500,
        description="New connection description",
        examples=["Updated connection description"]
    )


# ==================== Output Schemas ====================

class ConnectionOut(BaseModel):
    """Connection output schema"""

    id: int = Field(..., description="Connection database ID")
    user_id: int = Field(..., description="Owner user ID")
    mosaic_id: int = Field(..., description="Mosaic ID this connection belongs to")
    source_node_id: str = Field(..., description="Source node identifier")
    target_node_id: str = Field(..., description="Target node identifier")
    session_alignment: SessionAlignment = Field(..., description="Session alignment strategy")
    description: str | None = Field(None, description="Connection description")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")

    class Config:
        from_attributes = True  # Enable ORM mode
