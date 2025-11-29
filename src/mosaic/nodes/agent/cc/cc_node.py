from typing import Dict

from mosaic.core.node import BaseNode
from mosaic.core.models import MeshEvent
from mosaic.core.types import MeshID, NodeID, TransportType

class ClaudeCodeNode(BaseNode):
    def __init__(self, mesh_id: MeshID, node_id: NodeID, transport: TransportType, config: Dict[str, str]):
        super().__init__(mesh_id, node_id, transport)
        self._config = config

    async def process_event(self, event: MeshEvent): ...
    async def on_start(self): ...
    async def on_shutdown(self): ...