import subprocess
import asyncio
import sys
import json
import os
import signal
import uuid
from typing import Any, Dict, List, Optional

import mosaic.core.util as core_util
import mosaic.core.repository as core_repo
from mosaic.core.catalog import NODE_CATALOG
from mosaic.core.events import get_event_names
from mosaic.core.models import Mesh, MeshEvent, Subscription, Node
from mosaic.core.transport import TransportBackend
from mosaic.core.types import MeshStatus, NodeStatus, NodeType, TransportType
from mosaic.nodes.agent.types import (
    SessionRoutingStrategy,
    AgentNodeRunningMode,
)
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class MeshClient:
    def __init__(
        self, 
        mesh_id: str,
        node_id: str,
        transport: TransportBackend):
        self._mesh_id = mesh_id
        self._node_id = node_id
        self._transport = transport
        self._connected = False
    
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
        await self._transport.send(event)

    async def send_blocking(
        self, 
        event: MeshEvent, 
        timeout: float
    ) -> MeshEvent: ...


    async def receive(self) -> MeshEvent:
        return await self._transport.receive()

    async def ack(self, event: MeshEvent):
        await self._transport.ack(event)

    async def nack(self, event: MeshEvent, reason: Optional[str] = None):
        await self._transport.nack(event, reason)

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
    ) -> List[Subscription]:
        subscriptions = await core_repo.list_subscriptions(
            mesh_id, source_id
        )
        return [subscription for subscription in subscriptions \
            if subscription.event_pattern == event_pattern]

    async def get_subscribers(
        self,
        mesh_id: str,
        target_id: str,
        event_pattern: str
    ) -> List[Subscription]:
        return await core_repo.list_subscribers(
            mesh_id, target_id, event_pattern
        )

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
            request_content = json.dumps(req)
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
        mesh = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

        node = await core_repo.get_node(mesh_id, node_id)
        if node:
            raise RuntimeError(
                f"Node {node_id} already exists in mesh {mesh_id}"
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
                "--config", json.dumps(node.config)
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
                from mosaic.nodes.agent.cc.cc_node import ClaudeCodeNode
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
                from mosaic.nodes.agent.cc.cc_node import ClaudeCodeNode
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
        target_id: str
    ): 
        raise RuntimeError("Deleting a subscription is not supported yet")
    
    async def list_subscriptions(
        self, 
        mesh_id: str, 
        source_id: str, 
        target_id: Optional[str] = None
    ) -> List[Subscription]:
        mesh = await core_repo.get_mesh(mesh_id)
        if not mesh:
            raise RuntimeError(f"Mesh {mesh_id} not found")

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
        
        subscriptions = []
        if target_id:
            subscriptions = await core_repo.list_subscriptions(mesh_id, source_id, target_id)
        else:
            subscriptions = await core_repo.list_subscriptions(mesh_id, source_id)
        return subscriptions