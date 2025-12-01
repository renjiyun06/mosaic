from enum import StrEnum
from typing import TypeAlias

NodeID: TypeAlias = str
MeshID: TypeAlias = str
EventID: TypeAlias = str

class NodeType(StrEnum):
    CLAUDE_CODE = "cc"
    CODEX = "codex"
    GEMINI = "gemini"
    CURSOR = "cursor"
    OPENHANDS = "openhands"
    SCHEDULER = "scheduler"
    WEBHOOK = "webhook"
    DUMMY = "dummy"

class MeshStatus(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"

class NodeStatus(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    CRASHED = "crashed"
    BACKOFF = "backoff"

class TransportType(StrEnum):
    SQLITE = "sqlite"
    KAFKA = "kafka"
    REDIS = "redis"

class SessionRoutingStrategy(StrEnum):
    MIRRORING = "mirroring"
    TASKING = "tasking"
    STATEFUL = "stateful"

class AgentRunningMode(StrEnum):
    CHAT = "chat"
    PROGRAM = "program"
    BACKGROUND = "background"

class ClaudeCodeHook(StrEnum):
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    STOP = "stop"