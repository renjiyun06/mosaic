from abc import ABC, abstractmethod
from typing import Dict, Any, Literal

from mosaic.core.zmq import ZmqClient
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class MosaicNode(ABC):
    def __init__(
        self, 
        node_id: str, 
        config: Dict[str, Any],
        zmq_server_pull_host: str,
        zmq_server_pull_port: int,
        zmq_server_pub_host: str,
        zmq_server_pub_port: int
    ):
        self.node_id = node_id
        self.config = config
        self._zmq_server_pull_host = zmq_server_pull_host
        self._zmq_server_pull_port = zmq_server_pull_port
        self._zmq_server_pub_host = zmq_server_pub_host
        self._zmq_server_pub_port = zmq_server_pub_port
        self._zmq_client = ZmqClient(
            zmq_server_pull_host,
            zmq_server_pull_port,
            zmq_server_pub_host,
            zmq_server_pub_port,
            self.node_id,
            self.process_event
        )

        self._status: Literal["stopped", "running"] = "stopped"

    async def start(self):
        if self._status == "stopped":
            await self.on_start()
            self._zmq_client.connect()
            self._status = "running"


    async def shutdown(self):
        if self._status == "running":
            self._zmq_client.disconnect()
            await self.on_shutdown()
            self._status = "stopped"


    @abstractmethod
    async def on_start(self): ...
    @abstractmethod
    async def on_shutdown(self): ...
    @abstractmethod
    async def process_event(self, event: Dict[str, Any]): ...