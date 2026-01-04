"""User-level WebSocket message broker.

This module manages WebSocket connections at the user level (one connection per user)
instead of session level (one connection per session).

Key features:
- Thread-safe message delivery from worker threads
- Single WebSocket connection per user
- Message routing by session_id in message payload
- Async message forwarding from queue to WebSocket

Architecture:
    Worker Thread (Loop B)
        ClaudeCodeSession
            ↓ user_broker.push_from_worker(user_id, msg)
            ↓ call_soon_threadsafe
    FastAPI Main Thread (Loop A)
        UserMessageBroker._forward_messages(user_id)
            ↓ queue.get()
            ↓ websocket.send_json(msg)
        Browser
"""

import asyncio
import logging
from typing import Dict, Optional, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class UserMessageBroker:
    """
    Global message broker for user WebSocket connections.

    This is a singleton managed by the FastAPI application (stored in app.state).

    Responsibilities:
    - Manage user WebSocket connections (one per user)
    - Route messages from worker threads to user WebSockets
    - Thread-safe message delivery via call_soon_threadsafe

    Lifecycle:
    - Created once during application startup via create_instance()
    - Stored in app.state.user_message_broker
    - Cleaned up during application shutdown
    """

    # Singleton instance
    _instance: Optional['UserMessageBroker'] = None

    def __init__(self):
        # User WebSocket connections: {user_id → Set[WebSocket]}
        # Each user can have multiple connections (e.g., multiple browser tabs)
        self._user_websockets: Dict[int, Set[WebSocket]] = {}

        # Message queues for each connection: {user_id → {WebSocket → asyncio.Queue}}
        # Each connection has its own queue for independent message delivery
        self._user_queues: Dict[int, Dict[WebSocket, asyncio.Queue]] = {}

        # Message forwarding tasks: {user_id → {WebSocket → asyncio.Task}}
        # Each connection has its own forwarding task
        self._user_tasks: Dict[int, Dict[WebSocket, asyncio.Task]] = {}

        # Main event loop reference (set on startup)
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

    @classmethod
    def create_instance(cls) -> 'UserMessageBroker':
        """
        Create singleton instance of UserMessageBroker.

        This should be called once during application startup.

        Returns:
            Created UserMessageBroker instance

        Raises:
            RuntimeError: If instance already exists
        """
        if cls._instance is not None:
            raise RuntimeError("UserMessageBroker already initialized")

        cls._instance = cls()
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'UserMessageBroker':
        """
        Get the singleton instance.

        Returns:
            UserMessageBroker instance

        Raises:
            RuntimeError: If instance not yet created
        """
        if cls._instance is None:
            raise RuntimeError(
                "UserMessageBroker not initialized. "
                "Call create_instance() during application startup."
            )
        return cls._instance

    def set_main_loop(self, loop: asyncio.AbstractEventLoop):
        """
        Set main event loop reference.

        Must be called during application startup.

        Args:
            loop: Main FastAPI event loop
        """
        self._main_loop = loop
        logger.info("UserMessageBroker: Main event loop set")

    async def connect_user(self, user_id: int, websocket: WebSocket):
        """
        Register user WebSocket connection.

        Called from main event loop when user connects.
        Supports multiple concurrent connections per user (e.g., multiple browser tabs).

        Args:
            user_id: User database ID
            websocket: WebSocket connection
        """
        # Initialize user's connection set if first connection
        if user_id not in self._user_websockets:
            logger.debug(f"Initializing connection set for user {user_id}")
            self._user_websockets[user_id] = set()
            self._user_queues[user_id] = {}
            self._user_tasks[user_id] = {}

        # Check if this WebSocket is already registered
        if websocket in self._user_websockets[user_id]:
            logger.warning(
                f"User {user_id} WebSocket already registered (ws_id={id(websocket)}), skipping"
            )
            return

        # Add connection to set
        self._user_websockets[user_id].add(websocket)

        # Create independent queue for this connection
        self._user_queues[user_id][websocket] = asyncio.Queue()

        # Start independent message forwarding task for this connection
        task = asyncio.create_task(self._forward_messages(user_id, websocket))
        self._user_tasks[user_id][websocket] = task

        # Add callback to catch task exceptions
        def task_done_callback(t: asyncio.Task):
            try:
                if not t.cancelled():
                    exc = t.exception()
                    if exc:
                        logger.error(
                            f"Forwarding task failed for user {user_id} "
                            f"(ws_id={id(websocket)}): {exc}",
                            exc_info=(type(exc), exc, exc.__traceback__)
                        )
            except Exception as e:
                logger.error(
                    f"Error in task callback for user {user_id} "
                    f"(ws_id={id(websocket)}): {e}"
                )

        task.add_done_callback(task_done_callback)

        connection_count = len(self._user_websockets[user_id])
        logger.info(
            f"User {user_id} WebSocket connected (ws_id={id(websocket)}), "
            f"total_connections={connection_count}"
        )

    async def disconnect_user(self, user_id: int, websocket: Optional[WebSocket] = None):
        """
        Disconnect user WebSocket connection.

        Args:
            user_id: User database ID
            websocket: Optional WebSocket object to disconnect.
                      If None, all connections for the user will be disconnected.
                      If provided, only that specific connection will be disconnected.
        """
        if user_id not in self._user_websockets:
            logger.debug(f"User {user_id} has no connections to disconnect")
            return

        # If websocket specified, disconnect only that connection
        if websocket is not None:
            if websocket not in self._user_websockets[user_id]:
                logger.debug(
                    f"User {user_id} WebSocket not found (ws_id={id(websocket)}), "
                    f"probably already disconnected"
                )
                return

            logger.debug(
                f"Disconnecting specific WebSocket for user {user_id} (ws_id={id(websocket)})"
            )

            # Cancel message forwarding task for this connection
            if websocket in self._user_tasks[user_id]:
                task = self._user_tasks[user_id][websocket]
                if not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=1.0)
                    except asyncio.CancelledError:
                        logger.debug(
                            f"Forwarding task cancelled for user {user_id} (ws_id={id(websocket)})"
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"Task cancellation timed out for user {user_id} (ws_id={id(websocket)})"
                        )
                    except Exception as e:
                        logger.debug(
                            f"Task cancellation error for user {user_id} (ws_id={id(websocket)}): {e}"
                        )

                del self._user_tasks[user_id][websocket]

            # Close WebSocket
            try:
                await websocket.close()
            except Exception as e:
                logger.debug(
                    f"Error closing WebSocket for user {user_id} (ws_id={id(websocket)}): {e}"
                )

            # Remove from connection set
            self._user_websockets[user_id].discard(websocket)

            # Remove queue
            if websocket in self._user_queues[user_id]:
                del self._user_queues[user_id][websocket]

            remaining_connections = len(self._user_websockets[user_id])

            # Clean up user entry if no more connections
            if remaining_connections == 0:
                logger.debug(f"User {user_id} has no more connections, cleaning up user entry")
                del self._user_websockets[user_id]
                del self._user_queues[user_id]
                del self._user_tasks[user_id]

            logger.info(
                f"User {user_id} WebSocket disconnected (ws_id={id(websocket)}), "
                f"remaining_connections={remaining_connections}"
            )

        # If no websocket specified, disconnect all connections
        else:
            logger.debug(f"Disconnecting all WebSockets for user {user_id}")
            websockets = list(self._user_websockets[user_id])

            for ws in websockets:
                await self.disconnect_user(user_id, ws)

            logger.info(
                f"All WebSocket connections disconnected for user {user_id} "
                f"(count={len(websockets)})"
            )

    async def _forward_messages(self, user_id: int, websocket: WebSocket):
        """
        Forward messages from connection-specific queue to WebSocket.

        Runs in main event loop (Loop A).
        Each connection has its own independent forwarding task.

        Args:
            user_id: User database ID
            websocket: Specific WebSocket connection
        """
        ws_id = id(websocket)
        logger.info(
            f"Message forwarding task started for user {user_id} (ws_id={ws_id})"
        )

        # Get connection-specific queue (defensive check)
        if user_id not in self._user_queues or websocket not in self._user_queues[user_id]:
            logger.error(
                f"Queue not found for user {user_id} (ws_id={ws_id}), task exiting"
            )
            return

        queue = self._user_queues[user_id][websocket]

        try:
            while user_id in self._user_websockets and websocket in self._user_websockets[user_id]:
                try:
                    # Wait for message from worker threads
                    message = await queue.get()

                    # Double-check connection still exists before sending
                    if user_id in self._user_websockets and websocket in self._user_websockets[user_id]:
                        await websocket.send_json(message)
                        logger.debug(
                            f"Sent to user {user_id} (ws_id={ws_id}): "
                            f"type={message.get('message_type')}, "
                            f"session={message.get('session_id')}"
                        )
                    else:
                        logger.warning(
                            f"WebSocket for user {user_id} (ws_id={ws_id}) no longer available"
                        )
                        break

                except asyncio.CancelledError:
                    # Task was cancelled (normal during disconnect)
                    logger.debug(
                        f"Message forwarding task cancelled for user {user_id} (ws_id={ws_id})"
                    )
                    raise  # Re-raise to properly cancel the task

                except Exception as e:
                    logger.error(
                        f"Error forwarding message to user {user_id} (ws_id={ws_id}): {e}",
                        exc_info=True
                    )
                    break

        except asyncio.CancelledError:
            # Task cancellation (normal during disconnect)
            logger.debug(
                f"Message forwarding task cancelled for user {user_id} (ws_id={ws_id})"
            )
        finally:
            logger.info(
                f"Message forwarding task ended for user {user_id} (ws_id={ws_id})"
            )

    def push_from_worker(self, user_id: int, message: dict):
        """
        Push message from worker thread to user WebSocket.

        Thread-safe method called from worker threads (any Loop B).
        All dictionary access is delegated to main loop for thread safety.

        Args:
            user_id: Target user ID
            message: Message dict (should include 'session_id' field)

        Note:
            This method schedules the operation in the main event loop.
            No direct dictionary access happens in worker threads.

            The _main_loop reference is read-only after initialization (set once
            during startup before any worker threads start), making this access safe.
        """
        # Schedule message delivery in main loop (thread-safe)
        # All checks and dictionary access happen in main thread
        logger.debug(f"Pushing message to WebSocket: user_id={user_id}, message={message}")
        if self._main_loop:
            self._main_loop.call_soon_threadsafe(
                self._push_message_internal, user_id, message
            )

    def _push_message_internal(self, user_id: int, message: dict):
        """
        Internal method to push message (runs in main loop).

        Broadcasts the message to all active connections for the user.
        Each connection has its own queue, ensuring independent delivery.

        Args:
            user_id: Target user ID
            message: Message dict
        """
        # All checks happen here in the main thread
        if not self._main_loop:
            logger.error("Main loop not set in UserMessageBroker")
            return

        # Get all queues for this user
        user_queues = self._user_queues.get(user_id)
        if not user_queues:
            logger.debug(f"No WebSocket connections for user {user_id}, message dropped")
            return

        # Broadcast to all connections
        success_count = 0
        failed_count = 0

        for websocket, queue in user_queues.items():
            try:
                queue.put_nowait(message)
                success_count += 1
                logger.debug(
                    f"Message queued for user {user_id} (ws_id={id(websocket)}): "
                    f"type={message.get('message_type')}"
                )
            except Exception as e:
                failed_count += 1
                logger.error(
                    f"Failed to queue message for user {user_id} (ws_id={id(websocket)}): {e}"
                )

        total_connections = len(user_queues)
        logger.debug(
            f"Message broadcast for user {user_id}: "
            f"success={success_count}, failed={failed_count}, total={total_connections}"
        )

    def is_user_connected(self, user_id: int) -> bool:
        """
        Check if user has any active WebSocket connections.

        Args:
            user_id: User database ID

        Returns:
            True if user has at least one active connection, False otherwise
        """
        return user_id in self._user_websockets and len(self._user_websockets[user_id]) > 0

    async def disconnect_all_users(self):
        """
        Disconnect all user WebSocket connections.

        Called during application shutdown.
        Iterates through all users and disconnects all their connections.
        """
        user_ids = list(self._user_websockets.keys())
        total_connections = sum(len(connections) for connections in self._user_websockets.values())

        logger.info(
            f"Disconnecting all users: {len(user_ids)} users, {total_connections} connections"
        )

        for user_id in user_ids:
            # disconnect_user with no websocket parameter will disconnect all connections
            await self.disconnect_user(user_id)

        logger.info(
            f"Disconnected all users: {len(user_ids)} users, {total_connections} connections"
        )
