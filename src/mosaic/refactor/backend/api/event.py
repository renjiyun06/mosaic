from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from .deps import SessionDep, CurrentUser
from ..services.event_service import EventService
from ..services.mosaic_service import MosaicService
from ..schemas.event import EventResponse, EventListResponse


router = APIRouter()


@router.get("/mosaics/{mosaic_id}/events", response_model=EventListResponse)
async def list_events(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = Query(None),
    source_node_id: Optional[int] = Query(None),
    target_node_id: Optional[int] = Query(None),
    session_id: Optional[str] = Query(None),
):
    """
    List events with filtering and pagination

    Query parameters:
    - event_type: Filter by event type
    - source_node_id: Filter by source node
    - target_node_id: Filter by target node
    - session_id: Filter by session (matches either upstream or downstream)
    - limit/offset: Pagination (default: limit=50, offset=0)
    """
    # Verify mosaic ownership
    mosaic = await MosaicService.get_mosaic(session, current_user.id, mosaic_id)
    if not mosaic:
        raise HTTPException(status_code=404, detail="Mosaic not found")

    # Get events
    events, total = await EventService.list_events(
        db=session,
        user_id=current_user.id,
        mosaic_id=mosaic_id,
        limit=limit,
        offset=offset,
        event_type=event_type,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        session_id=session_id
    )

    return EventListResponse(
        events=[EventResponse.model_validate(event) for event in events],
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/mosaics/{mosaic_id}/events/{event_id}", response_model=EventResponse)
async def get_event(
    mosaic_id: int,
    event_id: str,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Get single event by event_id"""
    # Verify mosaic ownership
    mosaic = await MosaicService.get_mosaic(session, current_user.id, mosaic_id)
    if not mosaic:
        raise HTTPException(status_code=404, detail="Mosaic not found")

    # Get event
    event = await EventService.get_event(
        db=session,
        user_id=current_user.id,
        mosaic_id=mosaic_id,
        event_id=event_id
    )

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return EventResponse.model_validate(event)
