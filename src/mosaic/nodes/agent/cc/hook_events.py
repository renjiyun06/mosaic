from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

from mosaic.core.types import EventID, MeshID, NodeID
from mosaic.core.models import MeshEvent, SessionTrace
from mosaic.core.events import get_event_definition

class PreToolUse(BaseModel):
    tool_name: str
    tool_input: Dict[str, Any]

    def to_mesh_event(
        self,
        event_id: EventID,
        mesh_id: MeshID,
        source_id: NodeID,
        target_id: NodeID,
        session_trace: Optional[SessionTrace],
        reply_to: Optional[EventID],
        created_at: datetime
    ) -> MeshEvent:
        return get_event_definition(PreToolUse.mesh_event_type()).to_mesh_event(
            event_id=event_id,
            mesh_id=mesh_id,
            source_id=source_id,
            target_id=target_id,
            payload=self.model_dump(),
            session_trace=session_trace,
            reply_to=reply_to,
            created_at=created_at,
        )

    @classmethod
    def from_hook_input(cls, hook_input: Dict[str, Any]) -> 'PreToolUse':
        return cls(
            tool_name=hook_input["tool_name"],
            tool_input=hook_input["tool_input"],
        )

    @classmethod
    def mesh_event_type(cls) -> str:
        return "cc.tool.pre_tool_use"

    @classmethod
    def default_hook_output(cls) -> Dict[str, Any]:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "",
            }
        }


def get_hook_event_type(name: str):
    if name == "PreToolUse":
        return PreToolUse
    else:
        raise ValueError(f"Unknown hook event name: {name}")