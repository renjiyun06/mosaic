from abc import ABC, abstractmethod
from typing import Dict, Any

from mosaic.core.type import NodeType
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class MosaicNode(ABC):
    def __init__(self, node_id: str, type: NodeType, config: Dict[str, Any]):
        self.node_id = node_id
        self.type = type
        self.config = config

    async def start(self):
        pass

    async def shutdown(self):
        pass