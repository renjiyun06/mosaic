import asyncio
import argparse
from mosaic.core.models import MeshEvent
from mosaic.core.node import BaseNode
from mosaic.core.types import TransportType, MeshID, NodeID

class DummyNode(BaseNode):
    def __init__(self, mesh_id: MeshID, node_id: NodeID, transport: TransportType):
        super().__init__(mesh_id, node_id, transport)

    async def process_event(self, event: MeshEvent): ...
    async def on_start(self): ...
    async def on_shutdown(self): ...

async def main(mesh_id: MeshID, node_id: NodeID, transport: TransportType):
    node = DummyNode(mesh_id, node_id, transport)
    await node.start()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-id", type=str, required=True)
    parser.add_argument("--node-id", type=str, required=True)
    parser.add_argument("--transport", type=str, default=TransportType.SQLITE)
    args = parser.parse_args()
    asyncio.run(main(args.mesh_id, args.node_id, args.transport))