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

class MeshStatus(StrEnum):
    STARTED = "started"
    STOPPED = "stopped"

class NodeStatus(StrEnum):
    STARTED = "started"
    STOPPED = "stopped"