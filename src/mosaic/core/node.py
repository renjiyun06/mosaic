import asyncio
import os
import json
import signal
from typing import Dict, List
from abc import ABC, abstractmethod

import mosaic.core.util as core_util
from mosaic.core.client import MeshClient
from mosaic.core.models import MeshEvent
from mosaic.core.types import NodeStatus
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class BaseNode(ABC):
    def __init__(
        self, 
        mesh_id: str, 
        node_id: str, 
        config: Dict[str, str], 
        client: MeshClient
    ):
        self.mesh_id = mesh_id
        self.node_id = node_id
        self.config = config
        self.client = client
        self._sock_server = None
        self._event_processing_task = None
        self._status = NodeStatus.STOPPED
        self._pid_path = core_util.node_pid_path(mesh_id, node_id)
        self._sock_path = core_util.node_sock_path(mesh_id, node_id)
        self._stop_event = asyncio.Event()
    
    @abstractmethod
    async def on_event(self, event: MeshEvent): ...
    @abstractmethod
    async def on_start(self): ...
    @abstractmethod
    async def on_shutdown(self): ...
    async def register_chat_session(self, session_id: str): ...
    async def unregister_chat_session(self, session_id: str): ...
    async def list_chat_sessions(self) -> List[str]:
        return []


    async def start(self):
        logger.info(f"Starting node {self.node_id} in mesh {self.mesh_id}")
        if self._status != NodeStatus.STOPPED:
            raise RuntimeError(
                f"Node {self.node_id} is already running in mesh {self.mesh_id}"
            )
        await self.client.connect()
        await self._start_sock_server()
        await self._start_event_processing_task()
        await self.on_start()
        self._pid_path.parent.mkdir(parents=True, exist_ok=True)
        self._pid_path.write_text(str(os.getpid()))
        await self._add_sigterm_handler()
        self._status = NodeStatus.RUNNING

        logger.info(f"Node {self.node_id} in mesh {self.mesh_id} started")

        await self._stop_event.wait()

    
    async def stop(self):
        logger.info(f"Stopping node {self.node_id} in mesh {self.mesh_id}")
        if self._status != NodeStatus.RUNNING:
            raise ValueError(
                f"Node {self.node_id} is not running in mesh {self.mesh_id}"
            )
        self._status = NodeStatus.STOPPING
        await self.on_shutdown()
        await self._stop_event_processing_task()
        await self._stop_sock_server()
        await self.client.disconnect()
        
        self._pid_path.unlink(missing_ok=True)
        self._status = NodeStatus.STOPPED

        logger.info(f"Node {self.node_id} in mesh {self.mesh_id} stopped")
        self._stop_event.set()


    async def _start_sock_server(self):
        logger.info(
            f"Starting Unix socket server for "
            f"node {self.node_id} in mesh {self.mesh_id}"
        )
        if self._sock_path.exists():
            logger.error(
                f"Unix socket path {self._sock_path} already exists for "
                f"node {self.node_id} in mesh {self.mesh_id}"
            )
            raise ValueError(
                f"Unix socket path {self._sock_path} already exists for "
                f"node {self.node_id} in mesh {self.mesh_id}"
            )
        self._sock_path.parent.mkdir(parents=True, exist_ok=True)
        self._sock_server = await asyncio.start_unix_server(
            self._handle_command,
            path=str(self._sock_path)
        )
        logger.info(
            f"Unix socket server for "
            f"node {self.node_id} in mesh {self.mesh_id} started"
        )

    async def _stop_sock_server(self):
        self._sock_path.unlink(missing_ok=True)
        if self._sock_server:
            self._sock_server.close()
            await self._sock_server.wait_closed()
        self._sock_server = None


    async def _handle_command(self, reader, writer):
        try:
            length = int.from_bytes(await reader.readexactly(4), "big")
            request_content = (await reader.readexactly(length)).decode("utf-8")
            logger.info(
                f"Node {self.node_id} in mesh {self.mesh_id} received command: "
                f"{request_content}"
            )
            request = json.loads(request_content)
            command = request["command"]
            response = None
            if command == "status":
                response = {
                    "is_error": False,
                    "status": self._status
                }
            elif command == "register_chat_session":
                await self.register_chat_session(request["session_id"])
                response = {
                    "is_error": False
                }
            elif command == "unregister_chat_session":
                await self.unregister_chat_session(request["session_id"])
                response = {
                    "is_error": False
                }
            elif command == "list_chat_sessions":
                sessions = await self.list_chat_sessions()
                response = {
                    "is_error": False,
                    "sessions": sessions
                }
            else:
                response = {
                    "is_error": True,
                    "message": f"Invalid command: {command}"
                }
            
            response_content = json.dumps(response).encode()
            writer.write(len(response_content).to_bytes(4, "big"))
            writer.write(response_content)
            await writer.drain()
        except Exception as e:
            response = {
                "is_error": True,
                "message": str(e)
            }
            response_content = json.dumps(response).encode()
            writer.write(len(response_content).to_bytes(4, "big"))
            writer.write(response_content)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()


    async def _start_event_processing_task(self):
        logger.info(
            f"Starting event processing task for "
            f"node {self.node_id} in mesh {self.mesh_id}"
        )
        self._event_processing_task = asyncio.create_task(
            self._event_processing_loop()
        )
        logger.info(
            f"Event processing task for "
            f"node {self.node_id} in mesh {self.mesh_id} started"
        )

    
    async def _stop_event_processing_task(self):
        if self._event_processing_task:
            self._event_processing_task.cancel()
            self._event_processing_task = None

        logger.info(
            f"Event processing task for "
            f"node {self.node_id} in mesh {self.mesh_id} stopped"
        )


    async def _event_processing_loop(self):
        while self._status == NodeStatus.RUNNING:
            event = await self.client.receive()
            if not event:
                await self.on_event(event)


    async def _add_sigterm_handler(self):
        asyncio.get_running_loop().add_signal_handler(
            signal.SIGTERM, lambda: asyncio.create_task(self.stop())
        )