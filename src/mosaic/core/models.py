from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel

from mosaic.core.types import (
    MeshID, 
    NodeID, 
    NodeType, 
    EventID, 
    MeshStatus, 
    NodeStatus, 
    SessionRoutingStrategy,
)

class SessionTrace(BaseModel):
    upstream_session_id: str
    event_seq: int

class MeshEvent(BaseModel):
    event_id: EventID
    mesh_id: MeshID
    source_id: NodeID
    target_id: NodeID
    type: str   # EventDefinition.name
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

class Subscription(BaseModel):
    mesh_id: MeshID
    source_id: NodeID
    target_id: NodeID
    event_pattern: str
    is_blocking: bool
    session_routing_strategy: SessionRoutingStrategy
    session_routing_strategy_config: Dict[str, Any]

class EventDefinition(BaseModel):
    name: str   # domain.entity.action, e.g., "cc.tool.pre_tool_use
    description: str    # llm friendly    
    payload_schema: Dict[str, Any]

class NodeCapability(BaseModel):
    type: NodeType
    produced_events: List[str]
    consumed_events: List[str]
    description: str