"""Service layer for session management"""

from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import uuid
from typing import Optional, List

from ..models.session import Session
from ..models.mosaic import Mosaic
from ..models.node import Node
from ..exceptions import NotFoundError
from ..logger import get_logger

logger = get_logger(__name__)


class SessionService:
    """Service layer for session management"""

    @staticmethod
    async def create_session(
        db: AsyncSession,
        user_id: int,
        mosaic_id: int,
        node_id: int,
        mode: str = "chat",
        model: Optional[str] = None,
        config: Optional[dict] = None
    ) -> Session:
        """
        Create a new session.

        Args:
            db: Database session
            user_id: Owner user ID
            mosaic_id: Mosaic instance ID
            node_id: Claude Code node ID
            mode: Session mode - background (publish events) | program (node guidance, no events) | chat (interactive)
            model: Claude model (sonnet/opus/haiku, see ClaudeModel enum)
            config: Additional session configuration

        Returns:
            Created session

        Raises:
            NotFoundError: If mosaic or node not found
        """
        # Backward compatibility: convert old 'user' mode to 'chat'
        if mode == "user":
            logger.warning(f"Converting deprecated 'user' mode to 'chat' for session creation")
            mode = "chat"

        # Verify mosaic exists and belongs to user
        result = await db.execute(
            select(Mosaic).where(
                Mosaic.id == mosaic_id,
                Mosaic.user_id == user_id,
                Mosaic.deleted_at.is_(None)
            )
        )
        mosaic = result.scalar_one_or_none()
        if not mosaic:
            raise NotFoundError(f"Mosaic {mosaic_id} not found or access denied")

        # Verify node exists and belongs to mosaic
        result = await db.execute(
            select(Node).where(
                Node.id == node_id,
                Node.mosaic_id == mosaic_id,
                Node.deleted_at.is_(None)
            )
        )
        node = result.scalar_one_or_none()
        if not node:
            raise NotFoundError(f"Node {node_id} not found in mosaic {mosaic_id}")

        # Verify node is Claude Code type
        if node.node_type != "cc":
            raise ValueError(f"Node {node_id} is not a Claude Code node (type: {node.node_type})")

        # Check node runtime status
        from ..runtime.manager import RuntimeManager
        from ..exceptions import ValidationError

        runtime_manager = RuntimeManager.get_instance()
        node_status = runtime_manager.get_node_status(mosaic_id, node.node_id)

        if node_status != "running":
            raise ValidationError(
                f"Cannot create session: node '{node.node_id}' is not running "
                f"(status: {node_status})"
            )

        # Create session
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            mosaic_id=mosaic_id,
            node_id=node_id,
            mode=mode,
            model=model,
            config=config or {},
            status="active"
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        logger.info(
            f"Created session {session.session_id} for user {user_id} "
            f"on node {node_id} in mosaic {mosaic_id}"
        )

        return session

    @staticmethod
    async def get_session(
        db: AsyncSession,
        session_id: str,
        user_id: Optional[int] = None
    ) -> Session:
        """
        Get session by ID.

        Args:
            db: Database session
            session_id: Session UUID
            user_id: Optional user ID for ownership check

        Returns:
            Session object

        Raises:
            NotFoundError: If session not found or access denied
        """
        query = select(Session).where(
            Session.session_id == session_id,
            Session.deleted_at.is_(None)
        )

        if user_id is not None:
            query = query.where(Session.user_id == user_id)

        result = await db.execute(query)
        session = result.scalar_one_or_none()

        if not session:
            raise NotFoundError(f"Session {session_id} not found")

        return session

    @staticmethod
    async def list_sessions(
        db: AsyncSession,
        user_id: int,
        mosaic_id: Optional[int] = None,
        node_id: Optional[int] = None,
        status: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Session]:
        """
        List sessions for a user.

        Args:
            db: Database session
            user_id: Owner user ID
            mosaic_id: Optional filter by mosaic
            node_id: Optional filter by node
            status: Optional filter by status (active/archived)
            include_archived: Include archived sessions (default: False)
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of sessions
        """
        query = select(Session).where(
            Session.user_id == user_id,
            Session.deleted_at.is_(None)
        )

        if mosaic_id is not None:
            query = query.where(Session.mosaic_id == mosaic_id)

        if node_id is not None:
            query = query.where(Session.node_id == node_id)

        # Filter by status
        if status is not None:
            query = query.where(Session.status == status)
        elif not include_archived:
            # By default, show active and closed sessions, exclude archived
            query = query.where(Session.status.in_(["active", "closed"]))

        # Order by last activity (most recent first)
        query = query.order_by(Session.last_activity_at.desc())

        # Pagination
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        sessions = result.scalars().all()

        return list(sessions)

    @staticmethod
    async def count_sessions(
        db: AsyncSession,
        user_id: int,
        mosaic_id: Optional[int] = None,
        node_id: Optional[int] = None,
        status: Optional[str] = None,
        include_archived: bool = False
    ) -> int:
        """
        Count total sessions matching the filter criteria.

        Args:
            db: Database session
            user_id: Owner user ID
            mosaic_id: Optional filter by mosaic
            node_id: Optional filter by node
            status: Optional filter by status (active/archived)
            include_archived: Include archived sessions (default: False)

        Returns:
            Total count of matching sessions
        """
        query = select(func.count(Session.id)).where(
            Session.user_id == user_id,
            Session.deleted_at.is_(None)
        )

        if mosaic_id is not None:
            query = query.where(Session.mosaic_id == mosaic_id)

        if node_id is not None:
            query = query.where(Session.node_id == node_id)

        # Filter by status
        if status is not None:
            query = query.where(Session.status == status)
        elif not include_archived:
            # By default, show active and closed sessions, exclude archived
            query = query.where(Session.status.in_(["active", "closed"]))

        result = await db.execute(query)
        total = result.scalar_one()

        return total

    @staticmethod
    async def update_activity(
        db: AsyncSession,
        session_id: str
    ):
        """
        Update last activity timestamp and increment message count.

        Args:
            db: Database session
            session_id: Session UUID
        """
        session = await SessionService.get_session(db, session_id)
        session.last_activity_at = datetime.now()
        session.message_count += 1
        await db.commit()

    @staticmethod
    async def update_statistics(
        db: AsyncSession,
        session_id: str,
        total_input_tokens: int,
        total_output_tokens: int,
        total_cost_usd: float
    ):
        """
        Update token and cost statistics.

        Args:
            db: Database session
            session_id: Session UUID
            total_input_tokens: Cumulative input tokens
            total_output_tokens: Cumulative output tokens
            total_cost_usd: Cumulative cost in USD
        """
        session = await SessionService.get_session(db, session_id)
        session.total_input_tokens = total_input_tokens
        session.total_output_tokens = total_output_tokens
        session.total_cost_usd = total_cost_usd
        session.last_activity_at = datetime.now()
        await db.commit()

        logger.debug(
            f"Updated session {session_id} statistics: "
            f"{total_input_tokens} input tokens, "
            f"{total_output_tokens} output tokens, "
            f"${total_cost_usd:.4f}"
        )

    @staticmethod
    async def archive_session(
        db: AsyncSession,
        session_id: str,
        user_id: Optional[int] = None
    ) -> Session:
        """
        Archive a session.

        This marks the session as archived but does not delete it.
        Archived sessions are hidden from the active session list by default.

        Args:
            db: Database session
            session_id: Session UUID
            user_id: Optional user ID for ownership check

        Returns:
            Updated session

        Raises:
            NotFoundError: Session not found
            ValidationError: Session is already archived
        """
        from ..exceptions import ValidationError

        session = await SessionService.get_session(db, session_id, user_id)

        if session.status == "archived":
            raise ValidationError("Session is already archived")

        session.status = "archived"
        session.closed_at = datetime.now()
        session.updated_at = datetime.now()

        await db.commit()
        await db.refresh(session)

        logger.info(f"Archived session {session_id}")

        return session

    @staticmethod
    async def unarchive_session(
        db: AsyncSession,
        session_id: str,
        user_id: Optional[int] = None
    ) -> Session:
        """
        Unarchive a session.

        This restores an archived session to closed status.
        Note: It cannot restore to active status as the runtime connection is lost.

        Args:
            db: Database session
            session_id: Session UUID
            user_id: Optional user ID for ownership check

        Returns:
            Updated session

        Raises:
            NotFoundError: Session not found
            ValidationError: Session is not archived
        """
        from ..exceptions import ValidationError

        session = await SessionService.get_session(db, session_id, user_id)

        if session.status != "archived":
            raise ValidationError("Session is not archived")

        session.status = "closed"
        session.updated_at = datetime.now()

        await db.commit()
        await db.refresh(session)

        logger.info(f"Unarchived session {session_id}")

        return session

    @staticmethod
    async def close_session(
        db: AsyncSession,
        session_id: str,
        user_id: Optional[int] = None
    ) -> Session:
        """
        Close a session.

        This releases resources and marks the session as closed.
        Closed sessions remain visible in the list but cannot send new messages.
        Cannot be reopened due to session alignment with upstream/downstream nodes.

        Args:
            db: Database session
            session_id: Session UUID
            user_id: Optional user ID for ownership check

        Returns:
            Updated session
        """
        session = await SessionService.get_session(db, session_id, user_id)
        session.status = "closed"
        session.closed_at = datetime.now()
        session.updated_at = datetime.now()
        await db.commit()
        await db.refresh(session)

        logger.info(f"Closed session {session_id}")

        return session

    @staticmethod
    async def close_node_sessions(
        db: AsyncSession,
        node_id: int
    ):
        """
        Close all active sessions for a node.

        This is called when a node is stopped.

        Args:
            db: Database session
            node_id: Node database ID
        """
        result = await db.execute(
            select(Session).where(
                Session.node_id == node_id,
                Session.status == "active",
                Session.deleted_at.is_(None)
            )
        )
        sessions = result.scalars().all()

        closed_count = 0
        for session in sessions:
            session.status = "closed"
            session.closed_at = datetime.now()
            session.updated_at = datetime.now()
            closed_count += 1

        await db.commit()

        logger.info(f"Closed {closed_count} session(s) for node {node_id}")

    @staticmethod
    async def close_mosaic_sessions(
        db: AsyncSession,
        mosaic_id: int
    ):
        """
        Close all active sessions for a mosaic.

        This is called when a mosaic is stopped.

        Args:
            db: Database session
            mosaic_id: Mosaic database ID
        """
        result = await db.execute(
            select(Session).where(
                Session.mosaic_id == mosaic_id,
                Session.status == "active",
                Session.deleted_at.is_(None)
            )
        )
        sessions = result.scalars().all()

        closed_count = 0
        for session in sessions:
            session.status = "closed"
            session.closed_at = datetime.now()
            session.updated_at = datetime.now()
            closed_count += 1

        await db.commit()

        logger.info(f"Closed {closed_count} session(s) for mosaic {mosaic_id}")

    @staticmethod
    async def delete_session(
        db: AsyncSession,
        session_id: str,
        user_id: Optional[int] = None
    ):
        """
        Soft delete a session.

        Args:
            db: Database session
            session_id: Session UUID
            user_id: Optional user ID for ownership check
        """
        session = await SessionService.get_session(db, session_id, user_id)
        session.deleted_at = datetime.now()
        await db.commit()

        logger.info(f"Deleted session {session_id}")

    @staticmethod
    async def delete_node_sessions(
        db: AsyncSession,
        node_id: int
    ):
        """
        Soft delete all sessions for a node.

        This is called when a node is deleted (cascade deletion).

        Args:
            db: Database session
            node_id: Node database ID
        """
        result = await db.execute(
            select(Session).where(
                Session.node_id == node_id,
                Session.deleted_at.is_(None)
            )
        )
        sessions = result.scalars().all()

        deleted_count = 0
        for session in sessions:
            session.deleted_at = datetime.now()
            deleted_count += 1

        await db.commit()

        logger.info(f"Deleted {deleted_count} session(s) for node {node_id}")
