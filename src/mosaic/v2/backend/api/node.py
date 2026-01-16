"""Node management API endpoints"""

import logging
from pathlib import Path
from datetime import datetime
import mimetypes
import base64
import os

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Annotated

from ..schema.response import SuccessResponse
from ..schema.node import (
    CreateNodeRequest,
    UpdateNodeRequest,
    NodeOut,
    WorkspaceInfoOut,
    WorkspaceFilesOut,
    WorkspaceFileContentOut,
    CodeServerUrlOut,
)
from ..model import Mosaic, Node, Session
from ..dep import get_db_session, get_current_user
from ..model.user import User
from ..exception import ConflictError, NotFoundError, PermissionError, ValidationError, InternalError
from ..enum import NodeStatus, SessionStatus, MosaicStatus

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
       - node_id, node_type, description, config (default={}), auto_start from request
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
    logger.info(
        f"Creating node: mosaic_id={mosaic_id}, node_id={request.node_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Verify mosaic exists and ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to access this mosaic")

    # 2. Validate node_id uniqueness within mosaic
    node_check_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == request.node_id,
        Node.deleted_at.is_(None)
    )
    node_check_result = await session.execute(node_check_stmt)
    existing_node = node_check_result.scalar_one_or_none()

    if existing_node:
        logger.warning(
            f"Node with node_id={request.node_id} already exists in mosaic {mosaic_id}"
        )
        raise ConflictError(
            f"Node with node_id '{request.node_id}' already exists in this mosaic"
        )

    # 3. Create Node record in database
    node = Node(
        user_id=current_user.id,
        mosaic_id=mosaic_id,
        node_id=request.node_id,
        node_type=request.node_type,
        description=request.description,
        config=request.config or {},
        auto_start=request.auto_start
    )
    session.add(node)
    await session.flush()  # Get the ID

    logger.info(f"Node created in database: id={node.id}, node_id={node.node_id}")

    # 4. Create node working directory
    instance_path = req.app.state.instance_path
    node_dir = instance_path / "users" / str(current_user.id) / str(mosaic_id) / str(node.id)

    try:
        node_dir.mkdir(parents=True, exist_ok=False)
        logger.info(f"Node directory created: {node_dir}")
    except FileExistsError:
        logger.warning(f"Node directory already exists: {node_dir}")
    except Exception as e:
        logger.error(f"Failed to create node directory: {node_dir}, error: {e}")
        await session.rollback()
        raise InternalError(f"Failed to create node directory: {e}")

    # 5. Construct response (new node is always stopped with zero sessions)
    node_out = NodeOut(
        id=node.id,
        user_id=node.user_id,
        mosaic_id=node.mosaic_id,
        node_id=node.node_id,
        node_type=node.node_type,
        description=node.description,
        config=node.config,
        auto_start=node.auto_start,
        status=NodeStatus.STOPPED,
        active_session_count=0,
        created_at=node.created_at,
        updated_at=node.updated_at
    )

    logger.info(f"Node created successfully: id={node.id}, node_id={node.node_id}")
    return SuccessResponse(data=node_out)


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
    logger.info(f"Listing nodes: mosaic_id={mosaic_id}, user_id={current_user.id}")

    # 1. Verify mosaic exists and ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to access this mosaic")

    # 2. Query all nodes for this mosaic
    nodes_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.deleted_at.is_(None)
    ).order_by(Node.created_at.asc())

    nodes_result = await session.execute(nodes_stmt)
    nodes = nodes_result.scalars().all()

    logger.debug(f"Found {len(nodes)} nodes in mosaic {mosaic_id}")

    # 3. Get RuntimeManager from app state
    runtime_manager = req.app.state.runtime_manager

    # 4. Build response with statistics for each node
    node_list = []
    for node in nodes:
        # Count active sessions
        session_count_stmt = select(func.count(Session.id)).where(
            Session.mosaic_id == mosaic_id,
            Session.node_id == node.node_id,
            Session.deleted_at.is_(None),
            Session.status == SessionStatus.ACTIVE
        )
        session_count_result = await session.execute(session_count_stmt)
        active_session_count = session_count_result.scalar() or 0

        # Get runtime status
        status = await runtime_manager.get_node_status(node)

        # Construct NodeOut
        node_out = NodeOut(
            id=node.id,
            user_id=node.user_id,
            mosaic_id=node.mosaic_id,
            node_id=node.node_id,
            node_type=node.node_type,
            description=node.description,
            config=node.config,
            auto_start=node.auto_start,
            status=status,
            active_session_count=active_session_count,
            created_at=node.created_at,
            updated_at=node.updated_at
        )
        node_list.append(node_out)

    logger.info(f"Listed {len(node_list)} nodes in mosaic {mosaic_id}")
    return SuccessResponse(data=node_list)


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
    logger.info(
        f"Getting node: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Verify mosaic exists and ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to access this mosaic")

    # 2. Query node
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(f"Node not found: mosaic_id={mosaic_id}, node_id={node_id}")
        raise NotFoundError("Node not found")

    # 3. Count active sessions
    session_count_stmt = select(func.count(Session.id)).where(
        Session.mosaic_id == mosaic_id,
        Session.node_id == node.node_id,
        Session.deleted_at.is_(None),
        Session.status == SessionStatus.ACTIVE
    )
    session_count_result = await session.execute(session_count_stmt)
    active_session_count = session_count_result.scalar() or 0

    # 4. Get runtime status
    runtime_manager = req.app.state.runtime_manager
    status = await runtime_manager.get_node_status(node)

    # 5. Construct response
    node_out = NodeOut(
        id=node.id,
        user_id=node.user_id,
        mosaic_id=node.mosaic_id,
        node_id=node.node_id,
        node_type=node.node_type,
        description=node.description,
        config=node.config,
        auto_start=node.auto_start,
        status=status,
        active_session_count=active_session_count,
        created_at=node.created_at,
        updated_at=node.updated_at
    )

    logger.info(f"Node retrieved successfully: id={node.id}, node_id={node.node_id}")
    return SuccessResponse(data=node_out)


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
    1. Validate request: at least one field (description, config, or auto_start) must be provided
    2. Verify mosaic exists and ownership
    3. Query node and verify it exists
    4. Verify node is stopped (check RuntimeManager.get_node_status())
       - Cannot modify running node configuration
    5. Update provided fields:
       - description (if provided)
       - config (if provided)
       - auto_start (if provided)
    6. Update updated_at timestamp
    7. Return updated node information

    Raises:
        ValidationError: No fields provided for update or node is running
        NotFoundError: Mosaic or node not found or deleted
        PermissionError: Current user is not the mosaic owner
    """
    logger.info(
        f"Updating node: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Validate request: at least one field must be provided
    if (request.description is None and
        request.config is None and
        request.auto_start is None):
        raise ValidationError(
            "At least one field (description, config, or auto_start) must be provided"
        )

    # 2. Verify mosaic exists and ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to access this mosaic")

    # 3. Query node
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(f"Node not found: mosaic_id={mosaic_id}, node_id={node_id}")
        raise NotFoundError("Node not found")

    # 4. Verify node is stopped
    runtime_manager = req.app.state.runtime_manager
    status = await runtime_manager.get_node_status(node)
    if status == NodeStatus.RUNNING:
        logger.warning(f"Cannot update running node: id={node.id}, node_id={node_id}")
        raise ValidationError("Cannot update running node. Please stop it first.")

    # 5. Update provided fields
    if request.description is not None:
        node.description = request.description
        logger.debug(f"Node description updated: id={node.id}")

    if request.config is not None:
        node.config = request.config
        logger.debug(f"Node config updated: id={node.id}")

    if request.auto_start is not None:
        node.auto_start = request.auto_start
        logger.debug(f"Node auto_start updated: id={node.id}, auto_start={request.auto_start}")

    # 6. Update the updated_at timestamp
    node.updated_at = datetime.now()

    # 7. Count active sessions for response
    session_count_stmt = select(func.count(Session.id)).where(
        Session.mosaic_id == mosaic_id,
        Session.node_id == node.node_id,
        Session.deleted_at.is_(None),
        Session.status == SessionStatus.ACTIVE
    )
    session_count_result = await session.execute(session_count_stmt)
    active_session_count = session_count_result.scalar() or 0

    # 8. Construct response
    node_out = NodeOut(
        id=node.id,
        user_id=node.user_id,
        mosaic_id=node.mosaic_id,
        node_id=node.node_id,
        node_type=node.node_type,
        description=node.description,
        config=node.config,
        auto_start=node.auto_start,
        status=status,  # Already retrieved, reuse it
        active_session_count=active_session_count,
        created_at=node.created_at,
        updated_at=node.updated_at
    )

    logger.info(f"Node updated successfully: id={node.id}, node_id={node_id}")
    return SuccessResponse(data=node_out)


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
    logger.info(
        f"Deleting node: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Verify mosaic exists and ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to access this mosaic")

    # 2. Query node
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(f"Node not found: mosaic_id={mosaic_id}, node_id={node_id}")
        raise NotFoundError("Node not found")

    # 3. Validate deletion prerequisites

    # Check if node is stopped
    runtime_manager = req.app.state.runtime_manager
    status = await runtime_manager.get_node_status(node)
    if status == NodeStatus.RUNNING:
        logger.warning(f"Cannot delete running node: id={node.id}, node_id={node_id}")
        raise ValidationError("Cannot delete running node. Please stop it first.")

    # Check if node directory is empty
    instance_path = req.app.state.instance_path
    node_dir = instance_path / "users" / str(current_user.id) / str(mosaic_id) / str(node.id)

    if node_dir.exists():
        contents = list(node_dir.iterdir())
        if contents:
            logger.warning(
                f"Node directory is not empty: {node_dir}, "
                f"contents={[p.name for p in contents]}"
            )
            raise ValidationError(
                "Node directory is not empty. Please ensure all data is removed first."
            )

    # 4. Soft delete (set deleted_at)
    node.deleted_at = datetime.now()
    logger.debug(f"Node soft deleted in database: id={node.id}, node_id={node_id}")

    # 5. Delete node directory
    try:
        if node_dir.exists():
            # Directory is empty (already checked above), safe to remove
            node_dir.rmdir()
            logger.info(f"Node directory deleted: {node_dir}")
        else:
            logger.warning(f"Node directory does not exist: {node_dir}")

    except Exception as e:
        logger.error(f"Failed to delete node directory: {node_dir}, error: {e}")
        await session.rollback()
        raise InternalError(f"Failed to delete node directory: {e}")

    # 6. Commit and return success
    logger.info(f"Node deleted successfully: id={node.id}, node_id={node_id}")
    return SuccessResponse(data=None)


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
    logger.info(
        f"Starting node: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Verify mosaic exists and ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to access this mosaic")

    # 2. Query node
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(f"Node not found: mosaic_id={mosaic_id}, node_id={node_id}")
        raise NotFoundError("Node not found")

    # 3. Get runtime manager
    runtime_manager = req.app.state.runtime_manager

    # Verify mosaic is running
    mosaic_status = await runtime_manager.get_mosaic_status(mosaic)
    if mosaic_status != MosaicStatus.RUNNING:
        logger.warning(
            f"Cannot start node in stopped mosaic: mosaic_id={mosaic_id}, "
            f"node_id={node_id}"
        )
        raise ValidationError(
            "Cannot start node. The mosaic is not running. Please start the mosaic first."
        )

    # 4. Check if node is already running (idempotent)
    node_status = await runtime_manager.get_node_status(node)
    if node_status == NodeStatus.RUNNING:
        logger.info(f"Node already running: id={node.id}, node_id={node_id}")
    else:
        # 5. Start node via RuntimeManager
        await runtime_manager.start_node(node, timeout=30.0)
        logger.info(f"Node started successfully: id={node.id}, node_id={node_id}")
        node_status = NodeStatus.RUNNING

    # 6. Count active sessions for response
    session_count_stmt = select(func.count(Session.id)).where(
        Session.mosaic_id == mosaic_id,
        Session.node_id == node.node_id,
        Session.deleted_at.is_(None),
        Session.status == SessionStatus.ACTIVE
    )
    session_count_result = await session.execute(session_count_stmt)
    active_session_count = session_count_result.scalar() or 0

    # 7. Construct response
    node_out = NodeOut(
        id=node.id,
        user_id=node.user_id,
        mosaic_id=node.mosaic_id,
        node_id=node.node_id,
        node_type=node.node_type,
        description=node.description,
        config=node.config,
        auto_start=node.auto_start,
        status=node_status,
        active_session_count=active_session_count,
        created_at=node.created_at,
        updated_at=node.updated_at
    )

    return SuccessResponse(data=node_out)


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
    logger.info(
        f"Stopping node: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Verify mosaic exists and ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to access this mosaic")

    # 2. Query node
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(f"Node not found: mosaic_id={mosaic_id}, node_id={node_id}")
        raise NotFoundError("Node not found")

    # 3. Get runtime manager and check status
    runtime_manager = req.app.state.runtime_manager
    node_status = await runtime_manager.get_node_status(node)

    if node_status == NodeStatus.STOPPED:
        logger.info(f"Node already stopped: id={node.id}, node_id={node_id}")
    else:
        # 4. Stop node via RuntimeManager
        await runtime_manager.stop_node(node, timeout=60.0)
        logger.info(f"Node stopped successfully: id={node.id}, node_id={node_id}")
        node_status = NodeStatus.STOPPED

    # 5. Count active sessions for response
    session_count_stmt = select(func.count(Session.id)).where(
        Session.mosaic_id == mosaic_id,
        Session.node_id == node.node_id,
        Session.deleted_at.is_(None),
        Session.status == SessionStatus.ACTIVE
    )
    session_count_result = await session.execute(session_count_stmt)
    active_session_count = session_count_result.scalar() or 0

    # 6. Construct response
    node_out = NodeOut(
        id=node.id,
        user_id=node.user_id,
        mosaic_id=node.mosaic_id,
        node_id=node.node_id,
        node_type=node.node_type,
        description=node.description,
        config=node.config,
        auto_start=node.auto_start,
        status=node_status,
        active_session_count=active_session_count,
        created_at=node.created_at,
        updated_at=node.updated_at
    )

    return SuccessResponse(data=node_out)

# ==================== Workspace API Endpoints ====================

def _validate_workspace_path(workspace_root: Path, requested_path: str) -> Path:
    """Validate and resolve a path within workspace

    Args:
        workspace_root: Workspace root directory
        requested_path: User-requested relative path

    Returns:
        Absolute path within workspace

    Raises:
        ValidationError: If path is invalid
    """
    # Normalize path (remove leading/trailing slashes)
    normalized_path = requested_path.strip("/")

    # Construct full path
    if normalized_path:
        full_path = workspace_root / normalized_path
    else:
        full_path = workspace_root

    return full_path


def _build_file_item(file_path: Path, workspace_root: Path, recursive: bool, current_depth: int, max_depth: int):
    """Build a WorkspaceFileItem from a file path

    Args:
        file_path: Absolute path to file/directory
        workspace_root: Workspace root directory
        recursive: Whether to recursively list subdirectories
        current_depth: Current recursion depth
        max_depth: Maximum recursion depth

    Returns:
        WorkspaceFileItem dict
    """
    from ..schema.node import WorkspaceFileItem

    stat = file_path.stat()
    is_dir = file_path.is_dir()

    # Calculate relative path from workspace root
    rel_path = "/" + str(file_path.relative_to(workspace_root)).replace("\\", "/")
    if rel_path == "/.":
        rel_path = "/"

    # Get file extension and MIME type
    extension = None
    mime_type = None
    if not is_dir:
        extension = file_path.suffix.lstrip(".") if file_path.suffix else None
        mime_type, _ = mimetypes.guess_type(file_path.name)

    # Build children if recursive and is directory
    children = None
    if recursive and is_dir and current_depth < max_depth:
        children = []
        try:
            # List and sort directory contents
            items = list(file_path.iterdir())
            # Sort: directories first, then files, alphabetically
            items.sort(key=lambda p: (not p.is_dir(), p.name.lower()))

            for item in items:
                try:
                    child_item = _build_file_item(
                        item, workspace_root, recursive, current_depth + 1, max_depth
                    )
                    children.append(child_item)
                except (OSError, PermissionError) as e:
                    logger.warning(f"Skipping inaccessible item: {item}, error: {e}")
                    continue
        except (OSError, PermissionError) as e:
            logger.warning(f"Failed to list directory: {file_path}, error: {e}")
            children = None

    return WorkspaceFileItem(
        name=file_path.name,
        path=rel_path,
        type="directory" if is_dir else "file",
        size=None if is_dir else stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime),
        extension=extension,
        mime_type=mime_type,
        children=children
    )


@router.get("/{node_id}/workspace", response_model=SuccessResponse[WorkspaceInfoOut])
async def get_workspace_info(
    mosaic_id: int,
    node_id: str,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Get workspace information for a node

    Business logic:
    1. Verify mosaic exists and ownership (mosaic.user_id == current_user.id)
    2. Query node and verify it exists
    3. Construct workspace path: {instance_path}/users/{user_id}/{mosaic_id}/{node.id}/
    4. Check if workspace directory exists and is readable
    5. Optionally calculate workspace statistics:
       - Count total files (recursively)
       - Count total directories (recursively)
       - Calculate total size (sum of all file sizes)
    6. Return workspace information

    Path construction:
    - instance_path: req.app.state.instance_path (e.g., /home/tomato/mosaic)
    - Workspace path: {instance_path}/users/{user_id}/{mosaic_id}/{node.id}/

    Security:
    - Only returns information about the workspace, no file listing
    - Validates ownership before revealing paths

    Raises:
        NotFoundError: Mosaic or node not found or deleted
        PermissionError: Current user is not the mosaic owner

    Returns:
        WorkspaceInfoOut: Workspace path, existence status, readability, and optional stats
    """
    logger.info(
        f"Getting workspace info: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Verify mosaic exists and ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to access this mosaic")

    # 2. Query node
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(f"Node not found: mosaic_id={mosaic_id}, node_id={node_id}")
        raise NotFoundError("Node not found")

    # 3. Construct workspace path
    instance_path = req.app.state.instance_path
    workspace_path = instance_path / "users" / str(current_user.id) / str(mosaic_id) / str(node.id)

    # 4. Check if workspace exists and is readable
    exists = workspace_path.exists()
    readable = exists and os.access(workspace_path, os.R_OK)

    # 5. Calculate statistics (optional, only if workspace exists)
    stats = None
    if exists and readable:
        try:
            total_files = 0
            total_directories = 0
            total_size_bytes = 0

            for root, dirs, files in os.walk(workspace_path):
                total_directories += len(dirs)
                total_files += len(files)
                for file in files:
                    file_path = Path(root) / file
                    try:
                        total_size_bytes += file_path.stat().st_size
                    except (OSError, PermissionError):
                        # Skip files we can't access
                        pass

            from ..schema.node import WorkspaceStats
            stats = WorkspaceStats(
                total_files=total_files,
                total_directories=total_directories,
                total_size_bytes=total_size_bytes
            )
        except Exception as e:
            logger.warning(f"Failed to calculate workspace stats: {e}")
            # Don't fail the request if stats calculation fails

    # 6. Return workspace information
    workspace_info = WorkspaceInfoOut(
        workspace_path=str(workspace_path),
        node_id=node.node_id,
        mosaic_id=mosaic_id,
        exists=exists,
        readable=readable,
        stats=stats
    )

    logger.info(f"Workspace info retrieved: path={workspace_path}, exists={exists}")
    return SuccessResponse(data=workspace_info)


@router.get("/{node_id}/workspace/files", response_model=SuccessResponse[WorkspaceFilesOut])
async def list_workspace_files(
    mosaic_id: int,
    node_id: str,
    path: str = "/",
    recursive: bool = False,
    max_depth: int = 1,
    req: Request = None,
    session: SessionDep = None,
    current_user: CurrentUserDep = None,
):
    """List files and directories in workspace

    Business logic:
    1. Verify mosaic exists and ownership
    2. Query node and verify it exists
    3. Construct base workspace path: {instance_path}/users/{user_id}/{mosaic_id}/{node.id}/
    4. Validate and sanitize requested path:
       - Remove leading/trailing slashes for normalization
       - Construct full path: base_path / requested_path
       - Resolve to absolute path using Path.resolve()
       - Security check: ensure resolved path is within workspace (prevent path traversal)
    5. Check if target path exists and is a directory
    6. List directory contents:
       - If recursive=False: Only list immediate children (files and directories)
       - If recursive=True: Recursively list up to max_depth levels
       - For each item, collect:
         * name: File/directory name
         * path: Relative path from workspace root (e.g., '/src/components/Button.tsx')
         * type: 'file' or 'directory'
         * size: File size in bytes (null for directories)
         * modified_at: Last modification timestamp
         * extension: File extension (e.g., 'tsx', 'json'), null for directories
         * mime_type: MIME type (e.g., 'text/plain'), null for directories
         * children: Child items if recursive=True and type='directory'
    7. Sort items: directories first (alphabetical), then files (alphabetical)
    8. Return file list with metadata

    Query parameters:
    - path: Relative path from workspace root (default: '/')
    - recursive: Whether to recursively list subdirectories (default: false)
    - max_depth: Maximum recursion depth if recursive=true (default: 1)

    Path traversal security:
    - MUST validate that final resolved path is within workspace directory
    - Examples of attacks to prevent:
      * path='../../etc/passwd'
      * path='/etc/passwd'
      * path='../../../secrets'
    - Implementation: Use Path.resolve() and check if resolved path starts with workspace path

    Example requests:
    - GET /mosaics/1/nodes/main/workspace/files?path=/
      → List root directory
    - GET /mosaics/1/nodes/main/workspace/files?path=/src
      → List /src directory
    - GET /mosaics/1/nodes/main/workspace/files?path=/src&recursive=true&max_depth=2
      → Recursively list /src and its subdirectories up to 2 levels

    Raises:
        NotFoundError: Mosaic, node, or requested path not found
        PermissionError: Current user is not the mosaic owner
        ValidationError: Invalid path (path traversal attempt or not a directory)

    Returns:
        WorkspaceFilesOut: List of files and directories with metadata
    """
    logger.info(
        f"Listing workspace files: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"path={path}, recursive={recursive}, user_id={current_user.id}"
    )

    # 1. Verify mosaic exists and ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to access this mosaic")

    # 2. Query node
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(f"Node not found: mosaic_id={mosaic_id}, node_id={node_id}")
        raise NotFoundError("Node not found")

    # 3. Construct workspace path
    instance_path = req.app.state.instance_path
    workspace_root = instance_path / "users" / str(current_user.id) / str(mosaic_id) / str(node.id)

    # 4. Validate and sanitize requested path
    target_path = _validate_workspace_path(workspace_root, path)

    # 5. Check if target path exists and is a directory
    if not target_path.exists():
        logger.warning(f"Path not found: {target_path}")
        raise NotFoundError(f"Path not found: {path}")

    if not target_path.is_dir():
        logger.warning(f"Path is not a directory: {target_path}")
        raise ValidationError(f"Path is not a directory: {path}")

    # 6. List directory contents
    items = []
    try:
        # List immediate children
        children = list(target_path.iterdir())
        # Sort: directories first, then files, alphabetically
        children.sort(key=lambda p: (not p.is_dir(), p.name.lower()))

        for child in children:
            try:
                item = _build_file_item(child, workspace_root, recursive, 1, max_depth)
                items.append(item)
            except (OSError, PermissionError) as e:
                logger.warning(f"Skipping inaccessible item: {child}, error: {e}")
                continue
    except (OSError, PermissionError) as e:
        logger.error(f"Failed to list directory: {target_path}, error: {e}")
        raise ValidationError(f"Failed to list directory: {e}")

    # 7. Return file list
    files_out = WorkspaceFilesOut(
        path=path,
        absolute_path=str(target_path),
        items=items
    )

    logger.info(f"Listed {len(items)} items in workspace path: {path}")
    return SuccessResponse(data=files_out)


@router.get("/{node_id}/workspace/file-content", response_model=SuccessResponse[WorkspaceFileContentOut])
async def get_workspace_file_content(
    mosaic_id: int,
    node_id: str,
    path: str,
    encoding: str = "utf-8",
    max_size: int = 1048576,  # 1MB default
    req: Request = None,
    session: SessionDep = None,
    current_user: CurrentUserDep = None,
):
    """Get file content from workspace

    Business logic:
    1. Verify mosaic exists and ownership
    2. Query node and verify it exists
    3. Construct base workspace path: {instance_path}/users/{user_id}/{mosaic_id}/{node.id}/
    4. Validate and sanitize requested path (same as list_workspace_files):
       - Construct full path: base_path / requested_path
       - Resolve to absolute path using Path.resolve()
       - Security check: ensure resolved path is within workspace
    5. Check if target path exists and is a file (not directory)
    6. Check file size:
       - If size > max_size, either:
         * Return error with file_too_large code
         * Or truncate content and set truncated=true flag
    7. Read file content based on encoding:
       - 'utf-8': Read as text, decode as UTF-8
       - 'base64': Read as binary, encode as base64 (for images, PDFs, etc.)
       - 'binary': Read as binary (use case: downloading files)
    8. Infer additional metadata:
       - mime_type: Use mimetypes.guess_type() or python-magic
       - language: Infer from file extension (e.g., '.tsx' → 'typescript', '.py' → 'python')
    9. Return file content with metadata

    Query parameters:
    - path: Relative path to file from workspace root (required)
    - encoding: Content encoding - 'utf-8' (default), 'base64', 'binary'
    - max_size: Maximum file size in bytes (default: 1048576 = 1MB)

    File size handling:
    - Check size before reading to avoid memory issues
    - If file > max_size:
      * Option 1: Raise ValidationError with 'file_too_large' code
      * Option 2: Read up to max_size bytes and set truncated=true

    Encoding selection guide:
    - Text files (.txt, .md, .py, .tsx, etc.): encoding='utf-8'
    - Binary files (.png, .jpg, .pdf, etc.): encoding='base64'

    Path traversal security:
    - Same validation as list_workspace_files
    - MUST prevent access to files outside workspace

    Example requests:
    - GET /mosaics/1/nodes/main/workspace/file-content?path=/src/app.tsx
      → Read app.tsx as UTF-8 text
    - GET /mosaics/1/nodes/main/workspace/file-content?path=/public/logo.png&encoding=base64
      → Read logo.png as base64
    - GET /mosaics/1/nodes/main/workspace/file-content?path=/large-file.txt&max_size=2097152
      → Read with 2MB size limit

    Raises:
        NotFoundError: Mosaic, node, or file not found
        PermissionError: Current user is not the mosaic owner
        ValidationError: Invalid path, path traversal attempt, target is directory, or file too large

    Returns:
        WorkspaceFileContentOut: File content with metadata (encoding, size, mime_type, etc.)
    """
    logger.info(
        f"Getting file content: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"path={path}, encoding={encoding}, user_id={current_user.id}"
    )

    # 1. Verify mosaic exists and ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to access this mosaic")

    # 2. Query node
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(f"Node not found: mosaic_id={mosaic_id}, node_id={node_id}")
        raise NotFoundError("Node not found")

    # 3. Construct workspace path
    instance_path = req.app.state.instance_path
    workspace_root = instance_path / "users" / str(current_user.id) / str(mosaic_id) / str(node.id)

    # 4. Validate and sanitize requested path
    file_path = _validate_workspace_path(workspace_root, path)

    # 5. Check if target path exists and is a file
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        raise NotFoundError(f"File not found: {path}")

    if file_path.is_dir():
        logger.warning(f"Path is a directory, not a file: {file_path}")
        raise ValidationError(f"Path is a directory, not a file: {path}")

    # 6. Check file size
    file_size = file_path.stat().st_size
    truncated = False

    if file_size > max_size:
        logger.warning(f"File size {file_size} exceeds limit {max_size}: {file_path}")
        # Option: truncate content
        truncated = True

    # 7. Read file content based on encoding
    try:
        if encoding == "utf-8":
            # Read as text
            if truncated:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(max_size)
            else:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

        elif encoding == "base64":
            # Read as binary and encode as base64
            if truncated:
                with open(file_path, "rb") as f:
                    binary_content = f.read(max_size)
            else:
                with open(file_path, "rb") as f:
                    binary_content = f.read()
            content = base64.b64encode(binary_content).decode("ascii")

        elif encoding == "binary":
            # Read as binary (return base64 encoded)
            if truncated:
                with open(file_path, "rb") as f:
                    binary_content = f.read(max_size)
            else:
                with open(file_path, "rb") as f:
                    binary_content = f.read()
            content = base64.b64encode(binary_content).decode("ascii")

        else:
            raise ValidationError(f"Unsupported encoding: {encoding}")

    except UnicodeDecodeError as e:
        logger.error(f"Failed to decode file as UTF-8: {file_path}, error: {e}")
        raise ValidationError(f"Failed to decode file as UTF-8. Try using 'base64' encoding.")
    except Exception as e:
        logger.error(f"Failed to read file: {file_path}, error: {e}")
        raise InternalError(f"Failed to read file: {e}")

    # 8. Infer metadata
    mime_type, _ = mimetypes.guess_type(file_path.name)

    # Infer language from extension
    language = None
    extension = file_path.suffix.lstrip(".")
    language_map = {
        "ts": "typescript",
        "tsx": "typescript",
        "js": "javascript",
        "jsx": "javascript",
        "py": "python",
        "java": "java",
        "cpp": "cpp",
        "c": "c",
        "go": "go",
        "rs": "rust",
        "rb": "ruby",
        "php": "php",
        "cs": "csharp",
        "swift": "swift",
        "kt": "kotlin",
        "scala": "scala",
        "sh": "bash",
        "bash": "bash",
        "zsh": "zsh",
        "fish": "fish",
        "sql": "sql",
        "html": "html",
        "css": "css",
        "scss": "scss",
        "sass": "sass",
        "less": "less",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "toml": "toml",
        "xml": "xml",
        "md": "markdown",
        "markdown": "markdown",
    }
    language = language_map.get(extension)

    # 9. Return file content with metadata
    file_content_out = WorkspaceFileContentOut(
        path=path,
        name=file_path.name,
        size=file_size,
        encoding=encoding,
        content=content,
        truncated=truncated,
        mime_type=mime_type,
        language=language
    )

    logger.info(f"File content retrieved: path={path}, size={file_size}, truncated={truncated}")
    return SuccessResponse(data=file_content_out)


# ==================== Code Server API Endpoints ====================

@router.get("/{node_id}/code-server/url", response_model=SuccessResponse[CodeServerUrlOut])
async def get_code_server_url(
    mosaic_id: int,
    node_id: str,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Get code-server URL for a node's workspace

    Business logic:
    1. Verify mosaic exists and user has permission (ownership check)
    2. Query node and verify it exists
    3. Construct workspace path: {instance_path}/users/{user_id}/{mosaic_id}/{node.id}/
    4. Build code-server URL with folder parameter
    5. Return URL for frontend to load in iframe

    Returns:
        CodeServerUrlOut: URL with folder parameter and workspace path

    Raises:
        NotFoundError: Mosaic or node not found or deleted
        PermissionError: Current user doesn't own this mosaic

    Notes:
    - Code-server instance is always running (started at application startup)
    - No need to manage instance lifecycle (no start/stop operations)
    - URL includes ?folder= parameter to open the specific workspace
    - Frontend can directly load this URL in an iframe

    Example:
    - Node workspace: /home/user/mosaic/users/1/1/5/
    - Returned URL: http://192.168.1.8:20000/?folder=/home/user/mosaic/users/1/1/5/
    """
    logger.info(
        f"Getting code-server URL: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Verify mosaic exists and ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to access this mosaic")

    # 2. Query node
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(f"Node not found: mosaic_id={mosaic_id}, node_id={node_id}")
        raise NotFoundError("Node not found")

    # 3. Construct workspace path
    instance_path = req.app.state.instance_path
    workspace_path = instance_path / "users" / str(current_user.id) / str(mosaic_id) / str(node.id)

    # 4. Get code-server configuration
    code_server_config = req.app.state.config.get('code_server', {})
    external_host = code_server_config.get('external_host', 'localhost')
    port = code_server_config.get('port', 20000)

    # 5. Build URL with folder parameter
    url = f"https://{external_host}:{port}/?folder={workspace_path}"

    logger.info(
        f"Code-server URL generated: node_db_id={node.id}, url={url}"
    )

    # 6. Return response
    url_out = CodeServerUrlOut(
        url=url,
        workspace_path=str(workspace_path)
    )

    return SuccessResponse(data=url_out)
