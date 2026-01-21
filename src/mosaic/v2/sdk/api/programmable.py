"""
Programmable Call API Client

Responsibilities:
- Execute programmable call endpoint wrapper
- Session management endpoints (create, destroy)
- Request/response handling for programmable calls
- Schema validation support

This module wraps backend programmable call endpoints.
"""

from typing import Any, Dict, Optional
from .base import APIClient
from ..exceptions import ProgrammableCallError
from ..utils import validate_json_schema


class ProgrammableCallAPI:
    """
    API client for Programmable Call endpoints.

    Endpoints:
    - POST /api/programmable/call
    - POST /api/mosaics/{mosaic_id}/sessions
    - POST /api/mosaics/{mosaic_id}/sessions/{session_id}/close

    Args:
        api_client: Base APIClient instance
    """

    def __init__(self, api_client: APIClient):
        """Initialize programmable call API client."""
        self.api_client = api_client

    async def execute(
        self,
        mosaic_id: int,
        node_id: str,
        session_id: str,
        method: str,
        instruction: Optional[str] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        return_schema: Optional[Dict[str, Any]] = None,
        timeout: int = 60,
    ) -> Any:
        """
        Execute a programmable call.

        This is the core API for invoking methods on remote nodes.

        Args:
            mosaic_id: Target mosaic ID
            node_id: Target node ID
            session_id: Target session ID (required)
            method: Method name to invoke
            instruction: Optional natural language instruction for the agent
            kwargs: Method parameters as dict
            return_schema: Optional JSON schema for return value validation
            timeout: Timeout in seconds (default: 60)

        Returns:
            Method execution result (type depends on method)

        Raises:
            SessionError: If session doesn't exist
            ProgrammableCallError: If execution fails
            TimeoutError: If execution exceeds timeout
        """
        # Build request payload matching backend ProgrammableCallRequest schema
        payload = {
            "mosaic_id": mosaic_id,
            "node_id": node_id,
            "session_id": session_id,
            "method": method,
            "kwargs": kwargs or {},
            "timeout": timeout
        }
        if instruction is not None:
            payload["instruction"] = instruction
        if return_schema is not None:
            payload["return_schema"] = return_schema

        # Send execute request
        try:
            response = await self.api_client.post(
                "/api/programmable/call",
                json=payload
            )

            # Extract result from SuccessResponse wrapper
            # Response format: {"success": true, "data": {"status": "success", "result": ...}, "message": null}
            data = response.get("data", {})
            status = data.get("status")

            if status == "error":
                error_msg = data.get("error", "Unknown error")
                raise ProgrammableCallError(f"Programmable call failed: {error_msg}")

            if status == "timeout":
                raise ProgrammableCallError(f"Programmable call timed out after {timeout} seconds")

            result = data.get("result")

            # Validate return schema if provided
            if return_schema is not None:
                self._validate_return_schema(result, return_schema)

            return result

        except Exception as e:
            if not isinstance(e, ProgrammableCallError):
                raise ProgrammableCallError(f"Programmable call failed: {str(e)}")
            raise

    async def create_session(self, mosaic_id: int, node_id: str) -> str:
        """
        Create a new session on a node.

        Args:
            mosaic_id: Mosaic identifier (database ID)
            node_id: Node identifier

        Returns:
            Created session ID

        Raises:
            ConnectionError: If mosaic or node doesn't exist
        """
        # Send create session request matching backend CreateSessionRequest schema
        # Backend expects: node_id, mode, model (optional)
        response = await self.api_client.post(
            f"/api/mosaics/{mosaic_id}/sessions",
            json={
                "node_id": node_id,
                "mode": "program",  # Default mode for SDK sessions
            }
        )

        # Extract session_id from SuccessResponse wrapper
        # Response format: {"success": true, "data": {"session_id": "...", ...}, "message": null}
        data = response.get("data", {})
        session_id = data.get("session_id")

        if not session_id:
            raise ProgrammableCallError("Failed to create session: no session_id in response")

        return session_id

    async def close_session(self, mosaic_id: int, session_id: str) -> None:
        """
        Close an existing session.

        Args:
            mosaic_id: Mosaic identifier (database ID)
            session_id: Session ID to close

        Raises:
            SessionError: If session doesn't exist or not active
        """
        # Send close session request (POST, not DELETE)
        await self.api_client.post(f"/api/mosaics/{mosaic_id}/sessions/{session_id}/close")

    def _validate_return_schema(self, result: Any, schema: Dict[str, Any]) -> None:
        """
        Validate result against JSON schema (client-side validation).

        This is optional client-side validation before returning to user.

        Args:
            result: Method execution result
            schema: JSON schema dict

        Raises:
            ProgrammableCallError: If validation fails
        """
        try:
            validate_json_schema(result, schema)
        except Exception as e:
            raise ProgrammableCallError(f"Return value validation failed: {str(e)}")
