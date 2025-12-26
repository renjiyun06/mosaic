"""Node-related request/response schemas"""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Dict, Any
from ..enums import NodeType


# ============================================================================
# Request Schemas
# ============================================================================

class NodeCreateRequest(BaseModel):
    """Request schema for creating a node"""
    node_id: str = Field(..., max_length=100, description="Unique node identifier within mosaic")
    node_type: NodeType = Field(..., description="Node type (currently only 'cc' for Claude Code)")
    description: str | None = Field(None, max_length=1000, description="Node description")
    config: Dict[str, Any] = Field(default_factory=dict, description="Node configuration (JSON)")
    auto_start: bool = Field(default=False, description="Auto-start when mosaic starts")


class NodeUpdateRequest(BaseModel):
    """Request schema for updating a node"""
    description: str | None = Field(None, max_length=1000, description="Node description")
    config: Dict[str, Any] | None = Field(None, description="Node configuration (JSON)")
    auto_start: bool | None = Field(None, description="Auto-start when mosaic starts")


# ============================================================================
# Response Schemas
# ============================================================================

class NodeResponse(BaseModel):
    """Response schema for node data"""
    id: int
    user_id: int
    mosaic_id: int
    node_id: str
    node_type: NodeType
    description: str | None
    config: Dict[str, Any]
    auto_start: bool
    created_at: datetime
    updated_at: datetime
    status: str | None = Field(None, description="Runtime status (not persisted in database)")

    model_config = {"from_attributes": True}
