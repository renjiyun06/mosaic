"""Session routing query API endpoints"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..schema.response import SuccessResponse, PaginatedData
from ..schema.session_routing import SessionRoutingOut
from ..model import SessionRouting
from ..dep import get_db_session, get_current_user
from ..model.user import User

logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(prefix="/mosaics/{mosaic_id}/session-routings", tags=["Session Routing"])


# ==================== Type Aliases ====================

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ==================== API Endpoints ====================

@router.get("", response_model=SuccessResponse[PaginatedData[SessionRoutingOut]])
async def list_session_routings(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
    local_node_id: str | None = Query(None, description="Filter by local node ID"),
    local_session_id: str | None = Query(None, description="Filter by local session ID"),
    remote_node_id: str | None = Query(None, description="Filter by remote node ID"),
    remote_session_id: str | None = Query(None, description="Filter by remote session ID"),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(100, ge=1, le=1000, description="Number of items per page"),
):
    """List all session routings in a mosaic with filters and pagination

    Business logic:
    1. Build base query with filters: mosaic_id AND user_id AND deleted_at IS NULL
    2. Apply optional filters if provided:
       - local_node_id
       - local_session_id
       - remote_node_id
       - remote_session_id
    3. Query total count (for pagination metadata)
    4. Order by created_at DESC (newest first)
    5. Apply pagination (calculate offset from page and page_size)
    6. Query routing items
    7. Return paginated response with metadata

    Validation Rules:
    - page must be >= 1
    - page_size must be between 1 and 1000

    Note:
    - Returns empty items list if no routings found (doesn't raise exception)
    - This is a read-only endpoint - session routings are managed internally by the runtime
    - Session routings use soft delete (deleted_at field)

    Raises:
        (No exceptions raised - returns empty list if no routings found)
    """
    logger.info(
        f"Listing session routings: mosaic_id={mosaic_id}, user_id={current_user.id}, "
        f"filters=(local_node={local_node_id}, local_session={local_session_id}, "
        f"remote_node={remote_node_id}, remote_session={remote_session_id}), "
        f"pagination=(page={page}, page_size={page_size})"
    )

    # 1. Build base WHERE clause (will be reused for both count and data queries)
    base_where = [
        SessionRouting.mosaic_id == mosaic_id,
        SessionRouting.user_id == current_user.id,
        SessionRouting.deleted_at.is_(None)
    ]

    # 2. Apply optional filters
    if local_node_id is not None:
        base_where.append(SessionRouting.local_node_id == local_node_id)
    if local_session_id is not None:
        base_where.append(SessionRouting.local_session_id == local_session_id)
    if remote_node_id is not None:
        base_where.append(SessionRouting.remote_node_id == remote_node_id)
    if remote_session_id is not None:
        base_where.append(SessionRouting.remote_session_id == remote_session_id)

    # 3. Query total count
    count_stmt = select(func.count(SessionRouting.id)).where(*base_where)
    count_result = await session.execute(count_stmt)
    total = count_result.scalar() or 0

    logger.debug(f"Total session routings matching filters: {total}")

    # 4. Calculate pagination
    offset = (page - 1) * page_size
    total_pages = (total + page_size - 1) // page_size  # Ceiling division

    # 5. Build data query with ordering and pagination
    data_stmt = select(SessionRouting).where(*base_where)
    data_stmt = data_stmt.order_by(SessionRouting.created_at.desc())
    data_stmt = data_stmt.limit(page_size).offset(offset)

    # 6. Execute data query
    result = await session.execute(data_stmt)
    routings = result.scalars().all()

    logger.debug(
        f"Retrieved {len(routings)} session routings for page {page}: "
        f"mosaic_id={mosaic_id}, user_id={current_user.id}"
    )

    # 7. Build response items
    items = [
        SessionRoutingOut(
            local_node_id=routing.local_node_id,
            local_session_id=routing.local_session_id,
            remote_node_id=routing.remote_node_id,
            remote_session_id=routing.remote_session_id,
            created_at=routing.created_at
        )
        for routing in routings
    ]

    # 8. Construct paginated response
    paginated_data = PaginatedData(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

    logger.info(
        f"Listed session routings: mosaic_id={mosaic_id}, user_id={current_user.id}, "
        f"page={page}/{total_pages}, items={len(items)}, total={total}"
    )
    return SuccessResponse(data=paginated_data)
