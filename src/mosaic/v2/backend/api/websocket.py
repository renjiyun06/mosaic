"""WebSocket API for session interaction"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select

from ..model import Session
from ..security import verify_token_and_get_user
from ..exception import AuthenticationError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/user")
async def websocket_user_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token")
):
    """
    User-level WebSocket endpoint for all sessions.

    This is the single WebSocket connection per user that handles all session
    interactions. Messages are routed by session_id in the message payload.

    Connection Establishment:
    1. Client provides JWT token in query parameter: /ws/user?token=xxx
    2. Server verifies token and extracts user_id
    3. Server accepts WebSocket connection
    4. Server registers connection in UserMessageBroker

    Client → Server Message Format:
    {
        "session_id": "session-uuid",
        "type": "user_message",
        "message": "user input text"
    }
    {
        "session_id": "session-uuid",
        "type": "interrupt"
    }

    Server → Client Message Format:
    {
        "session_id": "session-uuid",
        "role": "user" | "assistant" | "system",
        "message_type": "user_message" | "assistant_text" | "assistant_thinking" | ...,
        "message_id": "uuid",
        "sequence": 10,
        "timestamp": "2025-12-31T10:00:00Z",
        "payload": { ... }
    }

    Error Response Format:
    {
        "session_id": "session-uuid",  # Optional, may be null
        "type": "error",
        "message": "error description"
    }

    Args:
        websocket: WebSocket connection
        token: JWT token from query parameter
    """
    # 1. Get dependencies from app state
    async_session_factory = websocket.app.state.async_session_factory
    user_message_broker = websocket.app.state.user_message_broker
    runtime_manager = websocket.app.state.runtime_manager
    jwt_config = websocket.app.state.config.get("jwt", {})

    # 2. Verify token and get user
    try:
        # Verify token (reuse shared logic from security module)
        async with async_session_factory() as session:
            current_user = await verify_token_and_get_user(token, jwt_config, session)
    except AuthenticationError as e:
        logger.warning(f"WebSocket auth failed: {e.message}")
        await websocket.close(code=4401, reason="Unauthorized")
        return
    except Exception as e:
        logger.error(f"WebSocket auth error: {e}", exc_info=True)
        await websocket.close(code=4500, reason="Internal error")
        return

    # 3. Accept WebSocket connection
    await websocket.accept()
    logger.info(f"User WebSocket accepted for user {current_user.id} ({current_user.email})")

    # 4. Register connection in UserMessageBroker
    await user_message_broker.connect_user(current_user.id, websocket)

    try:
        # 5. Receive messages from WebSocket and route to sessions
        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                logger.info(f"User {current_user.id} WebSocket disconnected normally")
                break
            except Exception as e:
                logger.error(f"Error receiving WebSocket message: {e}", exc_info=True)
                break

            session_id = data.get("session_id")
            message_type = data.get("type")

            if not session_id:
                logger.warning(f"Message missing session_id from user {current_user.id}: {data}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Missing session_id in message"
                })
                continue

            # Verify session ownership and status
            try:
                async with async_session_factory() as db_session:
                    stmt = select(Session).where(Session.session_id == session_id)
                    result = await db_session.execute(stmt)
                    session = result.scalar_one_or_none()

                    if not session:
                        await websocket.send_json({
                            "session_id": session_id,
                            "type": "error",
                            "message": "Session not found"
                        })
                        continue

                    if session.user_id != current_user.id:
                        await websocket.send_json({
                            "session_id": session_id,
                            "type": "error",
                            "message": "Forbidden: session does not belong to user"
                        })
                        continue

                    # Get node information (exclude soft-deleted nodes)
                    from ..model.node import Node
                    stmt = select(Node).where(
                        Node.mosaic_id == session.mosaic_id,
                        Node.node_id == session.node_id,
                        Node.deleted_at.is_(None)
                    )
                    result = await db_session.execute(stmt)
                    node = result.scalar_one_or_none()

                    if not node:
                        await websocket.send_json({
                            "session_id": session_id,
                            "type": "error",
                            "message": "Node not found or deleted"
                        })
                        continue

            except Exception as e:
                logger.error(f"Failed to verify session {session_id}: {e}", exc_info=True)
                await websocket.send_json({
                    "session_id": session_id,
                    "type": "error",
                    "message": "Internal error verifying session"
                })
                continue

            # Route message based on type
            if message_type == "user_message":
                user_message = data.get("message")
                if not user_message:
                    await websocket.send_json({
                        "session_id": session_id,
                        "type": "error",
                        "message": "Missing message content"
                    })
                    continue

                # Extract optional context (e.g., GeoGebra states)
                context = data.get("context")

                # Submit command to RuntimeManager (non-blocking)
                try:
                    runtime_manager.submit_send_message(
                        node=node,
                        session=session,
                        message=user_message,
                        context=context
                    )
                    logger.debug(
                        f"User message submitted: session_id={session_id}, "
                        f"user_id={current_user.id}, message_length={len(user_message)}"
                    )
                except Exception as e:
                    logger.error(f"Failed to submit message: {e}", exc_info=True)
                    await websocket.send_json({
                        "session_id": session_id,
                        "type": "error",
                        "message": f"Failed to send message: {str(e)}"
                    })

            elif message_type == "interrupt":
                # Submit interrupt command
                try:
                    await runtime_manager.interrupt_session(node=node, session=session)
                    logger.info(f"Session interrupted: session_id={session_id}")
                except Exception as e:
                    logger.error(f"Failed to interrupt session: {e}", exc_info=True)
                    await websocket.send_json({
                        "session_id": session_id,
                        "type": "error",
                        "message": f"Failed to interrupt: {str(e)}"
                    })

            elif message_type == "terminal_start":
                # Start terminal session
                try:
                    # Build workspace path
                    instance_path = websocket.app.state.instance_path
                    workspace_path = instance_path / "users" / str(current_user.id) / str(node.mosaic_id) / str(node.id)

                    await runtime_manager.start_terminal(
                        node=node,
                        session=session,
                        user_id=current_user.id,
                        workspace_path=workspace_path
                    )
                    logger.info(f"Terminal started: session_id={session_id}")
                except Exception as e:
                    logger.error(f"Failed to start terminal: {e}", exc_info=True)
                    await websocket.send_json({
                        "session_id": session_id,
                        "type": "error",
                        "message": f"Failed to start terminal: {str(e)}"
                    })

            elif message_type == "terminal_input":
                # Send terminal input
                terminal_data = data.get("data")
                if terminal_data is None:
                    await websocket.send_json({
                        "session_id": session_id,
                        "type": "error",
                        "message": "Missing terminal data"
                    })
                    continue

                try:
                    await runtime_manager.send_terminal_input(
                        session=session,
                        data=terminal_data
                    )
                except Exception as e:
                    logger.error(f"Failed to send terminal input: {e}", exc_info=True)
                    await websocket.send_json({
                        "session_id": session_id,
                        "type": "error",
                        "message": f"Failed to send terminal input: {str(e)}"
                    })

            elif message_type == "terminal_resize":
                # Resize terminal
                cols = data.get("cols")
                rows = data.get("rows")
                if cols is None or rows is None:
                    await websocket.send_json({
                        "session_id": session_id,
                        "type": "error",
                        "message": "Missing cols or rows"
                    })
                    continue

                try:
                    await runtime_manager.resize_terminal(
                        session=session,
                        cols=cols,
                        rows=rows
                    )
                except Exception as e:
                    logger.error(f"Failed to resize terminal: {e}", exc_info=True)
                    # Don't send error to client for resize failures (non-critical)

            elif message_type == "terminal_stop":
                # Stop terminal
                try:
                    await runtime_manager.stop_terminal(session=session)
                    logger.info(f"Terminal stopped: session_id={session_id}")
                except Exception as e:
                    logger.error(f"Failed to stop terminal: {e}", exc_info=True)
                    # Don't send error to client for stop failures (session may be closing)

            elif message_type == "tool_response":
                # Handle tool response from frontend (e.g., GeoGebra execution result)
                response_id = data.get("response_id")
                result = data.get("result")

                if not response_id:
                    await websocket.send_json({
                        "session_id": session_id,
                        "type": "error",
                        "message": "Missing response_id in tool_response"
                    })
                    continue

                # Submit tool response handling (non-blocking)
                try:
                    runtime_manager.submit_tool_response(
                        node=node,
                        session=session,
                        response_id=response_id,
                        result=result
                    )
                    logger.debug(
                        f"Tool response submitted: session_id={session_id}, "
                        f"response_id={response_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to submit tool response: {e}", exc_info=True)
                    await websocket.send_json({
                        "session_id": session_id,
                        "type": "error",
                        "message": f"Failed to handle tool response: {str(e)}"
                    })

            else:
                logger.warning(f"Unknown message type from user {current_user.id}: {message_type}")
                await websocket.send_json({
                    "session_id": session_id,
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })

    except Exception as e:
        logger.error(
            f"Unexpected error in WebSocket connection for user {current_user.id}: {e}",
            exc_info=True
        )
    finally:
        # 6. Cleanup: Disconnect from UserMessageBroker
        await user_message_broker.disconnect_user(current_user.id, websocket)
        logger.info(f"User {current_user.id} WebSocket connection closed")
