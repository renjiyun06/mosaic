"""
Mosaic Core Module

This module provides the foundational abstractions for the Mosaic event system.
It defines interfaces, data models, types, and exceptions that all other modules
depend on.

Architecture Role:
==================
core is the FOUNDATION layer with ZERO dependencies on other mosaic modules.
All other modules (transport, storage, runtime, nodes, daemon, cli) depend on core.

Contents:
=========
- types: Enums, type aliases, and constants
- exceptions: Exception hierarchy for error handling
- models: Pydantic data models for events, subscriptions, nodes
- interfaces: Abstract base classes defining system contracts

Usage:
======
    from mosaic.core import (
        # Interfaces
        MeshClient,
        MeshInbox,
        MeshOutbox,
        EventEnvelope,
        MeshAdmin,
        MeshContext,
        NodeRuntime,
        
        # Models
        MeshEvent,
        Subscription,
        Node,
        SessionTrace,
        
        # Types
        NodeType,
        EventStatus,
        SessionScope,
        
        # Exceptions
        MosaicError,
        NodeNotFoundError,
    )
"""

# Types - fundamental type definitions
from .types import (
    # Node types
    NodeType,
    NodeState,
    # Event types
    EventCategory,
    EventStatus,
    # Subscription configuration
    SessionScope,
    SessionFilter,
    # Decision types
    PermissionDecision,
    # Daemon types
    RestartPolicy,
    # Type aliases
    NodeId,
    MeshId,
    EventId,
    SessionId,
    SubscriptionId,
    EventPattern,
    # Constants
    BLOCKING_PREFIX,
)

# Exceptions - error handling
from .exceptions import (
    # Base
    MosaicError,
    # Node errors
    NodeError,
    NodeNotFoundError,
    NodeAlreadyExistsError,
    NodeStateError,
    # Subscription errors
    SubscriptionError,
    SubscriptionNotFoundError,
    SubscriptionAlreadyExistsError,
    InvalidEventPatternError,
    # Event errors
    EventError,
    EventDeliveryError,
    EventTimeoutError,
    EventNotFoundError,
    EventSerializationError,
    # Transport errors
    TransportError,
    TransportConnectionError,
    TransportUnavailableError,
    # Mesh errors
    MeshError,
    MeshNotFoundError,
    MeshAlreadyExistsError,
    # Configuration errors
    ConfigurationError,
    # Waiter errors
    WaiterError,
    WaiterNotFoundError,
    WaiterAlreadyExistsError,
)

# Models - data structures
from .models import (
    # Core event models
    MeshEvent,
    SessionTrace,
    # Subscription and node models
    Subscription,
    Node,
    NodeStatus,
    Mesh,
    # Context models
    TopologyContext,
    EventSemantics,
    NodeCapabilities,
    # Reply models
    BlockingReply,
    AggregatedDecision,
)

# Interfaces - abstract contracts
from .interfaces import (
    # Data plane
    EventEnvelope,
    MeshInbox,
    MeshOutbox,
    MeshClient,
    # Control plane
    MeshAdmin,
    # Context plane
    MeshContext,
    # Node runtime
    NodeRuntime,
)


__all__ = [
    # === Types ===
    "NodeType",
    "NodeState",
    "EventCategory",
    "EventStatus",
    "SessionScope",
    "SessionFilter",
    "PermissionDecision",
    "RestartPolicy",
    # Type aliases
    "NodeId",
    "MeshId",
    "EventId",
    "SessionId",
    "SubscriptionId",
    "EventPattern",
    "BLOCKING_PREFIX",
    
    # === Exceptions ===
    "MosaicError",
    "NodeError",
    "NodeNotFoundError",
    "NodeAlreadyExistsError",
    "NodeStateError",
    "SubscriptionError",
    "SubscriptionNotFoundError",
    "SubscriptionAlreadyExistsError",
    "InvalidEventPatternError",
    "EventError",
    "EventDeliveryError",
    "EventTimeoutError",
    "EventNotFoundError",
    "EventSerializationError",
    "TransportError",
    "TransportConnectionError",
    "TransportUnavailableError",
    "MeshError",
    "MeshNotFoundError",
    "MeshAlreadyExistsError",
    "ConfigurationError",
    "WaiterError",
    "WaiterNotFoundError",
    "WaiterAlreadyExistsError",
    
    # === Models ===
    "MeshEvent",
    "SessionTrace",
    "Subscription",
    "Node",
    "NodeStatus",
    "Mesh",
    "TopologyContext",
    "EventSemantics",
    "NodeCapabilities",
    "BlockingReply",
    "AggregatedDecision",
    
    # === Interfaces ===
    "EventEnvelope",
    "MeshInbox",
    "MeshOutbox",
    "MeshClient",
    "MeshAdmin",
    "MeshContext",
    "NodeRuntime",
]

