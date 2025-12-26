"""Workspace file management API"""
from fastapi import APIRouter, Depends, Query

from ..schemas.workspace import WorkspaceTreeResponse, WorkspaceFileResponse
from ..services.workspace_service import WorkspaceService
from .deps import CurrentUser, SessionDep

router = APIRouter()


@router.get("/nodes/{node_id}/workspace/tree", response_model=WorkspaceTreeResponse)
async def list_workspace_directory(
    node_id: int,
    current_user: CurrentUser,
    db: SessionDep,
    path: str = Query("", description="Relative path from workspace root")
):
    """
    List directory contents in node's workspace.

    Args:
        node_id: Node database ID
        path: Relative path from workspace root (default: root directory)
        current_user: Authenticated user
        db: Database session

    Returns:
        Directory listing with entries

    Security:
        - User must own the node
        - Path must be within workspace
        - Sensitive files are filtered out
    """
    return await WorkspaceService.list_directory(
        db=db,
        node_id=node_id,
        user_id=current_user.id,
        path=path
    )


@router.get("/nodes/{node_id}/workspace/file", response_model=WorkspaceFileResponse)
async def read_workspace_file(
    node_id: int,
    current_user: CurrentUser,
    db: SessionDep,
    path: str = Query(..., description="Relative file path from workspace root")
):
    """
    Read file content from node's workspace.

    Args:
        node_id: Node database ID
        path: Relative file path from workspace root
        current_user: Authenticated user
        db: Database session

    Returns:
        File content (truncated if larger than 1MB)

    Security:
        - User must own the node
        - Path must be within workspace
        - Sensitive files are blocked
        - Binary files cannot be previewed
        - Large files are truncated
    """
    return await WorkspaceService.read_file(
        db=db,
        node_id=node_id,
        user_id=current_user.id,
        path=path
    )
