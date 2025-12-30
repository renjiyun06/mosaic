"""Session routing related schemas for API input/output"""

from datetime import datetime
from pydantic import BaseModel, Field


# ==================== Output Schemas ====================

class SessionRoutingOut(BaseModel):
    """Session routing output schema"""

    local_node_id: str = Field(..., description="Local node identifier")
    local_session_id: str = Field(..., description="Local session identifier (UUID)")
    remote_node_id: str = Field(..., description="Remote node identifier")
    remote_session_id: str = Field(..., description="Remote session identifier (UUID)")
    created_at: datetime = Field(..., description="Routing creation time")

    class Config:
        from_attributes = True  # Enable ORM mode
