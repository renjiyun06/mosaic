import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel
from jsonschema import validate

from mosaic.core.types import (
    NodeType, 
    MeshStatus, 
    NodeStatus, 
)
from mosaic.nodes.agent.types import SessionRoutingStrategy

class SessionTrace(BaseModel):
    upstream_session_id: str
    downstream_session_id: Optional[str] = None

class MeshEvent(BaseModel):
    event_id: str
    mesh_id: str
    source_id: str
    target_id: str
    type: str   # EventDefinition.name
    payload: Dict[str, Any]
    session_trace: Optional[SessionTrace]
    reply_to: Optional[str]
    created_at: datetime

    def to_xml(self) -> str:
        return f"""
<event id="{self.event_id}" type="{self.type}" from="{self.source_id}">
    <payload>{json.dumps(self.payload)}</payload>
</event>
""".strip()

class Mesh(BaseModel):
    mesh_id: str


class Node(BaseModel):
    node_id: str
    mesh_id: str
    type: NodeType
    config: Dict[str, str]


class Subscription(BaseModel):
    mesh_id: str
    source_id: str
    target_id: str
    event_pattern: str
    is_blocking: bool
    session_routing_strategy: SessionRoutingStrategy
    session_routing_strategy_config: Dict[str, str]

class EventDefinition(BaseModel):
    name: str   # domain.entity.action, e.g., "cc.tool.pre_tool_use
    description: str    # llm friendly    
    payload_schema: Dict[str, Any]

    def to_mesh_event(
        self, 
        event_id: str,
        mesh_id: str,
        source_id: str,
        target_id: str,
        payload: Dict[str, Any],
        session_trace: Optional[SessionTrace],
        reply_to: Optional[str],
        created_at: datetime
    ) -> MeshEvent:
        validate(payload, self.payload_schema)
        return MeshEvent(
            event_id=event_id,
            mesh_id=mesh_id,
            source_id=source_id,
            target_id=target_id,
            type=self.name,
            payload=payload,
            session_trace=session_trace,
            reply_to=reply_to,
            created_at=created_at,
        )

class NodeCapability(BaseModel):
    type: NodeType
    produced_events: List[str]
    consumed_events: List[str]
    description: str