from enum import StrEnum
from pydantic import BaseModel
from typing import Dict, Any

class NodeType(StrEnum):
    CLAUDE_CODE = "cc"


class EventType(StrEnum):
    CC_SESSION_END = "cc.session_end"
    CC_SESSION_RESPONSE = "cc.session_response"
    CC_SESSION_START = "cc.session_start"
    CC_USER_PROMPT_SUBMIT = "cc.user_prompt_submit"
    CC_PRE_TOOL_USE = "cc.pre_tool_use"
    CC_POST_TOOL_USE = "cc.post_tool_use"


class SessionRoutingStrategy(StrEnum):
    MIRRORING = "mirroring"
    TASKING = "tasking"


class Node(BaseModel):
    node_id: str
    type: NodeType
    config: Dict[str, Any]


class Subscription(BaseModel):
    source_id: str
    target_id: str
    event_type: EventType
    config: Dict[str, Any]