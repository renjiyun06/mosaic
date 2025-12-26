from datetime import datetime
from sqlmodel import select, func, or_
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import Optional

from ..models.event import Event


class EventService:
    """Service for event storage and retrieval"""

    @staticmethod
    async def create_event(
        db: AsyncSession,
        event_data: dict,
        user_id: int,
        mosaic_id: int
    ) -> Event:
        """
        Store an event from ZMQ runtime

        Args:
            event_data: Event dict from ZMQ (contains event_id, source_id, etc.)
            user_id: Owner user ID
            mosaic_id: Mosaic instance ID
        """
        event = Event(
            event_id=event_data["event_id"],
            user_id=user_id,
            mosaic_id=mosaic_id,
            source_node_id=event_data["source_id"],
            target_node_id=event_data["target_id"],
            event_type=event_data["event_type"],
            upstream_session_id=event_data.get("upstream_session_id"),
            downstream_session_id=event_data.get("downstream_session_id"),
            payload=event_data.get("payload", {}),
            event_created_at=datetime.fromisoformat(event_data["created_at"])
        )

        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def list_events(
        db: AsyncSession,
        user_id: int,
        mosaic_id: int,
        limit: int,
        offset: int,
        event_type: Optional[str] = None,
        source_node_id: Optional[int] = None,
        target_node_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> tuple[list[Event], int]:
        """
        List events with filters

        Args:
            session_id: Matches either upstream_session_id or downstream_session_id
        """
        # Build base query
        query = select(Event).where(
            Event.user_id == user_id,
            Event.mosaic_id == mosaic_id,
            Event.deleted_at.is_(None)
        )

        # Apply filters
        if event_type:
            query = query.where(Event.event_type == event_type)
        if source_node_id:
            query = query.where(Event.source_node_id == source_node_id)
        if target_node_id:
            query = query.where(Event.target_node_id == target_node_id)
        if session_id:
            query = query.where(
                or_(
                    Event.upstream_session_id == session_id,
                    Event.downstream_session_id == session_id
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()

        # Get paginated results (ordered by event_created_at desc)
        query = query.order_by(Event.event_created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        events = result.scalars().all()

        return events, total

    @staticmethod
    async def get_event(
        db: AsyncSession,
        user_id: int,
        mosaic_id: int,
        event_id: str
    ) -> Optional[Event]:
        """Get single event by event_id"""
        result = await db.execute(
            select(Event).where(
                Event.user_id == user_id,
                Event.mosaic_id == mosaic_id,
                Event.event_id == event_id,
                Event.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()
