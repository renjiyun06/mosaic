import asyncio
import json
import argparse
from typing import Dict

from mosaic.nodes.agent.cc.cc_node import ClaudeCodeNode
from mosaic.core.types import TransportType, MeshID, NodeID

async def main(mesh_id: MeshID, node_id: NodeID, transport: TransportType, config: Dict[str, str]):
    node = ClaudeCodeNode(mesh_id, node_id, transport, config)
    await node.start()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-id", type=str, required=True)
    parser.add_argument("--node-id", type=str, required=True)
    parser.add_argument("--transport", type=str, default=TransportType.SQLITE)
    parser.add_argument("--config", type=str, required=False)
    args = parser.parse_args()
    if args.config:
        config = json.loads(args.config)
    else:
        config = {}
    asyncio.run(main(args.mesh_id, args.node_id, args.transport, config))