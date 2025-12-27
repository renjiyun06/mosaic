"""Node-related data models"""
from sqlmodel import Field, Column, Text, Index
from sqlalchemy import text
from .base import BaseModel
from ..enums import NodeType


class Node(BaseModel, table=True):
    """Node table - stores node definitions for Mosaic instances"""

    __tablename__ = "nodes"
    __table_args__ = (
        # Partial unique index: only enforce uniqueness for non-deleted records
        Index(
            "idx_active_nodes_unique",
            "mosaic_id",
            "node_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    user_id: int = Field(index=True, description="Reference to users.id")
    mosaic_id: int = Field(index=True, description="Reference to mosaics.id")
    node_id: str = Field(max_length=100, index=True, description="Unique node identifier within mosaic")
    node_type: NodeType = Field(description="Node type")
    description: str | None = Field(default=None, max_length=1000, description="Node description")
    mcp_servers: str = Field(
        default="{}",
        sa_column=Column(Text),
        description="MCP servers configuration (JSON object)"
    )
    auto_start: bool = Field(default=False, description="Auto-start when mosaic starts")

    def get_identifier_for_agent(self) -> str:
        """
        Get the node identifier to show to AI agents in system prompts.

        This method generates the node name that will be shown to AI agents
        in their system prompts (e.g., "You are now a node operating within
        the Mosaic Event Mesh system. [Identity] Node ID: {name}").

        This is NOT for frontend UI display - frontend should use node_id
        or custom display logic based on node_type and other metadata.

        Returns:
            Node identifier string for agent prompts (currently just returns node_id)
        """
        return self.node_id
