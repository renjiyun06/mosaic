"""Mosaic management API endpoints"""

import logging
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Annotated

from ..schema.response import SuccessResponse
from ..schema.mosaic import (
    CreateMosaicRequest,
    UpdateMosaicRequest,
    MosaicOut,
)
from ..model import Mosaic, Node, Session
from ..dep import get_db_session, get_current_user
from ..model.user import User
from ..exception import ConflictError, NotFoundError, PermissionError, ValidationError, InternalError
from ..enum import MosaicStatus, SessionStatus

logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(prefix="/mosaics", tags=["Mosaic Management"])


# ==================== Type Aliases ====================

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ==================== API Endpoints ====================

@router.post("", response_model=SuccessResponse[MosaicOut])
async def create_mosaic(
    request: CreateMosaicRequest,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Create a new mosaic instance

    Business logic:
    1. Create Mosaic record in database
    2. Create mosaic directory: {instance_path}/users/{user_id}/{mosaic_id}/
    3. Return created mosaic information

    Raises:
        InternalError: Failed to create mosaic directory
    """
    logger.info(f"Creating mosaic: name={request.name}, user_id={current_user.id}")

    # 1. Create Mosaic record in database
    mosaic = Mosaic(
        user_id=current_user.id,
        name=request.name,
        description=request.description
    )
    session.add(mosaic)
    await session.flush()  # Get the ID

    logger.info(f"Mosaic created in database: id={mosaic.id}, name={mosaic.name}")

    # 3. Create mosaic directory
    instance_path = req.app.state.instance_path
    mosaic_dir = instance_path / "users" / str(current_user.id) / str(mosaic.id)

    try:
        mosaic_dir.mkdir(parents=True, exist_ok=False)
        logger.info(f"Mosaic directory created: {mosaic_dir}")
    except FileExistsError:
        logger.warning(f"Mosaic directory already exists: {mosaic_dir}")
    except Exception as e:
        logger.error(f"Failed to create mosaic directory: {mosaic_dir}, error: {e}")
        await session.rollback()
        raise InternalError(f"Failed to create mosaic directory: {e}")

    # 4. Construct response (new mosaic is always stopped, with zero counts)
    mosaic_out = MosaicOut(
        id=mosaic.id,
        user_id=mosaic.user_id,
        name=mosaic.name,
        description=mosaic.description,
        status=MosaicStatus.STOPPED,
        node_count=0,
        active_session_count=0,
        created_at=mosaic.created_at,
        updated_at=mosaic.updated_at
    )

    logger.info(f"Mosaic created successfully: id={mosaic.id}")
    return SuccessResponse(data=mosaic_out)


@router.get("", response_model=SuccessResponse[list[MosaicOut]])
async def list_mosaics(
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """List all mosaics owned by current user

    Business logic:
    1. Query all mosaics WHERE user_id = current_user.id AND deleted_at IS NULL
    2. Order by created_at DESC (newest first)
    3. For each mosaic:
       - Count nodes: COUNT nodes WHERE mosaic_id=X AND deleted_at IS NULL
       - Count active sessions: COUNT sessions WHERE mosaic_id=X AND deleted_at IS NULL AND status='active'
       - Get runtime status from RuntimeManager
    4. Return complete list with statistics (no pagination)

    Returns:
        List of all mosaics with statistics and runtime status
    """
    logger.info(f"Listing mosaics for user: user_id={current_user.id}")

    # 1. Query all mosaics for this user
    stmt = select(Mosaic).where(
        Mosaic.user_id == current_user.id,
        Mosaic.deleted_at.is_(None)
    ).order_by(Mosaic.created_at.desc())

    result = await session.execute(stmt)
    mosaics = result.scalars().all()

    logger.debug(f"Found {len(mosaics)} mosaics for user: user_id={current_user.id}")

    # 2. Get RuntimeManager from app state
    runtime_manager = req.app.state.runtime_manager

    # 3. Build response with statistics for each mosaic
    mosaic_list = []
    for mosaic in mosaics:
        # Count nodes
        node_count_stmt = select(func.count(Node.id)).where(
            Node.mosaic_id == mosaic.id,
            Node.deleted_at.is_(None)
        )
        node_count_result = await session.execute(node_count_stmt)
        node_count = node_count_result.scalar() or 0

        # Count active sessions
        session_count_stmt = select(func.count(Session.id)).where(
            Session.mosaic_id == mosaic.id,
            Session.deleted_at.is_(None),
            Session.status == SessionStatus.ACTIVE
        )
        session_count_result = await session.execute(session_count_stmt)
        active_session_count = session_count_result.scalar() or 0

        # Get runtime status
        status = await runtime_manager.get_mosaic_status(mosaic)

        # Construct MosaicOut
        mosaic_out = MosaicOut(
            id=mosaic.id,
            user_id=mosaic.user_id,
            name=mosaic.name,
            description=mosaic.description,
            status=status,
            node_count=node_count,
            active_session_count=active_session_count,
            created_at=mosaic.created_at,
            updated_at=mosaic.updated_at
        )
        mosaic_list.append(mosaic_out)

    logger.info(
        f"Listed {len(mosaic_list)} mosaics for user: user_id={current_user.id}"
    )
    return SuccessResponse(data=mosaic_list)


@router.get("/{mosaic_id}", response_model=SuccessResponse[MosaicOut])
async def get_mosaic(
    mosaic_id: int,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Get detailed information of a specific mosaic

    Business logic:
    1. Query mosaic by ID (check deleted_at IS NULL)
    2. Verify ownership: mosaic.user_id == current_user.id
    3. Count related resources:
       - node_count: COUNT nodes WHERE mosaic_id=X AND deleted_at IS NULL
       - active_session_count: COUNT sessions WHERE mosaic_id=X AND deleted_at IS NULL AND status='active'
    4. Get runtime status from RuntimeManager
    5. Construct MosaicOut and return

    Raises:
        NotFoundError: Mosaic not found or deleted
        PermissionError: Current user is not the owner
    """
    logger.info(f"Getting mosaic: id={mosaic_id}, user_id={current_user.id}")

    # 1. Query mosaic by ID
    stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    mosaic = result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    # 2. Verify ownership
    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to access this mosaic")

    # 3. Count nodes
    node_count_stmt = select(func.count(Node.id)).where(
        Node.mosaic_id == mosaic.id,
        Node.deleted_at.is_(None)
    )
    node_count_result = await session.execute(node_count_stmt)
    node_count = node_count_result.scalar() or 0

    # 4. Count active sessions
    session_count_stmt = select(func.count(Session.id)).where(
        Session.mosaic_id == mosaic.id,
        Session.deleted_at.is_(None),
        Session.status == SessionStatus.ACTIVE
    )
    session_count_result = await session.execute(session_count_stmt)
    active_session_count = session_count_result.scalar() or 0

    # 5. Get runtime status from RuntimeManager
    runtime_manager = req.app.state.runtime_manager
    status = await runtime_manager.get_mosaic_status(mosaic)

    # 6. Construct MosaicOut
    mosaic_out = MosaicOut(
        id=mosaic.id,
        user_id=mosaic.user_id,
        name=mosaic.name,
        description=mosaic.description,
        status=status,
        node_count=node_count,
        active_session_count=active_session_count,
        created_at=mosaic.created_at,
        updated_at=mosaic.updated_at
    )

    logger.info(f"Mosaic retrieved successfully: id={mosaic_id}")
    return SuccessResponse(data=mosaic_out)


@router.patch("/{mosaic_id}", response_model=SuccessResponse[MosaicOut])
async def update_mosaic(
    mosaic_id: int,
    request: UpdateMosaicRequest,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Update mosaic name and/or description

    Business logic:
    1. Validate request: at least one field (name or description) must be provided
    2. Query mosaic and verify ownership
    3. Verify mosaic is stopped (cannot modify running mosaic)
    4. Update fields and commit
    5. Return updated mosaic

    Raises:
        ValidationError: No fields provided for update or mosaic is running
        NotFoundError: Mosaic not found or deleted
        PermissionError: Current user is not the owner
    """
    logger.info(f"Updating mosaic: id={mosaic_id}, user_id={current_user.id}")

    # 1. Validate request: at least one field must be provided
    if request.name is None and request.description is None:
        raise ValidationError("At least one field (name or description) must be provided")

    # 2. Query mosaic and verify ownership
    stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    mosaic = result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to modify this mosaic")

    # 3. Verify mosaic is stopped
    runtime_manager = req.app.state.runtime_manager
    status = await runtime_manager.get_mosaic_status(mosaic)
    if status == MosaicStatus.RUNNING:
        logger.warning(f"Cannot update running mosaic: id={mosaic_id}")
        raise ValidationError("Cannot update running mosaic. Please stop it first.")

    # 4. Update name if provided
    if request.name is not None:
        mosaic.name = request.name
        logger.debug(f"Mosaic name updated: id={mosaic_id}, new_name={request.name}")

    # 5. Update description if provided
    if request.description is not None:
        mosaic.description = request.description
        logger.debug(f"Mosaic description updated: id={mosaic_id}")

    # Update the updated_at timestamp
    mosaic.updated_at = datetime.now()

    # 6. Get statistics for response
    node_count_stmt = select(func.count(Node.id)).where(
        Node.mosaic_id == mosaic.id,
        Node.deleted_at.is_(None)
    )
    node_count_result = await session.execute(node_count_stmt)
    node_count = node_count_result.scalar() or 0

    session_count_stmt = select(func.count(Session.id)).where(
        Session.mosaic_id == mosaic.id,
        Session.deleted_at.is_(None),
        Session.status == SessionStatus.ACTIVE
    )
    session_count_result = await session.execute(session_count_stmt)
    active_session_count = session_count_result.scalar() or 0

    # 7. Construct response
    mosaic_out = MosaicOut(
        id=mosaic.id,
        user_id=mosaic.user_id,
        name=mosaic.name,
        description=mosaic.description,
        status=status,  # Already retrieved, reuse it
        node_count=node_count,
        active_session_count=active_session_count,
        created_at=mosaic.created_at,
        updated_at=mosaic.updated_at
    )

    logger.info(f"Mosaic updated successfully: id={mosaic_id}")
    return SuccessResponse(data=mosaic_out)


@router.delete("/{mosaic_id}", response_model=SuccessResponse[None])
async def delete_mosaic(
    mosaic_id: int,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Soft delete a mosaic instance

    Business logic:
    1. Query mosaic and verify ownership
    2. Validate deletion prerequisites:
       - Mosaic must be stopped (check runtime MosaicInstance status, not data model)
       - Mosaic must have no nodes (COUNT nodes WHERE mosaic_id=X AND deleted_at IS NULL must be 0)
    3. Set deleted_at = datetime.now() (soft delete)
    4. Delete mosaic directory: {instance_path}/users/{user_id}/{mosaic_id}/
    5. Commit and return success

    Raises:
        NotFoundError: Mosaic not found or already deleted
        PermissionError: Current user is not the owner
        ValidationError: Mosaic is running or has nodes (cannot delete)
        InternalError: Failed to delete mosaic directory
    """
    logger.info(f"Deleting mosaic: id={mosaic_id}, user_id={current_user.id}")

    # 1. Query mosaic and verify ownership
    stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    mosaic = result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to delete this mosaic")

    # 2. Validate deletion prerequisites

    # Check if mosaic is stopped
    runtime_manager = req.app.state.runtime_manager
    status = await runtime_manager.get_mosaic_status(mosaic)
    if status == MosaicStatus.RUNNING:
        logger.warning(f"Cannot delete running mosaic: id={mosaic_id}")
        raise ValidationError("Cannot delete running mosaic. Please stop it first.")

    # Check if mosaic has no nodes
    node_count_stmt = select(func.count(Node.id)).where(
        Node.mosaic_id == mosaic.id,
        Node.deleted_at.is_(None)
    )
    node_count_result = await session.execute(node_count_stmt)
    node_count = node_count_result.scalar() or 0

    if node_count > 0:
        logger.warning(
            f"Cannot delete mosaic with nodes: id={mosaic_id}, node_count={node_count}"
        )
        raise ValidationError(
            f"Cannot delete mosaic with {node_count} node(s). "
            "Please delete all nodes first."
        )

    # 3. Soft delete (set deleted_at)
    mosaic.deleted_at = datetime.now()
    logger.debug(f"Mosaic soft deleted in database: id={mosaic_id}")

    # 4. Delete mosaic directory
    instance_path = req.app.state.instance_path
    mosaic_dir = instance_path / "users" / str(mosaic.user_id) / str(mosaic.id)

    try:
        # Check if directory exists and is empty
        if mosaic_dir.exists():
            # List contents
            contents = list(mosaic_dir.iterdir())
            if contents:
                logger.warning(
                    f"Mosaic directory is not empty: {mosaic_dir}, "
                    f"contents={[p.name for p in contents]}"
                )
                raise ValidationError(
                    "Mosaic directory is not empty. Please ensure all data is removed first."
                )

            # Directory is empty, safe to remove
            mosaic_dir.rmdir()
            logger.info(f"Mosaic directory deleted: {mosaic_dir}")
        else:
            logger.warning(f"Mosaic directory does not exist: {mosaic_dir}")

    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to delete mosaic directory: {mosaic_dir}, error: {e}")
        await session.rollback()
        raise InternalError(f"Failed to delete mosaic directory: {e}")

    # 5. Commit and return success
    logger.info(f"Mosaic deleted successfully: id={mosaic_id}")
    return SuccessResponse(data=None)


@router.post("/{mosaic_id}/start", response_model=SuccessResponse[MosaicOut])
async def start_mosaic(
    mosaic_id: int,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Start a mosaic instance

    Business logic:
    1. Query mosaic and verify ownership
    2. Validate mosaic has at least one node
    3. Start runtime components via RuntimeManager
    4. Return mosaic information

    Note: This operation is idempotent (starting an already-running mosaic succeeds)

    Raises:
        NotFoundError: Mosaic not found or deleted
        PermissionError: Current user is not the owner
        ValidationError: Mosaic has no nodes (cannot start empty mosaic)
    """
    logger.info(f"Starting mosaic: id={mosaic_id}, user_id={current_user.id}")

    # 1. Query mosaic and verify ownership
    stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    mosaic = result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to start this mosaic")

    # 2. Get runtime manager
    runtime_manager = req.app.state.runtime_manager

    # Check if already running (idempotent)
    status = await runtime_manager.get_mosaic_status(mosaic)
    if status == MosaicStatus.RUNNING:
        logger.info(f"Mosaic already running: id={mosaic_id}")
    else:
        # 3. Validate mosaic has at least one node
        node_count_stmt = select(func.count(Node.id)).where(
            Node.mosaic_id == mosaic.id,
            Node.deleted_at.is_(None)
        )
        node_count_result = await session.execute(node_count_stmt)
        node_count = node_count_result.scalar() or 0

        if node_count == 0:
            logger.warning(f"Cannot start empty mosaic: id={mosaic_id}")
            raise ValidationError(
                "Cannot start mosaic with no nodes. Please add at least one node first."
            )

        # 4. Start runtime mosaic instance
        await runtime_manager.start_mosaic(mosaic, timeout=30.0)
        logger.info(f"Mosaic started successfully: id={mosaic_id}")

    # 5. Get statistics for response
    # Recount nodes (already done above, but for consistency)
    node_count_stmt = select(func.count(Node.id)).where(
        Node.mosaic_id == mosaic.id,
        Node.deleted_at.is_(None)
    )
    node_count_result = await session.execute(node_count_stmt)
    node_count = node_count_result.scalar() or 0

    session_count_stmt = select(func.count(Session.id)).where(
        Session.mosaic_id == mosaic.id,
        Session.deleted_at.is_(None),
        Session.status == SessionStatus.ACTIVE
    )
    session_count_result = await session.execute(session_count_stmt)
    active_session_count = session_count_result.scalar() or 0

    # 6. Construct response
    mosaic_out = MosaicOut(
        id=mosaic.id,
        user_id=mosaic.user_id,
        name=mosaic.name,
        description=mosaic.description,
        status=MosaicStatus.RUNNING,  # Now running
        node_count=node_count,
        active_session_count=active_session_count,
        created_at=mosaic.created_at,
        updated_at=mosaic.updated_at
    )

    return SuccessResponse(data=mosaic_out)


@router.post("/{mosaic_id}/stop", response_model=SuccessResponse[MosaicOut])
async def stop_mosaic(
    mosaic_id: int,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Stop a running mosaic instance

    Business logic:
    1. Query mosaic and verify ownership
    2. Stop runtime components via RuntimeManager
    3. Return mosaic information

    Note: This operation is idempotent (stopping an already-stopped mosaic succeeds)

    Raises:
        NotFoundError: Mosaic not found or deleted
        PermissionError: Current user is not the owner
    """
    logger.info(f"Stopping mosaic: id={mosaic_id}, user_id={current_user.id}")

    # 1. Query mosaic and verify ownership
    stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    mosaic = result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to stop this mosaic")

    # 2. Get runtime manager and check status
    runtime_manager = req.app.state.runtime_manager
    status = await runtime_manager.get_mosaic_status(mosaic)

    if status == MosaicStatus.STOPPED:
        logger.info(f"Mosaic already stopped: id={mosaic_id}")
    else:
        # 3. Stop runtime mosaic instance
        await runtime_manager.stop_mosaic(mosaic, timeout=60.0)
        logger.info(f"Mosaic stopped successfully: id={mosaic_id}")

    # 4. Get statistics for response
    node_count_stmt = select(func.count(Node.id)).where(
        Node.mosaic_id == mosaic.id,
        Node.deleted_at.is_(None)
    )
    node_count_result = await session.execute(node_count_stmt)
    node_count = node_count_result.scalar() or 0

    session_count_stmt = select(func.count(Session.id)).where(
        Session.mosaic_id == mosaic.id,
        Session.deleted_at.is_(None),
        Session.status == SessionStatus.ACTIVE
    )
    session_count_result = await session.execute(session_count_stmt)
    active_session_count = session_count_result.scalar() or 0

    # 5. Construct response
    mosaic_out = MosaicOut(
        id=mosaic.id,
        user_id=mosaic.user_id,
        name=mosaic.name,
        description=mosaic.description,
        status=MosaicStatus.STOPPED,  # Now stopped
        node_count=node_count,
        active_session_count=active_session_count,
        created_at=mosaic.created_at,
        updated_at=mosaic.updated_at
    )

    return SuccessResponse(data=mosaic_out)
