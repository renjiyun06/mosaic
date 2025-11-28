from typing import Dict
from pydantic import BaseModel
from mosaic.core.types import MeshID, NodeID, NodeType
from mosaic.core.types import MeshStatus, NodeStatus

class SessionTrace(BaseModel): ...
class MeshEvent(BaseModel): ...

class Mesh(BaseModel):
    mesh_id: MeshID
    status: MeshStatus = MeshStatus.STOPPED

class Node(BaseModel):
    node_id: NodeID
    mesh_id: MeshID
    type: NodeType
    config: Dict[str, str]
    status: NodeStatus = NodeStatus.STOPPED

class Subscription(BaseModel): ...
class EventDefinition(BaseModel): ...
class NodeCapability(BaseModel): ...