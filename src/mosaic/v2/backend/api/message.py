"""Message management API endpoints"""

import logging
from math import ceil

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Annotated

from ..schema.response import SuccessResponse, PaginatedData
from ..schema.message import MessageOut
from ..model import Message, Session
from ..dep import get_db_session, get_current_user
from ..model.user import User
from ..exception import NotFoundError

logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(
    prefix="/mosaics/{mosaic_id}/nodes/{node_id}/sessions/{session_id}/messages",
    tags=["Message Management"]
)


# ==================== Type Aliases ====================

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ==================== API Endpoints ====================

@router.get("", response_model=SuccessResponse[PaginatedData[MessageOut]])
async def list_messages(
    mosaic_id: int,
    session_id: str,
    node_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """List messages in a session

    Business logic:
    1. Verify session exists and belongs to current user
    2. Build query with filters:
       - mosaic_id (from path)
       - session_id (from path)
       - node_id (from path)
       - user_id (current user)
       - deleted_at IS NULL
    3. Count total matching records
    4. Apply pagination: ORDER BY sequence ASC, LIMIT, OFFSET
    5. Return paginated results

    Query Parameters:
    - page: Page number (starts from 1)
    - page_size: Items per page (1-100, default 20)

    Returns:
        Paginated list of messages, ordered by sequence ASC (chronological order)

    Raises:
        NotFoundError: If session not found or doesn't belong to user

    Note:
        Messages are ordered by sequence (1, 2, 3, ...) for chronological display
    """
    logger.info(
        f"Listing messages: mosaic_id={mosaic_id}, session_id={session_id}, "
        f"node_id={node_id}, user_id={current_user.id}, page={page}, page_size={page_size}"
    )

    # 1. Verify session exists and belongs to current user
    session_stmt = select(Session).where(
        Session.mosaic_id == mosaic_id,
        Session.session_id == session_id,
        Session.node_id == node_id,
        Session.user_id == current_user.id,
        Session.deleted_at.is_(None)
    )
    session_result = await session.execute(session_stmt)
    db_session = session_result.scalar_one_or_none()

    if not db_session:
        logger.warning(
            f"Session not found: mosaic_id={mosaic_id}, session_id={session_id}, "
            f"node_id={node_id}, user_id={current_user.id}"
        )
        raise NotFoundError("Session not found")

    # 2. Build base query with filters
    stmt = select(Message).where(
        Message.mosaic_id == mosaic_id,
        Message.session_id == session_id,
        Message.node_id == node_id,
        Message.user_id == current_user.id,
        Message.deleted_at.is_(None)
    )

    # 3. Count total records
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await session.execute(count_stmt)
    total = count_result.scalar() or 0

    # 4. Calculate pagination
    total_pages = ceil(total / page_size) if total > 0 else 0
    offset = (page - 1) * page_size

    # 5. Apply sorting and pagination
    stmt = stmt.order_by(Message.sequence.asc()).offset(offset).limit(page_size)

    # 6. Execute query
    result = await session.execute(stmt)
    messages = result.scalars().all()

    logger.debug(
        f"Found {len(messages)} messages (total={total}, page={page}/{total_pages})"
    )

    # 7. Build response list
    message_list = [
        MessageOut(
            id=msg.id,
            message_id=msg.message_id,
            user_id=msg.user_id,
            mosaic_id=msg.mosaic_id,
            node_id=msg.node_id,
            session_id=msg.session_id,
            role=msg.role,
            message_type=msg.message_type,
            payload=msg.payload,
            sequence=msg.sequence,
            created_at=msg.created_at
        )
        for msg in messages
    ]

    # 8. Construct paginated response
    paginated_data = PaginatedData(
        items=message_list,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

    logger.info(
        f"Listed {len(message_list)} messages: session_id={session_id}, "
        f"page={page}/{total_pages}, total={total}"
    )

    return SuccessResponse(data=paginated_data)
