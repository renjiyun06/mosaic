from fastmcp import FastMCP
from typing import Literal, Optional, Dict, Any

from mosaic.core.models import MeshEvent
from mosaic.core.client import MeshClient
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

mcp = FastMCP("mosaic-mcp-server")

@mcp.tool
async def response_to_cc_pre_tool_use(
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


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)