import uuid
from datetime import datetime
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Dict, Any, Type

from mosaic.core.models import MeshEvent, SessionTrace
from mosaic.core.events import get_event_definition

class Hook(ABC, BaseModel):
    mesh_event_type: str
    session_id: str

    @abstractmethod
    def to_mesh_event(
        self, 
        mesh_id: str, 
        node_id: str,
        target_id: str
    ) -> MeshEvent: ...

    @classmethod
    @abstractmethod
    def from_hook_input(cls, hook_input: Dict[str, Any]) -> 'Hook': ...

    @classmethod
    @abstractmethod
    def default_hook_output(cls) -> Dict[str, Any]: ...

    @classmethod
    def get_hook_type(cls, name: str) -> Type['Hook']:
        if name == "PreToolUse":
            return PreToolUse
        else:
            raise ValueError(f"Unknown hook type: {name}")


class PreToolUse(Hook):
    mesh_event_type: str = "cc.tool.pre_tool_use"
    tool_name: str
    tool_input: Dict[str, Any]

    @classmethod
    def from_hook_input(cls, hook_input: Dict[str, Any]) -> 'PreToolUse':
        return cls(
            session_id=hook_input["session_id"],
            tool_name=hook_input["tool_name"],
            tool_input=hook_input["tool_input"],
        )

    @classmethod
    def default_hook_output(cls) -> Dict[str, Any]:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "",
            }
        }

    def to_mesh_event(
        self, 
        mesh_id: str, 
        node_id: str,
        target_id: str
    ) -> MeshEvent:
        return get_event_definition(self.mesh_event_type).to_mesh_event(
            event_id=str(uuid.uuid4()),
            mesh_id=mesh_id,
            source_id=node_id,
            target_id=target_id,
            payload=self.model_dump(exclude={"mesh_event_type", "session_id"}),
            session_trace=SessionTrace(
                upstream_session_id=self.session_id,
                downstream_session_id=None
            ),
            reply_to=None,
            created_at=datetime.now(),
        )