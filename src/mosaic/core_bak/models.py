import json
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
from jsonschema import validate

from mosaic.core.enums import NodeType
from mosaic.nodes.agent.enums import SessionRoutingStrategy

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
        assert self.type != "mosaic.node_message"
        return f"""
<event id="{self.event_id}" type="{self.type}" from="{self.source_id}">
    <payload>{json.dumps(self.payload, ensure_ascii=False)}</payload>
</event>
""".strip()


    def to_node_message_xml(self) -> str:
        assert self.type == "mosaic.node_message"
        return f"""
<node_message id="{self.event_id}" from="{self.source_id}">
{self.payload["message"]}
</node_message>
""".strip()



class Mesh(BaseModel):
    mesh_id: str

    def __str__(self):
        return f"{self.mesh_id}"


class Node(BaseModel):
    node_id: str
    mesh_id: str
    type: NodeType
    config: Dict[str, str]
    label: Optional[str] = None

    def __str__(self):
        return f"{self.mesh_id}#{self.node_id}"


class Subscription(BaseModel):
    mesh_id: str
    source_id: str
    target_id: str
    event_pattern: str
    is_blocking: bool
    session_routing_strategy: Optional[SessionRoutingStrategy] = None
    session_routing_strategy_config: Optional[Dict[str, str]] = None

class EventDefinition(BaseModel):
    name: str
    description: str
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