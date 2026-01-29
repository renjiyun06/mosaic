"""
Data Models

Responsibilities:
- Define SDK data structures
- Request/response models
- Data validation helpers
- Type definitions

This module may reuse backend schema definitions or define
SDK-specific models.
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class ProgrammableCallRequest:
    """
    Request model for programmable call.

    This mirrors the backend schema but provides a Python-friendly interface.

    Attributes:
        session_id: Target session ID
        method: Method name to invoke
        instruction: Natural language instruction
        kwargs: Method parameters
        return_schema: Optional JSON schema for validation
    """
    session_id: str
    method: str
    instruction: str
    kwargs: Optional[Dict[str, Any]] = None
    return_schema: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API request."""
        result = {
            "session_id": self.session_id,
            "method": self.method,
            "instruction": self.instruction,
        }
        if self.kwargs is not None:
            result["kwargs"] = self.kwargs
        if self.return_schema is not None:
            result["return_schema"] = self.return_schema
        return result


@dataclass
class ProgrammableCallResponse:
    """
    Response model for programmable call.

    Attributes:
        result: Method execution result
        execution_time: Time taken in seconds
        session_id: Session that executed the call
    """
    result: Any
    execution_time: float
    session_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProgrammableCallResponse':
        """Create instance from API response dict."""
        return cls(
            result=data.get("result"),
            execution_time=data.get("execution_time", 0.0),
            session_id=data.get("session_id", "")
        )


@dataclass
class SessionInfo:
    """
    Session information model.

    Attributes:
        session_id: Session identifier
        mosaic_id: Parent mosaic ID
        node_id: Parent node ID
        created_at: Session creation timestamp
    """
    session_id: str
    mosaic_id: str
    node_id: str
    created_at: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionInfo':
        """Create instance from API response dict."""
        return cls(
            session_id=data["session_id"],
            mosaic_id=data["mosaic_id"],
            node_id=data["node_id"],
            created_at=data["created_at"]
        )


@dataclass
class AuthToken:
    """
    Authentication token model.

    Attributes:
        access_token: JWT token string
        token_type: Token type (usually "Bearer")
        expires_in: Token validity duration in seconds
    """
    access_token: str
    token_type: str
    expires_in: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuthToken':
        """Create instance from API response dict."""
        return cls(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 3600)
        )
