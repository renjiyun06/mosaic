import asyncio
import json
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    HookMatcher,
    tool, 
    create_sdk_mcp_server
)
from jinja2 import Template

import mosaic.core.db as db
from mosaic.core.type import (
    Session, EventType, Node, Subscription, NodeType, Connection
)
from mosaic.core.node import MosaicNode, MosaicSession
from mosaic.core.event import MosaicEvent, EVENTS
from mosaic.core.zmq import ZmqClient
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class ClaudeCodeSession(MosaicSession):
    def __init__(
        self, 
        session: Session,
        node: 'ClaudeCodeNode'
    ):
        super().__init__(session, node)
        
        self.mode = session.config.get("mode", "background")
        model = None
        if session.config.get("model"):
            model = session.config.get("model")
        elif node.config.get("model"):
            model = node.config.get("model")
        else:
            model = "sonnet"
        
        self.model: str = model
        self._queue = asyncio.Queue()
        self._zmq_client = ZmqClient(
            session.pull_host,
            session.pull_port,
            session.pub_host,
            session.pub_port,
            subscribe_topic=f"{session.session_id}#incoming",
            on_event=self.process_user_message,
            debug_message=f"{self.node.node_id}#{self.session.session_id}"
        )
        self._run_forever_task = None

        self._total_cost_usd = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        self._is_interrupted = False


    async def start(self):
        system_prompt = await self.get_system_prompt()
        logger.info(
            f"System prompt for session {self.session.session_id}: "
            f"\n{system_prompt}")
        
        mcp_servers = self.node.config.get("mcp_servers", {})
        mcp_servers["mosaic-mcp-server"] = self.create_mosaic_mcp_server()
        logger.debug(
            f"MCP servers for session {self.session}: "
            f"{list(mcp_servers.keys())}"
        )
        logger.debug(
            f"Model for session {self.session}: {self.model}"
        )
        cc_options = ClaudeAgentOptions(
            model=self.model,
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": system_prompt
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
            setting_sources=["project"],
            max_thinking_tokens=2000
        )
        self._cc_client = ClaudeSDKClient(cc_options)
        await self._cc_client.connect()

        self._run_forever_task = asyncio.create_task(self._run_forever())
        self._zmq_client.connect()

        if self.mode != "program":
            await self.node.publish_event(
                session_id=self.session.session_id,
                event_type=EventType.SESSION_START,
                payload={}
            )

    
    async def close(self, force: bool = False):
        logger.info(f"Closing session {self.session}")
        self._total_cost_usd = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        if self._run_forever_task:
            self._run_forever_task.cancel()
            self._run_forever_task = None
        if self._zmq_client:
            self._zmq_client.disconnect()

        if self.mode != "program" and not force:
            await self.node.publish_event(
                session_id=self.session.session_id,
                event_type=EventType.SESSION_END,
                payload={}
            )
        logger.info(f"Session {self.session} closed")


    async def process_user_message(self, user_message: Dict[str, Any]):
        future = asyncio.get_event_loop().create_future()
        type = user_message.get("type")
        if type == "user_interrupt":
            await self._cc_client.interrupt()
            self._is_interrupted = True
            logger.info(
                f"Session {self.session} interrupted by user"
            )
        else:
            await self._queue.put((user_message.get("message"), future))
    

    async def process_event(self, event: MosaicEvent) -> asyncio.Future:
        future = asyncio.get_event_loop().create_future()
        await self._queue.put((event, future))
        return future

    
    async def _run_forever(self):
        async def _receive_assistant_message():
            async for message in self._cc_client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            logger.debug(
                                f"Assistant text in session {self.session}: "
                                f"{block.text}"
                            )
                            await self._zmq_client.send(
                                topic=f"{self.session.session_id}#outgoing",
                                event={
                                    "type": "session_message",
                                    "sub_type": "assistant_text",
                                    "role": "assistant",
                                    "message": block.text
                                }
                            )
                        elif isinstance(block, ThinkingBlock):
                            logger.debug(
                                f"Assistant thinking in session {self.session}: "
                                f"{block.thinking}"
                            )
                            await self._zmq_client.send(
                                topic=f"{self.session.session_id}#outgoing",
                                event={
                                    "type": "session_message",
                                    "sub_type": "assistant_thinking",
                                    "role": "assistant",
                                    "message": block.thinking
                                }
                            )
                        elif isinstance(block, ToolUseBlock):
                            logger.debug(
                                f"Assistant tool use in session {self.session}: "
                                f"{block.name} with input {block.input}"
                            )
                            await self._zmq_client.send(
                                topic=f"{self.session.session_id}#outgoing",
                                event={
                                    "type": "session_message",
                                    "sub_type": "assistant_tool_use",
                                    "role": "assistant",
                                    "tool_name": block.name,
                                    "tool_input": block.input
                                }
                            )
                elif isinstance(message, ResultMessage):
                    logger.debug(
                        f"Assistant result in session {self.session}: "
                        f"{message.result}"
                    )
                    logger.debug(
                        f"Usage: {json.dumps(message.usage, ensure_ascii=False)}"
                    )

                    self._total_cost_usd += message.total_cost_usd or 0.0
                    self._total_input_tokens += message.usage.get(
                        "input_tokens", 0
                    )
                    self._total_output_tokens += message.usage.get(
                        "output_tokens", 0
                    )
                    await self._zmq_client.send(
                        topic=f"{self.session.session_id}#outgoing",
                        event={
                            "type": "session_message",
                            "sub_type": "assistant_result",
                            "role": "assistant",
                            "message": message.result,
                            "total_cost_usd": self._total_cost_usd,
                            "total_input_tokens": self._total_input_tokens,
                            "total_output_tokens": self._total_output_tokens,
                            "cost_usd": message.total_cost_usd,
                            "usage": message.usage
                        }
                    )
                    if self.mode != "program":
                        if self._is_interrupted:
                            return
                        
                        await self.node.publish_event(
                            session_id=self.session.session_id,
                            event_type=EventType.SESSION_RESPONSE,
                            payload={
                                "response": message.result
                            }
                        )
        try:
            while True:
                event, future = await self._queue.get()
                llm_message = None
                if isinstance(event, str):
                    llm_message = event
                    await self._zmq_client.send(
                        topic=f"{self.session.session_id}#outgoing",
                        event={
                            "type": "session_message",
                            "sub_type": "user_message",
                            "role": "user",
                            "message": event
                        }
                    )
                    if self.mode != "program":
                        await self.node.publish_event(
                            session_id=self.session.session_id,
                            event_type=EventType.USER_PROMPT_SUBMIT,
                            payload={
                                "prompt": event
                            }
                        )
                else:
                    llm_message = event.to_llm_message()
                    await self._zmq_client.send(
                        topic=f"{self.session.session_id}#outgoing",
                        event={
                            "type": "session_message",
                            "sub_type": "system_message",
                            "role": "system",
                            "message": llm_message
                        }
                    )

                logger.debug(
                    f"Sending query to session {self.session}: {llm_message}"
                )
                await self._cc_client.query(llm_message)
                await _receive_assistant_message()
                self._is_interrupted = False
                future.set_result(None)
        except asyncio.CancelledError:
            future.set_exception(asyncio.CancelledError("Session cancelled"))
            if self._cc_client:
                await self._cc_client.query("/exit")
                async for _ in self._cc_client.receive_response(): ...
                await self._cc_client.disconnect()
                self._cc_client = None
        except Exception as e:
            logger.error(
                f"Error in _run_forever for session {self.session}: "
                f"{e}\n{traceback.format_exc()}"
            )
            future.set_exception(e)


    async def get_system_prompt(self) -> str:
        nodes: List[Node] = await db.list_nodes()
        for node in nodes:
            if node.type == NodeType.EMAIL:
                node.node_id = f'{node.node_id}["{node.config.get("account")}"]'
            elif node.type == NodeType.SCHEDULER:
                node.node_id = f'{node.node_id}["{node.config.get("cron")}"]'
        subscriptions: List[Subscription] = await db.list_subscriptions()
        connections: List[Connection] = await db.list_connections()
        # remove all connections that are in the subscriptions
        connections = [
            connection for connection in connections 
            if not any(
                subscription.source_id == connection.source_id and \
                    subscription.target_id == connection.target_id
                for subscription in subscriptions
            )
        ]
        print(connections)
        event_types = list(EVENTS.keys())

        template = Template("""
You are now a node operating within the Mosaic Event Mesh system.

[Identity]
Node ID: {{ node_id }}

[Current Session]
Session ID: {{ session_id }}

[Nodes In Mesh]
{% for node in nodes -%}
- {{ node.node_id }}
{% endfor %}
{% if subscriptions or connections -%}
[Network Topology]
graph LR
{% for sub in subscriptions -%}
    {{ sub.source_id }} --> |{{ sub.event_type }}| {{ sub.target_id }}
{% endfor -%}
{% for connection in connections -%}
    {{ connection.source_id }} --> {{ connection.target_id }}
{% endfor -%}
{% endif %}
{% if event_types -%}
[Event Definitions]
{% for event_type in event_types -%}
{{ event_type }}: 
    - description: {{ EVENTS[event_type].description() }}
{%- if EVENTS[event_type].payload_schema() %}
    - payload_schema: {{ json.dumps(EVENTS[event_type].payload_schema(), ensure_ascii=False) }}
{%- endif %}
{% if not loop.last %}
{% endif -%}
{% endfor -%}
{% endif -%}
""")
        system_prompt = template.render(
            node_id=self.node.node_id,
            session_id=self.session.session_id,
            nodes=nodes,
            subscriptions=subscriptions,
            connections=connections,
            EVENTS=EVENTS,
            event_types=event_types,
            json=json
        )

        return system_prompt.strip()

    
    async def _pre_tool_use_hook(
        self, 
        hook_input: Dict[str, Any],
        tool_use_id: str | None,
        context: Any
    ):
        if self.mode != "program":
            await self.node.publish_event(
                session_id=self.session.session_id,
                event_type=EventType.PRE_TOOL_USE,
                payload={
                    "tool_name": hook_input.get("tool_name"),
                    "tool_input": hook_input.get("tool_input")
                }
            )
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "",
            }
        }

    
    def create_mosaic_mcp_server(self):
        @tool(
            "send_message",
            "Send a message to a node",
            {
                "target_node_id": str,
                "message": str
            }
        )
        async def send_message(args):
            try:
                target_node_id = args['target_node_id']
                message = args['message']
                await self.node.publish_event(
                    session_id=self.session.session_id,
                    event_type=EventType.NODE_MESSAGE,
                    payload={
                        "message": message
                    },
                    target_node_id=target_node_id
                )
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Successfully sent message to node {target_node_id}"
                        }
                    ]
                }
            except Exception as e:
                logger.error(
                    f"Failed to send message to node {target_node_id}: "
                    f"{e}\n{traceback.format_exc()}"
                )
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to send message to node {target_node_id}: {str(e)}"
                        }
                    ]
                }


        @tool(
            "send_email",
            "Send email through the email node",
            {
                "email_node_id": str,
                "to": str,
                "subject": str,
                "text": str
            }
        )
        async def send_email(args):
            try:
                email_node_id = args['email_node_id']
                to = args['to']
                subject = args['subject']
                text = args['text']
                await self.node.publish_event(
                   session_id=self.session.session_id,
                   event_type=EventType.SYSTEM_MESSAGE,
                   payload={
                        "to": to,
                        "subject": subject,
                        "text": text
                   },
                   target_node_id=email_node_id
                )
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Successfully sent email to {to}"
                        }
                    ]
                }
            except Exception as e:
                logger.error(
                    f"Failed to send email: {e}\n{traceback.format_exc()}"
                )
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to send email: {str(e)}"
                        }
                    ]
                }

        return create_sdk_mcp_server(
            name="mosaic-mcp-server",
            tools=[send_message, send_email]
        )


class ClaudeCodeNode(MosaicNode):
    def __init__(
        self, 
        node_id: str, 
        config: Dict[str, Any],
        zmq_server_pull_host: str,
        zmq_server_pull_port: int,
        zmq_server_pub_host: str,
        zmq_server_pub_port: int
    ):
        super().__init__(
            node_id, 
            config,
            zmq_server_pull_host,
            zmq_server_pull_port,
            zmq_server_pub_host,
            zmq_server_pub_port
        )
        
        self.workspace = Path(config["workspace"])


    async def on_start(self): ...
    async def on_stop(self): ...


    async def start_mosaic_session(
        self,
        session_id: Optional[str] = None,
        config: Dict[str, Any] = {}
    ) -> ClaudeCodeSession:
        mode = config.get("mode")
        if not mode:
            mode = "background"
            config["mode"] = mode
        
        session = Session(
            session_id=session_id or str(uuid.uuid4()),
            node_id=self.node_id,
            config=config,
            pull_host=self.zmq_server_pull_host,
            pull_port=self.zmq_server_pull_port,
            pub_host=self.zmq_server_pub_host,
            pub_port=self.zmq_server_pub_port,
            status="open",
            created_at=datetime.now().isoformat()
        )
        logger.info(f"Starting session {session} in {mode} mode")
        claude_code_session = ClaudeCodeSession(session, self)
        await claude_code_session.start()
        notify_on_session_start = self.config.get(
            "notify_on_session_start", False
        )
        if notify_on_session_start:
            logger.info(
                f"Notifying on session start for session {session}"
            )
            await claude_code_session.process_event(
                EVENTS[EventType.SYSTEM_MESSAGE](
                    event_id=str(uuid.uuid4()),
                    source_id=self.node_id,
                    target_id=self.node_id,
                    upstream_session_id=session.session_id,
                    downstream_session_id=session.session_id,
                    payload={
                        "message": "Session started"
                    },
                    created_at=datetime.now().isoformat()
                )
            )
        logger.info(f"Session {session} in {mode} mode started")
        return claude_code_session