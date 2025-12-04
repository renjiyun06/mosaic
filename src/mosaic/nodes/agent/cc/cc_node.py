import uuid
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Dict
from rich.console import Console

import mosaic.core.util as core_util
from mosaic.core.client import MeshClient
from mosaic.core.models import MeshEvent
from mosaic.nodes.agent.base import AgentNode, Session
from mosaic.nodes.agent.types import AgentNodeRunningMode
from mosaic.nodes.agent.cc.hooks import Hook
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

console = Console()

class HookServer:
    def __init__(self, node: 'ClaudeCodeNode'):
        self._node = node
        self._sock_path = core_util.cc_hook_server_sock_path(
            node.mesh_id, node.node_id
        )
        self._sock_server = None

    async def start(self):
        logger.info(
            f"Starting hook server for "
            f"node {self._node.node_id} in mesh {self._node.mesh_id}"
        )
        self._sock_path.parent.mkdir(parents=True, exist_ok=True)
        self._sock_server = await asyncio.start_unix_server(
            self._handle_hook,
            path=str(self._sock_path)
        )
        logger.info(
            f"Hook server for "
            f"node {self._node.node_id} in mesh {self._node.mesh_id} started"
        )

    async def stop(self):
        if self._sock_server:
            self._sock_server.close()
            await self._sock_server.wait_closed()
        self._sock_server = None


    async def _handle_hook(self, reader, writer):
        try:
            length = int.from_bytes(await reader.read(4), "big")
            request_content = (await reader.read(length)).decode("utf-8")
            request = json.loads(request_content)
            
            response = None

            hook_name = request.get("hook_event_name")
            hook_type = Hook.get_hook_type(hook_name)
            hook = hook_type.from_hook_input(request)
            
            logger.info(
                f"Node {self._node.node_id} in mesh {self._node.mesh_id} "
                f"received hook request from session {hook.session_id}: "
                f"{request_content}"
            )
            
            subsriptions = await self._node.client.get_subscriptions(
                self._node.mesh_id,
                self._node.node_id,
                hook.mesh_event_type
            )
            if not subsriptions:
                response = hook_type.default_hook_output()
            else:
                blocking_events = []
                for subscription in subsriptions:
                    mesh_event = hook.to_mesh_event(
                        self._node.mesh_id,
                        self._node.node_id,
                        subscription.target_id
                    )
                    if subscription.is_blocking:
                        blocking_events.append(mesh_event)
                    else:
                        await self._node.client.send(mesh_event)
                
                if blocking_events:
                    reply_events = []
                    for blocking_event in blocking_events:
                        reply_events.append(
                            await self._node.client.send_blocking(
                                blocking_event,
                                timeout=30
                            )
                        )

                    # TODO merge the decisions from the reply events
                else:
                    response = hook_type.default_hook_output()
            
            response_content = json.dumps(response)
            logger.info(
                f"Node {self._node.node_id} in mesh {self._node.mesh_id} "
                f"sending hook response to session {hook.session_id}: "
                f"{response_content}"
            )
            writer.write(len(response_content.encode()).to_bytes(4, "big"))
            writer.write(response_content.encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()


class McpServer:
    def __init__(self, node: 'ClaudeCodeNode'): ...
    async def start(self): ...
    async def stop(self): ...


class ClaudeCodeSession(Session):
    def __init__(
        self, 
        session_id: str, 
        node: 'ClaudeCodeNode', 
    ):
        super().__init__(session_id, node)
      
    async def start(self): ...
    async def close(self): ...
    async def process_event(self, event: MeshEvent): ...
    async def chat(self): ...

    
    async def program(self):
        subprocess.run(
            [
                "claude", "--append-system-prompt", self.node.system_prompt
            ]
        )


class ClaudeCodeNode(AgentNode):
    def __init__(
        self, 
        mesh_id: str, 
        node_id: str, 
        config: Dict[str, str],
        client: MeshClient,
        mode: AgentNodeRunningMode
    ):
        super().__init__(mesh_id, node_id, config, client, mode)

        workspace = config.get("workspace", None)
        if not workspace:
            raise RuntimeError("Workspace is required")
        self._workspace = Path(workspace)
        if not self._workspace.is_absolute():
            raise RuntimeError("Workspace must be an absolute path")
        self._workspace.mkdir(parents=True, exist_ok=True)
        
        self.system_prompt = None
        self._hook_server = None
        self._mcp_server = None
        

    async def create_session(self, mesh_id: str, node_id: str) -> Session:
        return ClaudeCodeSession(str(uuid.uuid4()), self)
    
    async def chat(self):
        await self._chat_session.chat()
        
    async def program(self):
        await self._program_session.program()
    

    async def start_chat_mode(self, session_id: str):
        assert self.mode == AgentNodeRunningMode.CHAT
        self.system_prompt = await self._assemble_system_prompt()
        await self.client.connect()
        await self._start_event_processing_task()
        self._chat_session = ClaudeCodeSession(
            session_id,
            self
        )
        await self._chat_session.start()
        
    
    async def stop_chat_mode(self):
        await self._stop_event_processing_task()
        await self._chat_session.close()
        self._chat_session = None
        await self.client.disconnect()


    async def start_program_mode(self, session_id: str):
        assert self.mode == AgentNodeRunningMode.PROGRAM
        self.system_prompt = await self._assemble_system_prompt()
        await self.client.connect()
        self._program_session = ClaudeCodeSession(
            session_id,
            self
        )
        await self._program_session.start()


    async def stop_program_mode(self):
        await self._program_session.close()
        self._program_session = None
        await self.client.disconnect()

    
    async def _install_settings(self): ...
    async def _uninstall_settings(self): ...


    async def on_start(self):
        self._hook_server = HookServer(self)
        await self._hook_server.start()
        self._mcp_server = McpServer(self)
        await self._mcp_server.start()
        await self._install_settings()

        self.system_prompt = await self._assemble_system_prompt()

    
    async def on_shutdown(self):
        await self._uninstall_settings()
        await self._mcp_server.stop()
        self._mcp_server = None
        await self._hook_server.stop()
        self._hook_server = None

    async def _assemble_system_prompt(self) -> str: ...