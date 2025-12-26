import asyncio
import zmq
import zmq.asyncio
import json
import traceback
from typing import Dict, Any, Callable, Optional

from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class ZmqServer:
    def __init__(
        self, 
        pull_host: str, 
        pull_port: int, 
        pub_host: str, 
        pub_port: int
    ):
        self._pull_host = pull_host
        self._pull_port = pull_port
        self._pull_url = f"tcp://{pull_host}:{pull_port}"
        self._pub_host = pub_host
        self._pub_port = pub_port
        self._pub_url = f"tcp://{pub_host}:{pub_port}"

        self._context = None
        self._pull_sock = None
        self._pub_sock = None
        self._broadcast_task = None


    def start(self):
        logger.info(
            f"Starting zmq server for pull {self._pull_url} "
            f"and pub {self._pub_url}"
        )
        self._context = zmq.asyncio.Context()
        self._pull_sock = self._context.socket(zmq.PULL)
        self._pull_sock.bind(self._pull_url)
        self._pub_sock = self._context.socket(zmq.PUB)
        self._pub_sock.bind(self._pub_url)
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        logger.info(
            f"Zmq server for pull {self._pull_url} "
            f"and pub {self._pub_url} started"
        )

    def stop(self):
        logger.info(
            f"Stopping zmq server for pull {self._pull_url} "
            f"and pub {self._pub_url}"
        )
        if self._broadcast_task:
            self._broadcast_task.cancel()
            self._broadcast_task = None
        if self._pull_sock:
            self._pull_sock.close()
            self._pull_sock = None
        if self._pub_sock:
            self._pub_sock.close()
            self._pub_sock = None
        if self._context:
            self._context.term()
            self._context = None
        logger.info(
            f"Zmq server for pull {self._pull_url} "
            f"and pub {self._pub_url} stopped"
        )


    async def _broadcast_loop(self):
        while True:
            try:
                topic = await self._pull_sock.recv_string()
                event = await self._pull_sock.recv_json()
                logger.debug(
                    f"Broadcasting event {json.dumps(event, ensure_ascii=False)} "
                    f"on topic {topic}"
                )
                await self._pub_sock.send_string(topic, zmq.SNDMORE)
                await self._pub_sock.send_json(event)
                logger.debug(
                    f"Event broadcasted: {json.dumps(event, ensure_ascii=False)} "
                    f"on topic {topic}"
                )
            except asyncio.CancelledError:
                break


class ZmqClient:
    def __init__(
        self,
        pull_host: str,
        pull_port: int,
        pub_host: str,
        pub_port: int,
        subscribe_topic: str,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        debug_message: Optional[str] = None
    ):
        self._pull_host = pull_host
        self._pull_port = pull_port
        self._pull_url = f"tcp://{pull_host}:{pull_port}"
        self._pub_host = pub_host
        self._pub_port = pub_port
        self._pub_url = f"tcp://{pub_host}:{pub_port}"
        self._subscribe_topic = subscribe_topic
        self._on_event = on_event
        self._debug_message = debug_message

        self._context = None
        self._push_sock = None
        self._sub_sock = None
        self._receive_task = None
        
    
    def connect(self):
        logger.info(
            f"Connecting to zmq server for pull {self._pull_url} "
            f"and pub {self._pub_url}"
        )
        self._context = zmq.asyncio.Context()
        self._push_sock = self._context.socket(zmq.PUSH)
        self._push_sock.connect(self._pull_url)
        self._sub_sock = self._context.socket(zmq.SUB)
        self._sub_sock.connect(self._pub_url)
        self._sub_sock.setsockopt_string(zmq.SUBSCRIBE, self._subscribe_topic)
        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.info(
            f"Zmq server for pull {self._pull_url} "
            f"and pub {self._pub_url} connected"
        )
    

    def disconnect(self):
        logger.info(
            f"Disconnecting from zmq server for pull {self._pull_url} "
            f"and pub {self._pub_url}"
        )
        if self._receive_task:
            self._receive_task.cancel()
            self._receive_task = None
        if self._push_sock:
            self._push_sock.close()
            self._push_sock = None
        if self._sub_sock:
            self._sub_sock.close()
            self._sub_sock = None
        if self._context:
            self._context.term()
            self._context = None
        logger.info(
            f"Zmq server for pull {self._pull_url} "
            f"and pub {self._pub_url} disconnected"
        )


    async def send(self, topic: str, event: Dict[str, Any]):
        logger.debug(
            f"Sending event {json.dumps(event, ensure_ascii=False)} "
            f"on topic {topic}"
        )
        await self._push_sock.send_string(topic, zmq.SNDMORE)  
        await self._push_sock.send_json(event)


    async def _receive_loop(self):
        while True:
            try:
                topic = await self._sub_sock.recv_string()
                if topic != self._subscribe_topic:
                    continue
                event = await self._sub_sock.recv_json()
                logger.debug(
                    f"Received event {json.dumps(event, ensure_ascii=False)} "
                    f"on topic {topic}"
                )
                if self._on_event:
                    asyncio.create_task(self._on_event(event))
            except asyncio.CancelledError:
                logger.debug(f"Receive loop cancelled")
                break
            except Exception as e:
                logger.error(
                    f"Error in receive loop: {e}\n{traceback.format_exc()}"
                )
                break