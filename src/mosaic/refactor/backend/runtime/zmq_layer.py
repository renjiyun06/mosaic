"""ZeroMQ message layer for Mosaic runtime

This module implements the global message broker using ZeroMQ.
Key design: Single ZMQ server instance, topic format: {mosaic_id}#{node_id}
"""
import zmq
import zmq.asyncio
import asyncio
from typing import Callable, Awaitable, Optional

from ..config import settings
from ..logger import get_logger

logger = get_logger(__name__)


class ZmqServer:
    """
    Global ZMQ message broker (singleton).

    Pattern: PULL-PUB
    - PULL socket (5555): Receive messages from all nodes
    - PUB socket (5556): Broadcast messages to subscribed topics

    Topic format: {mosaic_id}#{node_id}
    This ensures complete isolation between different mosaics.
    """

    _instance: Optional['ZmqServer'] = None
    _lock = asyncio.Lock()

    def __init__(self, pull_port: int = 5555, pub_port: int = 5556, db_url: Optional[str] = None):
        self.pull_port = pull_port
        self.pub_port = pub_port
        self._db_url = db_url

        self._context: Optional[zmq.asyncio.Context] = None
        self._pull_sock: Optional[zmq.asyncio.Socket] = None
        self._pub_sock: Optional[zmq.asyncio.Socket] = None
        self._broadcast_task: Optional[asyncio.Task] = None
        self._running = False
        self._engine = None

    @classmethod
    async def get_instance(cls, pull_port: Optional[int] = None, pub_port: Optional[int] = None, db_url: Optional[str] = None) -> 'ZmqServer':
        """Get or create the singleton instance

        Args:
            pull_port: Optional PULL port override (defaults to config)
            pub_port: Optional PUB port override (defaults to config)
            db_url: Optional database URL for event storage
        """
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    # Use provided ports or fallback to settings
                    actual_pull_port = pull_port if pull_port is not None else settings.runtime_zmq_pull_port
                    actual_pub_port = pub_port if pub_port is not None else settings.runtime_zmq_pub_port
                    cls._instance = cls(pull_port=actual_pull_port, pub_port=actual_pub_port, db_url=db_url)
                    await cls._instance.start()
        return cls._instance

    async def start(self):
        """Start the ZMQ server"""
        if self._running:
            logger.warning("ZmqServer already running")
            return

        # Create database engine if db_url is provided
        if self._db_url:
            from sqlalchemy.ext.asyncio import create_async_engine
            # Convert sqlite:/// to sqlite+aiosqlite:/// for async driver
            async_db_url = self._db_url.replace("sqlite://", "sqlite+aiosqlite://")
            self._engine = create_async_engine(async_db_url, echo=False)
            logger.info("ZmqServer database connection initialized")

        self._context = zmq.asyncio.Context()

        # PULL socket: receive from all nodes
        self._pull_sock = self._context.socket(zmq.PULL)
        self._pull_sock.bind(f"tcp://0.0.0.0:{self.pull_port}")

        # PUB socket: broadcast to all nodes
        self._pub_sock = self._context.socket(zmq.PUB)
        self._pub_sock.bind(f"tcp://0.0.0.0:{self.pub_port}")

        # Start broadcast loop
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())

        self._running = True
        logger.info(
            f"Global ZmqServer started: PULL={self.pull_port}, PUB={self.pub_port}"
        )

    async def stop(self):
        """Stop the ZMQ server"""
        if not self._running:
            return

        self._running = False

        # Cancel broadcast task
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

        # Close sockets
        if self._pull_sock:
            self._pull_sock.close()
        if self._pub_sock:
            self._pub_sock.close()

        # Terminate context
        if self._context:
            self._context.term()

        # Close database engine
        if self._engine:
            await self._engine.dispose()
            logger.info("ZmqServer database connection closed")

        logger.info("Global ZmqServer stopped")

    async def _broadcast_loop(self):
        """
        Continuously receive and broadcast messages.

        Message format:
        - topic: {mosaic_id}#{node_id}
        - event: JSON data
        """
        logger.info("ZmqServer broadcast loop started")

        while self._running:
            try:
                # Receive: topic + event
                topic = await self._pull_sock.recv_string()
                event = await self._pull_sock.recv_json()

                logger.info(
                    f"[ZMQ_SERVER] Received event on PULL socket: topic={topic}, "
                    f"event_id={event.get('event_id')}, event_type={event.get('event_type')}"
                )

                # Broadcast to subscribers of this topic
                await self._pub_sock.send_string(topic, zmq.SNDMORE)
                await self._pub_sock.send_json(event)

                logger.info(
                    f"[ZMQ_SERVER] Broadcasted event to PUB socket: topic={topic}, "
                    f"event_id={event.get('event_id')}"
                )

                # Store event to database (non-blocking)
                if self._engine:
                    logger.debug(f"[ZMQ_SERVER] Storing event {event.get('event_id')} to database")
                    asyncio.create_task(self._store_event(event, topic))
                else:
                    logger.warning(f"[ZMQ_SERVER] No database engine, skipping event storage")

            except asyncio.CancelledError:
                logger.info("Broadcast loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}", exc_info=True)

    async def _store_event(self, event: dict, topic: str):
        """
        Store event to database

        Args:
            event: Event dict containing event_id, source_id, target_id, etc.
            topic: ZMQ topic in format "{mosaic_id}#{node_id}"
        """
        try:
            logger.info(
                f"[ZMQ_STORAGE] Starting to store event {event.get('event_id')} "
                f"from topic {topic}"
            )

            # Parse mosaic_id from topic
            mosaic_id_str, _ = topic.split("#")
            mosaic_id = int(mosaic_id_str)

            logger.debug(f"[ZMQ_STORAGE] Parsed mosaic_id={mosaic_id} from topic")

            # Get user_id from target node
            from sqlmodel.ext.asyncio.session import AsyncSession
            from sqlmodel import select
            from ..models.node import Node

            async with AsyncSession(self._engine) as db:
                # Convert target_id from string to int for database query
                target_node_id = int(event['target_id'])
                logger.debug(
                    f"[ZMQ_STORAGE] Querying user_id for target_node_id={target_node_id} "
                    f"(converted from string '{event['target_id']}')"
                )
                result = await db.execute(
                    select(Node.user_id).where(Node.id == target_node_id)
                )
                user_id = result.scalar_one_or_none()

                if user_id is None:
                    logger.warning(
                        f"[ZMQ_STORAGE] Cannot store event {event['event_id']}: "
                        f"target node {event['target_id']} not found"
                    )
                    return

                logger.debug(f"[ZMQ_STORAGE] Found user_id={user_id}")

                # Store event
                from ..services.event_service import EventService
                await EventService.create_event(
                    db=db,
                    event_data=event,
                    user_id=user_id,
                    mosaic_id=mosaic_id
                )

                logger.info(
                    f"[ZMQ_STORAGE] Successfully stored event {event['event_id']} to database"
                )

        except Exception as e:
            logger.error(f"[ZMQ_STORAGE] Failed to store event to database: {e}", exc_info=True)
            # Don't raise - event delivery should not fail due to storage issues


class ZmqClient:
    """
    ZMQ client for a node.

    Pattern: PUSH-SUB
    - PUSH socket: Send messages to global server
    - SUB socket: Subscribe to messages for this node

    Subscribe topic: {mosaic_id}#{node_id}
    This ensures the node only receives messages intended for it.
    """

    def __init__(
        self,
        mosaic_id: str,
        node_id: str,
        server_host: str = "localhost",
        server_pull_port: int = 5555,
        server_pub_port: int = 5556,
        on_event: Optional[Callable[[dict], Awaitable[None]]] = None
    ):
        self.mosaic_id = mosaic_id
        self.node_id = node_id
        self.subscribe_topic = f"{mosaic_id}#{node_id}"  # Key design point

        self.server_host = server_host
        self.server_pull_port = server_pull_port
        self.server_pub_port = server_pub_port
        self.on_event = on_event

        self._context: Optional[zmq.asyncio.Context] = None
        self._push_sock: Optional[zmq.asyncio.Socket] = None
        self._sub_sock: Optional[zmq.asyncio.Socket] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._connected = False

    def connect(self):
        """Connect to global ZMQ server"""
        if self._connected:
            logger.warning(f"ZmqClient already connected: {self.subscribe_topic}")
            return

        self._context = zmq.asyncio.Context()

        # PUSH socket: send to server
        self._push_sock = self._context.socket(zmq.PUSH)
        self._push_sock.connect(
            f"tcp://{self.server_host}:{self.server_pull_port}"
        )

        # SUB socket: subscribe to {mosaic_id}#{node_id}
        self._sub_sock = self._context.socket(zmq.SUB)
        self._sub_sock.connect(
            f"tcp://{self.server_host}:{self.server_pub_port}"
        )
        self._sub_sock.subscribe(self.subscribe_topic.encode())

        # Start receive loop
        self._receive_task = asyncio.create_task(self._receive_loop())

        self._connected = True
        logger.info(f"ZmqClient connected: topic={self.subscribe_topic}")

    def disconnect(self):
        """Disconnect from ZMQ server"""
        if not self._connected:
            return

        self._connected = False

        # Cancel receive task
        if self._receive_task:
            self._receive_task.cancel()

        # Close sockets
        if self._push_sock:
            self._push_sock.close()
        if self._sub_sock:
            self._sub_sock.close()

        # Terminate context
        if self._context:
            self._context.term()

        logger.info(f"ZmqClient disconnected: topic={self.subscribe_topic}")

    async def send(self, target_mosaic_id: str, target_node_id: str, event: dict):
        """
        Send an event to a target node.

        Args:
            target_mosaic_id: Mosaic ID of target node
            target_node_id: ID of target node
            event: Event data (must be JSON-serializable)
        """
        if not self._connected:
            raise RuntimeError("ZmqClient not connected")

        # Construct topic: {mosaic_id}#{node_id}
        topic = f"{target_mosaic_id}#{target_node_id}"

        logger.info(
            f"[ZMQ_CLIENT_SEND] Sending event via PUSH socket: "
            f"topic={topic}, event_id={event.get('event_id')}, "
            f"event_type={event.get('event_type')}, my_topic={self.subscribe_topic}"
        )

        await self._push_sock.send_string(topic, zmq.SNDMORE)
        await self._push_sock.send_json(event)

        logger.info(f"[ZMQ_CLIENT_SEND] Successfully sent event to topic: {topic}")

    async def _receive_loop(self):
        """Continuously receive messages"""
        logger.info(f"[ZMQ_CLIENT_RECV] Receive loop started, subscribed to: {self.subscribe_topic}")

        while self._connected:
            try:
                # Receive: topic + event
                topic = await self._sub_sock.recv_string()
                event = await self._sub_sock.recv_json()

                logger.info(
                    f"[ZMQ_CLIENT_RECV] Received event on SUB socket: "
                    f"topic={topic}, event_id={event.get('event_id')}, "
                    f"event_type={event.get('event_type')}, my_topic={self.subscribe_topic}"
                )

                # Verify topic matches (should always match due to subscription)
                if topic != self.subscribe_topic:
                    logger.warning(
                        f"[ZMQ_CLIENT_RECV] Received message for wrong topic: {topic} "
                        f"(expected {self.subscribe_topic})"
                    )
                    continue

                # Process event asynchronously
                if self.on_event:
                    logger.info(
                        f"[ZMQ_CLIENT_RECV] Dispatching event {event.get('event_id')} "
                        f"to on_event callback"
                    )
                    asyncio.create_task(self.on_event(event))
                else:
                    logger.warning(
                        f"[ZMQ_CLIENT_RECV] No on_event callback registered, "
                        f"dropping event {event.get('event_id')}"
                    )

            except asyncio.CancelledError:
                logger.info(f"[ZMQ_CLIENT_RECV] Receive loop cancelled: {self.subscribe_topic}")
                break
            except Exception as e:
                logger.error(
                    f"[ZMQ_CLIENT_RECV] Error in receive loop ({self.subscribe_topic}): {e}",
                    exc_info=True
                )
