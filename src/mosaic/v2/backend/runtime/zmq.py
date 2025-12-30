"""ZeroMQ message layer for Mosaic runtime

This module implements the global message broker using ZeroMQ.
Pattern: PULL-PUB (server) + PUSH-SUB (client)
Topic format: {mosaic_id}#{node_id}
"""
import zmq
import zmq.asyncio
import asyncio
import logging
from typing import Callable, Awaitable, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class ZmqServer:
    """
    Global ZMQ message broker (singleton).

    Pattern: PULL-PUB
    - PULL socket (default 5555): Receive messages from all nodes across all mosaics
    - PUB socket (default 5556): Broadcast messages to subscribed topics

    Topic format: {mosaic_id}#{node_id}
    This ensures complete isolation between different mosaics and precise routing to target nodes.

    The server acts as a simple relay and event store:
    1. Receive (topic, event) from PULL socket
    2. Broadcast (topic, event) to PUB socket
    3. Persist event to database (non-blocking)

    This is a global singleton service, similar to an external message queue like Kafka.
    It serves all mosaics and users in the instance.
    """

    _instance: Optional['ZmqServer'] = None

    def __init__(
        self,
        async_session_factory,
        host: str,
        pull_port: int,
        pub_port: int
    ):
        """Initialize ZMQ server

        Args:
            async_session_factory: AsyncSession factory from app.state (shared connection pool)
            host: Host address to bind to
            pull_port: PULL socket port
            pub_port: PUB socket port
        """
        self.async_session_factory = async_session_factory
        self.host = host
        self.pull_port = pull_port
        self.pub_port = pub_port

        # ZMQ components
        self._context: Optional[zmq.asyncio.Context] = None
        self._pull_sock: Optional[zmq.asyncio.Socket] = None
        self._pub_sock: Optional[zmq.asyncio.Socket] = None
        self._broadcast_task: Optional[asyncio.Task] = None
        self._running = False

        logger.info(
            f"ZmqServer initialized (global singleton): "
            f"host={host}, pull_port={pull_port}, pub_port={pub_port}"
        )

    @classmethod
    async def get_instance(
        cls,
        async_session_factory,
        host: str,
        pull_port: int,
        pub_port: int
    ) -> 'ZmqServer':
        """Get or create the global singleton instance

        Args:
            async_session_factory: AsyncSession factory from app.state (shared connection pool)
            host: Host address to bind to
            pull_port: PULL socket port
            pub_port: PUB socket port

        Returns:
            Global ZmqServer instance
        """
        if cls._instance is None:
            cls._instance = cls(
                async_session_factory=async_session_factory,
                host=host,
                pull_port=pull_port,
                pub_port=pub_port
            )
            await cls._instance.start()
            logger.info("Global ZmqServer singleton created and started")
        return cls._instance

    @classmethod
    async def shutdown_instance(cls):
        """Shutdown the global singleton instance"""
        if cls._instance is not None:
            await cls._instance.stop()
            cls._instance = None
            logger.info("Global ZmqServer singleton shutdown")

    async def start(self):
        """Start the ZMQ server

        Creates PULL and PUB sockets, binds to ports, and starts the broadcast loop.
        """
        if self._running:
            logger.warning("ZmqServer already running")
            return

        logger.info("Starting global ZmqServer...")

        # Initialize ZMQ context and sockets
        self._context = zmq.asyncio.Context()

        # PULL socket: receive from all nodes
        self._pull_sock = self._context.socket(zmq.PULL)
        self._pull_sock.bind(f"tcp://{self.host}:{self.pull_port}")
        logger.info(f"ZmqServer PULL socket bound: {self.host}:{self.pull_port}")

        # PUB socket: broadcast to all nodes
        self._pub_sock = self._context.socket(zmq.PUB)
        self._pub_sock.bind(f"tcp://{self.host}:{self.pub_port}")
        logger.info(f"ZmqServer PUB socket bound: {self.host}:{self.pub_port}")

        # Start broadcast loop
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        self._running = True

        logger.info(
            f"ZmqServer started successfully: {self.host}:{self.pull_port} (PULL), "
            f"{self.host}:{self.pub_port} (PUB)"
        )

    async def stop(self):
        """Stop the ZMQ server

        Cancels the broadcast loop, closes sockets, and cleans up resources.
        """
        if not self._running:
            logger.debug("ZmqServer not running, skip stop")
            return

        logger.info("Stopping global ZmqServer...")

        self._running = False

        # Cancel broadcast task
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                logger.debug("Broadcast task cancelled")

        # Close sockets
        if self._pull_sock:
            self._pull_sock.close()
            logger.debug("PULL socket closed")
        if self._pub_sock:
            self._pub_sock.close()
            logger.debug("PUB socket closed")

        # Terminate context
        if self._context:
            self._context.term()
            logger.debug("ZMQ context terminated")

        logger.info("ZmqServer stopped")

    async def _broadcast_loop(self):
        """
        Continuously receive and broadcast messages.

        Message format (multipart):
        - Part 1 (string): topic in format {mosaic_id}#{node_id}
        - Part 2 (JSON): event data

        Flow:
        1. Receive (topic, event) from PULL socket
        2. Broadcast (topic, event) to PUB socket
        3. Persist event to database (async, non-blocking)
        """
        logger.info(
            f"Broadcast loop started: thread={asyncio.current_task().get_name()}"
        )

        while self._running:
            try:
                # Receive multipart message: [topic, event]
                topic = await self._pull_sock.recv_string()
                event = await self._pull_sock.recv_json()

                event_id = event.get('event_id', 'UNKNOWN')
                event_type = event.get('event_type', 'UNKNOWN')

                logger.info(
                    f"[ZMQ_SERVER_RECV] Received event: topic={topic}, "
                    f"event_id={event_id}, event_type={event_type}"
                )
                logger.debug(
                    f"[ZMQ_SERVER_RECV] Event payload: event_id={event_id}, payload={event}"
                )

                # Broadcast to PUB socket
                await self._pub_sock.send_string(topic, zmq.SNDMORE)
                await self._pub_sock.send_json(event)

                logger.info(
                    f"[ZMQ_SERVER_SEND] Broadcasted event: topic={topic}, "
                    f"event_id={event_id}, event_type={event_type}"
                )

                # Persist to database (non-blocking)
                asyncio.create_task(self._store_event(event, topic))

            except asyncio.CancelledError:
                logger.info("Broadcast loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: error={e}", exc_info=True)

        logger.info("Broadcast loop exited")

    async def _store_event(self, event: dict, topic: str):
        """
        Persist event to database.

        Args:
            event: Event dict containing event_id, event_type, source_*, target_*, payload
            topic: ZMQ topic in format "{mosaic_id}#{node_id}"

        Note:
            This method runs asynchronously and should not block the broadcast loop.
            Errors are logged but do not affect event delivery.

        Implementation:
            - Parse mosaic_id from topic
            - Query user_id from nodes table using target_node_id
            - Store event record with extracted mosaic_id and user_id
        """
        event_id = event.get('event_id', 'UNKNOWN')

        try:
            logger.debug(
                f"[ZMQ_STORAGE] Starting event persistence: event_id={event_id}, topic={topic}"
            )

            # Parse mosaic_id from topic
            topic_parts = topic.split("#")
            if len(topic_parts) != 2:
                logger.warning(
                    f"[ZMQ_STORAGE] Invalid topic format: topic={topic}, "
                    f"event_id={event_id}, expected format: mosaic_id#node_id"
                )
                return

            mosaic_id = int(topic_parts[0])
            target_node_id = event.get('target_node_id')

            if not target_node_id:
                logger.warning(
                    f"[ZMQ_STORAGE] Missing target_node_id in event: "
                    f"event_id={event_id}, topic={topic}"
                )
                return

            logger.debug(
                f"[ZMQ_STORAGE] Parsed from topic: mosaic_id={mosaic_id}, "
                f"target_node_id={target_node_id}"
            )

            # Query user_id from nodes table
            from sqlalchemy import select
            from ..model.node import Node
            from ..model.event import Event

            async with self.async_session_factory() as db:
                # Find user_id for this mosaic
                result = await db.execute(
                    select(Node.user_id).where(
                        Node.mosaic_id == mosaic_id,
                        Node.node_id == target_node_id,
                        Node.deleted_at.is_(None)
                    )
                )
                user_id = result.scalar_one_or_none()

                if user_id is None:
                    logger.warning(
                        f"[ZMQ_STORAGE] Cannot find user_id for target node: "
                        f"mosaic_id={mosaic_id}, node_id={target_node_id}, event_id={event_id}"
                    )
                    return

                logger.debug(
                    f"[ZMQ_STORAGE] Found user_id={user_id} for mosaic_id={mosaic_id}"
                )

                # Create event record
                event_record = Event(
                    event_id=event['event_id'],
                    user_id=user_id,
                    mosaic_id=mosaic_id,
                    event_type=event['event_type'],
                    source_node_id=event['source_node_id'],
                    source_session_id=event['source_session_id'],
                    target_node_id=event['target_node_id'],
                    target_session_id=event['target_session_id'],
                    payload=event.get('payload')
                )

                db.add(event_record)
                await db.commit()

                logger.info(
                    f"[ZMQ_STORAGE] Event persisted successfully: mosaic_id={mosaic_id}, "
                    f"user_id={user_id}, event_id={event_id}, event_type={event['event_type']}"
                )
                logger.debug(
                    f"[ZMQ_STORAGE] Persisted event details: event_id={event_id}, "
                    f"source={event['source_node_id']}/{event['source_session_id']}, "
                    f"target={event['target_node_id']}/{event['target_session_id']}"
                )

        except Exception as e:
            logger.error(
                f"[ZMQ_STORAGE] Failed to persist event: event_id={event_id}, error={e}",
                exc_info=True
            )
            # Don't raise - event delivery should not fail due to storage issues


class ZmqClient:
    """
    ZMQ client for a node.

    Pattern: PUSH-SUB
    - PUSH socket: Send messages to global server's PULL socket
    - SUB socket: Subscribe to messages for this node from server's PUB socket

    Subscribe topic: {mosaic_id}#{node_id}
    This ensures the node only receives messages intended for it.
    """

    def __init__(
        self,
        mosaic_id: int,
        node_id: str,
        server_host: str,
        server_pull_port: int,
        server_pub_port: int,
        on_event: Optional[Callable[[dict], Awaitable[None]]]
    ):
        """Initialize ZMQ client

        Args:
            mosaic_id: Mosaic instance ID
            node_id: Node identifier
            server_host: ZMQ server host
            server_pull_port: Server's PULL port (client connects with PUSH)
            server_pub_port: Server's PUB port (client connects with SUB)
            on_event: Async callback for received events (can be None)
        """
        self.mosaic_id = mosaic_id
        self.node_id = node_id
        self.subscribe_topic = f"{mosaic_id}#{node_id}"
        self.server_host = server_host
        self.server_pull_port = server_pull_port
        self.server_pub_port = server_pub_port
        self.on_event = on_event

        # ZMQ components
        self._context: Optional[zmq.asyncio.Context] = None
        self._push_sock: Optional[zmq.asyncio.Socket] = None
        self._sub_sock: Optional[zmq.asyncio.Socket] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._connected = False

        logger.info(
            f"ZmqClient initialized: mosaic_id={mosaic_id}, node_id={node_id}, "
            f"subscribe_topic={self.subscribe_topic}, server={server_host}"
        )

    def connect(self):
        """Connect to global ZMQ server

        Establishes PUSH socket to send events and SUB socket to receive events.
        Starts the receive loop in the background.
        """
        if self._connected:
            logger.warning(
                f"ZmqClient already connected: topic={self.subscribe_topic}"
            )
            return

        logger.info(f"Connecting ZmqClient: topic={self.subscribe_topic}...")

        self._context = zmq.asyncio.Context()

        # PUSH socket: send to server's PULL socket
        self._push_sock = self._context.socket(zmq.PUSH)
        self._push_sock.connect(
            f"tcp://{self.server_host}:{self.server_pull_port}"
        )
        logger.info(
            f"PUSH socket connected: topic={self.subscribe_topic}, "
            f"server={self.server_host}:{self.server_pull_port}"
        )

        # SUB socket: subscribe to server's PUB socket
        self._sub_sock = self._context.socket(zmq.SUB)
        self._sub_sock.connect(
            f"tcp://{self.server_host}:{self.server_pub_port}"
        )
        self._sub_sock.subscribe(self.subscribe_topic.encode())
        logger.info(
            f"SUB socket connected and subscribed: topic={self.subscribe_topic}, "
            f"server={self.server_host}:{self.server_pub_port}"
        )

        # Start receive loop
        self._receive_task = asyncio.create_task(self._receive_loop())
        self._connected = True

        logger.info(
            f"ZmqClient connected successfully: topic={self.subscribe_topic}"
        )

    def disconnect(self):
        """Disconnect from ZMQ server

        Cancels the receive loop, closes sockets, and cleans up resources.
        """
        if not self._connected:
            logger.debug(
                f"ZmqClient not connected, skip disconnect: topic={self.subscribe_topic}"
            )
            return

        logger.info(f"Disconnecting ZmqClient: topic={self.subscribe_topic}...")

        self._connected = False

        # Cancel receive task
        if self._receive_task:
            self._receive_task.cancel()
            logger.debug(
                f"Receive task cancelled: topic={self.subscribe_topic}"
            )

        # Close sockets
        if self._push_sock:
            self._push_sock.close()
            logger.debug(f"PUSH socket closed: topic={self.subscribe_topic}")
        if self._sub_sock:
            self._sub_sock.close()
            logger.debug(f"SUB socket closed: topic={self.subscribe_topic}")

        # Terminate context
        if self._context:
            self._context.term()
            logger.debug(f"ZMQ context terminated: topic={self.subscribe_topic}")

        logger.info(f"ZmqClient disconnected: topic={self.subscribe_topic}")

    async def send(
        self,
        target_mosaic_id: int,
        target_node_id: str,
        event: dict
    ):
        """
        Send an event to a target node.

        Args:
            target_mosaic_id: Mosaic ID of target node
            target_node_id: Node ID of target node
            event: Event data (must be JSON-serializable dict)

        Raises:
            RuntimeError: If client is not connected

        Note:
            The event dict should contain at minimum:
            - event_id (str): Unique event identifier
            - event_type (str): Event type
            - source_node_id (str): Sender node ID
            - source_session_id (str): Sender session ID
            - target_node_id (str): Recipient node ID
            - target_session_id (str): Recipient session ID
            - payload (Any, optional): Event-specific data
        """
        if not self._connected:
            raise RuntimeError(
                f"ZmqClient not connected: topic={self.subscribe_topic}"
            )

        # Construct target topic
        target_topic = f"{target_mosaic_id}#{target_node_id}"

        event_id = event.get('event_id', 'UNKNOWN')
        event_type = event.get('event_type', 'UNKNOWN')

        logger.info(
            f"[ZMQ_CLIENT_SEND] Sending event: my_topic={self.subscribe_topic}, "
            f"target_topic={target_topic}, event_id={event_id}, event_type={event_type}"
        )
        logger.debug(
            f"[ZMQ_CLIENT_SEND] Event details: event_id={event_id}, "
            f"source={event.get('source_node_id')}/{event.get('source_session_id')}, "
            f"target={event.get('target_node_id')}/{event.get('target_session_id')}, "
            f"payload={event.get('payload')}"
        )

        # Send multipart message: [topic, event]
        await self._push_sock.send_string(target_topic, zmq.SNDMORE)
        await self._push_sock.send_json(event)

        logger.info(
            f"[ZMQ_CLIENT_SEND] Event sent successfully: target_topic={target_topic}, "
            f"event_id={event_id}"
        )

    async def _receive_loop(self):
        """
        Continuously receive messages subscribed to this node.

        Message format (multipart):
        - Part 1 (string): topic (should match subscribe_topic)
        - Part 2 (JSON): event data

        Flow:
        1. Receive (topic, event) from SUB socket
        2. Verify topic matches subscribe_topic
        3. Dispatch to on_event callback (if registered)
        """
        logger.info(
            f"[ZMQ_CLIENT_RECV] Receive loop started: topic={self.subscribe_topic}, "
            f"thread={asyncio.current_task().get_name()}"
        )

        while self._connected:
            try:
                # Receive multipart message: [topic, event]
                topic = await self._sub_sock.recv_string()
                event = await self._sub_sock.recv_json()

                event_id = event.get('event_id', 'UNKNOWN')
                event_type = event.get('event_type', 'UNKNOWN')

                logger.info(
                    f"[ZMQ_CLIENT_RECV] Received event: my_topic={self.subscribe_topic}, "
                    f"received_topic={topic}, event_id={event_id}, event_type={event_type}"
                )
                logger.debug(
                    f"[ZMQ_CLIENT_RECV] Event details: event_id={event_id}, "
                    f"source={event.get('source_node_id')}/{event.get('source_session_id')}, "
                    f"target={event.get('target_node_id')}/{event.get('target_session_id')}, "
                    f"payload={event.get('payload')}"
                )

                # Verify topic matches (should always match due to subscription filter)
                if topic != self.subscribe_topic:
                    logger.warning(
                        f"[ZMQ_CLIENT_RECV] Topic mismatch: received_topic={topic}, "
                        f"expected_topic={self.subscribe_topic}, event_id={event_id}"
                    )
                    continue

                # Dispatch to callback (sequential processing)
                if self.on_event:
                    logger.debug(
                        f"[ZMQ_CLIENT_RECV] Dispatching to callback: event_id={event_id}"
                    )
                    await self.on_event(event)
                else:
                    logger.warning(
                        f"[ZMQ_CLIENT_RECV] No callback registered, dropping event: "
                        f"event_id={event_id}, event_type={event_type}"
                    )

            except asyncio.CancelledError:
                logger.info(
                    f"[ZMQ_CLIENT_RECV] Receive loop cancelled: topic={self.subscribe_topic}"
                )
                break
            except Exception as e:
                logger.error(
                    f"[ZMQ_CLIENT_RECV] Error in receive loop: topic={self.subscribe_topic}, "
                    f"error={e}",
                    exc_info=True
                )

        logger.info(
            f"[ZMQ_CLIENT_RECV] Receive loop exited: topic={self.subscribe_topic}"
        )
