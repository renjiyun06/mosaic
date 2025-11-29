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