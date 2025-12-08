import asyncio
import uuid
import json
from fastmcp import FastMCP
from typing import Literal, Optional, Dict, Any, Annotated
from datetime import datetime

import mosaic.core.util as core_util
from mosaic.core.events import get_event_definition
from mosaic.core.models import MeshEvent, SessionTrace
from mosaic.nodes.agent.base import AgentNode
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class McpRequestServer:
    def __init__(self, node: AgentNode):
        self._node = node
        self._sock_path = core_util.mcp_request_server_sock_path(
            node.mesh_id, node.node_id
        )
        self._sock_server = None

    async def start(self):
        logger.info(
            f"Starting MCP request server for node {self._node.node_id} in mesh "
            f"{self._node.mesh_id}"
        )
        self._sock_path.parent.mkdir(parents=True, exist_ok=True)
        self._sock_server = await asyncio.start_unix_server(
            self._handle_mcp_request,
            path=str(self._sock_path)
        )
        logger.info(
            f"MCP request server for node {self._node.node_id} in mesh "
            f"{self._node.mesh_id} started"
        )

    async def stop(self): 
        if self._sock_server:
            self._sock_server.close()
            await self._sock_server.wait_closed()
        self._sock_server = None


    async def _handle_mcp_request(self, reader, writer):
        async def handle_request(request: Dict[str, Any]) -> Dict[str, Any]:
            mesh_id = request.get("mesh_id")
            node_id = request.get("node_id")
            session_id = request.get("session_id")
            target_node_id = request.get("target_node_id")
            reply_to = request.get("reply_to")
            type = request.get("type")
            target_event = None
            if reply_to:
                target_event: Optional[MeshEvent] = await self._node.client.get_event(
                    event_id = reply_to
                )
                if not target_event:
                    return {
                        "is_error": True,
                        "error_message": f"The Event {reply_to} you "
                                         f"replied to does not exist"
                    }

                if target_event.source_id != target_node_id:
                    return {
                        "is_error": True,
                        "error_message": f"The Event {reply_to} you replied to "
                                         f"is not from the target node "
                                         f"{target_node_id}"
                    }

            mesh_event: MeshEvent = None
            if type == "respond_to_cc_pre_tool_use":
                ...
            elif type == "respond_to_cc_user_prompt_submit": ...
            elif type == "send_message":
                event_definition = get_event_definition("mosaic.node_message")
                message_type = request.get("message_type")
                if message_type == "reply" and not reply_to:
                    return {
                        "is_error": True,
                        "error_message": "The message type is reply but "
                                         "the reply_to is not provided"
                    }
                mesh_event = event_definition.to_mesh_event(
                    event_id=str(uuid.uuid4()),
                    mesh_id=mesh_id,
                    source_id=node_id,
                    target_id=target_node_id,
                    payload={"message": request.get("message")},
                    session_trace=SessionTrace(
                        upstream_session_id=session_id,
                        downstream_session_id=target_event.session_trace.\
                            upstream_session_id if target_event else None
                    ),
                    reply_to=reply_to,
                    created_at=datetime.now(),
                )
            else:
                raise RuntimeError(f"Unknown MCP request type: {type}")

            await self._node.client.send(mesh_event)
            return {
                "is_error": False
            }


        try:
            length = int.from_bytes(await reader.readexactly(4), "big")
            request_content = (await reader.readexactly(length)).decode("utf-8")
            logger.info(
                f"Received MCP request for node "
                f"{self._node.node_id} in mesh {self._node.mesh_id} with input: "
                f"{request_content}"
            )
            request = json.loads(request_content)
            try:
                response = await handle_request(request)
            except Exception as e:
                import traceback
                logger.error(
                    f"Error handling MCP request: {e}\n{traceback.format_exc()}"
                )
                response = {
                    "is_error": True,
                    "error_message": str(e)
                }
            response_content = json.dumps(response, ensure_ascii=False).encode()
            writer.write(len(response_content).to_bytes(4, "big"))
            writer.write(response_content)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()


mcp = FastMCP("mosaic-mcp-server")

async def _send_mcp_request(
    mesh_id: str,
    node_id: str,
    session_id: str,
    request: Dict[str, Any]
) -> Dict[str, Any]:
    sock_path = core_util.mcp_request_server_sock_path(mesh_id, node_id)
    if not sock_path.exists():
        raise RuntimeError(
            f"MCP request server socket path {sock_path} does not exist"
        )
    reader, writer = await asyncio.open_unix_connection(str(sock_path))
    try:
        request_content = json.dumps(request, ensure_ascii=False)
        logger.info(
            f"Sending MCP request for session {session_id} of "
            f"node {node_id} in mesh {mesh_id}: {request_content}"
        )
        request_content_bytes = request_content.encode()
        writer.write(len(request_content_bytes).to_bytes(4, "big"))
        writer.write(request_content_bytes)
        await writer.drain()
        length = int.from_bytes(await reader.readexactly(4), "big")
        response_content = await reader.readexactly(length)
        response = response_content.decode("utf-8")
        logger.info(
            f"Received MCP response for session {session_id} of "
            f"node {node_id} in mesh {mesh_id}: {response}"
        )
        return json.loads(response)
    except Exception as e:
        import traceback
        logger.error(
            f"Error sending MCP request: {e}\n{traceback.format_exc()}"
        )
        return {
            "is_error": True,
            "error_message": str(e)
        }
    finally:
        writer.close()
        await writer.wait_closed()


@mcp.tool
async def respond_to_cc_pre_tool_use(
    mesh_id: Annotated[str, "The mesh ID of the responder"],
    node_id: Annotated[str, "The node ID of the responder"],
    session_id: Annotated[str, "The session ID of the responder"],
    target_node_id: Annotated[
        str, 
        "the node ID of the target node that sent the cc.pre_tool_use event"
    ],
    reply_to: Annotated[str, "The event ID to reply to"],
    permission_decision: Literal["allow", "deny"],
    permission_decision_reason: Optional[str] = None,
) -> Dict[str, Any]:
    request = {
        "type": "respond_to_cc_pre_tool_use",
        "mesh_id": mesh_id,
        "node_id": node_id,
        "session_id": session_id,
        "target_node_id": target_node_id,
        "reply_to": reply_to,
        "permission_decision": permission_decision,
        "permission_decision_reason": permission_decision_reason,
    }
    return await _send_mcp_request(mesh_id, node_id, session_id, request)


@mcp.tool
async def respond_to_cc_user_prompt_submit(
    mesh_id: Annotated[str, "The mesh ID of the responder"],
    node_id: Annotated[str, "The node ID of the responder"],
    session_id: Annotated[str, "The session ID of the responder"],
    target_node_id: Annotated[
        str, 
        "the node ID of the target node that sent the cc.user_prompt_submit event"
    ],
    reply_to: Annotated[str, "The event ID to reply to"],
    decision: Annotated[
        Literal["block", "continue"], 
        "The decision to make: block the user prompt or continue"
    ],
    reason: Annotated[Optional[str], "The reason for the decision"] = None,
    additional_context: Annotated[
        Optional[str], 
        "Additional context for the target node to consider"
    ] = None
) -> Dict[str, Any]:
    request = {
        "type": "respond_to_cc_user_prompt_submit",
        "mesh_id": mesh_id,
        "node_id": node_id,
        "session_id": session_id,
        "target_node_id": target_node_id,
        "reply_to": reply_to,
        "decision": decision,
        "reason": reason,
        "additional_context": additional_context,
    }
    return await _send_mcp_request(mesh_id, node_id, session_id, request)


@mcp.tool
async def send_message(
    mesh_id: Annotated[str, "The mesh ID of the sender"],
    node_id: Annotated[str, "The node ID of the sender"],
    session_id: Annotated[str, "The session ID of the sender"],
    target_node_id: Annotated[str, "The node ID of the receiver"],
    message_type: Annotated[
        Literal["reply", "send"], 
        "The type of the message: reply or send"
    ],
    message: str,
    reply_to: Annotated[
        Optional[str], 
        "The event/message ID to reply to"
    ] = None
) -> Dict[str, Any]:
    logger.info(
        f"Sending message from node {node_id} in mesh {mesh_id} for session "
        f"{session_id} to node {target_node_id} with message type: {message_type} "
        f"and message: {message}"
    )
    request = {
        "type": "send_message",
        "mesh_id": mesh_id,
        "node_id": node_id,
        "session_id": session_id,
        "target_node_id": target_node_id,
        "message_type": message_type,
        "message": message,
        "reply_to": reply_to
    }
    return await _send_mcp_request(mesh_id, node_id, session_id, request)

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)