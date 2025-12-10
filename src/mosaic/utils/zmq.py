import asyncio
import zmq
import zmq.asyncio
from pathlib import Path
from typing import Dict, Any, Callable

from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class BroadcastServer:
    def __init__(self, pull_sock_path: Path, pub_sock_path: Path):
        self._pull_sock_path = pull_sock_path
        self._pub_sock_path = pub_sock_path

        self._context = None
        self._pull_sock = None
        self._pub_sock = None
        self._broadcast_task = None


    async def start(self):
        logger.info(
            f"Starting broadcast server at {self._pull_sock_path} and {self._pub_sock_path}"
        )
        self._pull_sock_path.parent.mkdir(parents=True, exist_ok=True)
        self._pub_sock_path.parent.mkdir(parents=True, exist_ok=True)
        self._context = zmq.asyncio.Context()
        self._pull_sock = self._context.socket(zmq.PULL)
        self._pull_sock.bind("ipc://" + str(self._pull_sock_path))
        self._pub_sock = self._context.socket(zmq.PUB)
        self._pub_sock.bind("ipc://" + str(self._pub_sock_path))
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        logger.info(
            f"Broadcast server at {self._pull_sock_path} and {self._pub_sock_path} started"
        )


    async def stop(self):
        logger.info(
            f"Stopping broadcast server at {self._pull_sock_path} and {self._pub_sock_path}"
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
            f"Broadcast server at {self._pull_sock_path} and {self._pub_sock_path} stopped"
        )


    async def _broadcast_loop(self):
        while True:
            try:
                message = await self._pull_sock.recv_json()
                await self._pub_sock.send_json(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error broadcasting messages: {e}")
                raise e


class BroadcastClient:
    def __init__(
        self,
        pull_sock_path: Path,
        pub_sock_path: Path,
        on_message: Callable[[Dict[str, Any]], None]
    ):
        self._pull_sock_path = pull_sock_path
        self._pub_sock_path = pub_sock_path
        self._on_message = on_message
        self._context = None
        self._push_sock = None
        self._sub_sock = None
        self._receive_task = None
        
    
    async def connect(self):
        logger.info(
            f"Connecting to broadcast server at {self._pull_sock_path} and {self._pub_sock_path}"
        )
        self._pull_sock_path.parent.mkdir(parents=True, exist_ok=True)
        self._pub_sock_path.parent.mkdir(parents=True, exist_ok=True)
        self._context = zmq.asyncio.Context()
        self._push_socket = self._context.socket(zmq.PUSH)
        self._push_socket.connect("ipc://" + str(self._pull_sock_path))
        self._sub_socket = self._context.socket(zmq.SUB)
        self._sub_socket.connect("ipc://" + str(self._pub_sock_path))
        self._sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.info(
            f"Connected to broadcast server at {self._pull_sock_path} and {self._pub_sock_path}"
        )
    

    async def disconnect(self):
        logger.info(
            f"Disconnecting from broadcast server at {self._pull_sock_path} and {self._pub_sock_path}"
        )
        if self._receive_task:
            self._receive_task.cancel()
            self._receive_task = None
        if self._push_socket:
            self._push_socket.close()
            self._push_socket = None
        if self._sub_socket:
            self._sub_socket.close()
            self._sub_socket = None
        if self._context:
            self._context.term()
            self._context = None
        logger.info(
            f"Disconnected from broadcast server at {self._pull_sock_path} and {self._pub_sock_path}"
        )


    async def send(self, message: Dict[str, Any]):
        await self._push_socket.send_json(message)


    async def _receive_loop(self):
        while True:
            try:
                message = await self._sub_socket.recv_json()
                await self._on_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error receiving messages: {e}")
                raise e