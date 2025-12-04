import asyncio
import argparse
import json
from typing import Dict

from mosaic.core.models import MeshEvent
from mosaic.core.client import MeshClient
from mosaic.core.node import BaseNode
from mosaic.core.types import TransportType
from mosaic.transport.sqlite import SqliteTransportBackend
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class DummyNode(BaseNode):
    def __init__(
        self, 
        mesh_id: str, 
        node_id: str, 
        config: Dict[str, str], 
        client: MeshClient
    ):
        super().__init__(mesh_id, node_id, config, client)

    async def on_event(self, event: MeshEvent): ...

    async def on_start(self):
        logger.info(
            f"Dummy node {self.node_id} in mesh {self.mesh_id} started"
        )

    async def on_shutdown(self):
        logger.info(
            f"Dummy node {self.node_id} in mesh {self.mesh_id} stopped"
        )


async def main(
    mesh_id: str, 
    node_id: str, 
    transport: TransportType, 
    config: Dict[str, str]
):
    transport_backend = None
    if transport == TransportType.SQLITE:
        transport_backend = SqliteTransportBackend()
    else:
        raise RuntimeError(f"Unsupported transport type: {transport}")
    
    dummy_node = DummyNode(
        mesh_id, 
        node_id, 
        config, 
        MeshClient(mesh_id, node_id, transport_backend),
    )
    await dummy_node.start()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-id", type=str, required=True)
    parser.add_argument("--node-id", type=str, required=True)
    parser.add_argument("--transport", type=str, required=True)
    parser.add_argument("--config", type=str, required=True)
    args = parser.parse_args()
    asyncio.run(
        main(
            args.mesh_id, 
            args.node_id, 
            args.transport, 
            json.loads(args.config)
        )
    )