"""WebSocket connection manager"""

import asyncio
import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages active WebSocket connections for sessions.

    Key design: Direct connection mapping, no ZMQ bridge.
    Each session has at most one active WebSocket connection.
    """

    def __init__(self):
        # Active connections: {session_id: WebSocket}
        self._connections: Dict[str, WebSocket] = {}
        # Locks for thread-safe sending: {session_id: asyncio.Lock}
        self._locks: Dict[str, asyncio.Lock] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        """
        Register a new WebSocket connection.

        If a connection already exists for this session, the old one will be closed.

        Args:
            session_id: Session UUID
            websocket: WebSocket connection
        """
        if session_id in self._connections:
            logger.warning(
                f"Session {session_id} already has an active connection, "
                f"closing old connection"
            )
            await self.disconnect(session_id)

        self._connections[session_id] = websocket
        self._locks[session_id] = asyncio.Lock()

        logger.info(f"WebSocket connected for session {session_id}")

    async def disconnect(self, session_id: str):
        """
        Remove WebSocket connection.

        Args:
            session_id: Session UUID
        """
        if session_id in self._connections:
            ws = self._connections[session_id]
            try:
                await ws.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket for session {session_id}: {e}")

            del self._connections[session_id]
            del self._locks[session_id]

            logger.info(f"WebSocket disconnected for session {session_id}")

    async def send_message(self, session_id: str, message: dict):
        """
        Send message to WebSocket client.

        This is called directly by ClaudeCodeSession via callback.

        Args:
            session_id: Session UUID
            message: Message dict to send (will be JSON serialized)
        """
        if session_id not in self._connections:
            logger.warning(
                f"No active WebSocket connection for session {session_id}"
            )
            return

        ws = self._connections[session_id]
        lock = self._locks[session_id]

        async with lock:
            try:
                await ws.send_json(message)
                logger.debug(
                    f"Sent message to session {session_id}: {message.get('type')}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to send message to session {session_id}: {e}",
                    exc_info=True
                )
                # Disconnect on error
                await self.disconnect(session_id)

    def is_connected(self, session_id: str) -> bool:
        """
        Check if session has active WebSocket connection.

        Args:
            session_id: Session UUID

        Returns:
            True if connected, False otherwise
        """
        return session_id in self._connections

    async def disconnect_by_node(self, node_id: int):
        """
        Disconnect all WebSocket connections for a specific node.

        This is called when a node is stopped.

        Args:
            node_id: Node database ID (primary key)
        """
        from sqlmodel import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from ..models.session import Session
        from ..database import engine

        # Find all sessions for this node
        async with AsyncSession(engine) as db:
            result = await db.execute(
                select(Session.session_id).where(
                    Session.node_id == node_id,
                    Session.deleted_at.is_(None)
                )
            )
            session_ids = [row[0] for row in result.all()]

        # Disconnect all WebSockets for these sessions
        for session_id in session_ids:
            await self.disconnect(session_id)

        logger.info(
            f"Disconnected {len(session_ids)} WebSocket(s) for node {node_id}"
        )

    async def disconnect_by_mosaic(self, mosaic_id: int):
        """
        Disconnect all WebSocket connections for a specific mosaic.

        This is called when a mosaic is stopped.

        Args:
            mosaic_id: Mosaic database ID (primary key)
        """
        from sqlmodel import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from ..models.session import Session
        from ..database import engine

        # Find all sessions for this mosaic
        async with AsyncSession(engine) as db:
            result = await db.execute(
                select(Session.session_id).where(
                    Session.mosaic_id == mosaic_id,
                    Session.deleted_at.is_(None)
                )
            )
            session_ids = [row[0] for row in result.all()]

        # Disconnect all WebSockets for these sessions
        for session_id in session_ids:
            await self.disconnect(session_id)

        logger.info(
            f"Disconnected {len(session_ids)} WebSocket(s) for mosaic {mosaic_id}"
        )


# Global singleton
ws_manager = WebSocketManager()
