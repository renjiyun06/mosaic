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
from typing import Dict, Optional
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
        # User WebSocket connections: {user_id → WebSocket}
        self._user_websockets: Dict[int, WebSocket] = {}

        # Message queues for each user: {user_id → asyncio.Queue}
        # Messages from worker threads are enqueued here
        self._user_queues: Dict[int, asyncio.Queue] = {}

        # Message forwarding tasks: {user_id → asyncio.Task}
        # Keep reference to tasks so we can cancel them on disconnect
        self._user_tasks: Dict[int, asyncio.Task] = {}

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
        If user already has a connection, the old one will be closed.

        Args:
            user_id: User database ID
            websocket: WebSocket connection
        """
        # Close old connection if exists
        if user_id in self._user_websockets:
            old_ws = self._user_websockets[user_id]

            # Check if it's the same WebSocket object
            if old_ws is websocket:
                logger.warning(f"User {user_id} WebSocket already registered, skipping")
                return

            logger.warning(f"User {user_id} reconnecting, closing old connection")
            await self.disconnect_user(user_id)

            # Give time for old connection to fully clean up
            await asyncio.sleep(0.1)

        # Register connection
        self._user_websockets[user_id] = websocket
        self._user_queues[user_id] = asyncio.Queue()

        # Start message forwarding task
        task = asyncio.create_task(self._forward_messages(user_id))
        self._user_tasks[user_id] = task  # Keep reference for cancellation

        # Add callback to catch task exceptions
        def task_done_callback(t: asyncio.Task):
            try:
                if not t.cancelled():  # Check if task was cancelled
                    exc = t.exception()  # Use exception() instead of result()
                    if exc:
                        logger.error(
                            f"Background task failed for user {user_id}: {exc}",
                            exc_info=(type(exc), exc, exc.__traceback__)
                        )
            except Exception as e:
                logger.error(f"Error in task callback for user {user_id}: {e}")

        task.add_done_callback(task_done_callback)

        logger.info(f"User {user_id} WebSocket connected")

    async def disconnect_user(self, user_id: int, websocket: Optional[WebSocket] = None):
        """
        Disconnect user WebSocket.

        Args:
            user_id: User database ID
            websocket: Optional WebSocket object to verify before disconnecting.
                      If provided, only disconnect if it matches the registered one.
        """
        if user_id in self._user_websockets:
            registered_ws = self._user_websockets[user_id]

            # If websocket is provided, only disconnect if it matches
            if websocket is not None and registered_ws is not websocket:
                logger.debug(
                    f"User {user_id} WebSocket mismatch, skipping disconnect "
                    f"(probably already reconnected)"
                )
                return

            # Cancel message forwarding task first
            if user_id in self._user_tasks:
                task = self._user_tasks[user_id]
                if not task.done():
                    task.cancel()
                    try:
                        # Wait for task cancellation with timeout
                        await asyncio.wait_for(task, timeout=1.0)
                    except asyncio.CancelledError:
                        logger.debug(f"Message forwarding task cancelled for user {user_id}")
                    except asyncio.TimeoutError:
                        logger.warning(f"Task cancellation timed out for user {user_id}")
                    except Exception as e:
                        logger.debug(f"Task cancellation error for user {user_id}: {e}")

                del self._user_tasks[user_id]

            try:
                await registered_ws.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket for user {user_id}: {e}")

            del self._user_websockets[user_id]
            del self._user_queues[user_id]

            logger.info(f"User {user_id} WebSocket disconnected")

    async def _forward_messages(self, user_id: int):
        """
        Forward messages from queue to WebSocket.

        Runs in main event loop (Loop A).
        Consumes messages from user queue and sends to WebSocket.

        Args:
            user_id: User database ID
        """
        logger.info(f"Message forwarding task started for user {user_id}")

        # Get queue reference (defensive check)
        queue = self._user_queues.get(user_id)
        if not queue:
            logger.error(f"Queue not found for user {user_id}, task exiting")
            return

        try:
            while user_id in self._user_websockets:
                try:
                    # Wait for message from worker threads
                    message = await queue.get()

                    ws = self._user_websockets.get(user_id)
                    if ws:
                        await ws.send_json(message)
                        logger.debug(
                            f"Sent to user {user_id}: "
                            f"type={message.get('message_type')}, "
                            f"session={message.get('session_id')}"
                        )
                    else:
                        logger.warning(f"WebSocket for user {user_id} no longer available")
                        break

                except asyncio.CancelledError:
                    # Task was cancelled (normal during disconnect)
                    logger.debug(f"Message forwarding task cancelled for user {user_id}")
                    raise  # Re-raise to properly cancel the task

                except Exception as e:
                    logger.error(f"Error forwarding message to user {user_id}: {e}", exc_info=True)
                    break

        except asyncio.CancelledError:
            # Task cancellation (normal during disconnect)
            logger.debug(f"Message forwarding task cancelled for user {user_id}")
        finally:
            logger.info(f"Message forwarding task ended for user {user_id}")

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
        if self._main_loop:
            self._main_loop.call_soon_threadsafe(
                self._push_message_internal, user_id, message
            )

    def _push_message_internal(self, user_id: int, message: dict):
        """
        Internal method to push message (runs in main loop).

        This method performs the actual dictionary access and message queuing
        in the main event loop, ensuring thread safety.

        Args:
            user_id: Target user ID
            message: Message dict
        """
        # All checks happen here in the main thread
        if not self._main_loop:
            logger.error("Main loop not set in UserMessageBroker")
            return

        queue = self._user_queues.get(user_id)
        if queue:
            try:
                queue.put_nowait(message)
                logger.debug(
                    f"Message queued for user {user_id}: "
                    f"type={message.get('message_type')}"
                )
            except Exception as e:
                logger.error(f"Failed to queue message for user {user_id}: {e}")
        else:
            logger.debug(f"No WebSocket connection for user {user_id}, message dropped")

    def is_user_connected(self, user_id: int) -> bool:
        """
        Check if user has active WebSocket connection.

        Args:
            user_id: User database ID

        Returns:
            True if user is connected, False otherwise
        """
        return user_id in self._user_websockets

    async def disconnect_all_users(self):
        """
        Disconnect all user WebSocket connections.

        Called during application shutdown.
        """
        user_ids = list(self._user_websockets.keys())

        for user_id in user_ids:
            await self.disconnect_user(user_id)

        logger.info(f"Disconnected all users ({len(user_ids)} connections)")
