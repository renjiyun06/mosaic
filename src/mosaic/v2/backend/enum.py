"""Enumeration types for backend"""
from enum import Enum


class NodeType(str, Enum):
    """Node type enumeration

    Defines the types of nodes that can be created in a Mosaic instance.
    """
    CLAUDE_CODE = "claude_code"
    SCHEDULER = "scheduler"
    EMAIL = "email"
    AGGREGATOR = "aggregator"


class MosaicStatus(str, Enum):
    """Mosaic instance status enumeration"""
    STARTING = "starting"  # Mosaic is being initialized (placeholder state)
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

    AGENT_DRIVEN: Agent-controlled session lifecycle. Session closes only when agent calls task_complete() tool.
                  Enables recursive task decomposition where parent sessions can wait for child sessions.
                  Session remains active even after event processing, until agent signals completion.
    """
    MIRRORING = "mirroring"
    TASKING = "tasking"
    AGENT_DRIVEN = "agent_driven"


class EventType(str, Enum):
    """Event types in Mosaic system

    Defines all types of events that can be emitted and subscribed to
    in the event mesh.

    Internal event types (session queue only, not published to mesh):
    - USER_MESSAGE_EVENT: User message input to session queue
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

    # Internal session events (not published to Event Mesh)
    USER_MESSAGE_EVENT = "user_message_event"
    TASK_COMPLETE_EVENT = "task_complete_event"  # Agent signals task completion


class SessionStatus(str, Enum):
    """Session status enumeration

    Defines the lifecycle states of agent sessions (database only).

    ACTIVE: Session is currently active and processing events
    CLOSED: Session has been closed (before archiving)
    ARCHIVED: Session has been archived for long-term storage

    Database lifecycle: ACTIVE → CLOSED → ARCHIVED

    Note:
        This enum is only used for agent sessions (those backed by database).
        Runtime-only sessions (scheduler, email) don't use this enum.
        Runtime state flags (_initialized, _should_close) are managed in MosaicSession.
    """
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class RuntimeStatus(str, Enum):
    """Runtime status enumeration

    Defines the runtime processing state of a session.

    IDLE: Session is not currently processing any request
    BUSY: Session is currently processing a request

    Runtime lifecycle: IDLE ⇄ BUSY
    """
    IDLE = "idle"
    BUSY = "busy"


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

    LONG_RUNNING: Long-running session mode with continuous availability (24/7 worker pattern).
                  When the session sends a message to itself, the Claude client is restarted
                  to clear conversation context while maintaining the same session_id.
                  This allows the session to continue indefinitely with fresh context.
                  External nodes can always reach this session using the same session_id.
                  DOES emit events to the event mesh during normal operation.
    """
    BACKGROUND = "background"
    PROGRAM = "program"
    CHAT = "chat"
    LONG_RUNNING = "long_running"


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
    NOTIFICATION = "notification"


class MessageType(str, Enum):
    """Message type enumeration

    Defines the specific type of message content and its structure.
    """
    USER_MESSAGE = "user_message"
    ASSISTANT_TEXT = "assistant_text"
    ASSISTANT_THINKING = "assistant_thinking"
    ASSISTANT_TOOL_USE = "assistant_tool_use"
    ASSISTANT_TOOL_OUTPUT = "assistant_tool_output"
    ASSISTANT_PRE_COMPACT = "assistant_pre_compact"
    ASSISTANT_RESULT = "assistant_result"
    SYSTEM_MESSAGE = "system_message"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    TOPIC_UPDATED = "topic_updated"
    RUNTIME_STATUS_CHANGED = "runtime_status_changed"
