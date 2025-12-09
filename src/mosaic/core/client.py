import subprocess
import asyncio
import sys
import json
import os
import signal
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from rich.console import Console

import mosaic.core.util as core_util
import mosaic.core.repository as core_repo
from mosaic.core.catalog import NODE_CATALOG
from mosaic.core.events import get_event_names
from mosaic.core.models import Mesh, MeshEvent, Subscription, Node
from mosaic.core.transport import TransportBackend
from mosaic.core.enums import MeshStatus, NodeStatus, NodeType, TransportType
from mosaic.nodes.agent.enums import (
    SessionRoutingStrategy,
    AgentNodeRunningMode,
)
from mosaic.transport.sqlite import SqliteTransportBackend
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

console = Console()

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
    async def _request_node_server(
        self,
        mesh_id: str,
        node_id: str,
        req: Dict[str, Any]
    ) -> Dict[str, Any]:
        sock_path = core_util.node_sock_path(mesh_id, node_id)
        if not sock_path.exists():
            raise RuntimeError(
                f"Node {node_id} is not running in mesh {mesh_id}"
            )

        reader, writer = await asyncio.open_unix_connection(str(sock_path))
        try:
            request_content = json.dumps(req, ensure_ascii=False)
            logger.info(
                f"Sending request to node {node_id} in mesh {mesh_id}: "
                f"{request_content}"
            )
            request_content_bytes = request_content.encode()
            writer.write(len(request_content_bytes).to_bytes(4, "big"))
            writer.write(request_content_bytes)
            await writer.drain()
            length = int.from_bytes(await reader.readexactly(4), "big")
            response_content = (await reader.readexactly(length)).decode("utf-8")
            response = json.loads(response_content)
            if response.get("is_error"):
                raise RuntimeError(response.get("message"))
            return response
        finally:
            writer.close()
            await writer.wait_closed()


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

    async def stop_mesh(self, mesh_id: str):
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")
        
        nodes: List[Node] = await core_repo.list_nodes(mesh_id)
        for node in nodes:
            await self.stop_node(mesh_id, node.node_id)
    

    async def get_mesh_status(self, mesh_id: str) -> MeshStatus:
        raise RuntimeError("Getting the status of a mesh is not supported yet")

    
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
    

    async def stop_node(self, mesh_id: str, node_id: str):
        node = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise RuntimeError(f"Node {node_id} not found in mesh {mesh_id}")

        sock_path = core_util.node_sock_path(mesh_id, node_id)
        if not sock_path.exists():
            raise RuntimeError(
                f"Node {node_id} is not running in mesh {mesh_id}"
            )

        chat_sessions = (await self._request_node_server(
            mesh_id, node_id, { "command": "list_chat_sessions" }
        )).get("sessions", [])
        
        if chat_sessions:
            raise RuntimeError(
                f"Node {node_id} has active chat sessions in mesh {mesh_id}"
            )

        pid_path = core_util.node_pid_path(mesh_id, node_id)
        if not pid_path.exists():
            raise RuntimeError(
                f"Node {node_id} is not running in mesh {mesh_id}"
            )

        pid = pid_path.read_text()
        os.kill(int(pid), signal.SIGTERM)
        
        
    async def get_node_status(
        self, 
        mesh_id: str, 
        node_id: str
    ) -> NodeStatus:
        node = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise RuntimeError(f"Node {node_id} not found in mesh {mesh_id}")

        sock_path = core_util.node_sock_path(mesh_id, node_id)
        if not sock_path.exists():
            return NodeStatus.STOPPED

        res = await self._request_node_server(
            mesh_id, node_id, { "command": "status" }
        )
        return NodeStatus(res.get("status"))


    async def chat_node(
        self, 
        mesh_id: str, 
        node_id: str, 
        transport: TransportType
    ):
        session_id = None
        try:
            node = await core_repo.get_node(mesh_id, node_id)
            if not node:
                raise RuntimeError(
                    f"Node {node_id} not found in mesh {mesh_id}"
                )

            if node.type not in [
                NodeType.CLAUDE_CODE,
                NodeType.CODEX,
                NodeType.GEMINI,
                NodeType.CURSOR,
                NodeType.OPENHANDS
            ]:
                raise RuntimeError(
                    f"Node {node_id} is not an agent node in mesh {mesh_id}"
                )

            lock_path = core_util.node_lock_path(mesh_id, node_id)
            if lock_path.exists():
                raise RuntimeError(
                    f"Node {node_id} is busy in mesh {mesh_id}"
                )

            pid_path = core_util.node_pid_path(mesh_id, node_id)
            if not pid_path.exists():
                raise RuntimeError(
                    f"Node {node_id} is not running in mesh {mesh_id}"
                )

            sock_path = core_util.node_sock_path(mesh_id, node_id)
            if not sock_path.exists():
                raise RuntimeError(
                    f"Node {node_id} is not running in mesh {mesh_id}"
                )

            session_id = str(uuid.uuid4())
            await self._request_node_server(
                mesh_id,
                node_id,
                {
                    "command": "register_chat_session",
                    "session_id": session_id
                }
            )

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
                    MeshClient(
                        mesh_id,
                        node_id,
                        transport_backend
                    ), 
                    AgentNodeRunningMode.CHAT
                )
                await cc_node.start_chat_mode(session_id)
                await cc_node.chat()
                await cc_node.stop_chat_mode()
            elif node.type == NodeType.CODEX: ...
            elif node.type == NodeType.GEMINI: ...
            elif node.type == NodeType.CURSOR: ...
            elif node.type == NodeType.OPENHANDS: ...
        finally:
            if session_id:
                await self._request_node_server(
                    mesh_id,
                    node_id,
                    {
                        "command": "unregister_chat_session",
                        "session_id": session_id
                    }
                )

        
    async def program_node(
        self, 
        mesh_id: str, 
        node_id: str,
        transport: TransportType
    ):
        lock_path = None
        try:
            node = await core_repo.get_node(mesh_id, node_id)
            if not node:
                raise RuntimeError(
                    f"Node {node_id} not found in mesh {mesh_id}"
                )

            pid_path = core_util.node_pid_path(mesh_id, node_id)
            if pid_path.exists():
                raise RuntimeError(
                    f"Node {node_id} is currently running in mesh {mesh_id}"
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
                    AgentNodeRunningMode.PROGRAM
                )
                session_id = str(uuid.uuid4())
                await cc_node.start_program_mode(session_id)
                await cc_node.program()
                await cc_node.stop_program_mode()
            elif node.type == NodeType.CODEX: ...
            elif node.type == NodeType.GEMINI: ...
            elif node.type == NodeType.CURSOR: ...
            elif node.type == NodeType.OPENHANDS: ...
            else:
                raise RuntimeError(
                    f"Node {node_id} is not an agent node in mesh {mesh_id}"
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
                    f"Node {source_id} not found in mesh {mesh_id}"
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
        node_id: str
    ) -> List[Dict[str, Any]]:
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        node: Optional[Node] = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise RuntimeError(f"Node {node_id} not found in mesh {mesh_id}")

        try:
            return (await self._request_node_server(
                mesh_id, node_id, { "command": "list_background_sessions" }
            )).get("sessions", [])
        except Exception as e:
            logger.error(
                f"Failed to list sessions for node {node_id} in mesh {mesh_id}: "
                f"{e}"
            )
            raise RuntimeError(
                f"Failed to list sessions for "
                f"node {node_id} in mesh {mesh_id}: {e}"
            )

    
    async def tail_session(
        self,
        mesh_id: str,
        node_id: str,
        session_id: str
    ):
        mesh: Optional[Mesh] = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        node: Optional[Node] = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise RuntimeError(f"Node {node_id} not found in mesh {mesh_id}")

        session_log_path = core_util.session_log_path(
            mesh_id, node_id, session_id
        )
        if not session_log_path.exists():
            raise RuntimeError(
                f"Session {session_id} not found for "
                f"node {node_id} in mesh {mesh_id}"
            )

        process = await asyncio.create_subprocess_exec(
            'tail', '-f', str(session_log_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
    
        try:
            assistant_message_started = False
            async for line in process.stdout:
                line_content = line.decode('utf-8')
                if not line_content.strip():
                    continue
                json_line = json.loads(line_content)
                role = json_line.get("role")
                message = json_line.get("message")
                if role == "User":
                    assistant_message_started = False
                    console.print(f"> {message}")
                elif role == "Assistant":
                    if not assistant_message_started:
                        console.print(f"• {message}")
                        assistant_message_started = True
                    else:
                        console.print(message)
                elif role == "System":
                    assistant_message_started = False
                    console.print(message, style="dim")
        except KeyboardInterrupt:
            process.terminate()
            await process.wait()
        