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


# ==================== Workspace Schemas ====================

class WorkspaceStats(BaseModel):
    """Workspace statistics"""

    total_files: int = Field(..., description="Total number of files")
    total_directories: int = Field(..., description="Total number of directories")
    total_size_bytes: int = Field(..., description="Total size in bytes")


class WorkspaceInfoOut(BaseModel):
    """Workspace information output schema"""

    workspace_path: str = Field(..., description="Absolute path to workspace directory")
    node_id: str = Field(..., description="Node identifier")
    mosaic_id: int = Field(..., description="Mosaic ID")
    exists: bool = Field(..., description="Whether workspace directory exists")
    readable: bool = Field(..., description="Whether workspace is readable")
    stats: WorkspaceStats | None = Field(None, description="Workspace statistics (optional)")


class WorkspaceFileItem(BaseModel):
    """Workspace file or directory item"""

    name: str = Field(..., description="File or directory name")
    path: str = Field(..., description="Relative path from workspace root (e.g., '/src/app.tsx')")
    type: str = Field(..., description="Item type: 'file' or 'directory'")
    size: int | None = Field(None, description="File size in bytes (null for directories)")
    modified_at: datetime = Field(..., description="Last modification time")
    extension: str | None = Field(None, description="File extension (e.g., 'tsx', 'json'), null for directories")
    mime_type: str | None = Field(None, description="MIME type (e.g., 'text/plain'), null for directories")
    children: list["WorkspaceFileItem"] | None = Field(
        None,
        description="Child items if recursive mode is enabled and this is a directory"
    )


class WorkspaceFilesOut(BaseModel):
    """Workspace files list output schema"""

    path: str = Field(..., description="Requested relative path")
    absolute_path: str = Field(..., description="Absolute path on server (for debugging)")
    items: list[WorkspaceFileItem] = Field(..., description="List of files and directories")


class WorkspaceFileContentOut(BaseModel):
    """Workspace file content output schema"""

    path: str = Field(..., description="Relative file path")
    name: str = Field(..., description="File name")
    size: int = Field(..., description="File size in bytes")
    encoding: str = Field(..., description="Content encoding: 'utf-8', 'base64', or 'binary'")
    content: str = Field(..., description="File content (text or base64 encoded)")
    truncated: bool = Field(..., description="Whether content was truncated due to size limit")
    mime_type: str | None = Field(None, description="MIME type")
    language: str | None = Field(None, description="Programming language (inferred from extension)")


# ==================== Code Server Schemas ====================

class CodeServerStatusOut(BaseModel):
    """Code server instance information and status

    Used for both starting instances and querying status.
    When instance is running, all fields are populated.
    When instance is stopped, port/url/started_at are None.
    """

    status: str = Field(..., description="Instance status: 'running', 'stopped', 'starting', 'error'")
    port: int | None = Field(None, description="Port number (null if not running)")
    url: str | None = Field(None, description="Full URL to access code-server (null if not running)")
    started_at: datetime | None = Field(None, description="Timestamp when instance was started (null if not running)")
    ref_count: int = Field(0, description="Number of active connections/sessions using this instance")
