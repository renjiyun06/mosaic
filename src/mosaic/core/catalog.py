from mosaic.core.types import NodeType

NODE_CATALOG = {
    NodeType.CLAUDE_CODE: {
        "entry": "mosaic.nodes.agent.cc.main"
    },
    NodeType.CODEX: {
        "entry": ...
    },
    NodeType.CURSOR: {
        "entry": ...
    },
    NodeType.GEMINI: {
        "entry": ...
    },
    NodeType.OPENHANDS: {
        "entry": ...
    },
    NodeType.SCHEDULER: {
        "entry": ...
    },
    NodeType.WEBHOOK: {
        "entry": ...
    },
    NodeType.DUMMY: {
        "entry": "mosaic.nodes.dummy"
    },
}