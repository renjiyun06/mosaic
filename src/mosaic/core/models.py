from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
from mosaic.core.types import MeshID, NodeID, NodeType, EventID
from mosaic.core.types import MeshStatus, NodeStatus

class SessionTrace(BaseModel):
    upstream_session_id: str
    event_seq: int

class MeshEvent(BaseModel):
    event_id: EventID
    mesh_id: MeshID
    source_id: NodeID
    target_id: NodeID
    type: str
    payload: Dict[str, Any]
    session_trace: Optional[SessionTrace]
    reply_to: Optional[EventID]
    created_at: datetime

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