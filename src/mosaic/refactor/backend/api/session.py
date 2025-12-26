"""Session management API"""

import logging
import asyncio
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session as get_db
from ..api.deps import get_current_user
from ..models.user import User
from ..schemas.session import (
    SessionCreate,
    SessionResponse,
    SessionListResponse,
    MessageResponse,
    MessageListResponse,
)
from ..services.session_service import SessionService
from ..services.message_service import MessageService
from ..runtime.manager import RuntimeManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post("", response_model=SessionResponse)
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new Claude Code session.

    Args:
        data: Session creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created session
    """
    session = await SessionService.create_session(
        db=db,
        user_id=current_user.id,
        mosaic_id=data.mosaic_id,
        node_id=data.node_id,
        mode=data.mode,
        model=data.model,
        config=data.config
    )

    # Register session with RuntimeManager for command routing
    runtime_manager = RuntimeManager.get_instance()
    runtime_manager.register_session(session.session_id, session.mosaic_id)

    # Submit CREATE_SESSION command to create runtime session
    try:
        runtime_manager.submit_create_session(
            mosaic_id=session.mosaic_id,
            node_id=session.node_id,
            session_id=session.session_id,
            user_id=current_user.id,
            config=session.config or {}
        )
        logger.info(
            f"Submitted create_session command for session {session.session_id}"
        )
    except Exception as e:
        logger.error(f"Failed to submit create_session command: {e}", exc_info=True)
        # Note: Database record already created
        # Runtime session creation failed but database state is consistent
        # User can retry by reconnecting or we can add retry logic

    logger.info(
        f"Created session {session.session_id} for user {current_user.id}"
    )

    return SessionResponse.model_validate(session)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    mosaic_id: int | None = Query(None, description="Filter by mosaic ID"),
    node_id: int | None = Query(None, description="Filter by node ID"),
    status: str | None = Query(None, description="Filter by status (active/closed/archived)"),
    include_archived: bool = Query(False, description="Include archived sessions"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List sessions for current user.

    Args:
        mosaic_id: Optional filter by mosaic
        node_id: Optional filter by node
        status: Optional filter by status (active/closed/archived)
        include_archived: Include archived sessions (default: False)
        limit: Maximum number of results
        offset: Offset for pagination
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of sessions with total count
    """
    # Get sessions and total count in parallel
    sessions, total = await asyncio.gather(
        SessionService.list_sessions(
            db=db,
            user_id=current_user.id,
            mosaic_id=mosaic_id,
            node_id=node_id,
            status=status,
            include_archived=include_archived,
            limit=limit,
            offset=offset
        ),
        SessionService.count_sessions(
            db=db,
            user_id=current_user.id,
            mosaic_id=mosaic_id,
            node_id=node_id,
            status=status,
            include_archived=include_archived
        )
    )

    return SessionListResponse(
        sessions=[SessionResponse.model_validate(s) for s in sessions],
        total=total
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get session details.

    Args:
        session_id: Session UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Session details
    """
    session = await SessionService.get_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id
    )

    return SessionResponse.model_validate(session)


@router.get("/{session_id}/messages", response_model=MessageListResponse)
async def get_session_messages(
    session_id: str,
    limit: int | None = Query(None, ge=1, le=1000, description="Maximum number of messages"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get messages for a session.

    Args:
        session_id: Session UUID
        limit: Optional maximum number of messages
        offset: Offset for pagination
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of messages
    """
    # Verify session ownership
    await SessionService.get_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id
    )

    # Get messages
    messages = await MessageService.get_session_messages(
        db=db,
        session_id=session_id,
        limit=limit,
        offset=offset
    )

    return MessageListResponse(
        messages=[MessageResponse.model_validate(m) for m in messages],
        total=len(messages)
    )


@router.post("/{session_id}/archive", response_model=SessionResponse)
async def archive_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Archive a session.

    This marks the session as archived but does not delete it.
    Archived sessions are hidden from the active session list by default.

    Args:
        session_id: Session UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated session
    """
    session = await SessionService.archive_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id
    )

    logger.info(f"Archived session {session_id}")

    return SessionResponse.model_validate(session)


@router.post("/{session_id}/unarchive", response_model=SessionResponse)
async def unarchive_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Unarchive a session.

    This restores an archived session to closed status.
    Note: It cannot restore to active status as the runtime connection is lost.

    Args:
        session_id: Session UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated session
    """
    session = await SessionService.unarchive_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id
    )

    logger.info(f"Unarchived session {session_id}")

    return SessionResponse.model_validate(session)


@router.post("/{session_id}/close", response_model=SessionResponse)
async def close_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Close a session.

    This releases resources and marks the session as closed.
    Closed sessions remain visible in the list but cannot send new messages.
    Cannot be reopened due to session alignment with upstream/downstream nodes.

    Args:
        session_id: Session UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated session
    """
    # Close in database
    session = await SessionService.close_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id
    )

    # Submit close command to runtime (if running)
    try:
        runtime_manager = RuntimeManager.get_instance()
        runtime_manager.submit_close_session(
            session_id=session_id,
            node_id=session.node_id,
            user_id=current_user.id,
            force=False
        )
        # Unregister from RuntimeManager
        runtime_manager.unregister_session(session_id)
        logger.info(f"Submitted close command for session {session_id}")
    except Exception as e:
        logger.warning(
            f"Failed to submit close command for session {session_id}: {e}"
        )

    return SessionResponse.model_validate(session)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a session (soft delete).

    Args:
        session_id: Session UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Success message
    """
    # Get session first (for mosaic_id and node_id)
    session = await SessionService.get_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id
    )

    # Submit close command to runtime (if running)
    try:
        runtime_manager = RuntimeManager.get_instance()
        runtime_manager.submit_close_session(
            session_id=session_id,
            node_id=session.node_id,
            user_id=current_user.id,
            force=True  # Force close for deletion
        )
        # Unregister from RuntimeManager
        runtime_manager.unregister_session(session_id)
    except Exception as e:
        logger.warning(
            f"Failed to submit close command for session {session_id}: {e}"
        )

    # Delete from database
    await SessionService.delete_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id
    )

    logger.info(f"Deleted session {session_id}")

    return {"message": "Session deleted successfully"}
