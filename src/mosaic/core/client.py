import subprocess
import asyncio
import sys
import json
import os
import signal
import uuid
import zmq
import zmq.asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from rich.console import Console
from prompt_toolkit.patch_stdout import StdoutProxy
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

import mosaic.core.util as core_util
import mosaic.core.repository as core_repo
from mosaic.core.catalog import NODE_CATALOG
from mosaic.core.events import get_event_names
from mosaic.core.models import Mesh, MeshEvent, Subscription, Node
from mosaic.core.transport import TransportBackend
from mosaic.core.enums import NodeType, TransportType
from mosaic.nodes.agent.enums import (
    SessionRoutingStrategy,
    SessionMode,
)
from mosaic.transport.sqlite import SqliteTransportBackend
from mosaic.utils.zmq import BroadcastClient
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class MeshClient:
    def __init__(
        self, 
        mesh_id: str,
        node_id: str,
        transport: TransportBackend
    ):
        self._mesh_id = mesh_id
        self._node_id = node_id
        self._transport = transport
        self._connected = False
        self._pending_replies: Dict[str, asyncio.Future[MeshEvent]] = {}
        
    
    async def connect(self):
        logger.info(
            f"Connecting to transport {self._transport.__class__.__name__} "
            f"for node {self._node_id} in mesh {self._mesh_id}"
        )
        try:
            await self._transport.connect()
        except Exception as e:
            logger.error(
                f"Failed to connect to transport "
                f"{self._transport.__class__.__name__} "
                f"for node {self._node_id} in mesh {self._mesh_id}: {e}"
            )
            raise
        
        logger.info(
            f"Connected to transport {self._transport.__class__.__name__} "
            f"for node {self._node_id} in mesh {self._mesh_id}"
        )
        self._connected = True
    
    async def disconnect(self):
        await self._transport.disconnect()
        self._connected = False
    
    async def __aenter__(self) -> 'MeshClient':
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    async def send(self, event: MeshEvent):
        logger.info(
            f"Sending event {event.model_dump_json()} to transport "
            f"{self._transport.__class__.__name__} for node {self._node_id} "
            f"in mesh {self._mesh_id}"
        )
        await self._transport.send(event)

    async def send_blocking(
        self, 
        event: MeshEvent, 
        timeout: float
    ) -> MeshEvent: ...


    def wait_reply(self, event_id: str) -> asyncio.Future[MeshEvent]:
        if event_id in self._pending_replies:
            return self._pending_replies[event_id]
        
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_replies[event_id] = future
        return future


    async def receive(self) -> Optional[MeshEvent]:
        event = await self._transport.receive()
        if event.reply_to and event.reply_to in self._pending_replies:
            self._pending_replies[event.reply_to].set_result(event)
            del self._pending_replies[event.reply_to]
            return None
        else:
            return event

    async def ack(self, event: MeshEvent):
        logger.info(
            f"Acknowledging event {event.event_id} "
            f"to transport {self._transport.__class__.__name__} "
            f"for node {self._node_id} in mesh {self._mesh_id}"
        )
        await self._transport.ack(event)
        logger.info(
            f"Event {event.event_id} acknowledged "
            f"to transport {self._transport.__class__.__name__} "
            f"for node {self._node_id} in mesh {self._mesh_id}"
        )

    async def nack(self, event: MeshEvent, reason: Optional[str] = None):
        await self._transport.nack(event, reason)

    async def mark_processing(self, event: MeshEvent):
        await self._transport.mark_processing(event)

    async def get_subscription(
        self,
        mesh_id: str,
        source_id: str,
        target_id: str,
        event_pattern: str
    ) -> Optional[Subscription]:
        return await core_repo.get_subscription(
            mesh_id, source_id, target_id, event_pattern
        )
    
    async def get_subscribers(
        self,
        mesh_id: str,
        target_id: str,
        event_pattern: Optional[str] = None
    ) -> List[Subscription]:
        return await core_repo.list_subscribers(
            mesh_id, target_id, event_pattern
        )

    async def get_subscriptions(
        self,
        mesh_id: str,
        source_id: str,
    ) -> List[Subscription]:
        return await core_repo.list_subscriptions(
            mesh_id, source_id
        )

    async def get_event(self, event_id: str) -> Optional[MeshEvent]:
        return await self._transport.get_event(event_id)


class AdminClient:
    async def _request_node_zmq_server(
        self,
        mesh_id: str,
        node_id: str,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        zmq_sock_path = core_util.node_zmq_sock_path(mesh_id, node_id)
        if not zmq_sock_path.exists():
            raise RuntimeError(
                f"Node {node_id} is not running in mesh {mesh_id}"
            )
        try:
            context = zmq.asyncio.Context()
            socket = context.socket(zmq.REQ)
            socket.connect("ipc://" + str(zmq_sock_path))
            await socket.send_json(request)
            response = await socket.recv_json()
            if response.get("is_error"):
                raise RuntimeError(response.get("message"))
            return response.get("response")
        finally:
            socket.close()
            context.term()


    async def create_mesh(self, mesh_id: str):
        mesh = await core_repo.get_mesh(mesh_id)
        if mesh:
            raise RuntimeError(f"Mesh {mesh_id} already exists")
        mesh = Mesh(mesh_id=mesh_id)
        await core_repo.create_mesh(mesh)

    async def delete_mesh(self, mesh_id: str):
        raise RuntimeError("Deleting a mesh is not supported yet")

    async def list_meshes(self) -> List[Mesh]:
        return await core_repo.list_meshes()

    async def start_mesh(
        self, 
        mesh_id: str,
        transport: TransportType
    ):
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")
        
        nodes: List[Node] = await core_repo.list_nodes(mesh_id)
        for node in nodes:
            await self.start_node(mesh_id, node.node_id, transport)

    async def stop_mesh(self, mesh_id: str, force: bool):
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")
        
        nodes: List[Node] = await core_repo.list_nodes(mesh_id)
        for node in nodes:
            try:
                await self.stop_node(mesh_id, node.node_id, force)
            except Exception as e:
                if force:
                    continue
                else:
                    raise e
    
    
    async def create_node(
        self,
        mesh_id: str,
        node_id: str,
        node_type: NodeType, 
        config: Dict[str, str]
    ) -> Node:
        mesh = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        node = await core_repo.get_node(mesh_id, node_id)
        if node:
            raise RuntimeError(
                f"Node {node_id} already exists in mesh {mesh_id}"
            )

        if node_type == NodeType.CLAUDE_CODE:
            workspace = config.get("workspace")
            if not workspace:
                raise RuntimeError("Workspace is required for cc node")
            workspace = Path(workspace)
            if not workspace.is_absolute():
                raise RuntimeError("Workspace must be an absolute path")

            nodes = await core_repo.list_nodes_by_type(NodeType.CLAUDE_CODE)
            for node in nodes:
                if Path(node.config.get("workspace")).resolve() \
                                                == workspace.resolve():
                    raise RuntimeError(
                        f"Workspace {workspace} is already used by "
                        f"node {node.node_id} in mesh {node.mesh_id}"
                    )


        node = Node(
            node_id=node_id, 
            mesh_id=mesh_id, 
            type=node_type, 
            config=config
        )
        await core_repo.create_node(node)
        return node


    async def get_node(self, mesh_id: str, node_id: str) -> Node:
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        node: Optional[Node] = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise RuntimeError(f"Node {node_id} not found in mesh {mesh}")
        return node
    

    async def update_node_config(
        self,
        mesh_id: str,
        node_id: str,
        config: Dict[str, str]
    ):
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        node: Optional[Node] = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise RuntimeError(f"Node {node_id} not found in mesh {mesh}")
        
        node.config = config
        await core_repo.update_node_config(node)


    async def add_node_config(
        self,
        mesh_id: str,
        node_id: str,
        config: Dict[str, str]
    ):
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        node: Optional[Node] = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise RuntimeError(f"Node {node_id} not found in mesh {mesh}")

        if not node.config:
            node.config = {}
        node.config.update(config)
        await core_repo.update_node_config(node)


    async def add_mcp_server(
        self,
        mesh_id: str,
        node_id: str,
        server_name: str,
        server_config: str
    ):
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        node: Optional[Node] = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise RuntimeError(f"Node {node_id} not found in mesh {mesh}")

        if not node.config:
            node.config = {}
        
        mcp_servers = json.loads(node.config.get("mcpServers", "{}"))
        mcp_servers[server_name] = json.loads(server_config)
        node.config["mcpServers"] = json.dumps(mcp_servers, ensure_ascii=False)
        await core_repo.update_node_config(node)
    

    async def add_label(
        self,
        mesh_id: str,
        node_id: str,
        label: str
    ):
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        node: Optional[Node] = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise RuntimeError(f"Node {node_id} not found in mesh {mesh}")

        current_labels = node.label.split(",") if node.label else []
        new_labels = label.split(",")
        for label in new_labels:
            label = label.strip()
            if label not in current_labels:
                current_labels.append(label)
        node.label = ",".join(current_labels)
        await core_repo.update_node_label(node)
    

    async def delete_node(self, mesh_id: str, node_id: str):
        raise RuntimeError("Deleting a node is not supported yet")

    async def list_nodes(self, mesh_id: str) -> List[Node]:
        mesh = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")
        return await core_repo.list_nodes(mesh_id)

    async def start_node(
        self, 
        mesh_id: str, 
        node_id: str,
        transport: TransportType
    ):
        node = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found in mesh {mesh_id}")

        lock_path = core_util.node_lock_path(mesh_id, node_id)
        if lock_path.exists():
            raise RuntimeError(
                f"Node {node_id} is busy in mesh {mesh_id}"
            )

        pid_path = core_util.node_pid_path(mesh_id, node_id)
        if pid_path.exists():
            raise RuntimeError(
                f"Node {node_id} is already running in mesh {mesh_id}"
            )

        node_entry = NODE_CATALOG[node.type]["entry"]
        subprocess.Popen(
            [
                sys.executable, "-m", node_entry,
                "--mesh-id", mesh_id,
                "--node-id", node_id,
                "--transport", transport,
                "--config", json.dumps(node.config, ensure_ascii=False)
            ],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )
    

    async def stop_node(self, mesh_id: str, node_id: str, force: bool):
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        node: Optional[Node] = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise RuntimeError(f"Node {node_id} not found in mesh {mesh}")

        node_zmq_sock_path = core_util.node_zmq_sock_path(mesh_id, node_id)
        if not node_zmq_sock_path.exists():
            raise RuntimeError(
                f"Node {node} is not running"
            )

        sessions = await self._request_node_zmq_server(
            mesh_id,
            node_id,
            {"type": "list_sessions"}
        )
        if sessions and not force:
            raise RuntimeError(
                f"Node {node_id} has active sessions in mesh {mesh_id}"
            )

        pid_path = core_util.node_pid_path(mesh_id, node_id)
        if not pid_path.exists():
            raise RuntimeError(
                f"Node {node_id} is not running in mesh {mesh_id}"
            )

        pid = pid_path.read_text()
        os.kill(int(pid), signal.SIGTERM)


    async def chat_node(
        self,
        mesh_id: str,
        node_id: str,
        session_id: Optional[str]=None
    ):
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        node: Optional[Node] = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise RuntimeError(f"Node {node_id} not found in mesh {mesh}")

        if node.type not in [
            NodeType.CLAUDE_CODE,
        ]:
            raise RuntimeError(f"Chat is not supported for node {node}")
        
        zmq_sock_path = core_util.node_zmq_sock_path(mesh_id, node_id)
        if not zmq_sock_path.exists():
            raise RuntimeError(f"Node {node} is not running")

        if session_id:
            sessions = await self._request_node_zmq_server(
                mesh_id,
                node_id,
                {"type": "list_sessions"}
            )
            if not sessions or session_id \
                not in [session.get("session_id") for session in sessions]:
                raise RuntimeError(f"Session {session_id} not found for node {node}")


        request = {
            "type": "start_chat"
        }
        if session_id:
            request["args"] = {
                "session_id": session_id
            }
        session_id = await self._request_node_zmq_server(
            mesh_id,
            node_id,
            request
        )

        console = Console(file=StdoutProxy(raw=True), force_terminal=True)
        async def process_message(message: Dict[str, Any]):
            if message.get("session_id") != session_id:
                return

            type = message.get("type")
            if type == "message":
                if message.get("role") == "assistant":
                    sub_type = message.get("sub_type")
                    if sub_type == "assistant_text":
                        console.print(f"• {message.get("message")}")
                    elif sub_type == "assistant_thinking":
                        console.print(f"• [dim italic]{message.get("message")}[/dim italic]")
                    elif sub_type == "assistant_tool_use":
                        console.print(f"• [bold cyan]{message.get("message")}[/bold cyan]")
                    
                elif message.get("role") == "user":
                    console.print(f"> [bold white on grey23]{message.get("message")}[/bold white on grey23]")
                else:
                    console.print(message.get("message"), style="dim")
            elif type == "system":
                sub_type = message.get("sub_type")
                if sub_type == "session_end":
                    logger.info(
                        f"Session {session_id} ended"
                    )
                    chat_loop_task.cancel()

        broadcast_client = BroadcastClient(
            core_util.session_broadcast_server_pull_sock_path(
                mesh_id, node_id, session_id
            ),
            core_util.session_broadcast_server_pub_sock_path(
                mesh_id, node_id, session_id
            ),
            process_message
        )
        await broadcast_client.connect()
        async def chat_loop():
            bindings = KeyBindings()
            @bindings.add('c-d')
            def submit_handler(event):
                event.current_buffer.validate_and_handle()

            prompt_session = PromptSession(
                multiline=True,
                key_bindings=bindings,
                erase_when_done=True
            )
            with patch_stdout():
                while True:
                    try:
                        user_input = await prompt_session.prompt_async("> ")
                        await broadcast_client.send({
                            "type": "message",
                            "session_id": session_id,
                            "role": "user",
                            "message": user_input
                        })
                    except (asyncio.CancelledError, KeyboardInterrupt):
                        break

        async def stop_chat():
            await broadcast_client.disconnect()
            await self._request_node_zmq_server(
                mesh_id,
                node_id,
                {
                    "type": "stop_chat",
                    "args": {"session_id": session_id}
                }
            )
        

        chat_loop_task = asyncio.create_task(chat_loop())
        chat_loop_task.add_done_callback(
            lambda _: asyncio.create_task(stop_chat())
        )
        await chat_loop_task
        
    async def program_node(
        self, 
        mesh_id: str, 
        node_id: str,
        transport: TransportType
    ):
        lock_path = None
        try:
            mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
            if not mesh:
                raise RuntimeError(f"Mesh {mesh_id} not found")

            node: Optional[Node] = await core_repo.get_node(mesh_id, node_id)
            if not node:
                raise RuntimeError(f"Node {node_id} not found in mesh {mesh}")

            pid_path = core_util.node_pid_path(mesh_id, node_id)
            if pid_path.exists():
                raise RuntimeError(
                    f"Node {node} is currently running"
                )

            lock_path = core_util.node_lock_path(mesh_id, node_id)
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.touch()

            transport_backend = None
            if transport == TransportType.SQLITE:
                transport_backend = SqliteTransportBackend(mesh_id, node_id)
            else:
                raise RuntimeError(f"Unsupported transport type: {transport}")

            if node.type == NodeType.CLAUDE_CODE:
                from mosaic.nodes.agent.cc.cc_node import ClaudeCodeNode
                cc_node = ClaudeCodeNode(
                    mesh_id, 
                    node_id, 
                    node.config, 
                    MeshClient(mesh_id, node_id, transport_backend), 
                    "program"
                )
                session_id = str(uuid.uuid4())
                await cc_node.start_program_mode(session_id)
                await cc_node.program()
                await cc_node.stop_program_mode()
            else:
                raise RuntimeError(
                    f"Program is not supported for node {node}"
                )
        finally:
            if lock_path:
                lock_path.unlink(missing_ok=True)
        
        
    async def create_subscription(
        self,
        mesh_id: str,
        source_id: str,
        target_id: str,
        event_pattern: str,
        session_routing_strategy: Optional[SessionRoutingStrategy],
        session_routing_strategy_config: Optional[Dict[str, str]]
    ):
        mesh = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        source_node = await core_repo.get_node(mesh_id, source_id)
        if not source_node:
            raise RuntimeError(
                f"Source node {source_id} not found in mesh {mesh_id}"
            )
        
        target_node = await core_repo.get_node(mesh_id, target_id)
        if not target_node:
            raise RuntimeError(
                f"Target node {target_id} not found in mesh {mesh_id}"
            )

        if session_routing_strategy and \
            session_routing_strategy not in SessionRoutingStrategy:
                raise RuntimeError(
                    f"Invalid session routing strategy: "
                    f"{session_routing_strategy}"
                )
        
        event_patterns = event_pattern.split(",")
        for event_pattern in event_patterns:
            event_pattern = event_pattern.strip()
            is_blocking = False
            if event_pattern.startswith("@"):
                is_blocking = True
                event_pattern = event_pattern[1:].strip()
            else:
                is_blocking = False
            
            event_names = get_event_names(event_pattern)
            for event_name in event_names:
                subscription = await core_repo.get_subscription(
                    mesh_id, source_id, target_id, event_name
                )
                if subscription:
                    continue
                subscription = Subscription(
                    mesh_id=mesh_id,
                    source_id=source_id,
                    target_id=target_id,
                    event_pattern=event_name,
                    is_blocking=is_blocking,
                    session_routing_strategy=session_routing_strategy,
                    session_routing_strategy_config=\
                        session_routing_strategy_config
                )
                await core_repo.create_subscription(subscription)
        

    async def delete_subscriptions(
        self, 
        mesh_id: str, 
        source_id: str, 
        target_id: str,
        event_pattern: Optional[str] = None
    ): 
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        if source_id:
            source_node = await core_repo.get_node(mesh_id, source_id)
            if not source_node:
                raise RuntimeError(f"Node {source_id} not found in mesh {mesh_id}")
        
        if target_id:
            target_node = await core_repo.get_node(mesh_id, target_id)
            if not target_node:
                raise RuntimeError(f"Node {target_id} not found in mesh {mesh_id}")
        
        event_patterns = event_pattern.split(",")
        for event_pattern in event_patterns:
            event_pattern = event_pattern.strip()
            if event_pattern.startswith("@"):
                event_pattern = event_pattern[1:].strip()
            
            event_names = get_event_names(event_pattern)
            for event_name in event_names:
                await core_repo.delete_subscription(
                    mesh_id, source_id, target_id, event_name
                )
            
    
    async def list_subscriptions(
        self, 
        mesh_id: str, 
        source_id: Optional[str] = None, 
        target_id: Optional[str] = None
    ) -> List[Subscription]:
        mesh = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        if source_id:
            source_node = await core_repo.get_node(mesh_id, source_id)
            if not source_node:
                raise RuntimeError(
                    f"Node {source_id} not found in mesh {mesh}"
                )
        
        if target_id:
            target_node = await core_repo.get_node(mesh_id, target_id)
            if not target_node:
                raise RuntimeError(
                    f"Node {target_id} not found in mesh {mesh_id}"
                )
        
        return await core_repo.list_subscriptions(mesh_id, source_id, target_id)

    
    async def list_sessions(
        self,
        mesh_id: str,
        node_id: str,
        mode: Optional[SessionMode]=None
    ) -> List[Dict[str, Any]]:
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        node: Optional[Node] = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise RuntimeError(f"Node {node} not found in mesh {mesh}")

        zmq_sock_path = core_util.node_zmq_sock_path(mesh_id, node_id)
        if not zmq_sock_path.exists():
            raise RuntimeError(
                f"Node {node} is not running"
            )

        request = {
            "type": "list_sessions"
        }
        if mode:
            request["args"] = {
                "mode": mode.value
            }
        sessions = await self._request_node_zmq_server(
            mesh_id, 
            node_id,
            request
        )
        return sessions