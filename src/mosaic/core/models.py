"""
Mosaic Core Data Models

This module defines the data structures used throughout the Mosaic event system.
All models use Pydantic for validation, serialization, and immutability.

Design Principles:
- Models are immutable (frozen=True) where appropriate
- Clear separation between event system data and node-specific data
- SessionTrace is just metadata; the event system doesn't interpret it
- Subscription configuration (session_scope, etc.) is opaque to event system
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from .types import (
    NodeId,
    MeshId,
    EventId,
    SessionId,
    EventPattern,
    NodeType,
    NodeState,
    EventStatus,
    SessionScope,
    SessionFilter,
    RestartPolicy,
)


# =============================================================================
# Session Trace (Event Metadata)
# =============================================================================

class SessionTrace(BaseModel):
    """
    Session tracing information attached to events.
    
    IMPORTANT: This is METADATA only. The event system does not interpret
    these fields - it simply passes them through. Agent nodes use this
    information to organize their internal sessions. Non-agent nodes
    can ignore this entirely.
    
    Attributes:
        node_id: The node that produced this event
        upstream_session_id: Session identifier in the upstream node
        event_seq: Sequence number of this event within the session
    
    Example:
        When worker node produces PreToolUse in session "sess-123":
        - SessionTrace(node_id="worker", upstream_session_id="sess-123", event_seq=5)
        
        Downstream auditor can use this to maintain session alignment.
    """
    
    model_config = {"frozen": True}
    
    node_id: NodeId = Field(
        description="Node that produced this event"
    )
    upstream_session_id: SessionId = Field(
        description="Session identifier in the producing node"
    )
    event_seq: int = Field(
        ge=0,
        description="Sequence number within the session (0-indexed)"
    )


# =============================================================================
# Events
# =============================================================================

class MeshEvent(BaseModel):
    """
    Base class for all events in the Mosaic mesh.
    
    Events are the fundamental unit of communication between nodes.
    The event system handles routing and delivery; the payload is
    interpreted by the receiving node.
    
    Attributes:
        event_id: Globally unique identifier for this event
        mesh_id: The mesh this event belongs to
        source_id: Node that sent this event
        target_id: Node that should receive this event
        event_type: Type identifier (e.g., "PreToolUse", "NodeMessage")
        timestamp: When the event was created (UTC)
        session_trace: Optional session tracing information (metadata)
        reply_to: If this is a reply, the event_id being replied to
        payload: Event-specific data (interpreted by receiver)
    
    Note on Routing:
        - source_id: Set by the sender (who am I?)
        - target_id: Set during routing (who should receive this?)
        
        When a node produces an event, target_id is initially empty.
        The EventRouter populates target_id based on subscriptions.
    """
    
    event_id: EventId = Field(
        description="Globally unique event identifier"
    )
    mesh_id: MeshId = Field(
        description="Mesh this event belongs to"
    )
    source_id: NodeId = Field(
        description="Node that produced this event"
    )
    target_id: NodeId = Field(
        default="",
        description="Target node (populated by router)"
    )
    event_type: str = Field(
        description="Event type identifier"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event creation time (UTC)"
    )
    session_trace: Optional[SessionTrace] = Field(
        default=None,
        description="Session tracing metadata (for agent nodes)"
    )
    reply_to: Optional[EventId] = Field(
        default=None,
        description="Event ID this is replying to (for responses)"
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific payload data"
    )
    
    def is_reply(self) -> bool:
        """Check if this event is a reply to another event."""
        return self.reply_to is not None
    
    def create_reply(
        self,
        source_id: NodeId,
        event_id: EventId,
        payload: dict[str, Any],
    ) -> "MeshEvent":
        """
        Create a reply event to this event.
        
        Args:
            source_id: The node sending the reply
            event_id: Unique ID for the reply event
            payload: Reply payload data
            
        Returns:
            New MeshEvent configured as a reply
        """
        return MeshEvent(
            event_id=event_id,
            mesh_id=self.mesh_id,
            source_id=source_id,
            target_id=self.source_id,  # Reply goes back to sender
            event_type="NodeMessage",
            reply_to=self.event_id,
            payload=payload,
        )


# =============================================================================
# Subscription
# =============================================================================

class Subscription(BaseModel):
    """
    Defines an event subscription between nodes.
    
    A subscription specifies:
    - WHO subscribes to WHOM (source -> target)
    - WHAT events to receive (event_pattern)
    - HOW to handle blocking (! prefix)
    - Agent-specific configuration (session_scope, etc.)
    
    Terminology:
        - source_id: The SUBSCRIBER (downstream node, receives events)
        - target_id: The SUBSCRIBED (upstream node, produces events)
        
    Event Pattern Syntax:
        - "*": All events (non-blocking)
        - "PreToolUse": Specific event type (non-blocking)
        - "!PreToolUse": Blocking subscription (sender waits for reply)
        - "PreToolUse,PostToolUse": Multiple event types
    
    Attributes:
        mesh_id: The mesh this subscription belongs to
        source_id: Subscribing node (will receive events)
        target_id: Subscribed node (produces events)
        event_pattern: Which events to receive
        
        # Agent-specific configuration (opaque to event system)
        session_scope: How to organize sessions (agent nodes only)
        session_filter: Which session types can handle events
        session_profile: Profile identifier for session configuration
        min_sessions: Minimum number of sessions to maintain
        max_sessions: Maximum number of sessions allowed
    """
    
    model_config = {"frozen": True}
    
    mesh_id: MeshId = Field(
        description="Mesh this subscription belongs to"
    )
    source_id: NodeId = Field(
        description="Subscribing node (downstream, receives events)"
    )
    target_id: NodeId = Field(
        description="Subscribed node (upstream, produces events)"
    )
    event_pattern: EventPattern = Field(
        description="Event pattern to match"
    )
    
    # Agent-specific configuration
    # The event system passes these through without interpretation
    session_scope: SessionScope = Field(
        default=SessionScope.UPSTREAM_SESSION,
        description="Session organization strategy (agent nodes only)"
    )
    session_filter: SessionFilter = Field(
        default=SessionFilter.ANY,
        description="Session type filter (agent nodes only)"
    )
    session_profile: str = Field(
        default="default",
        description="Session configuration profile"
    )
    min_sessions: int = Field(
        default=1,
        ge=1,
        description="Minimum sessions to maintain"
    )
    max_sessions: int = Field(
        default=10,
        ge=1,
        description="Maximum sessions allowed"
    )
    
    def is_blocking(self) -> bool:
        """Check if this subscription requires blocking (sender waits)."""
        return self.event_pattern.startswith("!")
    
    def get_event_types(self) -> list[str]:
        """
        Extract event types from the pattern.
        
        Returns:
            List of event type strings (without ! prefix)
        
        Examples:
            "!PreToolUse" -> ["PreToolUse"]
            "PreToolUse,PostToolUse" -> ["PreToolUse", "PostToolUse"]
            "*" -> ["*"]
        """
        pattern = self.event_pattern.lstrip("!")
        return [t.strip() for t in pattern.split(",")]
    
    def matches_event(self, event_type: str) -> bool:
        """
        Check if this subscription matches a given event type.
        
        Args:
            event_type: The event type to check
            
        Returns:
            True if this subscription should receive the event
        """
        types = self.get_event_types()
        return "*" in types or event_type in types


# =============================================================================
# Node
# =============================================================================

class Node(BaseModel):
    """
    Definition of a node in the Mosaic mesh.
    
    A node is the basic unit of the system. It can produce events,
    consume events, or both. Different node types have different
    runtime implementations.
    
    Attributes:
        mesh_id: The mesh this node belongs to
        node_id: Unique identifier within the mesh
        node_type: Type of node (determines runtime implementation)
        workspace: Working directory path (for CC nodes)
        config: Node-specific configuration
        restart_policy: How to handle crashes
        max_retries: Maximum restart attempts before giving up
    """
    
    mesh_id: MeshId = Field(
        description="Mesh this node belongs to"
    )
    node_id: NodeId = Field(
        description="Unique identifier within the mesh"
    )
    node_type: NodeType = Field(
        description="Type of node (determines runtime)"
    )
    workspace: Optional[str] = Field(
        default=None,
        description="Working directory path"
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Node-specific configuration"
    )
    restart_policy: RestartPolicy = Field(
        default=RestartPolicy.ON_FAILURE,
        description="Automatic restart policy"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum restart attempts"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the node was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update time"
    )


class NodeStatus(BaseModel):
    """
    Runtime status of a node.
    
    This represents the current state of a running node,
    as tracked by the Daemon.
    
    Attributes:
        node_id: The node this status is for
        mesh_id: The mesh the node belongs to
        state: Current state (IDLE, RUNNING, FAILED, etc.)
        pid: Process ID if running
        uptime_seconds: How long the node has been running
        crash_count: Number of times this node has crashed
        last_error: Most recent error message
        pending_events: Number of events waiting to be processed
    """
    
    node_id: NodeId
    mesh_id: MeshId
    state: NodeState = NodeState.IDLE
    pid: Optional[int] = None
    uptime_seconds: float = 0.0
    crash_count: int = 0
    last_error: Optional[str] = None
    pending_events: int = 0
    last_heartbeat: Optional[datetime] = None


# =============================================================================
# Mesh
# =============================================================================

class Mesh(BaseModel):
    """
    Definition of a Mosaic mesh instance.
    
    A mesh is an isolated network of nodes. Multiple meshes can
    exist on the same system, each with independent nodes and
    subscriptions.
    
    Attributes:
        mesh_id: Unique identifier for this mesh
        config: Mesh-level configuration
        created_at: When the mesh was created
    """
    
    mesh_id: MeshId = Field(
        description="Unique mesh identifier"
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Mesh-level configuration"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp"
    )


# =============================================================================
# Context Models
# =============================================================================

class TopologyContext(BaseModel):
    """
    Topology information for a node.
    
    This provides a node with information about its position
    in the mesh network - who it subscribes to and who subscribes
    to it.
    
    Attributes:
        node_id: The node this context is for
        mesh_id: The mesh the node belongs to
        subscriptions: Subscriptions where this node is the subscriber
        subscribers: Subscriptions where this node is being subscribed to
    """
    
    node_id: NodeId
    mesh_id: MeshId
    subscriptions: list[Subscription] = Field(
        default_factory=list,
        description="Who this node subscribes to (downstream of us)"
    )
    subscribers: list[Subscription] = Field(
        default_factory=list,
        description="Who subscribes to this node (upstream of us)"
    )
    
    def get_blocking_subscribers(self, event_type: str) -> list[Subscription]:
        """
        Get subscribers that have blocking subscriptions for an event type.
        
        Args:
            event_type: The event type to check
            
        Returns:
            List of blocking subscriptions matching the event type
        """
        return [
            sub for sub in self.subscribers
            if sub.is_blocking() and sub.matches_event(event_type)
        ]


class EventSemantics(BaseModel):
    """
    Semantic description of an event type.
    
    This provides natural language descriptions and schema information
    for event types, which can be injected into agent prompts.
    
    Attributes:
        event_type: The event type this describes
        description: Human-readable description
        schema: JSON Schema for the payload (optional)
        examples: Example payloads
    """
    
    event_type: str = Field(
        description="Event type identifier"
    )
    description: str = Field(
        description="Human-readable description for agents"
    )
    schema_def: Optional[dict[str, Any]] = Field(
        default=None,
        description="JSON Schema for event payload"
    )
    examples: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Example payloads"
    )


class NodeCapabilities(BaseModel):
    """
    Capability declaration for a node type.
    
    This declares what events a node type can produce or consume,
    along with semantic descriptions.
    
    Attributes:
        node_type: The node type these capabilities are for
        produced_events: Event types this node can produce
        consumed_events: Event types this node can consume
    """
    
    node_type: NodeType
    produced_events: list[EventSemantics] = Field(
        default_factory=list,
        description="Events this node type can produce"
    )
    consumed_events: list[EventSemantics] = Field(
        default_factory=list,
        description="Events this node type can consume"
    )


# =============================================================================
# Reply and Decision Models
# =============================================================================

class BlockingReply(BaseModel):
    """
    Reply to a blocking event.
    
    When a subscriber receives a blocking event (!EventName),
    it must send a reply. This model wraps the reply payload.
    
    Attributes:
        event_id: The event being replied to
        subscriber_id: Node sending the reply
        payload: Reply-specific data (format depends on event type)
    """
    
    event_id: EventId = Field(
        description="Event this is a reply to"
    )
    subscriber_id: NodeId = Field(
        description="Node sending the reply"
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Reply payload"
    )


class AggregatedDecision(BaseModel):
    """
    Aggregated decision from multiple blocking subscribers.
    
    When multiple subscribers have blocking subscriptions to the
    same event, their responses are aggregated using one-vote-veto:
    - Any DENY -> final DENY
    - Any ASK (no DENY) -> final ASK
    - All ALLOW -> final ALLOW
    
    Attributes:
        final_decision: The aggregated decision
        individual_replies: Replies from each subscriber
        reasons: Collected reasons from all subscribers
    """
    
    final_decision: str = Field(
        description="Aggregated decision (allow/deny/ask)"
    )
    individual_replies: list[BlockingReply] = Field(
        default_factory=list,
        description="Individual replies from subscribers"
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="Reasons from all subscribers"
    )
    timed_out_subscribers: list[NodeId] = Field(
        default_factory=list,
        description="Subscribers that timed out"
    )

