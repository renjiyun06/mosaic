from typing import Dict

from mosaic.nodes.agent.base import AgentNode
from mosaic.core.types import MeshID, NodeID, TransportType
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class ClaudeCodeNode(AgentNode):
    def __init__(self, mesh_id: MeshID, node_id: NodeID, transport: TransportType, config: Dict[str, str]):
        super().__init__(mesh_id, node_id, transport, config)