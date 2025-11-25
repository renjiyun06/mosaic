"""
Mosaic Core Types

This module defines fundamental types, enums, and type aliases used throughout
the Mosaic event system. These are the building blocks for data models and interfaces.

Design Principles:
- All types are immutable or designed for read-only use
- Enums use string values for JSON serialization compatibility
- Type aliases improve code readability and maintainability
"""

from enum import Enum
from typing import Literal


# =============================================================================
# Node Types
# =============================================================================

class NodeType(str, Enum):
    """
    Defines the category of a node in the Mosaic mesh.
    
    Node types determine:
    - How the node processes events
    - What runtime implementation is used
    - Whether Session concepts are applicable (only for agent types)
    
    Extensible: New node types can be registered via NodeFactory.
    """
    
    # Agent nodes (have Session concept)
    CLAUDE_CODE = "cc"          # Claude Code instance
    GEMINI = "gemini"           # Google Gemini (future)
    
    # System nodes (no Session concept)
    SCHEDULER = "scheduler"     # Time-based event producer
    WEBHOOK = "webhook"         # HTTP-to-event bridge
    GENERIC = "generic"         # Custom node type


class NodeState(str, Enum):
    """
    Runtime state of a node instance.
    
    State transitions:
    - IDLE -> RUNNING (start)
    - RUNNING -> IDLE (stop)
    - RUNNING -> FAILED (crash)
    - FAILED -> RUNNING (restart)
    """
    
    IDLE = "idle"               # Not running
    RUNNING = "running"         # Active and processing events
    FAILED = "failed"           # Crashed, awaiting restart
    STOPPING = "stopping"       # Graceful shutdown in progress


# =============================================================================
# Event Types
# =============================================================================

class EventCategory(str, Enum):
    """
    High-level categorization of events.
    
    Note: Specific event types (PreToolUse, PostToolUse, etc.) are defined
    by node implementations, not in core. This enum only defines categories.
    """
    
    HOOK = "hook"               # Claude Code hook events
    MESSAGE = "message"         # Inter-node messages
    SYSTEM = "system"           # System/lifecycle events
    CUSTOM = "custom"           # User-defined events


class EventStatus(str, Enum):
    """
    Processing status of an event in the transport layer.
    
    Lifecycle:
    - PENDING: Newly created, waiting to be delivered
    - PROCESSING: Picked up by a node, being processed
    - COMPLETED: Successfully processed and ACKed
    - FAILED: Processing failed, may be retried
    - EXPIRED: Exceeded recovery window, archived
    """
    
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


# =============================================================================
# Subscription Configuration Types
# =============================================================================

class SessionScope(str, Enum):
    """
    Session organization strategy for subscriptions.
    
    IMPORTANT: This is configuration for agent nodes only. The event system
    treats this as opaque metadata and passes it through. Non-agent nodes
    can ignore this entirely.
    
    Creation Strategies (create or reuse sessions):
    - UPSTREAM_SESSION: One downstream session per upstream session
    - PER_EVENT: New session for each event
    - UPSTREAM_NODE: One session for all events from an upstream node
    - GLOBAL: Single long-lived session for all events
    
    Dispatch Strategies (select from existing sessions):
    - RANDOM: Random selection
    - ROUND_ROBIN: Rotate through sessions
    - LOAD_BALANCED: Select least loaded session
    - STICKY_SOURCE: Same source always goes to same session
    """
    
    # Creation strategies
    UPSTREAM_SESSION = "upstream-session"
    PER_EVENT = "per-event"
    UPSTREAM_NODE = "upstream-node"
    GLOBAL = "global"
    
    # Dispatch strategies
    RANDOM = "random"
    ROUND_ROBIN = "round-robin"
    LOAD_BALANCED = "load-balanced"
    STICKY_SOURCE = "sticky-source"


class SessionFilter(str, Enum):
    """
    Filter for session routing (agent nodes only).
    
    Determines which session types can handle events:
    - ANY: Route to any available session
    - BACKEND_ONLY: Only route to backend sessions
    - INTERACTIVE_ONLY: Only route to interactive sessions
    - INTERACTIVE_FIRST: Prefer interactive, fallback to backend
    """
    
    ANY = "any"
    BACKEND_ONLY = "backend-only"
    INTERACTIVE_ONLY = "interactive-only"
    INTERACTIVE_FIRST = "interactive-first"


# =============================================================================
# Permission and Decision Types
# =============================================================================

class PermissionDecision(str, Enum):
    """
    Decision for blocking hook events (e.g., PreToolUse).
    
    Used in responses to blocking subscriptions:
    - ALLOW: Permit the action to proceed
    - DENY: Block the action with a reason
    - ASK: Request user confirmation
    
    Aggregation rule for multiple subscribers: One-vote-veto
    - Any DENY -> final DENY
    - Any ASK (no DENY) -> final ASK  
    - All ALLOW -> final ALLOW
    """
    
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


# =============================================================================
# Daemon and Restart Types
# =============================================================================

class RestartPolicy(str, Enum):
    """
    Policy for automatic restart of crashed nodes.
    
    - ALWAYS: Always restart regardless of exit code
    - ON_FAILURE: Only restart on non-zero exit code
    - NEVER: Never automatically restart
    """
    
    ALWAYS = "always"
    ON_FAILURE = "on-failure"
    NEVER = "never"


# =============================================================================
# Type Aliases
# =============================================================================

# Identifiers
NodeId = str
MeshId = str
EventId = str
SessionId = str
SubscriptionId = str

# Event pattern for subscriptions
# Examples: "*", "PreToolUse", "!PreToolUse", "PreToolUse,PostToolUse"
EventPattern = str

# Blocking indicator in event pattern
# "!" prefix indicates blocking subscription
BLOCKING_PREFIX: Literal["!"] = "!"

