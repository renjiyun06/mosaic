import uuid
import json
import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Literal
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

from mosaic.core.client import MeshClient
from mosaic.core.models import MeshEvent
from mosaic.core.events import get_event_definition
from mosaic.nodes.agent.base import AgentNode, Session
from mosaic.nodes.agent.enums import SessionMode
from mosaic.nodes.agent.mcp_server import McpRequestServer
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

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
    

    async def on_start(self):
        try:
            self._system_prompt = await self.node.assemble_system_prompt(
                self.session_id
            )
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
                            self._pre_tool_use_hook
                        ])
                    ],
                },
                mcp_servers=mcp_servers,
                allowed_tools=["*"],
                setting_sources=["project"]
            )
            self._cc_client = ClaudeSDKClient(cc_options)
            await self._cc_client.connect()
            await self.publish_event("cc.session_start", {})
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
                await self.publish_event("cc.session_end", {})
        
        self._system_prompt = None


    async def _pre_tool_use_hook(
        self,
        hook_input: Dict[str, Any],
        tool_use_id: str | None,
        context: Any
    ) -> Dict[str, Any]:
        await self.publish_event("cc.pre_tool_use", {
            "tool_name": hook_input.get("tool_name"),
            "tool_input": hook_input.get("tool_input")
        })
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "",
            }
        }

    
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
                message = message.get("message")
                await self.publish_event(
                    "cc.user_prompt_submit",
                    {
                        "prompt": message
                    }
                )
                await self._cc_client.query(message)
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

        self._mcp_request_server = None
        

    async def create_session(self, mode: SessionMode) -> ClaudeCodeSession:
        logger.info(
            f"Creating new session in {mode} mode for node {self}"
        )
        return ClaudeCodeSession(str(uuid.uuid4()), self, mode)
    
        
    async def on_start(self):
        try:
            self._mcp_request_server = McpRequestServer(self)
            await self._mcp_request_server.start()
        except Exception as e:
            logger.error(f"Error on start node {self}: {e}")
            raise e

    
    async def on_shutdown(self):
        if self._mcp_request_server:
            await self._mcp_request_server.stop()
            self._mcp_request_server = None
        
        await self._session_manager.close()

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