"""WebSocket API for session interaction"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..auth import verify_websocket_token
from ..websocket.user_broker import user_broker
from ..services.session_service import SessionService
from ..runtime.manager import RuntimeManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/user")
async def websocket_user_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_session)
):
    """
    User-level WebSocket endpoint for all sessions.

    Protocol:

    Client → Server:
    {
        "session_id": "session-uuid",
        "type": "user_message",
        "message": "your question"
    }
    {
        "session_id": "session-uuid",
        "type": "user_interrupt"
    }

    Server → Client:
    {
        "session_id": "session-uuid",
        "type": "assistant_text",
        "role": "assistant",
        "content": {"message": "response text"},
        "message_id": "uuid",
        "sequence": 10,
        "timestamp": "2025-12-23T12:00:00"
    }
    {
        "session_id": "session-uuid",
        "type": "error",
        "message": "error description"
    }
    """

    # 1. Verify token and get user
    try:
        current_user = await verify_websocket_token(token, db)
    except Exception as e:
        logger.error(f"WebSocket auth failed: {e}")
        await websocket.close(code=4401, reason="Unauthorized")
        return

    # 2. Accept WebSocket connection
    await websocket.accept()
    logger.info(f"User WebSocket accepted for user {current_user.id}")

    # 3. Register connection in user_broker
    await user_broker.connect_user(current_user.id, websocket)

    try:
        # 4. Receive messages from WebSocket and route to sessions
        while True:
            data = await websocket.receive_json()

            session_id = data.get("session_id")
            message_type = data.get("type")

            if not session_id:
                logger.warning(f"Message missing session_id: {data}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Missing session_id in message"
                })
                continue

            # Verify session ownership
            try:
                session = await SessionService.get_session(db, session_id)
                if session.user_id != current_user.id:
                    await websocket.send_json({
                        "session_id": session_id,
                        "type": "error",
                        "message": "Forbidden: session does not belong to user"
                    })
                    continue

                if session.status != "active":
                    await websocket.send_json({
                        "session_id": session_id,
                        "type": "error",
                        "message": f"Session is not active (status: {session.status})"
                    })
                    continue

            except Exception as e:
                logger.error(f"Failed to get session {session_id}: {e}")
                await websocket.send_json({
                    "session_id": session_id,
                    "type": "error",
                    "message": f"Session not found: {session_id}"
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

                # Update session activity
                await SessionService.update_activity(db, session_id)

                # Submit command to RuntimeManager
                runtime_manager = RuntimeManager.get_instance()
                try:
                    runtime_manager.submit_send_message(
                        session_id=session_id,
                        message=user_message,
                        user_id=current_user.id
                    )
                except Exception as e:
                    logger.error(f"Failed to submit message: {e}")
                    await websocket.send_json({
                        "session_id": session_id,
                        "type": "error",
                        "message": str(e)
                    })

            elif message_type == "user_interrupt":
                # Submit interrupt command
                runtime_manager = RuntimeManager.get_instance()
                try:
                    runtime_manager.submit_interrupt_session(
                        session_id=session_id,
                        user_id=current_user.id
                    )
                    logger.info(f"User interrupted session {session_id}")
                except Exception as e:
                    logger.error(f"Failed to submit interrupt: {e}")
                    await websocket.send_json({
                        "session_id": session_id,
                        "type": "error",
                        "message": str(e)
                    })

            else:
                logger.warning(
                    f"Unknown message type from client: {message_type}"
                )
                await websocket.send_json({
                    "session_id": session_id,
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })

    except WebSocketDisconnect:
        logger.info(f"User WebSocket disconnected: user {current_user.id}")
    except Exception as e:
        logger.error(
            f"WebSocket error for user {current_user.id}: {e}",
            exc_info=True
        )
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        # 5. Cleanup
        # Pass websocket to ensure we only disconnect if it's still the registered one
        await user_broker.disconnect_user(current_user.id, websocket)
        logger.info(f"User WebSocket cleanup completed for user {current_user.id}")


@router.websocket("/ws/sessions/{session_id}")
async def websocket_session_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
    db: AsyncSession = Depends(get_session)
):
    """
    WebSocket endpoint for Claude Code session interaction.

    Protocol:

    Client → Server:
    {
        "type": "user_message",
        "message": "your question"
    }
    {
        "type": "user_interrupt"
    }

    Server → Client:
    {
        "type": "assistant_text",
        "role": "assistant",
        "content": {"message": "response text"},
        "message_id": "uuid",
        "sequence": 10,
        "timestamp": "2025-12-23T12:00:00"
    }
    {
        "type": "assistant_result",
        "role": "assistant",
        "content": {
            "message": "result",
            "total_cost_usd": 0.05,
            "total_input_tokens": 1000,
            "total_output_tokens": 500,
            "cost_usd": 0.02,
            "usage": {...}
        },
        "message_id": "uuid",
        "sequence": 11,
        "timestamp": "2025-12-23T12:00:01"
    }
    {
        "type": "error",
        "message": "error description"
    }
    """

    # 1. Verify token and get user
    try:
        current_user = await verify_websocket_token(token, db)
    except Exception as e:
        logger.error(f"WebSocket auth failed: {e}")
        await websocket.close(code=4401, reason="Unauthorized")
        return

    # 2. Get session and verify ownership
    try:
        session = await SessionService.get_session(db, session_id)

        if session.user_id != current_user.id:
            await websocket.close(code=4403, reason="Forbidden")
            return

        if session.status != "active":
            await websocket.close(code=4400, reason="Session is not active")
            return

    except Exception as e:
        logger.error(f"Failed to get session: {e}")
        await websocket.close(code=4404, reason="Session not found")
        return

    # 3. Check node runtime status
    from sqlmodel import select
    from ..models.node import Node
    from ..runtime.manager import RuntimeManager

    try:
        result = await db.execute(
            select(Node).where(
                Node.id == session.node_id,
                Node.deleted_at.is_(None)
            )
        )
        node = result.scalar_one_or_none()
        if not node:
            await websocket.close(code=4404, reason="Node not found")
            return

        runtime_manager = RuntimeManager.get_instance()
        node_status = runtime_manager.get_node_status(session.mosaic_id, node.node_id)

        if node_status != "running":
            await websocket.close(
                code=4400,
                reason=f"Node is not running (status: {node_status})"
            )
            return

    except Exception as e:
        logger.error(f"Failed to check node status: {e}")
        await websocket.close(code=4500, reason="Internal server error")
        return

    # 4. Accept WebSocket connection
    await websocket.accept()
    logger.info(f"WebSocket accepted for session {session_id}")

    # 5. Register connection in manager
    await ws_manager.connect(session_id, websocket)

    try:
        # 6. Get or create runtime Claude Code session
        runtime_manager = RuntimeManager.get_instance()

        claude_session = await runtime_manager.get_or_create_claude_session(
            mosaic_id=session.mosaic_id,
            node_id=session.node_id,
            session_id=session_id,
            config=session.config or {},
            # Direct callback to WebSocket manager
            on_message=lambda msg: ws_manager.send_message(session_id, msg)
        )

        logger.info(
            f"Claude session ready for WebSocket: "
            f"mosaic={session.mosaic_id}, node={session.node_id}, "
            f"session={session_id}"
        )

        # 7. Receive messages from WebSocket and process
        while True:
            data = await websocket.receive_json()

            if data["type"] == "user_message":
                user_message = data["message"]

                # Update session activity
                await SessionService.update_activity(db, session_id)

                # Send to Claude Code session (async, non-blocking)
                # Note: User message will be saved to database by ClaudeCodeSession
                # in _send_to_websocket() to ensure consistent sequence numbering
                await claude_session.send_user_message(user_message)

            elif data["type"] == "user_interrupt":
                # Interrupt Claude Code session
                await claude_session.interrupt()
                logger.info(f"User interrupted session {session_id}")

            else:
                logger.warning(
                    f"Unknown message type from client: {data.get('type')}"
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(
            f"WebSocket error for session {session_id}: {e}",
            exc_info=True
        )
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        # 8. Cleanup
        await ws_manager.disconnect(session_id)
        logger.info(f"WebSocket cleanup completed for session {session_id}")
