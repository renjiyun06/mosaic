import asyncio
import argparse
from mosaic.nodes.agent.cc.cc_node import ClaudeCodeNode
from mosaic.core.types import TransportType, MeshID, NodeID

async def main(mesh_id: MeshID, node_id: NodeID, transport: TransportType):
    node = ClaudeCodeNode(mesh_id, node_id, transport)
    await node.start()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-id", type=str, required=True)
    parser.add_argument("--node-id", type=str, required=True)
    parser.add_argument("--transport", type=str, default=TransportType.SQLITE)
    args = parser.parse_args()
    asyncio.run(main(args.mesh_id, args.node_id, args.transport))