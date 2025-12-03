from enum import StrEnum

class SessionRoutingStrategy(StrEnum):
    MIRRORING = "mirroring"
    TASKING = "tasking"
    STATEFUL = "stateful"

class AgentNodeRunningMode(StrEnum):
    CHAT = "chat"
    PROGRAM = "program"
    BACKGROUND = "background"