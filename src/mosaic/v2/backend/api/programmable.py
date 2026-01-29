"""Programmable call API endpoints

This module provides the programmable call interface that allows external scripts/systems
to invoke nodes with structured method calls, enabling:
- Deterministic workflow orchestration
- Parallel agent collaboration
- External system integration
- Programmatic node control

Architecture:
- SDK makes HTTP POST to /programmable/call with structured request
- Backend validates request (auth, mosaic ownership, session status)
- Backend calls runtime_manager.execute_programmable_call()
- Runtime layer handles event dispatch and response waiting
- Backend returns structured response to SDK

Key features:
- Session management (SDK creates sessions via /session API)
- Timeout handling
- Structured input/output via JSON schemas
"""

import logging
import time
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..schema.response import SuccessResponse
from ..schema.programmable import (
    ProgrammableCallRequest,
    ProgrammableCallResponse,
    CallStatus,
)
from ..model import User, Mosaic, Node, Session
from ..dep import get_db_session, get_current_user
from ..exception import (
    NotFoundError,
    ValidationError,
    PermissionError as PermissionDeniedError,
)
from ..exception import (
    RuntimeTimeoutError,
    RuntimeInternalError,
    MosaicNotRunningError,
    NodeNotFoundError,
)
from ..enum import SessionStatus

logger = logging.getLogger(__name__)


# ==================== Router Configuration ====================

router = APIRouter(
    prefix="/programmable",
    tags=["Programmable Call"]
)


# ==================== Type Aliases ====================

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ==================== API Endpoints ====================

@router.post(
    "/call",
    response_model=SuccessResponse[ProgrammableCallResponse],
    summary="Execute programmable call to a node",
    description="""
    Execute a programmable call to a node in the event mesh.

    **What is Programmable Call?**

    Programmable Call allows scripts/systems to invoke nodes with structured method calls,
    combining the deterministic nature of programming with the cognitive abilities of AI agents.

    **Use Cases:**
    - 🔄 Deterministic workflow orchestration (multi-step data pipelines)
    - ⚡ Parallel agent collaboration (multiple experts working simultaneously)
    - 🔌 External system integration (cron jobs, monitoring, CI/CD)
    - 🎯 Conditional branching and dynamic routing (program logic + AI judgment)
    - 📊 Long-term project tracking (session continuity across days/weeks)
    - 🧪 A/B testing and model comparison

    **Request Flow:**
    1. Client sends ProgrammableCallRequest (mosaic_id, node_id, session_id, method, kwargs, etc.)
    2. Backend validates request (auth, mosaic ownership, session status)
    3. Backend calls runtime_manager.execute_programmable_call()
    4. Runtime layer dispatches event and waits for response
    5. Backend returns ProgrammableCallResponse to client

    **Session Management:**
    - session_id is **required** and must be pre-created via `/session` API
    - Session must be in ACTIVE status
    - SDK is responsible for creating and managing session lifecycle
    - Multiple calls can reuse the same session for context continuity

    **Timeout Handling:**
    - Default: 60 seconds (configurable 1-600s)
    - If timeout exceeded, returns status="timeout"
    - Node may still be processing (timeout is client-side)

    **Parameter Types:**
    - Only keyword arguments (kwargs) supported (no positional args)
    - Only JSON-serializable types: str, int, float, bool, None, list, dict
    - Argument names should be semantic (e.g., 'user_data', 'threshold')

    **Return Schema:**
    - Optional JSON Schema (Draft 7) to guide return value structure
    - Node attempts to format response according to schema

    **Authentication:**
    Requires JWT token in Authorization header:
    ```
    Authorization: Bearer <token>
    ```

    **Returns:**
    - success: true
    - data: ProgrammableCallResponse (status, result, session_id, call_id, execution_time_ms)
    - message: null

    **Errors:**
    - 200 + success=false + NOT_FOUND: Mosaic, node, or session not found
    - 200 + success=false + VALIDATION_ERROR: Invalid request or session not ACTIVE
    - 200 + success=false + RUNTIME_ERROR: Runtime execution error or timeout
    - 200 + success=false + AUTHENTICATION_ERROR: Invalid or expired token

    **Example Request:**
    ```json
    {
      "mosaic_id": 1,
      "node_id": "analyst",
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "method": "analyze_user_behavior",
      "instruction": "Analyze user behavior and assess risk level",
      "kwargs": {
        "user_data": {"user_id": 123, "events": [...]},
        "threshold": 0.95
      },
      "return_schema": {
        "type": "object",
        "required": ["score", "risk_level"],
        "properties": {
          "score": {"type": "number", "minimum": 0, "maximum": 100},
          "risk_level": {"type": "string", "enum": ["low", "medium", "high"]}
        }
      },
      "timeout": 120
    }
    ```

    **Example Response:**
    ```json
    {
      "success": true,
      "data": {
        "status": "success",
        "result": {
          "score": 75,
          "risk_level": "medium",
          "details": "User shows moderate risk patterns"
        },
        "error": null,
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "call_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "execution_time_ms": 1523
      },
      "message": null
    }
    ```
    """
)
async def programmable_call(
    request: ProgrammableCallRequest,
    req: Request,
    db_session: SessionDep,
    current_user: CurrentUserDep,
):
    """Execute programmable call to a node

    Business Logic:
    1. Validate authentication (via dependency injection)
    2. Verify mosaic exists and belongs to current user
    3. Verify node exists in the mosaic
    4. Validate session exists, is ACTIVE, and belongs to user/node
    5. Generate unique call_id (UUID)
    6. Track start time
    7. Call runtime_manager.execute_programmable_call()
    8. Calculate execution time
    9. Return ProgrammableCallResponse

    Args:
        request: Programmable call request (validated via Pydantic)
        req: FastAPI request object (to access app state: runtime_manager)
        db_session: Database session (injected via dependency)
        current_user: Authenticated user (injected via JWT dependency)

    Returns:
        SuccessResponse[ProgrammableCallResponse]: Call result with metadata

    Raises:
        NotFoundError: Mosaic, node, or session not found
        ValidationError: Invalid session status (not ACTIVE)
        RuntimeTimeoutError: Call exceeded timeout limit
        RuntimeInternalError: Runtime execution error
    """
    logger.info(
        f"Programmable call request: mosaic_id={request.mosaic_id}, "
        f"node_id={request.node_id}, session_id={request.session_id}, "
        f"method={request.method}, user_id={current_user.id}"
    )

    # 1. Verify mosaic exists and belongs to current user
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == request.mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await db_session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={request.mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={request.mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionDeniedError("You do not have permission to access this mosaic")

    # 2. Verify node exists in the mosaic
    node_stmt = select(Node).where(
        Node.mosaic_id == request.mosaic_id,
        Node.node_id == request.node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await db_session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(
            f"Node not found: mosaic_id={request.mosaic_id}, node_id={request.node_id}"
        )
        raise NotFoundError(f"Node '{request.node_id}' not found in mosaic")

    # 3. Validate session exists, is ACTIVE, and belongs to user/node
    session_obj = await validate_session_ownership(
        db_session=db_session,
        session_id=request.session_id,
        mosaic_id=request.mosaic_id,
        node_id=request.node_id,
        user_id=current_user.id
    )

    # 4. Generate unique call_id
    call_id = str(uuid4())

    logger.info(
        f"Executing programmable call: call_id={call_id}, "
        f"session_id={request.session_id}, method={request.method}"
    )

    # 5. Track start time
    start_time = time.time()

    try:
        # 6. Call runtime_manager.execute_programmable_call()
        runtime_manager = req.app.state.runtime_manager

        result = await runtime_manager.execute_programmable_call(
            node=node,
            session=session_obj,
            call_id=call_id,
            method=request.method,
            instruction=request.instruction,
            kwargs=request.kwargs,
            return_schema=request.return_schema,
            timeout=float(request.timeout)
        )

        # 7. Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Programmable call succeeded: call_id={call_id}, "
            f"execution_time_ms={execution_time_ms}"
        )

        # 8. Return success response
        return SuccessResponse(
            data=ProgrammableCallResponse(
                status=CallStatus.SUCCESS,
                result=result,
                error=None,
                session_id=request.session_id,
                call_id=call_id,
                execution_time_ms=execution_time_ms
            )
        )

    except RuntimeTimeoutError as e:
        # Timeout occurred
        execution_time_ms = int((time.time() - start_time) * 1000)
        logger.error(
            f"Programmable call timeout: call_id={call_id}, "
            f"execution_time_ms={execution_time_ms}, error={str(e)}"
        )

        return SuccessResponse(
            data=ProgrammableCallResponse(
                status=CallStatus.TIMEOUT,
                result=None,
                error=f"Call timed out after {request.timeout} seconds",
                session_id=request.session_id,
                call_id=call_id,
                execution_time_ms=execution_time_ms
            )
        )

    except (RuntimeInternalError, MosaicNotRunningError, NodeNotFoundError) as e:
        # Runtime error
        execution_time_ms = int((time.time() - start_time) * 1000)
        logger.error(
            f"Programmable call runtime error: call_id={call_id}, "
            f"execution_time_ms={execution_time_ms}, error={str(e)}"
        )

        return SuccessResponse(
            data=ProgrammableCallResponse(
                status=CallStatus.ERROR,
                result=None,
                error=str(e),
                session_id=request.session_id,
                call_id=call_id,
                execution_time_ms=execution_time_ms
            )
        )

    except Exception as e:
        # Unexpected error
        execution_time_ms = int((time.time() - start_time) * 1000)
        logger.exception(
            f"Programmable call unexpected error: call_id={call_id}, "
            f"execution_time_ms={execution_time_ms}, error={str(e)}"
        )

        return SuccessResponse(
            data=ProgrammableCallResponse(
                status=CallStatus.ERROR,
                result=None,
                error=f"Internal error: {str(e)}",
                session_id=request.session_id,
                call_id=call_id,
                execution_time_ms=execution_time_ms
            )
        )


# ==================== Helper Functions ====================

async def validate_session_ownership(
    db_session: AsyncSession,
    session_id: str,
    mosaic_id: int,
    node_id: str,
    user_id: int
) -> Session:
    """Validate that session exists, is ACTIVE, and belongs to user

    Implementation Logic:
    1. Query Session table with all required conditions
    2. If not found or status != ACTIVE: raise error
    3. Return Session object if valid

    Args:
        db_session: Database session
        session_id: Session ID to validate
        mosaic_id: Expected mosaic ID
        node_id: Expected node ID
        user_id: Expected user ID

    Returns:
        Session object if valid

    Raises:
        NotFoundError: Session not found
        ValidationError: Session is not in ACTIVE status
    """
    logger.debug(
        f"Validating session: session_id={session_id}, "
        f"mosaic_id={mosaic_id}, node_id={node_id}, user_id={user_id}"
    )

    # Query session with all required conditions
    session_stmt = select(Session).where(
        Session.session_id == session_id,
        Session.mosaic_id == mosaic_id,
        Session.user_id == user_id,
        Session.deleted_at.is_(None)
    )
    session_result = await db_session.execute(session_stmt)
    session_obj = session_result.scalar_one_or_none()

    if not session_obj:
        logger.warning(
            f"Session not found or access denied: session_id={session_id}, "
            f"mosaic_id={mosaic_id}, user_id={user_id}"
        )
        raise NotFoundError("Session not found or you do not have access to it")

    # Verify session belongs to the specified node
    # Query the node to get its database ID
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await db_session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(f"Node not found: mosaic_id={mosaic_id}, node_id={node_id}")
        raise NotFoundError(f"Node '{node_id}' not found")

    # Verify session is ACTIVE
    if session_obj.status != SessionStatus.ACTIVE:
        logger.warning(
            f"Session is not active: session_id={session_id}, "
            f"status={session_obj.status}"
        )
        raise ValidationError(
            f"Session is not active (status: {session_obj.status}). "
            f"Only ACTIVE sessions can be used for programmable calls."
        )

    logger.debug(f"Session validation successful: session_id={session_id}")
    return session_obj
