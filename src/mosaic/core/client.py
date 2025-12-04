import subprocess
import asyncio
import sys
import json
import uuid
from typing import Any, Dict, List, Optional

import mosaic.core.util as core_util
import mosaic.core.repository as core_repo
from mosaic.core.catalog import NODE_CATALOG
from mosaic.core.models import Mesh, MeshEvent, Subscription, Node
from mosaic.core.transport import TransportBackend
from mosaic.core.types import MeshStatus, NodeStatus, NodeType, TransportType
from mosaic.nodes.agent.types import (
    SessionRoutingStrategy,
    AgentNodeRunningMode,
)
from mosaic.nodes.agent.cc.cc_node import ClaudeCodeNode
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class EventEnvelope:
    def __init__(self, event: MeshEvent, transport: TransportBackend):
        self.event = event
        self._transport = transport
    
    async def ack(self):
        await self._transport.ack(self.event)

    async def nack(self, reason: Optional[str] = None):
        await self._transport.nack(self.event, reason)

class MeshClient:
    def __init__(self, transport: TransportBackend):
        self._transport = transport
        self._connected = False
    
    async def connect(self):
        await self._transport.connect()
        self._connected = True
    
    async def disconnect(self):
        await self._transport.disconnect()
        self._connected = False
    
    async def __aenter__(self) -> 'MeshClient':
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    async def send(self, event: MeshEvent): ...
    async def send_blocking(
        self, 
        event: MeshEvent, 
        timeout: float
    ) -> MeshEvent: ...
    async def receive(self) -> MeshEvent: ...

    async def get_subscription(
        self,
        mesh_id: str,
        source_id: str,
        target_id: str,
        event_pattern: str
    ) -> Optional[Subscription]: ...
    
    async def get_subscriptions(
        self,
        mesh_id: str,
        source_id: str,
        event_pattern: str
    ) -> List[Subscription]: ...


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
        async with asyncio.open_unix_connection(
            str(sock_path)
        ) as (reader, writer):
            try:
                request_content = json.dumps(req).encode()
                writer.write(len(request_content).to_bytes(4, "big"))
                writer.write(request_content)
                await writer.drain()
                length = int.from_bytes(await reader.read(4), "big")
                response_content = await reader.read(length)
                response = json.loads(response_content.decode("utf-8"))
                if response.get("is_error"):
                    raise RuntimeError(response.get("message"))
                return response
            finally:
                writer.close()
                await writer.wait_closed()


    async def create_mesh(self, mesh_id: str):
        mesh: Mesh = await core_repo.get_mesh(mesh_id)
        if mesh:
            raise RuntimeError(f"Mesh {mesh_id} already exists")
        mesh = Mesh(mesh_id)
        await core_repo.create_mesh(mesh)


    async def delete_mesh(self, mesh_id: str):
        raise RuntimeError("Deleting a mesh is not supported yet")

    async def list_meshes(self) -> List[Mesh]:
        return await core_repo.list_meshes()

    async def start_mesh(self, mesh_id: str):
        raise RuntimeError("Starting a mesh is not supported yet")

    async def stop_mesh(self, mesh_id: str):
        raise RuntimeError("Stopping a mesh is not supported yet")
    
    async def get_mesh_status(self, mesh_id: str) -> MeshStatus:
        raise RuntimeError("Getting the status of a mesh is not supported yet")

    
    async def create_node(
        self,
        mesh_id: str,
        node_id: str,
        node_type: NodeType, 
        config: Dict[str, str]
    ) -> Node:
        mesh: Mesh = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        node: Node = await core_repo.get_node(mesh_id, node_id)
        if node:
            raise RuntimeError(
                f"Node {node_id} already exists in mesh {mesh_id}"
            )

        node = Node(node_id, mesh_id, node_type, config)
        await core_repo.create_node(node)
        return node
    
    
    async def delete_node(self, mesh_id: str, node_id: str):
        raise RuntimeError("Deleting a node is not supported yet")

    async def list_nodes(self, mesh_id: str) -> List[Node]:
        mesh: Mesh = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")
        return await core_repo.list_nodes(mesh_id)

    async def start_node(
        self, 
        mesh_id: str, 
        node_id: str,
        transport: TransportType=TransportType.SQLITE
    ):
        node: Node = await core_repo.get_node(mesh_id, node_id)
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
                "--config", json.dumps(node.config)
            ],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )
    

    async def stop_node(self, mesh_id: str, node_id: str):
        node: Node = await core_repo.get_node(mesh_id, node_id)
        if not node:
            raise RuntimeError(f"Node {node_id} not found in mesh {mesh_id}")

        sock_path = core_util.node_sock_path(mesh_id, node_id)
        if not sock_path.exists():
            raise RuntimeError(
                f"Node {node_id} is not running in mesh {mesh_id}"
            )

        chat_sessions = await self._request_node_server(
            mesh_id, node_id, { "command": "list_chat_sessions" }
        )["sessions"]
        
        if chat_sessions:
            raise RuntimeError(
                f"Node {node_id} has active chat sessions in mesh {mesh_id}"
            )

        await self._request_node_server(
             mesh_id, node_id, { "command": "stop" }
        )
            
        
    async def get_node_status(
        self, 
        mesh_id: str, 
        node_id: str
    ) -> NodeStatus:
        node: Node = await core_repo.get_node(mesh_id, node_id)
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
        try:
            node: Node = await core_repo.get_node(mesh_id, node_id)
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

            if node.type == NodeType.CLAUDE_CODE:
                cc_node = ClaudeCodeNode(
                    mesh_id, 
                    node_id, 
                    node.config, 
                    MeshClient(transport), 
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
        try:
            node: Node = await core_repo.get_node(mesh_id, node_id)
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

            if node.type == NodeType.CLAUDE_CODE:
                cc_node = ClaudeCodeNode(
                    mesh_id, 
                    node_id, 
                    node.config, 
                    MeshClient(transport), 
                    AgentNodeRunningMode.PROGRAM
                )
                await cc_node.start_program_mode(str(uuid.uuid4()))
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
            lock_path.unlink(missing_ok=True)
        
        
    async def create_subscription(
        self,
        mesh_id: str,
        source_id: str,
        target_id: str,
        event_pattern: str,
        session_routing_strategy: SessionRoutingStrategy,
        session_routing_strategy_config: Dict[str, str]
    ): ...
    async def delete_subscription(
        self, 
        mesh_id: str, 
        source_id: str, 
        target_id: str, 
        event_pattern: str
    ): 
        raise RuntimeError("Deleting a subscription is not supported yet")
    
    async def list_subscriptions(
        self, 
        mesh_id: str, 
        source_id: str, 
        target_id: Optional[str] = None
    ) -> List[Subscription]: ...