"""Mosaic API request/response schemas"""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class MosaicCreate(BaseModel):
    """Schema for creating a new mosaic instance"""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class MosaicUpdate(BaseModel):
    """Schema for updating a mosaic instance"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class MosaicResponse(BaseModel):
    """Schema for mosaic instance API response"""

    id: int
    user_id: int
    name: str
    description: str | None
    status: Literal["running", "stopped"] | None = Field(None, description="Runtime status: running or stopped (not persisted in database)")
    node_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
