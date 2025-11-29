from mosaic.core.types import NodeType
from mosaic.core.models import NodeCapability

NODE_CATALOG = {
    NodeType.CLAUDE_CODE: {
        "capability": ...,
        "entry": "mosaic.nodes.agent.cc.main"
    },
    NodeType.CODEX: {
        "capability": ...,
        "entry": ...
    },
    NodeType.CURSOR: {
        "capability": ...,
        "entry": ...
    },
    NodeType.GEMINI: {
        "capability": ...,
        "entry": ...
    },
    NodeType.OPENHANDS: {
        "capability": ...,
        "entry": ...
    },
    NodeType.SCHEDULER: {
        "capability": ...,
        "entry": ...
    },
    NodeType.WEBHOOK: {
        "capability": ...,
        "entry": ...
    },
    NodeType.DUMMY: {
        "capability": NodeCapability(
            type=NodeType.DUMMY,
            produced_events=["*"],
            consumed_events=["*"],
            description=""
        ),
        "entry": "mosaic.nodes.dummy"
    },
}