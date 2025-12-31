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
