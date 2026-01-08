"""Database initialization and pre-flight checks"""
import logging
from datetime import datetime
from sqlmodel import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .model.session import Session
from .enum import SessionStatus

logger = logging.getLogger(__name__)


async def cleanup_orphaned_sessions(async_session_factory) -> None:
    """
    Clean up orphaned active sessions from system crash.

    When the system crashes or is force-stopped, sessions may remain in ACTIVE
    status in the database. Since sessions cannot be recovered after restart,
    this function force-closes all ACTIVE sessions during system startup.

    Args:
        async_session_factory: SQLAlchemy async session factory
    """
    logger.info("Cleaning up orphaned active sessions from previous run...")

    async with async_session_factory() as db_session:
        # Find all ACTIVE sessions
        result = await db_session.execute(
            select(Session).where(Session.status == SessionStatus.ACTIVE)
        )
        orphaned_sessions = result.scalars().all()

        if not orphaned_sessions:
            logger.info("No orphaned sessions found")
            return

        logger.warning(
            f"Found {len(orphaned_sessions)} orphaned active sessions, "
            "force closing them..."
        )

        # Batch update to CLOSED
        await db_session.execute(
            update(Session)
            .where(Session.status == SessionStatus.ACTIVE)
            .values(
                status=SessionStatus.CLOSED,
                closed_at=datetime.utcnow()
            )
        )
        await db_session.commit()

        logger.info(f"Successfully closed {len(orphaned_sessions)} orphaned sessions")


async def run_preflight_checks(async_session_factory) -> None:
    """
    Run all database preflight checks before system startup.

    This function performs necessary database cleanup and validation
    before the Mosaic system starts accepting requests.

    Current checks:
    - Cleanup orphaned active sessions from previous crash/shutdown

    Args:
        async_session_factory: SQLAlchemy async session factory
    """
    await cleanup_orphaned_sessions(async_session_factory)
    # Future preflight checks can be added here...
