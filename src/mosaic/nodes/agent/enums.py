from enum import StrEnum

class SessionRoutingStrategy(StrEnum):
    MIRRORING = "mirroring"
    TASKING = "tasking"
    STATEFUL = "stateful"

class SessionMode(StrEnum):
    CHAT = "chat"
    PROGRAM = "program"
    BACKGROUND = "background"

class AgentNodeRunningMode(StrEnum):
    CHAT = "chat"
    PROGRAM = "program"
    BACKGROUND = "background"