from enum import StrEnum
from pydantic import BaseModel
from typing import Dict, Any, Optional, Literal

class NodeType(StrEnum):
    CLAUDE_CODE = "cc"
    AGGREGATOR = "aggregator"
    EMAIL = "email"
    SCHEDULER = "scheduler"
    REDDIT_SCRAPER = "reddit_scraper"


class EventType(StrEnum):
    SESSION_END = "session_end"
    SESSION_RESPONSE = "session_response"
    SESSION_START = "session_start"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    NODE_MESSAGE = "node_message"
    SYSTEM_MESSAGE = "system_message"
    EVENT_BATCH = "event_batch"
    EMAIL_MESSAGE = "email_message"
    SCHEDULER_MESSAGE = "scheduler_message"
    REDDIT_SCRAPER_MESSAGE = "reddit_scraper_message"


class Node(BaseModel):
    node_id: str
    type: NodeType
    config: Dict[str, Any]


class Connection(BaseModel):
    source_id: str
    target_id: str
    config: Dict[str, Any]


class Subscription(BaseModel):
    source_id: str
    target_id: str
    event_type: EventType
    config: Dict[str, Any]


class Session(BaseModel):
    session_id: str
    node_id: str
    config: Dict[str, Any]
    pull_host: Optional[str]
    pull_port: Optional[int]    
    pub_host: Optional[str]
    pub_port: Optional[int]
    status: Literal["open", "closed"]
    created_at: str

    def __str__(self):
        return f"{self.node_id}#{self.session_id}"


class SessionRouting(BaseModel):
    a_node_id: str
    a_session_id: str
    b_node_id: str
    b_session_id: str