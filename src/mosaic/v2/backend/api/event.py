"""Event monitoring and history API endpoints"""

import logging
from typing import Annotated
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..schema.response import SuccessResponse, PaginatedData
from ..schema.event import EventListOut, EventDetailOut
from ..model import Event
from ..dep import get_db_session, get_current_user
from ..model.user import User
from ..exception import NotFoundError, ValidationError
from ..enum import EventType

logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(prefix="/mosaics/{mosaic_id}/events", tags=["Event Monitoring"])


# ==================== Type Aliases ====================

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ==================== API Endpoints ====================

@router.get("", response_model=SuccessResponse[PaginatedData[EventListOut]])
async def list_events(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
    created_at_start: datetime = Query(..., description="Start of time range (required)"),
    created_at_end: datetime = Query(..., description="End of time range (required)"),
    source_node_id: str | None = Query(None, description="Filter by source node ID"),
    source_session_id: str | None = Query(None, description="Filter by source session ID"),
    target_node_id: str | None = Query(None, description="Filter by target node ID"),
    target_session_id: str | None = Query(None, description="Filter by target session ID"),
    event_type: EventType | None = Query(None, description="Filter by event type"),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(100, ge=1, le=1000, description="Number of items per page"),
):
    """List all events in a mosaic with filters and pagination

    Business logic:
    1. Validate time range: created_at_start must be before created_at_end
    2. Build base query with filters: mosaic_id AND user_id
    3. Apply time range filter (required): created_at BETWEEN start AND end
    4. Apply optional filters if provided:
       - source_node_id
       - source_session_id
       - target_node_id
       - target_session_id
       - event_type
    5. Query total count (for pagination metadata)
    6. Order by created_at DESC (newest first)
    7. Apply pagination (calculate offset from page and page_size)
    8. Query event items
    9. Return paginated response with metadata

    Validation Rules:
    - created_at_start and created_at_end are required
    - created_at_start must be before created_at_end
    - page must be >= 1
    - page_size must be between 1 and 1000

    Note:
    - Events table does not have deleted_at field (events are never deleted)
    - Returns empty items list if no events found (doesn't raise exception)
    - This is a read-only endpoint - events cannot be created/updated/deleted via API
      (events are created automatically by the ZMQ message bus)

    Raises:
        ValidationError: If time range is invalid (start >= end)
    """
    logger.info(
        f"Listing events: mosaic_id={mosaic_id}, user_id={current_user.id}, "
        f"time_range=({created_at_start} to {created_at_end}), "
        f"filters=(source_node={source_node_id}, source_session={source_session_id}, "
        f"target_node={target_node_id}, target_session={target_session_id}, "
        f"event_type={event_type}), pagination=(page={page}, page_size={page_size})"
    )

    # 1. Validate time range
    if created_at_start >= created_at_end:
        logger.warning(
            f"Invalid time range: start={created_at_start}, end={created_at_end}"
        )
        raise ValidationError("created_at_start must be before created_at_end")

    # 2. Build base WHERE clause (will be reused for both count and data queries)
    base_where = [
        Event.mosaic_id == mosaic_id,
        Event.user_id == current_user.id
    ]

    # 3. Apply time range filter (required)
    base_where.extend([
        Event.created_at >= created_at_start,
        Event.created_at <= created_at_end
    ])

    # 4. Apply optional filters
    if source_node_id is not None:
        base_where.append(Event.source_node_id == source_node_id)
    if source_session_id is not None:
        base_where.append(Event.source_session_id == source_session_id)
    if target_node_id is not None:
        base_where.append(Event.target_node_id == target_node_id)
    if target_session_id is not None:
        base_where.append(Event.target_session_id == target_session_id)
    if event_type is not None:
        base_where.append(Event.event_type == event_type)

    # 5. Query total count
    count_stmt = select(func.count(Event.id)).where(*base_where)
    count_result = await session.execute(count_stmt)
    total = count_result.scalar() or 0

    logger.debug(f"Total events matching filters: {total}")

    # 6. Calculate pagination
    offset = (page - 1) * page_size
    total_pages = (total + page_size - 1) // page_size  # Ceiling division

    # 7. Build data query with ordering and pagination
    data_stmt = select(Event).where(*base_where)
    data_stmt = data_stmt.order_by(Event.created_at.desc())
    data_stmt = data_stmt.limit(page_size).offset(offset)

    # 8. Execute data query
    result = await session.execute(data_stmt)
    events = result.scalars().all()

    logger.debug(
        f"Retrieved {len(events)} events for page {page}: mosaic_id={mosaic_id}, "
        f"user_id={current_user.id}"
    )

    # 9. Build response items
    items = [
        EventListOut(
            event_id=event.event_id,
            event_type=event.event_type,
            source_node_id=event.source_node_id,
            source_session_id=event.source_session_id,
            target_node_id=event.target_node_id,
            target_session_id=event.target_session_id,
            created_at=event.created_at
        )
        for event in events
    ]

    # 10. Construct paginated response
    paginated_data = PaginatedData(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

    logger.info(
        f"Listed events: mosaic_id={mosaic_id}, user_id={current_user.id}, "
        f"page={page}/{total_pages}, items={len(items)}, total={total}"
    )
    return SuccessResponse(data=paginated_data)


@router.get("/{event_id}", response_model=SuccessResponse[EventDetailOut])
async def get_event(
    mosaic_id: int,
    event_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Get detailed information for a specific event

    Business logic:
    1. Query event WHERE event_id=X AND mosaic_id=Y AND user_id=Z
    2. If not found, raise NotFoundError
    3. Return complete event information including payload

    Note:
    - event_id is the UUID string (not the database ID)
    - Returns full event details including JSON payload

    Raises:
        NotFoundError: If event not found or doesn't belong to specified mosaic/user
    """
    logger.info(
        f"Getting event: event_id={event_id}, mosaic_id={mosaic_id}, "
        f"user_id={current_user.id}"
    )

    # Query event by event_id (UUID) with mosaic_id and user_id verification
    stmt = select(Event).where(
        Event.event_id == event_id,
        Event.mosaic_id == mosaic_id,
        Event.user_id == current_user.id
    )
    result = await session.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        logger.warning(
            f"Event not found: event_id={event_id}, mosaic_id={mosaic_id}, "
            f"user_id={current_user.id}"
        )
        raise NotFoundError("Event not found")

    # Construct response with full details
    event_detail = EventDetailOut(
        event_id=event.event_id,
        event_type=event.event_type,
        source_node_id=event.source_node_id,
        source_session_id=event.source_session_id,
        target_node_id=event.target_node_id,
        target_session_id=event.target_session_id,
        payload=event.payload,
        created_at=event.created_at
    )

    logger.info(f"Event retrieved successfully: event_id={event_id}")
    return SuccessResponse(data=event_detail)
