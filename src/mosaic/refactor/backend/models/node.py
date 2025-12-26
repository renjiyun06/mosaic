"""Node-related data models"""
from sqlmodel import Field, Column, JSON, Index
from sqlalchemy import text
from typing import Dict, Any
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

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    mosaic_id: int = Field(foreign_key="mosaics.id", index=True)
    node_id: str = Field(max_length=100, description="Unique node identifier within mosaic")
    node_type: str = Field(max_length=50, description="Node type (see NodeType enum)")
    description: str | None = Field(default=None, max_length=1000, description="Node description")
    config: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON), description="Node configuration (JSON)")
    auto_start: bool = Field(default=False, description="Auto-start when mosaic starts")

    def get_display_name(self) -> str:
        """
        Get display name for this node.

        This method generates a display name based on node type and configuration,
        ensuring consistency across frontend, backend, and AI agent prompts.

        Returns:
            Formatted display name (e.g., "node-1")

        Note:
            Currently only returns node_id. Custom formatting for EMAIL and SCHEDULER
            nodes will be added when those node types are implemented.
        """
        # TODO: Add custom formatting when EMAIL and SCHEDULER nodes are implemented
        # if self.node_type == NodeType.EMAIL:
        #     account = self.get_config_value("account")
        #     if account:
        #         return f'{self.node_id}["{account}"]'
        # elif self.node_type == NodeType.SCHEDULER:
        #     cron = self.get_config_value("cron")
        #     if cron:
        #         return f'{self.node_id}["{cron}"]'

        return self.node_id

    def get_config_value(self, key: str, default=None):
        """
        Safely get a configuration value.

        This method provides a unified way to access node configuration,
        handling the case where config might be None or missing keys.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return (self.config or {}).get(key, default)
