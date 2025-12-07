import asyncio
from fastmcp import FastMCP
from typing import Literal, Optional, Dict, Any

import mosaic.core.util as core_util
from mosaic.core.models import MeshEvent
from mosaic.core.client import MeshClient
from mosaic.nodes.agent.base import AgentNode
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class McpRequestServer:
    def __init__(self, node: AgentNode):
        self._node = node
        self._sock_path = core_util.mcp_server_sock_path(
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


    async def _handle_mcp_request(self, reader, writer): ...

mcp = FastMCP("mosaic-mcp-server")

@mcp.tool
async def respond_to_cc_pre_tool_use(
    mesh_id: str,
    node_id: str,
    session_id: str,
    permission_decision: Literal["allow", "deny", "ask"],
    permission_decision_reason: Optional[str] = None,
) -> Dict[str, Any]: ...


@mcp.tool
async def respond_to_cc_user_prompt_submit(
    mesh_id: str,
    node_id: str,
    session_id: str,
    decision: Literal["block", "continue"],
    reason: Optional[str] = None,
    additional_context: Optional[str] = None
) -> Dict[str, Any]: ...


@mcp.tool
async def send_message(
    mesh_id: str,
    node_id: str,
    session_id: str,
    message: str
) -> Dict[str, Any]: ...


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)