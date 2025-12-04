import asyncio
import argparse
import json
import sys
from typing import Dict, Any

import mosaic.core.util as core_util
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

async def _get_hook_input() -> Dict[str, Any]:
    return json.loads(sys.stdin.read().strip())

async def main(mesh_id: str, node_id: str):
    hook_server_sock = core_util.cc_hook_server_sock_path(mesh_id, node_id)
    if not hook_server_sock.exists():
        logger.error(
            f"Hook server socket path {hook_server_sock} does not exist"
        )
        raise RuntimeError(
            f"Hook server socket path {hook_server_sock} does not exist"
        )
    
    async with asyncio.open_unix_connection(
        str(hook_server_sock)
    ) as (reader, writer):
        try:
            request = await _get_hook_input()
            session_id = request.get("session_id")
            request_content = json.dumps(request)
            logger.info(
                f"Session {session_id} of node {node_id} in mesh {mesh_id} "
                f"triggered {request.get('hook_event_name')} hook with input: "
                f"{request_content}"
            )
            writer.write(len(request_content.encode()).to_bytes(4, "big"))
            writer.write(request_content)
            await writer.drain()
            length = int.from_bytes(await reader.read(4), "big")
            response_content = await reader.read(length)
            response = response_content.decode("utf-8")
            print(response)
        finally:
            writer.close()
            await writer.wait_closed()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-id", type=str, required=True)
    parser.add_argument("--node-id", type=str, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.mesh_id, args.node_id))