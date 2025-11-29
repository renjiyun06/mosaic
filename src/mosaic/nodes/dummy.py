import asyncio
import argparse
import json
from typing import Dict
from mosaic.core.models import MeshEvent
from mosaic.core.node import BaseNode
from mosaic.core.types import TransportType, MeshID, NodeID
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class DummyNode(BaseNode):
    def __init__(self, mesh_id: MeshID, node_id: NodeID, transport: TransportType, config: Dict[str, str]):
        super().__init__(mesh_id, node_id, transport)
        self._config = config

    async def process_event(self, event: MeshEvent):
        pass

    async def on_start(self):
        logger.info(f"Dummy node {self.node_id} for mesh {self.mesh_id} started")
    
    async def on_shutdown(self):
        logger.info(f"Dummy node {self.node_id} for mesh {self.mesh_id} stopped")

async def main(mesh_id: MeshID, node_id: NodeID, transport: TransportType, config: Dict[str, str]):
    node = DummyNode(mesh_id, node_id, transport, config)
    await node.start()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-id", type=str, required=True)
    parser.add_argument("--node-id", type=str, required=True)
    parser.add_argument("--transport", type=str, default=TransportType.SQLITE)
    parser.add_argument("--config", type=str, required=False)
    args = parser.parse_args()
    logger.info(f"Starting dummy node {args.node_id} for mesh {args.mesh_id} with transport {args.transport} and config {args.config}")
    if args.config:
        config = json.loads(args.config)
    else:
        config = {}
    asyncio.run(main(args.mesh_id, args.node_id, args.transport, config))