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
    TextBlock,
    HookMatcher
)
from prompt_toolkit.shortcuts import PromptSession

import mosaic.core.util as core_util
from mosaic.core.client import MeshClient
from mosaic.core.models import MeshEvent
from mosaic.core.events import get_event_definition
from mosaic.nodes.agent.base import AgentNode, Session
from mosaic.nodes.agent.enums import AgentNodeRunningMode
from mosaic.nodes.agent.cc.hooks import Hook
from mosaic.nodes.agent.mcp_server import McpRequestServer
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
                subsriptions = await self._node.client.get_subscribers(
                    self._node.mesh_id,
                    self._node.node_id,
                    hook.mesh_event_type
                )
                logger.info(
                    f"Event {hook.mesh_event_type} has "
                    f"{len(subsriptions)} subscribers"
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
                            subscription.source_id
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
        self._cc_client: ClaudeSDKClient = None
        self._system_prompt = None
      
    async def start(self):
        try:
            logger.info(
                f"Starting session {self.session_id} of node {self.node.node_id} "
                f"in mesh {self.node.mesh_id}"
            )
            os.chdir(str(self.node.workspace))
            self._system_prompt = await self.node.assemble_system_prompt(
                self.session_id
            )
            if self.node.mode != AgentNodeRunningMode.PROGRAM:
                cc_options = ClaudeAgentOptions(
                    system_prompt={
                        "type": "preset",
                        "preset": "claude_code",
                        "append": self._system_prompt
                    },
                    cwd=self.node.workspace,
                    permission_mode="bypassPermissions",
                    hooks={
                        'UserPromptSubmit': [
                            HookMatcher(hooks=[
                                self.node.handle_hook
                            ])
                        ]
                    },
                    mcp_servers={
                        "mosaic-mcp-server": {
                            "type": "http",
                            "url": "http://localhost:8000/mcp"
                        }
                    },
                    allowed_tools=["*"]
                )
                self._cc_client = ClaudeSDKClient(cc_options)
                await self._cc_client.connect()
                self._status = ClaudeCodeSessionStatus.STARTED
            logger.info(
                f"Session {self.session_id} of node {self.node.node_id} in mesh "
                f"{self.node.mesh_id} started"
            )
        except Exception as e:
            import traceback
            logger.error(
                f"Error starting session {self.session_id}: "
                f"{traceback.format_exc()}")
            raise e
        
    
    async def close(self):
        logger.info(
            f"Closing session {self.session_id} of node {self.node.node_id} "
            f"in mesh {self.node.mesh_id}"
        )
        if self._cc_client:
            await self._cc_client.query("/exit")
            async for _ in self._cc_client.receive_response(): ...
            await self._cc_client.disconnect()
            self._cc_client = None
        
        self._system_prompt = None
        logger.info(
            f"Session {self.session_id} of node {self.node.node_id} in mesh "
            f"{self.node.mesh_id} closed"
        )


    async def process_event(self, event: MeshEvent):
        async def receive():
            async for message in self._cc_client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            logger.info(
                                f"Session {self.session_id} received message: "
                                f"{block.text}"
                            )
        
        async with self._lock:
            xml_content = event.to_xml()
            logger.info(
                f"Session {self.session_id} processing event: "
                f"{xml_content}"
            )
            if self.node.mode == AgentNodeRunningMode.CHAT:
                console.print(xml_content)
            
            await self._cc_client.query(xml_content)
            await receive()
            await self.node.client.ack(event)


    async def chat(self):
        async def receive():
            async for message in self._cc_client.receive_response():
                logger.info(
                    f"Session {self.session_id} received message: {message}"
                )
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            console.print(f"• {block.text}")
        
        prompt_session = PromptSession()
        while True:
            try:
                user_input = await prompt_session.prompt_async("> ")
            except KeyboardInterrupt:
                break
            async with self._lock:
                if user_input.lower() in ["exit", "/exit"]:
                    break
                
                await self._cc_client.query(user_input)
                await receive()


    async def program(self):
        process = await asyncio.create_subprocess_exec(
            "claude", "--append-system-prompt", self._system_prompt
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
        
        self._hook_server = None
        self._mcp_request_server = None
        

    async def create_session(self, mesh_id: str, node_id: str) -> Session:
        return ClaudeCodeSession(str(uuid.uuid4()), self)
    
    async def chat(self):
        await self._chat_session.chat()
        
    async def program(self):
        await self._program_session.program()
    

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

        if not settings.get('enabledMcpjsonServers'):
            settings['enabledMcpjsonServers'] = []

        settings['enabledMcpjsonServers'].append('mosaic-mcp-server')
        with open(self._settings_path, "w") as f:
            f.write(json.dumps(settings, ensure_ascii=False, indent=2))

        mcp_config = {}
        if self._old_mcp_json:
            mcp_config = json.loads(self._old_mcp_json)

        if not mcp_config.get("mcpServers"):
            mcp_config["mcpServers"] = {}

        mcp_config["mcpServers"]["mosaic-mcp-server"] = {
            "type": "http",
            "url": "http://localhost:8000/mcp"
        }

        with open(self._mcp_json_path, "w") as f:
            f.write(json.dumps(mcp_config, ensure_ascii=False, indent=2))

        logger.info(
            f"Installed settings for node {self.node_id} in mesh {self.mesh_id}"
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
            self._mcp_request_server = McpRequestServer(self)
            await self._mcp_request_server.start()
            
            await self._install_settings()
        except Exception as e:
            import traceback
            logger.error(f"Error on start: {traceback.format_exc()}")
            raise e

    
    async def on_shutdown(self):
        await self._uninstall_settings()
        if self._mcp_request_server:
            await self._mcp_request_server.stop()
            self._mcp_request_server = None
        if self._hook_server:
            await self._hook_server.stop()
            self._hook_server = None

    async def assemble_system_prompt(self, session_id: str) -> str:
        event_types = set[str]()
        subscriptions = await self.client.get_subscriptions(
            self.mesh_id,
            self.node_id
        )
        subscriber_subscriptions = await self.client.get_subscribers(
            self.mesh_id,
            self.node_id
        )

        network_topology = ""
        network_topology += "graph LR\n"
        for sub in subscriptions + subscriber_subscriptions:
            event_types.add(sub.event_pattern)
            network_topology += f"  {sub.target_id} --> |{sub.event_pattern}| {sub.source_id}\n"
            
        if network_topology:
            network_topology = f"[Network Topology]\n{network_topology}"
        
        event_definitions = ""
        for event_type in event_types:
            event_definition = get_event_definition(event_type)
            event_definitions += f"{event_definition.name}: {event_definition.model_dump_json(exclude={'name'})}\n\n"

        if event_definitions:
            event_definitions = f"[Event Definitions]\n{event_definitions}"

        template = """
<mosaic_runtime_context>
You are now a node operating within the Mosaic Event Mesh system.

[Identity]
Mesh ID: {mesh_id}
Node ID: {node_id}
Current Session: {session_id}

{network_topology}
{event_definitions}
</mosaic_runtime_context>
""".strip()
        system_prompt = template.format(
            mesh_id=self.mesh_id,
            node_id=self.node_id,
            session_id=session_id,
            network_topology=network_topology,
            event_definitions=event_definitions,
        )
        logger.info(
            f"System prompt for session {session_id} of "
            f"node {self.node_id} in mesh {self.mesh_id}: {system_prompt}"
        )
        return system_prompt

    async def handle_hook(
        self,
        hook_input: Dict[str, Any],
        tool_use_id: str | None,
        context
    ) -> Dict[str, Any]:
        logger.info(
            f"Handling hook for session {hook_input.get('session_id')} of node "
            f"{self.node_id} in mesh {self.mesh_id} with input: {hook_input}"
        )
        hook_server_sock = core_util.cc_hook_server_sock_path(
            self.mesh_id, self.node_id
        )
        if not hook_server_sock.exists():
            logger.error(
                f"Hook server socket path {hook_server_sock} does not exist"
            )
            raise RuntimeError(
                f"Hook server socket path {hook_server_sock} does not exist"
            )
        
        reader, writer = await asyncio.open_unix_connection(str(hook_server_sock))
        try:
            request = hook_input
            request_content = json.dumps(request, ensure_ascii=False)
            request_content_bytes = request_content.encode()
            writer.write(len(request_content_bytes).to_bytes(4, "big"))
            writer.write(request_content_bytes)
            await writer.drain()
            length = int.from_bytes(await reader.readexactly(4), "big")
            response_content = await reader.readexactly(length)
            response = response_content.decode("utf-8")
            if self.mode == AgentNodeRunningMode.PROGRAM:
                print(response)
            else:
                return json.loads(response)
        except Exception as e:
            import traceback
            logger.error(f"Error handling hook: {e}\n{traceback.format_exc()}")
            raise e
        finally:
            writer.close()
            await writer.wait_closed()