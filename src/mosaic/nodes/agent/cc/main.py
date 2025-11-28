import asyncio
import argparse
from mosaic.nodes.agent.cc.cc_node import ClaudeCodeNode
from mosaic.core.client import MeshClient
from mosaic.transport.sqlite import SqliteTransportBackend
from mosaic.core.types import TransportType, MeshID, NodeID

async def main(mesh_id: MeshID, node_id: NodeID, transport: TransportType):
    transport_backend = None
    if transport == TransportType.SQLITE:
        transport_backend = SqliteTransportBackend(mesh_id=mesh_id, node_id=node_id)
    else:
        raise ValueError(f"Unsupported transport: {transport}")
    
    client = MeshClient(transport_backend)
    await client.connect()
    node = ClaudeCodeNode(client)
    await node.start()
    await client.disconnect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-id", type=str, required=True)
    parser.add_argument("--node-id", type=str, required=True)
    parser.add_argument("--transport", type=str, default=TransportType.SQLITE)
    args = parser.parse_args()
    asyncio.run(main(args.mesh_id, args.node_id, args.transport))