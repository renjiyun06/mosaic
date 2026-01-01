"""Session management API endpoints"""

import logging
from datetime import datetime
from math import ceil

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Annotated, Optional

from ..schema.response import SuccessResponse, PaginatedData
from ..schema.session import CreateSessionRequest, SessionOut
from ..model import Session, Node, Mosaic
from ..dep import get_db_session, get_current_user
from ..model.user import User
from ..exception import NotFoundError, PermissionError, ValidationError
from ..enum import SessionStatus

logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(prefix="/mosaics/{mosaic_id}/nodes/{node_id}/sessions", tags=["Session Management"])


# ==================== Type Aliases ====================

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ==================== API Endpoints ====================

@router.post("", response_model=SuccessResponse[SessionOut])
async def create_session(
    mosaic_id: int,
    node_id: str,
    request: CreateSessionRequest,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Create a new session

    Business logic:
    1. Query mosaic and verify ownership
    2. Verify node exists in the specified mosaic
    3. Call RuntimeManager.create_session() to create runtime session (runtime layer creates DB record)
    4. Query the database record created by runtime layer
    5. Return created session

    Validation Rules:
    - Mosaic must exist and belong to current user
    - Node must exist in the mosaic (node_id from path parameter)
    - Mode must be PROGRAM or CHAT (BACKGROUND not allowed, validated in schema)

    Note:
        The runtime layer automatically creates the database Session record during
        session initialization. This API layer only queries and returns the created record.

    Raises:
        NotFoundError: If mosaic or node not found
        PermissionError: If mosaic doesn't belong to current user
        RuntimeException: If runtime session creation fails
    """
    logger.info(
        f"Creating session: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"mode={request.mode}, user_id={current_user.id}"
    )

    # 1. Query mosaic and verify ownership
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
        raise PermissionError("You do not have permission to create sessions in this mosaic")

    # 2. Verify node exists
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(
            f"Node not found: mosaic_id={mosaic_id}, node_id={node_id}"
        )
        raise NotFoundError(f"Node '{node_id}' not found in this mosaic")

    # 3. Create runtime session and get session_id
    # Note: Runtime layer will create the database record during session initialization
    runtime_manager = req.app.state.runtime_manager
    session_id = await runtime_manager.create_session(
        node=node,
        mode=request.mode,
        model=request.model,
        timeout=10.0
    )

    logger.info(f"Runtime session created: session_id={session_id}")

    # 4. Query the database record created by runtime layer
    stmt = select(Session).where(Session.session_id == session_id)
    result = await session.execute(stmt)
    db_session = result.scalar_one()

    logger.info(
        f"Database session retrieved: id={db_session.id}, session_id={session_id}, "
        f"node_id={node_id}, mode={request.mode}"
    )

    # 5. Construct response
    session_out = SessionOut(
        id=db_session.id,
        session_id=db_session.session_id,
        user_id=db_session.user_id,
        mosaic_id=db_session.mosaic_id,
        node_id=db_session.node_id,
        mode=db_session.mode,
        model=db_session.model,
        status=db_session.status,
        message_count=db_session.message_count,
        total_input_tokens=db_session.total_input_tokens,
        total_output_tokens=db_session.total_output_tokens,
        total_cost_usd=db_session.total_cost_usd,
        created_at=db_session.created_at,
        updated_at=db_session.updated_at,
        last_activity_at=db_session.last_activity_at,
        closed_at=db_session.closed_at
    )

    return SuccessResponse(data=session_out)


@router.post("/{session_id}/close", response_model=SuccessResponse[SessionOut])
async def close_session(
    mosaic_id: int,
    node_id: str,
    session_id: str,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Close an active session

    Business logic:
    1. Query session and verify ownership (including node_id match)
    2. Query node for runtime close operation
    3. Verify session is currently ACTIVE
    4. Update database status to CLOSED
    5. Call RuntimeManager.close_session() to close runtime session
    6. Return updated session

    Validation Rules:
    - Session must exist and belong to current user
    - Session must belong to specified node
    - Session must be in ACTIVE status (cannot close already closed/archived session)

    Raises:
        NotFoundError: If session or node not found
        PermissionError: If session doesn't belong to current user
        ValidationError: If session is not active
        RuntimeException: If runtime session close fails
    """
    logger.info(
        f"Closing session: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"session_id={session_id}, user_id={current_user.id}"
    )

    # 1. Query session and verify ownership
    stmt = select(Session).where(
        Session.session_id == session_id,
        Session.mosaic_id == mosaic_id,
        Session.node_id == node_id,
        Session.user_id == current_user.id,
        Session.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    db_session = result.scalar_one_or_none()

    if not db_session:
        logger.warning(
            f"Session not found: session_id={session_id}, mosaic_id={mosaic_id}, "
            f"node_id={node_id}, user_id={current_user.id}"
        )
        raise NotFoundError("Session not found")

    # 2. Query node for runtime operation
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == db_session.node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(
            f"Node not found: mosaic_id={mosaic_id}, node_id={db_session.node_id}"
        )
        raise NotFoundError(f"Node '{db_session.node_id}' not found")

    # 3. Verify session is ACTIVE
    if db_session.status != SessionStatus.ACTIVE:
        logger.warning(
            f"Cannot close non-active session: session_id={session_id}, "
            f"current_status={db_session.status}"
        )
        raise ValidationError(
            f"Cannot close session with status '{db_session.status}'. "
            "Only active sessions can be closed."
        )

    # 4. Update database status to CLOSED
    db_session.status = SessionStatus.CLOSED
    db_session.closed_at = datetime.now()
    db_session.updated_at = datetime.now()
    await session.flush()

    logger.info(f"Database session status updated to CLOSED: session_id={session_id}")

    # 5. Close runtime session
    runtime_manager = req.app.state.runtime_manager
    await runtime_manager.close_session(
        node=node,
        session=db_session,
        timeout=10.0
    )

    logger.info(f"Runtime session closed successfully: session_id={session_id}")

    # 6. Construct response
    session_out = SessionOut(
        id=db_session.id,
        session_id=db_session.session_id,
        user_id=db_session.user_id,
        mosaic_id=db_session.mosaic_id,
        node_id=db_session.node_id,
        mode=db_session.mode,
        model=db_session.model,
        status=db_session.status,
        message_count=db_session.message_count,
        total_input_tokens=db_session.total_input_tokens,
        total_output_tokens=db_session.total_output_tokens,
        total_cost_usd=db_session.total_cost_usd,
        created_at=db_session.created_at,
        updated_at=db_session.updated_at,
        last_activity_at=db_session.last_activity_at,
        closed_at=db_session.closed_at
    )

    return SuccessResponse(data=session_out)


@router.post("/{session_id}/archive", response_model=SuccessResponse[SessionOut])
async def archive_session(
    mosaic_id: int,
    node_id: str,
    session_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Archive a closed session

    Business logic:
    1. Query session and verify ownership (including node_id match)
    2. Verify session is currently CLOSED
    3. Update status to ARCHIVED
    4. Update updated_at timestamp
    5. Return updated session

    Validation Rules:
    - Session must exist and belong to current user
    - Session must belong to specified node
    - Session must be in CLOSED status (archiving requires session to be closed first)

    Raises:
        NotFoundError: If session not found
        PermissionError: If session doesn't belong to current user
        ValidationError: If session is not closed
    """
    logger.info(
        f"Archiving session: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"session_id={session_id}, user_id={current_user.id}"
    )

    # 1. Query session and verify ownership
    stmt = select(Session).where(
        Session.session_id == session_id,
        Session.mosaic_id == mosaic_id,
        Session.node_id == node_id,
        Session.user_id == current_user.id,
        Session.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    db_session = result.scalar_one_or_none()

    if not db_session:
        logger.warning(
            f"Session not found: session_id={session_id}, mosaic_id={mosaic_id}, "
            f"node_id={node_id}, user_id={current_user.id}"
        )
        raise NotFoundError("Session not found")

    # 2. Verify session is CLOSED
    if db_session.status != SessionStatus.CLOSED:
        logger.warning(
            f"Cannot archive non-closed session: session_id={session_id}, "
            f"current_status={db_session.status}"
        )
        raise ValidationError(
            f"Cannot archive session with status '{db_session.status}'. "
            "Session must be closed before archiving."
        )

    # 3. Update status to ARCHIVED
    db_session.status = SessionStatus.ARCHIVED
    db_session.updated_at = datetime.now()

    logger.info(f"Session archived successfully: session_id={session_id}")

    # 4. Construct response
    session_out = SessionOut(
        id=db_session.id,
        session_id=db_session.session_id,
        user_id=db_session.user_id,
        mosaic_id=db_session.mosaic_id,
        node_id=db_session.node_id,
        mode=db_session.mode,
        model=db_session.model,
        status=db_session.status,
        message_count=db_session.message_count,
        total_input_tokens=db_session.total_input_tokens,
        total_output_tokens=db_session.total_output_tokens,
        total_cost_usd=db_session.total_cost_usd,
        created_at=db_session.created_at,
        updated_at=db_session.updated_at,
        last_activity_at=db_session.last_activity_at,
        closed_at=db_session.closed_at
    )

    return SuccessResponse(data=session_out)


@router.get("", response_model=SuccessResponse[PaginatedData[SessionOut]])
async def list_sessions(
    mosaic_id: int,
    node_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    status: Optional[SessionStatus] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """List sessions with filtering and pagination

    Business logic:
    1. Build query with filters:
       - mosaic_id (required, from path)
       - node_id (required, from path)
       - user_id (current user)
       - session_id (optional, exact match)
       - status (optional, exact match)
       - deleted_at IS NULL
    2. Count total matching records
    3. Apply pagination: ORDER BY last_activity_at DESC, LIMIT, OFFSET
    4. Return paginated results

    Query Parameters:
    - session_id: Filter by specific session ID (exact match)
    - status: Filter by status (active/closed/archived)
    - page: Page number (starts from 1)
    - page_size: Items per page (1-100, default 20)

    Returns:
        Paginated list of sessions for specified node, ordered by last_activity_at DESC (most recent first)

    Note: Returns empty list if no sessions found
    """
    logger.info(
        f"Listing sessions: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"user_id={current_user.id}, filters={{session_id={session_id}, status={status}}}, "
        f"page={page}, page_size={page_size}"
    )

    # 1. Build base query with filters
    stmt = select(Session).where(
        Session.mosaic_id == mosaic_id,
        Session.node_id == node_id,
        Session.user_id == current_user.id,
        Session.deleted_at.is_(None)
    )

    # Apply optional filters
    if session_id:
        stmt = stmt.where(Session.session_id == session_id)
    if status:
        stmt = stmt.where(Session.status == status)

    # 2. Count total records
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await session.execute(count_stmt)
    total = count_result.scalar() or 0

    # 3. Calculate pagination
    total_pages = ceil(total / page_size) if total > 0 else 0
    offset = (page - 1) * page_size

    # 4. Apply sorting and pagination
    stmt = stmt.order_by(Session.last_activity_at.desc()).offset(offset).limit(page_size)

    # 5. Execute query
    result = await session.execute(stmt)
    sessions = result.scalars().all()

    logger.debug(
        f"Found {len(sessions)} sessions (total={total}, page={page}/{total_pages})"
    )

    # 6. Build response list
    session_list = [
        SessionOut(
            id=s.id,
            session_id=s.session_id,
            user_id=s.user_id,
            mosaic_id=s.mosaic_id,
            node_id=s.node_id,
            mode=s.mode,
            model=s.model,
            status=s.status,
            message_count=s.message_count,
            total_input_tokens=s.total_input_tokens,
            total_output_tokens=s.total_output_tokens,
            total_cost_usd=s.total_cost_usd,
            created_at=s.created_at,
            updated_at=s.updated_at,
            last_activity_at=s.last_activity_at,
            closed_at=s.closed_at
        )
        for s in sessions
    ]

    # 7. Construct paginated response
    paginated_data = PaginatedData(
        items=session_list,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

    logger.info(
        f"Listed {len(session_list)} sessions: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"page={page}/{total_pages}, total={total}"
    )

    return SuccessResponse(data=paginated_data)
