import asyncio
import json
import argparse
from typing import Dict

from mosaic.core.types import TransportType
from mosaic.core.client import MeshClient
from mosaic.nodes.agent.cc.cc_node import ClaudeCodeNode
from mosaic.nodes.agent.types import AgentNodeRunningMode
from mosaic.transport.sqlite import SqliteTransportBackend

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
    
    cc_node = ClaudeCodeNode(
        mesh_id, 
        node_id, 
        config, 
        MeshClient(mesh_id, node_id,transport_backend),
        AgentNodeRunningMode.BACKGROUND
    )
    await cc_node.start()

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