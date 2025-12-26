"""Runtime utilities"""
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.node import Node


def get_node_workspace(node: 'Node', instance_path: Path) -> Path:
    """
    Calculate node workspace directory path.

    Args:
        node: Database Node instance
        instance_path: Mosaic instance path (e.g., ~/.mosaic)

    Returns:
        Node workspace path: {instance_path}/users/{user_id}/{mosaic_id}/{node.id}/
    """
    workspace = instance_path / "users" / str(node.user_id) / str(node.mosaic_id) / str(node.id)
    return workspace
