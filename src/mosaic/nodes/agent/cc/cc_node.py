import uuid
import json
import os
import asyncio
from pathlib import Path
from typing import Dict, Any
from enum import StrEnum
from rich.console import Console
from importlib.resources import files, as_file
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock
)
from prompt_toolkit.shortcuts import PromptSession

import mosaic.core.util as core_util
from mosaic.core.client import MeshClient
from mosaic.core.models import MeshEvent
from mosaic.core.events import get_event_definition
from mosaic.nodes.agent.base import AgentNode, Session
from mosaic.nodes.agent.types import AgentNodeRunningMode
from mosaic.nodes.agent.cc.hooks import Hook
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

console = Console()

class HookServer:
    def __init__(
        self, 
        node: 'ClaudeCodeNode'
    ):
        self._node = node
        self._sock_path = core_util.cc_hook_server_sock_path(
            node.mesh_id, node.node_id
        )
        self._sock_server = None

    async def start(self):
        logger.info(
            f"Starting hook server in {self._node.mode} mode for "
            f"node {self._node.node_id} in mesh {self._node.mesh_id}"
        )
        self._sock_path.parent.mkdir(parents=True, exist_ok=True)
        self._sock_server = await asyncio.start_unix_server(
            self._handle_hook,
            path=str(self._sock_path)
        )
        logger.info(
            f"Hook server in {self._node.mode} mode for "
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

            if self._node.mode == AgentNodeRunningMode.PROGRAM:
                response = hook_type.default_hook_output()
            else:
                subsriptions = await self._node.client.get_subscriptions(
                    self._node.mesh_id,
                    self._node.node_id,
                    hook.mesh_event_type
                )
                event_definition = get_event_definition(hook.mesh_event_type)
                if not subsriptions or not event_definition:
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
            
            response_content = json.dumps(response, ensure_ascii=False)
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
    def __init__(self, node: 'ClaudeCodeNode'):
        self._node = node

    async def start(self):
        pass

    async def stop(self):
        pass


class ClaudeCodeSessionStatus(StrEnum):
    STARTED = "started"
    CLOSING = "closing"
    CLOSED = "closed"

class ClaudeCodeSession(Session):
    def __init__(
        self, 
        session_id: str, 
        node: 'ClaudeCodeNode', 
    ):
        super().__init__(session_id, node)
        self._status = ClaudeCodeSessionStatus.CLOSED
        self._lock = asyncio.Lock()
        self._event_queue = None
        self._cc_client: ClaudeSDKClient = None
        self._event_processor_task = None
      
    async def start(self):
        os.chdir(str(self.node.workspace))
        self._event_queue = asyncio.Queue()
        cc_options = ClaudeAgentOptions(
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": self.node.system_prompt
            },
            cwd=self.node.workspace,
            permission_mode="bypassPermissions"
        )
        self._cc_client = ClaudeSDKClient(cc_options)
        await self._cc_client.connect()
        self._event_processor_task = asyncio.create_task(
            self._event_processor_loop()
        )
        self._status = ClaudeCodeSessionStatus.STARTED
        
    
    async def close(self):
        if self._event_processor_task:
            self._event_processor_task.cancel()
            self._event_processor_task = None
        if self._event_queue:
            self._event_queue.put_nowait(None)
            self._event_queue = None
        if self._cc_client:
            await self._cc_client.query("exit")
            async for _ in self._cc_client.receive_response(): ...
            await self._cc_client.disconnect()
            self._cc_client = None


    async def process_event(self, event: MeshEvent):
        if self._status == ClaudeCodeSessionStatus.STARTED:
            await self._event_queue.put(event)


    async def _event_processor_loop(self):
        async def receive(): ...
        while True:
            event: MeshEvent = await self._event_queue.get()
            if event:
                async with self._lock:
                    xml_content = event.to_xml()
                    if self.node.mode == AgentNodeRunningMode.CHAT:
                        console.print(xml_content)
                    
                    await self._cc_client.query(xml_content)
                    await receive()
            else:
                break
    

    async def chat(self):
        async def receive():
            async for message in self._cc_client.receive_response():
                logger.info(
                    f"Session {self.session_id} received message: {message}"
                )
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            console.print(block.text)
                elif isinstance(message, ResultMessage):
                    console.print(message.result)
               
        
        prompt_session = PromptSession()
        while True:
            user_input = await prompt_session.prompt_async("> ")
            async with self._lock:
                if user_input.lower() == "exit":
                    break
                
                await self._cc_client.query(user_input)
                await receive()


    async def program(self):
        process = await asyncio.create_subprocess_exec(
            "claude", "--append-system-prompt", self.node.system_prompt
        )
        await process.wait()


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
        self.workspace = Path(workspace)
        if not self.workspace.is_absolute():
            raise RuntimeError("Workspace must be an absolute path")
        self.workspace.mkdir(parents=True, exist_ok=True)

        self._settings_path = self.workspace / ".claude" / "settings.json"
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._old_settings: str = None
        if self._settings_path.exists():
            with open(self._settings_path, "r") as f:
                self._old_settings = f.read()
    
        self._mcp_json_path = self.workspace / ".mcp.json"
        self._old_mcp_json: str = None
        if self._mcp_json_path.exists():
            with open(self._mcp_json_path, "r") as f:
                self._old_mcp_json = f.read()
        
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
        await self.client.connect()
        await self.on_start()
        self._program_session = ClaudeCodeSession(
            session_id,
            self
        )
        await self._program_session.start()


    async def stop_program_mode(self):
        await self._program_session.close()
        self._program_session = None
        await self.on_shutdown()
        await self.client.disconnect()

    
    async def _install_settings(self):
        def install_hook(name, hooks: Dict[str, Any]):
            with as_file(
                files("mosaic.nodes.agent.cc") / "hook_entry.py"
            ) as hook_entry_path:
                hook_entry_path = hook_entry_path.as_posix()
            hook = {
                "hooks": [
                    {
                        "type": "command",
                        "command": f"python {hook_entry_path} \
                                        --mesh-id {self.mesh_id} \
                                        --node-id {self.node_id}"
                    }
                ]
            }

            if not hooks.get(name):
                hooks[name] = [hook]
            else:
                hooks[name] = [hook] + hooks[name]

        logger.info(
            f"Installing hooks for node {self.node_id} in mesh {self.mesh_id}"
        )
        settings: Dict[str, Any] = {}
        if self._old_settings:
            settings = json.loads(self._old_settings)
        
        if not settings.get("hooks"):
            settings["hooks"] = {}
        
        install_hook("PreToolUse", settings["hooks"])
        install_hook("UserPromptSubmit", settings["hooks"])

        
        with open(self._settings_path, "w") as f:
            f.write(json.dumps(settings, ensure_ascii=False, indent=2))
        
        logger.info(
            f"Installed hooks for node {self.node_id} in mesh {self.mesh_id}"
        )

    async def _uninstall_settings(self):
        if self._old_settings:
            with open(self._settings_path, "w") as f:
                f.write(self._old_settings)
            self._old_settings = None
        else:
            self._settings_path.unlink(missing_ok=True)
        
        if self._old_mcp_json:
            with open(self._mcp_json_path, "w") as f:
                f.write(self._old_mcp_json)
            self._old_mcp_json = None
        else:
            self._mcp_json_path.unlink(missing_ok=True)


    async def on_start(self):
        try:
            self._hook_server = HookServer(self)
            await self._hook_server.start()
            self._mcp_server = McpServer(self)
            await self._mcp_server.start()
            await self._install_settings()

            self.system_prompt = await self._assemble_system_prompt()
        except Exception as e:
            import traceback
            logger.error(f"Error on start: {e}\n{traceback.format_exc()}")
            raise e

    
    async def on_shutdown(self):
        await self._uninstall_settings()
        await self._mcp_server.stop()
        self._mcp_server = None
        await self._hook_server.stop()
        self._hook_server = None

    async def _assemble_system_prompt(self) -> str:
        return ""
