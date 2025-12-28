"""Node management API endpoints"""

import logging
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Annotated

from ..schema.response import SuccessResponse
from ..schema.node import (
    CreateNodeRequest,
    UpdateNodeRequest,
    NodeOut,
)
from ..model import Mosaic, Node, Session
from ..dep import get_db_session, get_current_user
from ..model.user import User
from ..exception import ConflictError, NotFoundError, PermissionError, ValidationError, InternalError
from ..enum import NodeStatus, SessionStatus

logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(prefix="/mosaics/{mosaic_id}/nodes", tags=["Node Management"])


# ==================== Type Aliases ====================

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ==================== API Endpoints ====================

@router.post("", response_model=SuccessResponse[NodeOut])
async def create_node(
    mosaic_id: int,
    request: CreateNodeRequest,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Create a new node in a mosaic instance

    Business logic:
    1. Verify mosaic exists and ownership (mosaic.user_id == current_user.id)
    2. Validate node_id uniqueness within mosaic:
       - Query nodes WHERE mosaic_id=X AND node_id=Y AND deleted_at IS NULL
       - If exists, raise ConflictError
    3. Create Node record in database:
       - user_id = current_user.id
       - mosaic_id = mosaic_id
       - node_id, node_type, description, mcp_servers (default={}), auto_start from request
    4. Create node working directory:
       - Path: {instance_path}/users/{user_id}/{mosaic_id}/{node.id}/
       - This provides isolated workspace for the node
    5. Return created node information with initial status (STOPPED, 0 sessions)

    Raises:
        NotFoundError: Mosaic not found or deleted
        PermissionError: Current user is not the mosaic owner
        ConflictError: Node with same node_id already exists in this mosaic
        InternalError: Failed to create node directory
    """
    # TODO: Implement
    pass


@router.get("", response_model=SuccessResponse[list[NodeOut]])
async def list_nodes(
    mosaic_id: int,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """List all nodes in a mosaic instance

    Business logic:
    1. Verify mosaic exists and ownership
    2. Query all nodes WHERE mosaic_id=X AND deleted_at IS NULL
    3. Order by created_at ASC (creation order)
    4. For each node:
       - Count active sessions: COUNT sessions WHERE node_id=X AND deleted_at IS NULL AND status='active'
       - Get runtime status from RuntimeManager.get_node_status(mosaic, node)
    5. Return complete list with statistics (no pagination)

    Raises:
        NotFoundError: Mosaic not found or deleted
        PermissionError: Current user is not the mosaic owner
    """
    # TODO: Implement
    pass


@router.get("/{node_id}", response_model=SuccessResponse[NodeOut])
async def get_node(
    mosaic_id: int,
    node_id: str,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Get detailed information of a specific node

    Business logic:
    1. Verify mosaic exists and ownership
    2. Query node WHERE mosaic_id=X AND node_id=Y AND deleted_at IS NULL
    3. If not found, raise NotFoundError
    4. Count active sessions: COUNT sessions WHERE node_id=X AND deleted_at IS NULL AND status='active'
    5. Get runtime status from RuntimeManager.get_node_status(mosaic, node)
    6. Construct NodeOut and return

    Raises:
        NotFoundError: Mosaic or node not found or deleted
        PermissionError: Current user is not the mosaic owner
    """
    # TODO: Implement
    pass


@router.patch("/{node_id}", response_model=SuccessResponse[NodeOut])
async def update_node(
    mosaic_id: int,
    node_id: str,
    request: UpdateNodeRequest,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Update node configuration

    Business logic:
    1. Validate request: at least one field (description, mcp_servers, or auto_start) must be provided
    2. Verify mosaic exists and ownership
    3. Query node and verify it exists
    4. Verify node is stopped (check RuntimeManager.get_node_status())
       - Cannot modify running node configuration
    5. Update provided fields:
       - description (if provided)
       - mcp_servers (if provided)
       - auto_start (if provided)
    6. Update updated_at timestamp
    7. Return updated node information

    Raises:
        ValidationError: No fields provided for update or node is running
        NotFoundError: Mosaic or node not found or deleted
        PermissionError: Current user is not the mosaic owner
    """
    # TODO: Implement
    pass


@router.delete("/{node_id}", response_model=SuccessResponse[None])
async def delete_node(
    mosaic_id: int,
    node_id: str,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Soft delete a node

    Business logic:
    1. Verify mosaic exists and ownership
    2. Query node and verify it exists
    3. Validate deletion prerequisites:
       - Node must be stopped (check RuntimeManager.get_node_status())
       - Node working directory must be empty
    4. Set deleted_at = datetime.now() (soft delete)
    5. Delete node directory: {instance_path}/users/{user_id}/{mosaic_id}/{node.id}/
       - Only if directory is empty
       - If not empty, raise ValidationError
    6. Commit and return success

    Note: Node deletion does not delete related sessions, connections, or subscriptions.
          They remain in database for historical reference but become inactive.

    Raises:
        NotFoundError: Mosaic or node not found or deleted
        PermissionError: Current user is not the mosaic owner
        ValidationError: Node is running or directory is not empty
        InternalError: Failed to delete node directory
    """
    # TODO: Implement
    pass


@router.post("/{node_id}/start", response_model=SuccessResponse[NodeOut])
async def start_node(
    mosaic_id: int,
    node_id: str,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Start a node (runtime operation)

    Business logic:
    1. Verify mosaic exists and ownership
    2. Query node and verify it exists
    3. Verify mosaic is running:
       - Check RuntimeManager.get_mosaic_status(mosaic)
       - If mosaic is not running, raise ValidationError
    4. Check if node is already running (idempotent):
       - Get status from RuntimeManager.get_node_status(mosaic, node)
       - If already running, log and return current status
    5. Start node via RuntimeManager.start_node(mosaic, node, timeout=30.0)
    6. Return node information with updated status

    Note: This operation is idempotent (starting an already-running node succeeds)

    Raises:
        NotFoundError: Mosaic or node not found or deleted
        PermissionError: Current user is not the mosaic owner
        ValidationError: Mosaic is not running (nodes can only start in running mosaic)
        RuntimeError: Node start operation failed (from RuntimeManager)
    """
    # TODO: Implement
    pass


@router.post("/{node_id}/stop", response_model=SuccessResponse[NodeOut])
async def stop_node(
    mosaic_id: int,
    node_id: str,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Stop a node (runtime operation)

    Business logic:
    1. Verify mosaic exists and ownership
    2. Query node and verify it exists
    3. Check if node is already stopped (idempotent):
       - Get status from RuntimeManager.get_node_status(mosaic, node)
       - If already stopped, log and return current status
    4. Stop node via RuntimeManager.stop_node(mosaic, node, timeout=60.0)
    5. Return node information with updated status

    Note: This operation is idempotent (stopping an already-stopped node succeeds)

    Raises:
        NotFoundError: Mosaic or node not found or deleted
        PermissionError: Current user is not the mosaic owner
        RuntimeError: Node stop operation failed (from RuntimeManager)
    """
    # TODO: Implement
    pass
