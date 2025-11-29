from typing import Dict

from mosaic.nodes.agent.base import AgentNode
from mosaic.core.types import MeshID, NodeID, TransportType

class ClaudeCodeNode(AgentNode):
    def __init__(self, mesh_id: MeshID, node_id: NodeID, transport: TransportType, config: Dict[str, str]):
        super().__init__(mesh_id, node_id, transport, config)