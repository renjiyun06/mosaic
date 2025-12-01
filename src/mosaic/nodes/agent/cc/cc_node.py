import os
import subprocess
import uuid
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

    async def start(self): ...
    async def stop(self): ...


class ClaudeCodeSession(Session):
    def __init__(self, node: 'ClaudeCodeNode', session_id: str, mode: AgentRunningMode):
        super().__init__(node, session_id, mode)
        self._cc_client: ClaudeSDKClient = self._get_cc_client()
        self._hook_server: HookServer = HookServer(self)
        self._old_hooks: Dict[str, Any] = self._install_hooks()
        self._old_mcp_tools: Dict[str, Any] = self._install_mcp_tools()
        

    async def start(self):
        await self._hook_server.start()
        
    async def close(self):
        if self.mode != AgentRunningMode.PROGRAM:
            await self._exit_cc_client()
        self._uninstall_hooks()
        self._uninstall_mcp_tools()
        await self._hook_server.stop()
    
    async def process_event(self, event: MeshEvent) -> bool: ...

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

    def _install_hooks(self) -> Dict[str, Any]: ...
    def _uninstall_hooks(self) -> Dict[str, Any]: ...
    def _install_mcp_tools(self) -> Dict[str, Any]: ...
    def _uninstall_mcp_tools(self) -> Dict[str, Any]: ...


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
        return ""

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
