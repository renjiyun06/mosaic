"""Connection schemas for API requests and responses"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from ..enums import SessionAlignment


class ConnectionCreateRequest(BaseModel):
    """Request schema for creating a new connection"""

    source_node_id: str = Field(..., max_length=100, description="Source node ID")
    target_node_id: str = Field(..., max_length=100, description="Target node ID")
    session_alignment: SessionAlignment = Field(
        default=SessionAlignment.TASKING,
        description="Session alignment strategy",
    )
    description: Optional[str] = Field(None, max_length=500, description="Connection description")

    @field_validator("description")
    @classmethod
    def convert_empty_string_to_none(cls, v: Optional[str]) -> Optional[str]:
        """Convert empty strings to None"""
        if v is not None and v.strip() == "":
            return None
        return v


class ConnectionUpdateRequest(BaseModel):
    """Request schema for updating a connection"""

    session_alignment: Optional[SessionAlignment] = Field(
        None, description="Session alignment strategy"
    )
    description: Optional[str] = Field(None, max_length=500, description="Connection description")

    @field_validator("description")
    @classmethod
    def convert_empty_string_to_none(cls, v: Optional[str]) -> Optional[str]:
        """Convert empty strings to None"""
        if v is not None and v.strip() == "":
            return None
        return v


class ConnectionResponse(BaseModel):
    """Response schema for connection data"""

    id: int
    user_id: int
    mosaic_id: int
    source_node_id: str
    target_node_id: str
    session_alignment: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
