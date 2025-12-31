"""Node-related schemas for API input/output"""

from datetime import datetime
from pydantic import BaseModel, Field

from ..enum import NodeType, NodeStatus


# ==================== Input Schemas ====================

class CreateNodeRequest(BaseModel):
    """Create node request"""

    node_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z][a-zA-Z0-9_-]*$",
        description="Unique node identifier within mosaic (must start with letter, then alphanumeric, underscore, hyphen)",
        examples=["scheduler_1", "emailNode", "aggregator"]
    )
    node_type: NodeType = Field(
        ...,
        description="Node type (currently only claude_code supported)",
        examples=[NodeType.CLAUDE_CODE]
    )
    description: str | None = Field(
        None,
        max_length=1000,
        description="Node description",
        examples=["A scheduler node that triggers daily tasks"]
    )
    config: dict | None = Field(
        None,
        description="Node configuration (JSON object, node-type-specific)",
        examples=[{"mcp_servers": {"chroma": {"url": "http://localhost:8001"}}}]
    )
    auto_start: bool = Field(
        False,
        description="Auto-start when mosaic starts",
        examples=[True, False]
    )


class UpdateNodeRequest(BaseModel):
    """Update node request (all fields optional, at least one required)"""

    description: str | None = Field(
        None,
        max_length=1000,
        description="New node description",
        examples=["Updated description"]
    )
    config: dict | None = Field(
        None,
        description="New node configuration (JSON object, node-type-specific)",
        examples=[{"mcp_servers": {"chroma": {"url": "http://localhost:8002"}}}]
    )
    auto_start: bool | None = Field(
        None,
        description="New auto-start setting",
        examples=[True, False]
    )


# ==================== Output Schemas ====================

class NodeOut(BaseModel):
    """Node output schema (includes runtime status and statistics)"""

    id: int = Field(..., description="Node database ID")
    user_id: int = Field(..., description="Owner user ID")
    mosaic_id: int = Field(..., description="Mosaic ID this node belongs to")
    node_id: str = Field(..., description="Unique node identifier within mosaic")
    node_type: NodeType = Field(..., description="Node type")
    description: str | None = Field(None, description="Node description")
    config: dict = Field(..., description="Node configuration (JSON object, node-type-specific)")
    auto_start: bool = Field(..., description="Auto-start when mosaic starts")
    status: NodeStatus = Field(..., description="Node runtime status")
    active_session_count: int = Field(..., description="Number of active sessions")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")

    class Config:
        from_attributes = True  # Enable ORM mode
