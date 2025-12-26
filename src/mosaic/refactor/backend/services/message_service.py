"""Service layer for message management"""

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from typing import List, Optional

from ..models.message import Message
from ..logger import get_logger

logger = get_logger(__name__)


class MessageService:
    """Service layer for message management"""

    @staticmethod
    async def create_message(
        db: AsyncSession,
        session_id: str,
        role: str,
        message_type: str,
        content: str
    ) -> Message:
        """
        Create a new message.

        Args:
            db: Database session
            session_id: Parent session ID
            role: Message role (user | assistant | system)
            message_type: Message type (user_message | assistant_text | etc.)
            content: JSON string containing message data

        Returns:
            Created message
        """
        # Get next sequence number for this session
        result = await db.execute(
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.deleted_at.is_(None)
            )
            .order_by(Message.sequence.desc())
            .limit(1)
        )
        last_message = result.scalar_one_or_none()
        next_sequence = (last_message.sequence + 1) if last_message else 1

        # Create message
        message = Message(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            type=message_type,
            content=content,
            sequence=next_sequence
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

        logger.debug(
            f"Created message {message.message_id} (seq {next_sequence}) "
            f"in session {session_id}: {role}/{message_type}"
        )

        return message

    @staticmethod
    async def get_session_messages(
        db: AsyncSession,
        session_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Message]:
        """
        Get all messages for a session.

        Args:
            db: Database session
            session_id: Session UUID
            limit: Optional maximum number of messages to return
            offset: Offset for pagination

        Returns:
            List of messages ordered by sequence
        """
        query = select(Message).where(
            Message.session_id == session_id,
            Message.deleted_at.is_(None)
        ).order_by(Message.sequence)

        if offset > 0:
            query = query.offset(offset)

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        messages = result.scalars().all()

        return list(messages)

    @staticmethod
    async def get_message(
        db: AsyncSession,
        message_id: str
    ) -> Optional[Message]:
        """
        Get a single message by ID.

        Args:
            db: Database session
            message_id: Message UUID

        Returns:
            Message object or None if not found
        """
        result = await db.execute(
            select(Message).where(
                Message.message_id == message_id,
                Message.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def delete_message(
        db: AsyncSession,
        message_id: str
    ):
        """
        Soft delete a message.

        Args:
            db: Database session
            message_id: Message UUID
        """
        message = await MessageService.get_message(db, message_id)
        if message:
            from datetime import datetime
            message.deleted_at = datetime.now()
            await db.commit()
            logger.info(f"Deleted message {message_id}")
