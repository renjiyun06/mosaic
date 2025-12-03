import uuid
from pathlib import Path
from typing import Dict
from rich.console import Console

import mosaic.core.util as core_util
from mosaic.core.client import MeshClient
from mosaic.core.models import MeshEvent
from mosaic.nodes.agent.base import AgentNode, Session
from mosaic.nodes.agent.types import AgentNodeRunningMode
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

console = Console()

class HookServer:
    def __init__(self, node: 'ClaudeCodeNode'):
        self._node = node
        self._sock_path = core_util.cc_hook_server_sock_path(
            node.mesh_id, node.node_id
        )

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
        
        self._system_prompt = None


    async def create_session(self, mesh_id: str, node_id: str) -> Session:
        return ClaudeCodeSession(str(uuid.uuid4()), self)
    
    async def chat(self): ...
    async def program(self): ...
    

    async def start_chat_mode(self, session_id: str):
        assert self.mode == AgentNodeRunningMode.CHAT
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


    async def on_start(self):
        # 1. Start hook server
        # 2. Start mcp server 
        pass
    async def on_shutdown(self): ...