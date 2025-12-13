from typing import Dict, Any

from mosaic.core.node import MosaicNode
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class ClaudeCodeNode(MosaicNode):
    def __init__(
        self, 
        node_id: str, 
        config: Dict[str, Any],
        zmq_server_pull_host: str,
        zmq_server_pull_port: int,
        zmq_server_pub_host: str,
        zmq_server_pub_port: int
    ):
        super().__init__(
            node_id, 
            config,
            zmq_server_pull_host,
            zmq_server_pull_port,
            zmq_server_pub_host,
            zmq_server_pub_port
        )

    async def on_start(self):
        pass

    async def on_shutdown(self):
        pass

    async def process_event(self, event: Dict[str, Any]):
        pass