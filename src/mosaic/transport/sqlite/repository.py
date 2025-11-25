"""
Event Repository for SQLite Transport

This module provides the data access layer for event storage.
It is INTERNAL to the transport layer and should not be used
directly by other modules.

Responsibilities:
-----------------
1. CRUD operations for events
2. Event status transitions
3. Recovery window handling
4. Event cleanup

Design Decisions:
-----------------
- Events are stored as JSON-serialized MeshEvent objects
- Status transitions are atomic (single UPDATE)
- Recovery window is checked during fetch, not with background job
- Delivery count is incremented on each fetch

Status Transitions:
-------------------
- save_event(): Creates with PENDING status
- fetch_pending(): PENDING/expired-PROCESSING -> PROCESSING
- mark_completed(): PROCESSING -> COMPLETED
- mark_failed(): PROCESSING -> FAILED
- requeue(): PROCESSING -> PENDING
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from mosaic.core.models import MeshEvent
from mosaic.core.types import NodeId, EventId, EventStatus

from .database import EventDatabase, utc_now, format_timestamp


class EventRepository:
    """
    Data access layer for event storage.
    
    This class provides methods for storing and retrieving events
    from the SQLite database. It handles status transitions and
    the recovery window mechanism.
    
    Note: This class is INTERNAL to the transport module. Other
    modules should use TransportBackend interface instead.
    
    Recovery Window:
    ----------------
    Events in PROCESSING status for longer than recovery_window_seconds
    are considered "stuck" (due to node crash) and become visible again.
    This implements at-least-once delivery semantics.
    """
    
    def __init__(
        self,
        database: EventDatabase,
        recovery_window_seconds: int = 300,
        max_delivery_attempts: int = 5,
    ) -> None:
        """
        Initialize the event repository.
        
        Args:
            database: The database manager
            recovery_window_seconds: Time before stuck events become visible
            max_delivery_attempts: Maximum delivery attempts before FAILED
        """
        self._db = database
        self._recovery_window_seconds = recovery_window_seconds
        self._max_delivery_attempts = max_delivery_attempts
    
    async def save_event(self, event: MeshEvent) -> None:
        """
        Save a new event to the database.
        
        The event is stored with PENDING status and delivery_count=0.
        
        Args:
            event: The event to save
        
        Raises:
            IntegrityError: If event_id already exists
        """
        now = utc_now()
        payload = event.model_dump_json()
        
        await self._db.execute(
            """
            INSERT INTO event_queue (
                event_id, mesh_id, source_id, target_id,
                event_type, payload, status, delivery_count,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.mesh_id,
                event.source_id,
                event.target_id,
                event.event_type,
                payload,
                EventStatus.PENDING.value,
                0,
                format_timestamp(now),
                format_timestamp(now),
            ),
        )
        await self._db.commit()
    
    async def fetch_pending_event(
        self,
        target_id: NodeId,
    ) -> Optional[tuple[MeshEvent, int]]:
        """
        Fetch one pending event for a target node.
        
        This method atomically:
        1. Finds the oldest PENDING event or expired PROCESSING event
        2. Updates status to PROCESSING
        3. Increments delivery_count
        4. Returns the event
        
        The recovery window is applied: events in PROCESSING status
        for longer than recovery_window_seconds are treated as PENDING.
        
        Args:
            target_id: The node to fetch events for
        
        Returns:
            Tuple of (event, delivery_count) if found, None otherwise
        """
        now = utc_now()
        recovery_threshold = now - timedelta(seconds=self._recovery_window_seconds)
        
        # Find eligible event (pending OR stuck-processing)
        cursor = await self._db.execute(
            """
            SELECT id, event_id, payload, delivery_count
            FROM event_queue
            WHERE target_id = ?
              AND (
                status = ?
                OR (status = ? AND updated_at < ?)
              )
              AND delivery_count < ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (
                target_id,
                EventStatus.PENDING.value,
                EventStatus.PROCESSING.value,
                format_timestamp(recovery_threshold),
                self._max_delivery_attempts,
            ),
        )
        
        row = await cursor.fetchone()
        if row is None:
            return None
        
        row_id, event_id, payload_json, delivery_count = row
        new_delivery_count = delivery_count + 1
        
        # Atomically update status and increment delivery_count
        await self._db.execute(
            """
            UPDATE event_queue
            SET status = ?,
                delivery_count = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                EventStatus.PROCESSING.value,
                new_delivery_count,
                format_timestamp(now),
                row_id,
            ),
        )
        await self._db.commit()
        
        # Deserialize the event
        event_data = json.loads(payload_json)
        event = MeshEvent.model_validate(event_data)
        
        return event, new_delivery_count
    
    async def mark_completed(self, event_id: EventId) -> bool:
        """
        Mark an event as successfully processed.
        
        Args:
            event_id: The event to mark completed
        
        Returns:
            True if event was updated, False if not found
        """
        now = utc_now()
        
        cursor = await self._db.execute(
            """
            UPDATE event_queue
            SET status = ?,
                updated_at = ?
            WHERE event_id = ?
              AND status = ?
            """,
            (
                EventStatus.COMPLETED.value,
                format_timestamp(now),
                event_id,
                EventStatus.PROCESSING.value,
            ),
        )
        await self._db.commit()
        
        return cursor.rowcount > 0
    
    async def mark_failed(self, event_id: EventId) -> bool:
        """
        Mark an event as permanently failed.
        
        This should be called when requeue=False is passed to nack(),
        or when max_delivery_attempts is exceeded.
        
        Args:
            event_id: The event to mark failed
        
        Returns:
            True if event was updated, False if not found
        """
        now = utc_now()
        
        cursor = await self._db.execute(
            """
            UPDATE event_queue
            SET status = ?,
                updated_at = ?
            WHERE event_id = ?
              AND status = ?
            """,
            (
                EventStatus.FAILED.value,
                format_timestamp(now),
                event_id,
                EventStatus.PROCESSING.value,
            ),
        )
        await self._db.commit()
        
        return cursor.rowcount > 0
    
    async def requeue(self, event_id: EventId) -> bool:
        """
        Return an event to pending status for redelivery.
        
        This is called when nack(requeue=True) is invoked.
        
        Args:
            event_id: The event to requeue
        
        Returns:
            True if event was updated, False if not found
        """
        now = utc_now()
        
        cursor = await self._db.execute(
            """
            UPDATE event_queue
            SET status = ?,
                updated_at = ?
            WHERE event_id = ?
              AND status = ?
            """,
            (
                EventStatus.PENDING.value,
                format_timestamp(now),
                event_id,
                EventStatus.PROCESSING.value,
            ),
        )
        await self._db.commit()
        
        return cursor.rowcount > 0
    
    async def get_event(self, event_id: EventId) -> Optional[MeshEvent]:
        """
        Get an event by ID.
        
        Args:
            event_id: The event to retrieve
        
        Returns:
            The event if found, None otherwise
        """
        cursor = await self._db.execute(
            "SELECT payload FROM event_queue WHERE event_id = ?",
            (event_id,),
        )
        
        row = await cursor.fetchone()
        if row is None:
            return None
        
        payload_json = row[0]
        event_data = json.loads(payload_json)
        return MeshEvent.model_validate(event_data)
    
    async def get_event_status(
        self,
        event_id: EventId,
    ) -> Optional[tuple[EventStatus, int]]:
        """
        Get the status and delivery count of an event.
        
        Args:
            event_id: The event to check
        
        Returns:
            Tuple of (status, delivery_count) if found, None otherwise
        """
        cursor = await self._db.execute(
            "SELECT status, delivery_count FROM event_queue WHERE event_id = ?",
            (event_id,),
        )
        
        row = await cursor.fetchone()
        if row is None:
            return None
        
        return EventStatus(row[0]), row[1]
    
    async def get_pending_count(self, target_id: NodeId) -> int:
        """
        Get count of pending events for a target node.
        
        Args:
            target_id: The node to check
        
        Returns:
            Number of pending events
        """
        cursor = await self._db.execute(
            """
            SELECT COUNT(*)
            FROM event_queue
            WHERE target_id = ?
              AND status = ?
            """,
            (target_id, EventStatus.PENDING.value),
        )
        
        row = await cursor.fetchone()
        return row[0] if row else 0
    
    async def cleanup_completed(
        self,
        older_than_seconds: int = 86400,
    ) -> int:
        """
        Remove completed events older than specified age.
        
        Args:
            older_than_seconds: Remove events older than this (default: 24h)
        
        Returns:
            Number of events removed
        """
        threshold = utc_now() - timedelta(seconds=older_than_seconds)
        
        cursor = await self._db.execute(
            """
            DELETE FROM event_queue
            WHERE status = ?
              AND updated_at < ?
            """,
            (
                EventStatus.COMPLETED.value,
                format_timestamp(threshold),
            ),
        )
        await self._db.commit()
        
        return cursor.rowcount
    
    async def cleanup_failed(
        self,
        older_than_seconds: int = 604800,
    ) -> int:
        """
        Remove failed events older than specified age.
        
        Args:
            older_than_seconds: Remove events older than this (default: 7 days)
        
        Returns:
            Number of events removed
        """
        threshold = utc_now() - timedelta(seconds=older_than_seconds)
        
        cursor = await self._db.execute(
            """
            DELETE FROM event_queue
            WHERE status = ?
              AND updated_at < ?
            """,
            (
                EventStatus.FAILED.value,
                format_timestamp(threshold),
            ),
        )
        await self._db.commit()
        
        return cursor.rowcount
    
    async def has_pending_events(self, target_id: NodeId) -> bool:
        """
        Check if there are any pending events for a target.
        
        This is a fast check used before blocking on signals.
        
        Args:
            target_id: The node to check
        
        Returns:
            True if there are pending events
        """
        now = utc_now()
        recovery_threshold = now - timedelta(seconds=self._recovery_window_seconds)
        
        cursor = await self._db.execute(
            """
            SELECT 1
            FROM event_queue
            WHERE target_id = ?
              AND (
                status = ?
                OR (status = ? AND updated_at < ?)
              )
              AND delivery_count < ?
            LIMIT 1
            """,
            (
                target_id,
                EventStatus.PENDING.value,
                EventStatus.PROCESSING.value,
                format_timestamp(recovery_threshold),
                self._max_delivery_attempts,
            ),
        )
        
        row = await cursor.fetchone()
        return row is not None

