"""Workspace API schemas"""
from pydantic import BaseModel, Field
from typing import Literal


class WorkspaceEntry(BaseModel):
    """File or directory entry in workspace"""
    name: str = Field(..., description="File or directory name")
    path: str = Field(..., description="Relative path from workspace root")
    type: Literal["file", "directory"] = Field(..., description="Entry type")
    size: int = Field(..., description="File size in bytes (0 for directories)")
    modified_at: str = Field(..., description="Last modified timestamp (ISO 8601)")


class WorkspaceTreeResponse(BaseModel):
    """Directory listing response"""
    entries: list[WorkspaceEntry] = Field(default_factory=list)
    current_path: str = Field(..., description="Current directory path")


class WorkspaceFileResponse(BaseModel):
    """File content response"""
    path: str = Field(..., description="File path")
    content: str = Field(..., description="File content (text)")
    size: int = Field(..., description="File size in bytes")
    is_truncated: bool = Field(..., description="Whether content was truncated")
    mime_type: str = Field(..., description="MIME type of the file")
