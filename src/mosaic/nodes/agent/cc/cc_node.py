import uuid
import json
import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Literal
from importlib.resources import files, as_file
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    HookMatcher
)

import mosaic.core.util as core_util
from mosaic.core.client import MeshClient
from mosaic.core.models import MeshEvent
from mosaic.core.events import get_event_definition
from mosaic.nodes.agent.base import AgentNode, Session
from mosaic.nodes.agent.enums import SessionMode
from mosaic.nodes.agent.cc.hooks import Hook
from mosaic.nodes.agent.mcp_server import McpRequestServer
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

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

            if self._node.mode == "program":
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
                        reply_futures = []
                        for blocking_event in blocking_events:
                            reply_futures.append(
                                self._node.client.wait_reply(
                                    blocking_event.event_id
                                )
                            )
                            await self._node.client.send(blocking_event)
                        reply_events = await asyncio.gather(*reply_futures)
                        response = hook_type.merge_decisions(reply_events)
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


class ClaudeCodeSession(Session):
    def __init__(
        self, 
        session_id: str, 
        node: 'ClaudeCodeNode', 
        mode: SessionMode
    ):
        super().__init__(session_id, node, mode)
        self._lock = asyncio.Lock()
        self._cc_client: ClaudeSDKClient = None
        self._system_prompt = None
        self._handle_hook = self.node.handle_hook_wrapper(self)
    

    async def on_start(self):
        try:
            os.chdir(str(self.node.workspace))
            self._system_prompt = await self.node.assemble_system_prompt(
                self.session_id
            )
            if self.mode != SessionMode.PROGRAM:
                mcp_servers = {
                    "mosaic-mcp-server": {
                        "type": "http",
                        "url": "http://localhost:8000/mcp"
                    }
                }
                mcp_servers.update(json.loads(
                    self.node.config.get("mcpServers", "{}"))
                )
                cc_options = ClaudeAgentOptions(
                    model="sonnet",
                    system_prompt={
                        "type": "preset",
                        "preset": "claude_code",
                        "append": self._system_prompt
                    },
                    cwd=self.node.workspace,
                    permission_mode="bypassPermissions",
                    hooks={
                        "PreToolUse": [
                            HookMatcher(hooks=[
                                self._handle_hook
                            ])
                        ],
                        'UserPromptSubmit': [
                            HookMatcher(hooks=[
                                # self._handle_hook
                            ])
                        ],
                        # Actually, Python SDK does not support SessionStart, 
                        # SessionEnd, and Notification hooks, just keep it here
                        "SessionEnd": [
                            HookMatcher(hooks=[
                                # self._handle_hook
                            ])
                        ]
                    },
                    mcp_servers=mcp_servers,
                    allowed_tools=["*"],
                    setting_sources=["project"]
                )
                self._cc_client = ClaudeSDKClient(cc_options)
                await self._cc_client.connect()
                await self._handle_hook(
                    hook_input={
                        "session_id": self.session_id,
                        "hook_event_name": "SessionStart"
                    },
                    tool_use_id=None,
                    context=None
                )
        except Exception as e:
            logger.error(f"Error on start cc session {self}: {e}")
            raise e
        
    
    async def on_close(self):
        if self._cc_client:
            await self._cc_client.query("/exit")
            async for _ in self._cc_client.receive_response(): ...
            await self._cc_client.disconnect()
            self._cc_client = None

            if self.mode != SessionMode.PROGRAM:
                # Python SDK does not support 
                # SessionStart, SessionEnd, and Notification hooks
                await self._handle_hook(
                    {
                        "session_id": self.session_id,
                        "hook_event_name": "SessionEnd"
                    },
                    None,
                    None
                )
        
        self._system_prompt = None

    
    async def _receive_assistant_message(self):
        async for message in self._cc_client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        await self.broadcast_client.send({
                            "type": "message",
                            "sub_type": "assistant_text",
                            "session_id": self.session_id,
                            "role": "assistant",
                            "message": block.text
                        })
                    elif isinstance(block, ThinkingBlock):
                        await self.broadcast_client.send({
                            "type": "message",
                            "sub_type": "assistant_thinking",
                            "session_id": self.session_id,
                            "role": "assistant",
                            "message": block.thinking
                        })
                    elif isinstance(block, ToolUseBlock):
                        await self.broadcast_client.send({
                            "type": "message",
                            "sub_type": "assistant_tool_use",
                            "session_id": self.session_id,
                            "role": "assistant",
                            "message": block.name
                        })
            elif isinstance(message, ResultMessage):
                await self.publish_event(
                    "cc.session_response",
                    {
                        "response": message.result
                    }
                )

    async def process_event(self, event: MeshEvent):
        async with self._lock:
            event_type = event.type
            xml_content = None
            if event_type == "mosaic.node_message":
                xml_content = event.to_node_message_xml()
            else:
                xml_content = event.to_xml()

            await self.broadcast_client.send({
                "type": "message",
                "session_id": self.session_id,
                "role": "system",
                "message": xml_content
            })
            await self._cc_client.query(xml_content)
            await self._receive_assistant_message()
            await self.node.client.ack(event)

    
    async def process_message(self, message: Dict[str, Any]):
        logger.info(
            f"Processing message for session {self}: "
            f"{json.dumps(message, ensure_ascii=False)}"
        )
        if message.get("session_id") != self.session_id:
            return

        if message.get("role") == "user":
            async with self._lock:
                await self._handle_hook(
                    {
                        "session_id": self.session_id,
                        "hook_event_name": "UserPromptSubmit",
                        "prompt": message.get("message")
                    },
                    None,
                    None
                )
                await self._cc_client.query(
                    message.get("message")
                )
                await self._receive_assistant_message()


    async def program(self):
        process = await asyncio.create_subprocess_exec(
            "claude", 
            "--model", "sonnet",
            "--append-system-prompt", self._system_prompt
        )
        await process.wait()


class ClaudeCodeNode(AgentNode):
    def __init__(
        self, 
        mesh_id: str, 
        node_id: str, 
        config: Dict[str, str],
        client: MeshClient,
        mode: Literal["default", "program"] = "default"
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
        

    async def create_session(self, mode: SessionMode) -> ClaudeCodeSession:
        logger.info(
            f"Creating new session in {mode} mode for node {self}"
        )
        return ClaudeCodeSession(str(uuid.uuid4()), self, mode)
    
        
    async def program(self):
        await self._program_session.program()
    

    async def start_program_mode(self, session_id: str):
        await self.client.connect()
        await self.on_start()
        await self._install_settings()
        self._program_session = ClaudeCodeSession(
            session_id,
            self,
            SessionMode.PROGRAM
        )
        await self._program_session.on_start()


    async def stop_program_mode(self):
        await self._program_session.on_close()
        self._program_session = None
        await self._uninstall_settings()
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
        install_hook("SessionEnd", settings["hooks"])

        if not settings.get('enabledMcpjsonServers'):
            settings['enabledMcpjsonServers'] = []

        mcp_config = {}
        if self._old_mcp_json:
            mcp_config = json.loads(self._old_mcp_json)

        if not mcp_config.get("mcpServers"):
            mcp_config["mcpServers"] = {}

        mcp_config["mcpServers"]["mosaic-mcp-server"] = {
            "type": "http",
            "url": "http://localhost:8000/mcp"
        }

        settings['enabledMcpjsonServers'].append('mosaic-mcp-server')

        mcp_servers: Dict[str, Any] = json.loads(self.config.get("mcpServers", "{}"))
        for name, config in mcp_servers.items():
            mcp_config["mcpServers"][name] = config
            settings['enabledMcpjsonServers'].append(name)

        with open(self._mcp_json_path, "w") as f:
            f.write(json.dumps(mcp_config, ensure_ascii=False, indent=2))

        with open(self._settings_path, "w") as f:
            f.write(json.dumps(settings, ensure_ascii=False, indent=2))

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
        except Exception as e:
            logger.error(f"Error on start node {self}: {e}")
            raise e

    
    async def on_shutdown(self):
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
        for sub in subscriptions + subscriber_subscriptions:
            event_pattern = sub.event_pattern
            if event_pattern == "mosaic.node_message":
                continue
            else:
                event_types.add(event_pattern)
                network_topology += f"  {sub.target_id} --> |{event_pattern}| {sub.source_id}\n"
            
        for sub in subscriber_subscriptions:
            if sub.event_pattern == "mosaic.node_message":
                network_topology += f"  {sub.target_id} --- {sub.source_id}\n"
        
        if network_topology:
            network_topology = f"[Network Topology]\ngraph LR\n{network_topology}"
        
        event_definitions = ""
        for event_type in event_types:
            event_definition = get_event_definition(event_type)
            event_definitions += f"{event_definition.name}: {event_definition.model_dump_json(exclude={'name'})}\n\n"

        if event_definitions:
            event_definitions = f"[Event Definitions]\n{event_definitions}"

        template = """
You are now a node operating within the Mosaic Event Mesh system.

[Identity]
Mesh ID: {mesh_id}
Node ID: {node_id}

[Current Session]
Session ID: {session_id}

{network_topology}
{event_definitions}
"""
        system_prompt = template.format(
            mesh_id=self.mesh_id,
            node_id=self.node_id,
            session_id=session_id,
            network_topology=network_topology,
            event_definitions=event_definitions,
        ).strip()
        
        system_prompt = f"""
<mosaic_runtime_context>

{system_prompt}

</mosaic_runtime_context>
""".strip()
        
        logger.info(
            f"System prompt for session {session_id} of "
            f"node {self.node_id} in mesh {self.mesh_id}: \n{system_prompt}"
        )
        return system_prompt


    def handle_hook_wrapper(self, session: ClaudeCodeSession):
        async def handle_hook(
            hook_input: Dict[str, Any],
            tool_use_id: str | None,
            context
        ) -> Dict[str, Any]:
            claude_code_session_id = hook_input.get('session_id')
            # TODO fix it
            logger.warning(
                f"Session {session} corresponds to claude code session "
                f"{claude_code_session_id}"
            )
            hook_input["session_id"] = session.session_id
            logger.info(
                f"Handling hook for session {session} with input: {hook_input}"
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
                if self.mode == "program":
                    print(response)
                else:
                    return json.loads(response)
            except Exception as e:
                logger.error(f"Error handling hook: {e}")
                raise e
            finally:
                writer.close()
                await writer.wait_closed()

        return handle_hook