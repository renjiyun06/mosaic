"""Node implementations for Mosaic Event Mesh"""

from .claude_code import ClaudeCodeNode, ClaudeCodeSession
from .aggregator import AggregatorNode, AggregatorSession

# Node registry: maps node type to node class
NODE_REGISTRY = {
    "aggregator": AggregatorNode,
    "cc": ClaudeCodeNode,  # Claude Code node (matches database node_type value)
}

__all__ = [
    "ClaudeCodeNode",
    "ClaudeCodeSession",
    "AggregatorNode",
    "AggregatorSession",
    "NODE_REGISTRY",
]
