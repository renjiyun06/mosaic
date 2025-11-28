from mosaic.core.node import BaseNode
from mosaic.core.client import MeshClient
from mosaic.core.models import MeshEvent

class ClaudeCodeNode(BaseNode):
    def __init__(self, client: MeshClient):
        super().__init__(client)

    async def process_event(self, event: MeshEvent): ...
    async def on_start(self): ...
    async def on_shutdown(self): ...