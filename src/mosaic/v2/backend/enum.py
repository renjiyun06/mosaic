"""Enumeration types for backend"""
from enum import Enum


class NodeType(str, Enum):
    """Node type enumeration

    Defines the types of nodes that can be created in a Mosaic instance.
    """
    CLAUDE_CODE = "claude_code"


class MosaicStatus(str, Enum):
    """Mosaic instance status enumeration"""
    RUNNING = "running"
    STOPPED = "stopped"


class NodeStatus(str, Enum):
    """Node status enumeration"""
    RUNNING = "running"
    STOPPED = "stopped"


class SessionAlignment(str, Enum):
    """Session alignment strategy for node connections

    Defines how downstream node sessions are managed in relation to upstream node sessions.

    MIRRORING: One-to-one session mapping. Downstream session lifecycle mirrors upstream session.
               When upstream session opens, downstream session opens; when upstream closes, downstream closes.
               All events from an upstream session route to the same downstream session.

    TASKING: One-to-many session mapping. Downstream creates a new session for each event.
             Each event triggers a new downstream session that closes immediately after processing.
             Upstream session lifetime is independent of downstream sessions.
    """
    MIRRORING = "mirroring"
    TASKING = "tasking"


class EventType(str, Enum):
    """Event types in Mosaic system

    Defines all types of events that can be emitted and subscribed to
    in the event mesh.
    """
    SESSION_START = "session_start"
    SESSION_RESPONSE = "session_response"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    SESSION_END = "session_end"
    NODE_MESSAGE = "node_message"
    EVENT_BATCH = "event_batch"
    SYSTEM_MESSAGE = "system_message"
    EMAIL_MESSAGE = "email_message"
    SCHEDULER_MESSAGE = "scheduler_message"
    REDDIT_SCRAPER_MESSAGE = "reddit_scraper_message"


class SessionStatus(str, Enum):
    """Session status enumeration

    Defines the lifecycle states of a session.

    ACTIVE: Session is currently active and can accept new messages
    CLOSED: Session has been closed but not yet archived
    ARCHIVED: Session has been archived for long-term storage
    """
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class SessionMode(str, Enum):
    """Session mode enumeration

    Defines how a session operates and emits events.

    BACKGROUND: Background session triggered by subscribed events.
                Session is opened to process incoming events from upstream nodes.
                Users can still interact with background sessions, but the session
                lifecycle is driven by event processing.

    PROGRAM: Programming/instruction session created by users for guiding agent nodes.
             Only available for agent nodes. Used to instruct and configure the agent.
             Does NOT emit any events to the event mesh.

    CHAT: Interactive chat session created by users for normal usage of agent nodes.
          Only available for agent nodes. Used for regular interaction with the agent.
          DOES emit events to the event mesh during normal operation.
    """
    BACKGROUND = "background"
    PROGRAM = "program"
    CHAT = "chat"


class LLMModel(str, Enum):
    """LLM model enumeration

    Defines available large language models for sessions.
    Currently supports Claude models from Anthropic.
    """
    SONNET = "sonnet"
    OPUS = "opus"
    HAIKU = "haiku"


class MessageRole(str, Enum):
    """Message role enumeration

    Defines the role of a message in a conversation.
    """
    SYSTEM = "system"
    ASSISTANT = "assistant"
    USER = "user"


class MessageType(str, Enum):
    """Message type enumeration

    Defines the specific type of message content and its structure.
    """
    USER_MESSAGE = "user_message"
    ASSISTANT_TEXT = "assistant_text"
    ASSISTANT_THINKING = "assistant_thinking"
    ASSISTANT_TOOL_USE = "assistant_tool_use"
    ASSISTANT_RESULT = "assistant_result"
    SYSTEM_MESSAGE = "system_message"
