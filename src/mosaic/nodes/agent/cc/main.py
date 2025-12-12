import asyncio
import json
import argparse
from typing import Dict

from mosaic.core.enums import TransportType
from mosaic.core.client import MeshClient
from mosaic.nodes.agent.cc.cc_node import ClaudeCodeNode
from mosaic.transport.sqlite import SqliteTransportBackend
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

async def main(
    mesh_id: str, 
    node_id: str, 
    transport: TransportType, 
    config: Dict[str, str]
):
    try:
        transport_backend = None
        if transport == TransportType.SQLITE:
            transport_backend = SqliteTransportBackend(mesh_id, node_id)
        else:
            raise RuntimeError(f"Unsupported transport type: {transport}")
        
        cc_node = ClaudeCodeNode(
            mesh_id, 
            node_id, 
            config, 
            MeshClient(mesh_id, node_id, transport_backend),
            "default"
        )
        await cc_node.start()
    except Exception as e:
        logger.error(f"Error starting cc node {node_id} in mesh {mesh_id}: {e}")
        raise e

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