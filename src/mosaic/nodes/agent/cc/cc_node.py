import os
import subprocess
import uuid
import asyncio
import json
from pathlib import Path
from typing import Dict, Any
from rich.console import Console
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    ResultMessage
)
from prompt_toolkit.shortcuts import PromptSession

from mosaic.nodes.agent.base import AgentNode, Session
from mosaic.core.types import AgentRunningMode, MeshID, NodeID, TransportType
from mosaic.core.models import MeshEvent
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

console = Console()

class HookServer:
    def __init__(self, session: 'ClaudeCodeSession'):
        self._session = session
        self._sock_path = Path.home() / ".mosaic" / session.node.mesh_id / "sockets" / "cc_hook_server" / f"{session.node.node_id}.{session.session_id}.sock"
        self._server = None

    async def start(self):
        if self._sock_path.exists():
            os.unlink(self._sock_path)
        self._sock_path.parent.mkdir(parents=True, exist_ok=True)
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(self._sock_path)
        )


    async def _handle_client(self, reader, writer):
        length = int.from_bytes(await reader.read(4), "big")
        request_content = await reader.read(length)
        request = json.loads(request_content.decode("utf-8"))
        response = await self._session.process_hook_event(request)
        response_content = json.dumps(response).encode()
        writer.write(len(response_content).to_bytes(4, "big"))
        writer.write(response_content)
        await writer.drain()

    
    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            if self._sock_path.exists():
                os.unlink(self._sock_path)
        self._server = None


class ClaudeCodeSession(Session):
    def __init__(self, node: 'ClaudeCodeNode', session_id: str, mode: AgentRunningMode):
        super().__init__(node, session_id, mode)
        self._cc_client: ClaudeSDKClient = self._get_cc_client()
        self._hook_server: HookServer = HookServer(self)
        self._settings_json_path = self.node.workspace / ".claude" / "settings.json"
        self._mcp_json_path = self.node.workspace / ".mcp.json"
        self._old_mcp_json: str = self._install_mcp_json()
        self._old_settings: str = self._install_settings_json()

    async def start(self):
        await self._hook_server.start()
        
    async def close(self):
        if self.mode != AgentRunningMode.PROGRAM:
            await self._exit_cc_client()
        self._uninstall_mcp_json()
        self._uninstall_settings_json()
        await self._hook_server.stop()
    
    
    async def process_event(self, event: MeshEvent) -> bool: ...
    async def process_hook_event(self, event: Dict[str, Any]) -> Dict[str, Any]: ...

    async def chat(self):
        async def receive_cc_response(): ...
        prompt_session = PromptSession()
        while True:
            user_input = prompt_session.prompt("> ")
            if user_input.lower() in ["exit", "quit"]:
                break
            await self._cc_client.query(user_input)
            await receive_cc_response()


    async def program(self):
        os.chdir(str(self.node.workspace))
        subprocess.run([
            "claude",
            "--append-system-prompt", self.node.system_prompt
        ])


    def _get_cc_client(self) -> ClaudeSDKClient:
        cc_options = ClaudeAgentOptions(
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": self.node.system_prompt
            },
            cwd=self.node.workspace,
            permission_mode="bypassPermissions"
        )
        return ClaudeSDKClient(cc_options)

    
    async def _exit_cc_client(self):
        await self._cc_client.query("/exit")

    def _install_settings_json(self):
        self._settings_json_path.parent.mkdir(parents=True, exist_ok=True)
        if self._settings_json_path.exists():
            with open(self._settings_json_path, "r") as f:
                self._old_settings = f.read()
        else:
            self._old_settings = "{}"

        settings = json.loads(self._old_settings)
        # TODO
        

    def _uninstall_settings_json(self):
        if self._old_settings:
            with open(self._settings_json_path, "w") as f:
                f.write(self._old_settings)

    def _install_mcp_json(self): ...
    def _uninstall_mcp_json(self):
        if self._old_mcp_json:
            with open(self._mcp_json_path, "w") as f:
                f.write(self._old_mcp_json)


class ClaudeCodeNode(AgentNode):
    @classmethod
    def check_config(cls, node_id: NodeID, mesh_id: MeshID, config: Dict[str, str]):
        workspace = config.get("workspace", None)
        if not workspace:
            raise ValueError(f"workspace is required")
        
        if not Path(workspace).is_absolute():
            raise ValueError(f"workspace must be an absolute path")
    

    def __init__(self, mesh_id: MeshID, node_id: NodeID, transport: TransportType, config: Dict[str, str]):
        super().__init__(mesh_id, node_id, transport, config)
        workspace = config.get("workspace", None)
        if not workspace:
            raise ValueError(f"cc node {self.node_id} for mesh {self.mesh_id} has no workspace")

        self.workspace = Path(workspace)
        self.system_prompt = self._get_system_prompt()
    

    def _get_system_prompt(self) -> str:
        return """
""".strip()

    async def on_start(self):
        logger.info(f"cc node {self.node_id} for mesh {self.mesh_id} started")

    async def on_shutdown(self):
        logger.info(f"cc node {self.node_id} for mesh {self.mesh_id} stopped")

    async def create_session(self, session_id: str, mode: AgentRunningMode) -> ClaudeCodeSession:
        return ClaudeCodeSession(self, session_id, mode)

    async def program(self):
        session = await self.create_session(str(uuid.uuid4()), AgentRunningMode.PROGRAM)
        await session.start()
        await session.program()
        await session.close()

    async def chat(self):
        session = await self.create_session(str(uuid.uuid4()), AgentRunningMode.CHAT)
        await session.start()
        await session.chat()
        await session.close()
