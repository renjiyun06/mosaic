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
        elif name == "PermissionRequest":
            return PermissionRequest
        elif name == "PostToolUse":
            return PostToolUse
        elif name == "Notification":
            return Notification
        elif name == "UserPromptSubmit":
            return UserPromptSubmit
        elif name == "Stop":
            return Stop
        elif name == "SubagentStop":
            return SubagentStop
        elif name == "PreCompact":
            return PreCompact
        elif name == "SessionStart":
            return SessionStart
        elif name == "SessionEnd":
            return SessionEnd
        else:
            raise ValueError(f"Unknown hook type: {name}")


class PreToolUse(Hook):
    mesh_event_type: str = "cc.pre_tool_use"
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


class PermissionRequest(Hook):
    mesh_event_type: str = "cc.permission_request"

    def to_mesh_event(
        self, 
        mesh_id: str, 
        node_id: str,
        target_id: str
    ) -> MeshEvent: ...

    @classmethod
    def from_hook_input(cls, hook_input: Dict[str, Any]) -> 'Hook':
        return cls(
            session_id=hook_input["session_id"]
        )
    
    @classmethod
    def default_hook_output(cls) -> Dict[str, Any]:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {
                    "behavior": "allow"
                }
            }
        }


class PostToolUse(Hook):
    mesh_event_type: str = "cc.post_tool_use"
    tool_name: str
    tool_input: Dict[str, Any]
    tool_response: Dict[str, Any]

    def to_mesh_event(
        self, 
        mesh_id: str, 
        node_id: str,
        target_id: str
    ) -> MeshEvent: ...

    @classmethod
    def from_hook_input(cls, hook_input: Dict[str, Any]) -> 'Hook':
        return cls(
            session_id=hook_input["session_id"],
            tool_name=hook_input["tool_name"],
            tool_input=hook_input["tool_input"],
            tool_response=hook_input["tool_response"],
        )

    @classmethod
    def default_hook_output(cls) -> Dict[str, Any]: 
        return {}


class Notification(Hook):
    mesh_event_type: str = "cc.notification"
    message: str

    def to_mesh_event(
        self, 
        mesh_id: str, 
        node_id: str,
        target_id: str
    ) -> MeshEvent: ...

    @classmethod
    def from_hook_input(cls, hook_input: Dict[str, Any]) -> 'Hook':
        return cls(
            session_id=hook_input["session_id"],
            message=hook_input["message"],
        )

    @classmethod
    def default_hook_output(cls) -> Dict[str, Any]:
        return {}        


class UserPromptSubmit(Hook):
    mesh_event_type: str = "cc.user_prompt_submit"
    prompt: str

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

    @classmethod
    def from_hook_input(cls, hook_input: Dict[str, Any]) -> 'Hook':
        return cls(
            session_id=hook_input["session_id"],
            prompt=hook_input["prompt"],
        )

    @classmethod
    def default_hook_output(cls) -> Dict[str, Any]:
        return {}


class Stop(Hook):
    mesh_event_type: str = "cc.stop"

    def to_mesh_event(
        self, 
        mesh_id: str, 
        node_id: str,
        target_id: str
    ) -> MeshEvent: ...

    @classmethod
    def from_hook_input(cls, hook_input: Dict[str, Any]) -> 'Hook':
        return cls(
            session_id=hook_input["session_id"]
        )
    
    @classmethod
    def default_hook_output(cls) -> Dict[str, Any]:
        return {}


class SubagentStop(Hook):
    mesh_event_type: str = "cc.subagent_stop"

    def to_mesh_event(
        self, 
        mesh_id: str, 
        node_id: str,
        target_id: str
    ) -> MeshEvent: ...

    @classmethod
    def from_hook_input(cls, hook_input: Dict[str, Any]) -> 'Hook':
        return cls(
            session_id=hook_input["session_id"]
        )
    
    @classmethod
    def default_hook_output(cls) -> Dict[str, Any]:
        return {}


class PreCompact(Hook):
    mesh_event_type: str = "cc.pre_compact"
    trigger: str
    custom_instructions: str

    def to_mesh_event(
        self, 
        mesh_id: str, 
        node_id: str,
        target_id: str
    ) -> MeshEvent: ...

    @classmethod
    def from_hook_input(cls, hook_input: Dict[str, Any]) -> 'Hook':
        return cls(
            session_id=hook_input["session_id"],
            trigger=hook_input["trigger"],
            custom_instructions=hook_input["custom_instructions"],
        )

    @classmethod
    def default_hook_output(cls) -> Dict[str, Any]:
        return {}


class SessionStart(Hook):
    mesh_event_type: str = "cc.session_start"

    def to_mesh_event(
        self, 
        mesh_id: str, 
        node_id: str,
        target_id: str
    ) -> MeshEvent: ...

    @classmethod
    def from_hook_input(cls, hook_input: Dict[str, Any]) -> 'Hook':
        return cls(
            session_id=hook_input["session_id"]
        )
    
    @classmethod
    def default_hook_output(cls) -> Dict[str, Any]:
        return {}


class SessionEnd(Hook):
    mesh_event_type: str = "cc.session_end"

    def to_mesh_event(
        self, 
        mesh_id: str, 
        node_id: str,
        target_id: str
    ) -> MeshEvent: ...

    @classmethod
    def from_hook_input(cls, hook_input: Dict[str, Any]) -> 'Hook':
        return cls(
            session_id=hook_input["session_id"]
        )
    
    @classmethod
    def default_hook_output(cls) -> Dict[str, Any]:
        return {}