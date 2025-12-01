import asyncio
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any

from mosaic.core.types import MeshID, NodeID, AgentRunningMode, ClaudeCodeHook
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

async def _get_hook_input() -> Dict[str, Any]:
    return json.loads(sys.stdin.read().strip())

def get_hook_server_sock_path(mesh_id: MeshID, node_id: NodeID, session_id: str) -> Path:
    return Path.home() / ".mosaic" / mesh_id / "sockets" / "cc_hook_server" / f"{node_id}.{session_id}.sock"

async def main(mesh_id: MeshID, node_id: NodeID, mode: AgentRunningMode, hook: ClaudeCodeHook):
    hook_input = await _get_hook_input()
    hook_event_name = hook_input["hook_event_name"]
    logger.info(f"Node {node_id} for mesh {mesh_id} triggered {hook_event_name} hook with input: {json.dumps(hook_input)}")
    session_id = hook_input.get("session_id")
    sock_path = get_hook_server_sock_path(mesh_id, node_id, session_id)
    if not sock_path.exists():
        logger.error(f"Hook server socket path {sock_path} does not exist")
        return
    async with asyncio.open_unix_connection(str(sock_path)) as (reader, writer):
        request = {
            "mode": mode,
            "name": hook_event_name,
            "input": hook_input
        }
        request_content = json.dumps(request).encode()
        writer.write(len(request_content).to_bytes(4, "big"))
        writer.write(request_content)
        await writer.drain()
        length = int.from_bytes(await reader.read(4), "big")
        response_content = await reader.read(length)
        response = response_content.decode("utf-8")
        logger.info(f"Node {node_id} for mesh {mesh_id} received response: {response} for hook {hook_event_name} with input: {json.dumps(hook_input)}")
        print(response)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-id", type=str, required=True)
    parser.add_argument("--node-id", type=str, required=True)
    parser.add_argument("--mode", type=str, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.mesh_id, args.node_id, args.mode, args.hook))