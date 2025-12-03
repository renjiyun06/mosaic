from enum import StrEnum

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
    STOPPING = "stopping"
    STOPPED = "stopped"

class NodeStatus(StrEnum):
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"

class TransportType(StrEnum):
    SQLITE = "sqlite"
    KAFKA = "kafka"
    REDIS = "redis"