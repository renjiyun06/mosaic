"""Programmable call schemas for API input/output"""

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum


# ==================== Enums ====================

class CallStatus(str, Enum):
    """Programmable call execution status"""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


# ==================== Input Schemas ====================

class ProgrammableCallRequest(BaseModel):
    """Programmable call request

    This schema defines the structure for making a programmable call to a node.

    Core concept:
    - method: Semantic identifier for the task (e.g., "analyze_data", "generate_report")
    - instruction: Optional detailed multi-step task description
    - kwargs: Keyword arguments (only JSON-serializable types supported)
    - return_schema: JSON Schema Draft 7 for expected return value structure

    Session management:
    - session_id is required and must be pre-created via /session API
    - SDK is responsible for creating and managing sessions
    - Session must be in ACTIVE status to be used for programmable calls
    """

    mosaic_id: int = Field(
        ...,
        description="Target mosaic ID",
        examples=[1]
    )

    node_id: str = Field(
        ...,
        description="Target node ID within the mosaic",
        examples=["analyst", "data-processor", "report-generator"]
    )

    session_id: str = Field(
        ...,
        description=(
            "Session ID to use for this call (must be pre-created via /session API). "
            "The session must be in ACTIVE status and belong to the target node. "
            "SDK is responsible for creating and managing session lifecycle."
        ),
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )

    method: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description=(
            "Semantic method identifier for the task. "
            "This should be descriptive and help the node understand the task intent. "
            "Examples: 'analyze_user_behavior', 'extract_entities', 'validate_data'"
        ),
        examples=["analyze_user_behavior", "extract_entities", "clean_data"]
    )

    instruction: Optional[str] = Field(
        None,
        max_length=10000,
        description=(
            "Detailed task instruction (optional). "
            "Use this for complex tasks that require multiple steps or detailed context. "
            "The node will use this along with method and kwargs to understand the task. "
            "For simple tasks, method + kwargs may be sufficient."
        ),
        examples=[
            "Analyze the user behavior data and identify patterns. "
            "Return a risk score (0-100) and risk level (low/medium/high).",
            None
        ]
    )

    kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Keyword arguments for the method call. "
            "Only JSON-serializable types are supported: str, int, float, bool, None, list, dict. "
            "Argument names should be semantic and help the node understand the data. "
            "Example: {'user_data': {...}, 'threshold': 0.95, 'include_history': true}"
        ),
        examples=[
            {"user_data": {"user_id": 123, "events": []}, "threshold": 0.95},
            {"text": "Hello world", "target_lang": "zh"}
        ]
    )

    return_schema: Optional[dict[str, Any]] = Field(
        None,
        description=(
            "JSON Schema (Draft 7) defining expected return value structure. "
            "The node will attempt to format its response according to this schema. "
            "If None, the node will return data in its natural format. "
            "Example: {'type': 'object', 'required': ['score'], 'properties': {...}}"
        ),
        examples=[
            {
                "type": "object",
                "required": ["score", "risk_level"],
                "properties": {
                    "score": {"type": "number", "minimum": 0, "maximum": 100},
                    "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                    "details": {"type": "string"}
                }
            },
            None
        ]
    )

    timeout: int = Field(
        default=60,
        ge=1,
        le=600,
        description=(
            "Timeout in seconds (1-600). "
            "If the node doesn't return within this time, the call will fail with status='timeout'. "
            "Default: 60 seconds."
        ),
        examples=[60, 120, 300]
    )

    @field_validator('kwargs')
    @classmethod
    def validate_kwargs_serializable(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate that all kwargs values are JSON-serializable

        Note:
            This is a basic check. The actual JSON serialization will be
            validated when the request is processed.
        """
        def is_json_serializable(obj: Any) -> bool:
            """Check if object is JSON-serializable (recursively)"""
            if obj is None:
                return True
            if isinstance(obj, (str, int, float, bool)):
                return True
            if isinstance(obj, (list, tuple)):
                return all(is_json_serializable(item) for item in obj)
            if isinstance(obj, dict):
                return all(
                    isinstance(k, str) and is_json_serializable(v)
                    for k, v in obj.items()
                )
            return False

        if not is_json_serializable(v):
            raise ValueError(
                "All kwargs values must be JSON-serializable "
                "(str, int, float, bool, None, list, dict)"
            )
        return v

    @field_validator('return_schema')
    @classmethod
    def validate_return_schema_format(cls, v: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Validate return_schema is a valid JSON Schema structure

        Note:
            This performs basic validation. Full JSON Schema Draft 7 validation
            will be done during request processing using jsonschema library.
        """
        if v is None:
            return v

        # Must be a dict
        if not isinstance(v, dict):
            raise ValueError("return_schema must be a dict (JSON Schema object)")

        # Should have 'type' field (common requirement)
        if 'type' not in v:
            raise ValueError(
                "return_schema should have a 'type' field "
                "(e.g., 'object', 'array', 'string')"
            )

        return v


# ==================== Output Schemas ====================

class ProgrammableCallResponse(BaseModel):
    """Programmable call response

    This schema defines the structure of the response from a programmable call.

    Status values:
    - success: Call completed successfully, result contains the return value
    - error: Call failed due to an error, error field contains error message
    - timeout: Call timed out before node could respond

    Session handling:
    - session_id: The session that was used (auto-created, reused, or explicitly specified)
    - This session_id can be used in subsequent calls for context continuity

    Performance metrics:
    - execution_time_ms: Wall-clock time from request to response
    """

    status: CallStatus = Field(
        ...,
        description=(
            "Call execution status. "
            "'success' = completed successfully, "
            "'error' = failed with error, "
            "'timeout' = exceeded timeout limit"
        ),
        examples=["success", "error", "timeout"]
    )

    result: Any = Field(
        None,
        description=(
            "Return value from the node. "
            "Type depends on return_schema (if provided) or node's natural response. "
            "Will be None if status is 'error' or 'timeout'."
        ),
        examples=[
            {"score": 75, "risk_level": "medium", "details": "User shows moderate risk patterns"},
            {"translation": "你好世界", "confidence": 0.98},
            None
        ]
    )

    error: Optional[str] = Field(
        None,
        description=(
            "Error message if status='error'. "
            "Contains human-readable description of what went wrong. "
            "Will be None if status='success'."
        ),
        examples=[
            "Node 'analyst' not found in mosaic",
            "Invalid kwargs: missing required field 'data'",
            "Return value does not match return_schema",
            None
        ]
    )

    session_id: str = Field(
        ...,
        description=(
            "Session ID that was used for this call. "
            "This can be: "
            "1) Auto-created by session pool (if request.session_id was None), "
            "2) The explicitly provided session_id from the request. "
            "Use this in subsequent calls to maintain context."
        ),
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )

    call_id: str = Field(
        ...,
        description=(
            "Unique identifier for this call (UUID). "
            "Can be used for debugging, logging, or tracing the call through the system."
        ),
        examples=["7c9e6679-7425-40de-944b-e07fc1f90ae7"]
    )

    execution_time_ms: int = Field(
        ...,
        ge=0,
        description=(
            "Execution time in milliseconds. "
            "Measures wall-clock time from when the call was initiated "
            "to when the response was received (or timeout occurred)."
        ),
        examples=[1523, 5672, 45000]
    )

    class Config:
        use_enum_values = True  # Serialize enum as string value
