from abc import ABC, abstractmethod
from typing import Dict, Any

from mosaic.core.node import BaseNode
from mosaic.core.types import MeshID, NodeID, TransportType
from mosaic.core.models import MeshEvent

class SessionRoutingStrategy(ABC):
    @abstractmethod
    def route(self, event: MeshEvent, config: Dict[str, Any]) -> str: ...

class MirroringStrategy(SessionRoutingStrategy): ...
class TaskingStrategy(SessionRoutingStrategy): ...
class StatefulStrategy(SessionRoutingStrategy): ...

class SessionManager: ...


class AgentNode(BaseNode):
    def __init__(self, mesh_id: MeshID, node_id: NodeID, transport: TransportType, config: Dict[str, str]):
        super().__init__(mesh_id, node_id, transport)
        self.config = config
        

    async def process_event(self, event: MeshEvent): ...
    async def on_start(self): ...
    async def on_shutdown(self): ...