"""
Mosaic Core Exceptions

This module defines the exception hierarchy for the Mosaic event system.
All exceptions inherit from MosaicError for unified error handling.

Design Principles:
- Clear error categories for different failure modes
- Rich error context for debugging
- Serializable error information for cross-process communication
"""

from typing import Any, Optional


# =============================================================================
# Base Exception
# =============================================================================

class MosaicError(Exception):
    """
    Base exception for all Mosaic errors.
    
    All Mosaic exceptions inherit from this class, allowing for unified
    error handling across the system.
    
    Attributes:
        message: Human-readable error description
        details: Additional context as key-value pairs
    """
    
    def __init__(self, message: str, **details: Any) -> None:
        self.message = message
        self.details = details
        super().__init__(message)
    
    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v!r}" for k, v in self.details.items())
            return f"{self.message} ({detail_str})"
        return self.message
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize exception for cross-process communication."""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# =============================================================================
# Node Exceptions
# =============================================================================

class NodeError(MosaicError):
    """Base exception for node-related errors."""
    pass


class NodeNotFoundError(NodeError):
    """Raised when a referenced node does not exist."""
    
    def __init__(self, node_id: str, mesh_id: Optional[str] = None) -> None:
        super().__init__(
            f"Node not found: {node_id}",
            node_id=node_id,
            mesh_id=mesh_id,
        )


class NodeAlreadyExistsError(NodeError):
    """Raised when attempting to create a node that already exists."""
    
    def __init__(self, node_id: str, mesh_id: Optional[str] = None) -> None:
        super().__init__(
            f"Node already exists: {node_id}",
            node_id=node_id,
            mesh_id=mesh_id,
        )


class NodeStateError(NodeError):
    """Raised when a node operation is invalid for its current state."""
    
    def __init__(
        self,
        node_id: str,
        current_state: str,
        expected_states: list[str],
    ) -> None:
        super().__init__(
            f"Invalid state for node {node_id}: {current_state}, expected one of {expected_states}",
            node_id=node_id,
            current_state=current_state,
            expected_states=expected_states,
        )


# =============================================================================
# Subscription Exceptions
# =============================================================================

class SubscriptionError(MosaicError):
    """Base exception for subscription-related errors."""
    pass


class SubscriptionNotFoundError(SubscriptionError):
    """Raised when a referenced subscription does not exist."""
    
    def __init__(
        self,
        source_id: str,
        target_id: str,
        pattern: Optional[str] = None,
    ) -> None:
        super().__init__(
            f"Subscription not found: {source_id} -> {target_id}",
            source_id=source_id,
            target_id=target_id,
            pattern=pattern,
        )


class SubscriptionAlreadyExistsError(SubscriptionError):
    """Raised when attempting to create a duplicate subscription."""
    
    def __init__(
        self,
        source_id: str,
        target_id: str,
        pattern: str,
    ) -> None:
        super().__init__(
            f"Subscription already exists: {source_id} -> {target_id} [{pattern}]",
            source_id=source_id,
            target_id=target_id,
            pattern=pattern,
        )


class InvalidEventPatternError(SubscriptionError):
    """Raised when an event pattern is malformed."""
    
    def __init__(self, pattern: str, reason: str) -> None:
        super().__init__(
            f"Invalid event pattern '{pattern}': {reason}",
            pattern=pattern,
            reason=reason,
        )


# =============================================================================
# Event Exceptions
# =============================================================================

class EventError(MosaicError):
    """Base exception for event-related errors."""
    pass


class EventDeliveryError(EventError):
    """Raised when event delivery fails."""
    
    def __init__(
        self,
        event_id: str,
        target_id: str,
        reason: str,
    ) -> None:
        super().__init__(
            f"Failed to deliver event {event_id} to {target_id}: {reason}",
            event_id=event_id,
            target_id=target_id,
            reason=reason,
        )


class EventTimeoutError(EventError):
    """Raised when waiting for event response times out."""
    
    def __init__(
        self,
        event_id: str,
        timeout_seconds: float,
        waiting_for: Optional[list[str]] = None,
    ) -> None:
        super().__init__(
            f"Timeout waiting for response to event {event_id} after {timeout_seconds}s",
            event_id=event_id,
            timeout_seconds=timeout_seconds,
            waiting_for=waiting_for,
        )


class EventNotFoundError(EventError):
    """Raised when a referenced event does not exist."""
    
    def __init__(self, event_id: str) -> None:
        super().__init__(
            f"Event not found: {event_id}",
            event_id=event_id,
        )


class EventSerializationError(EventError):
    """Raised when event serialization or deserialization fails."""
    
    def __init__(self, operation: str, reason: str) -> None:
        super().__init__(
            f"Event {operation} failed: {reason}",
            operation=operation,
            reason=reason,
        )


# =============================================================================
# Transport Exceptions
# =============================================================================

class TransportError(MosaicError):
    """Base exception for transport layer errors."""
    pass


class TransportConnectionError(TransportError):
    """Raised when transport connection fails."""
    
    def __init__(self, transport_type: str, reason: str) -> None:
        super().__init__(
            f"Transport connection failed ({transport_type}): {reason}",
            transport_type=transport_type,
            reason=reason,
        )


class TransportUnavailableError(TransportError):
    """Raised when the transport layer is not available."""
    
    def __init__(self, reason: str) -> None:
        super().__init__(
            f"Transport unavailable: {reason}",
            reason=reason,
        )


# =============================================================================
# Mesh Exceptions
# =============================================================================

class MeshError(MosaicError):
    """Base exception for mesh-related errors."""
    pass


class MeshNotFoundError(MeshError):
    """Raised when a referenced mesh does not exist."""
    
    def __init__(self, mesh_id: str) -> None:
        super().__init__(
            f"Mesh not found: {mesh_id}",
            mesh_id=mesh_id,
        )


class MeshAlreadyExistsError(MeshError):
    """Raised when attempting to create a mesh that already exists."""
    
    def __init__(self, mesh_id: str) -> None:
        super().__init__(
            f"Mesh already exists: {mesh_id}",
            mesh_id=mesh_id,
        )


# =============================================================================
# Configuration Exceptions
# =============================================================================

class ConfigurationError(MosaicError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, config_key: str, reason: str) -> None:
        super().__init__(
            f"Configuration error for '{config_key}': {reason}",
            config_key=config_key,
            reason=reason,
        )


# =============================================================================
# Waiter/Blocking Exceptions
# =============================================================================

class WaiterError(MosaicError):
    """Base exception for waiter-related errors."""
    pass


class WaiterNotFoundError(WaiterError):
    """Raised when a waiter for an event is not found."""
    
    def __init__(self, event_id: str) -> None:
        super().__init__(
            f"No waiter registered for event: {event_id}",
            event_id=event_id,
        )


class WaiterAlreadyExistsError(WaiterError):
    """Raised when a waiter for an event already exists."""
    
    def __init__(self, event_id: str) -> None:
        super().__init__(
            f"Waiter already exists for event: {event_id}",
            event_id=event_id,
        )

