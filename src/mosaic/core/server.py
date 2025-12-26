import uvicorn
import traceback
import os
from contextlib import asynccontextmanager
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, APIRouter
from typing import Dict, Any, Optional, List

import mosaic.core.db as db
from mosaic.core.type import Node, NodeType, Subscription, Connection
from mosaic.core.zmq import ZmqServer, ZmqClient
from mosaic.core.node import MosaicNode
from mosaic.nodes.agent.claude_code import ClaudeCodeNode
from mosaic.nodes.aggregator import AggregatorNode
from mosaic.nodes.email import EmailNode
from mosaic.nodes.scheduler import SchedulerNode
from mosaic.nodes.reddit_scraper import RedditScraperNode
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

_NODES = {
    NodeType.CLAUDE_CODE: ClaudeCodeNode,
    NodeType.AGGREGATOR: AggregatorNode,
    NodeType.EMAIL: EmailNode,
    NodeType.SCHEDULER: SchedulerNode,
    NodeType.REDDIT_SCRAPER: RedditScraperNode
}

class Response(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None


class MosaicServer:
    def __init__(
        self, 
        mosaic_home: Path, 
        host: str, 
        port: int,
        zmq_server_pull_host: str,
        zmq_server_pull_port: int,
        zmq_server_pub_host: str,
        zmq_server_pub_port: int
    ):
        self._mosaic_home = mosaic_home
        self._host = host
        self._port = port
        self._app = FastAPI(lifespan=self.lifespan)
        self._router = APIRouter()
        self._setup_routes()
        self._app.include_router(self._router)

        self._zmq_server_pull_host = zmq_server_pull_host
        self._zmq_server_pull_port = zmq_server_pull_port
        self._zmq_server_pub_host = zmq_server_pub_host
        self._zmq_server_pub_port = zmq_server_pub_port
        self._zmq_server = ZmqServer(
            zmq_server_pull_host,
            zmq_server_pull_port,
            zmq_server_pub_host,
            zmq_server_pub_port
        )
        self._zmq_client = ZmqClient(
            zmq_server_pull_host,
            zmq_server_pull_port,
            zmq_server_pub_host,
            zmq_server_pub_port,
            "",
            None
        )

        self._running_nodes: Dict[str, MosaicNode] = {}

    
    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        await self._on_start()
        yield
        await self._on_shutdown()


    async def _on_start(self):
        await db.ensure_initialized(self._mosaic_home / "mosaic.db")
        self._zmq_server.start()
        self._zmq_client.connect()


    async def _on_shutdown(self):
        self._zmq_client.disconnect()
        self._zmq_server.stop()


    def _setup_routes(self):
        self._router.add_api_route(
            "/nodes", 
            self.create_node, 
            methods=["POST"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/nodes", 
            self.list_nodes, 
            methods=["GET"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/nodes/{node_id}", 
            self.get_node, 
            methods=["GET"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/nodes/{node_id}", 
            self.delete_node, 
            methods=["DELETE"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/nodes/{node_id}", 
            self.update_node, 
            methods=["PUT"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/connections/{source_id}/{target_id}", 
            self.create_connection, 
            methods=["POST"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/connections/{source_id}/{target_id}", 
            self.delete_connection, 
            methods=["DELETE"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/connections",
            self.list_connections,
            methods=["GET"],
            response_model=Response
        )
        self._router.add_api_route(
            "/nodes/{node_id}/start", 
            self.start_node, 
            methods=["POST"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/nodes/{node_id}/stop", 
            self.stop_node, 
            methods=["POST"],
            response_model=Response
        )
        self._router.add_api_route(
            "/nodes/{node_id}/restart", 
            self.restart_node, 
            methods=["POST"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/nodes/restart", 
            self.restart_all_nodes, 
            methods=["POST"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/nodes/{node_id}/events", 
            self.send_event, 
            methods=["POST"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/nodes/{node_id}/sessions/{session_id}", 
            self.get_session, 
            methods=["GET"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/nodes/{node_id}/sessions", 
            self.create_session, 
            methods=["POST"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/nodes/{node_id}/sessions", 
            self.list_sessions, 
            methods=["GET"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/nodes/{node_id}/sessions/{session_id}", 
            self.close_session, 
            methods=["DELETE"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/subscriptions", 
            self.create_subscription, 
            methods=["POST"], 
            response_model=Response
        )
        self._router.add_api_route(
            "/subscriptions", 
            self.list_subscriptions, 
            methods=["GET"], 
            response_model=Response
        )


    async def create_node(self, node: Dict[str, Any]):
        try:
            node: Node = Node(**node)
            if await db.get_node(node.node_id):
                return Response(
                    success=False, 
                    message=f"Node already exists: {node.node_id}"
                )
            
            if node.type == NodeType.CLAUDE_CODE:
                workspace = node.config.get("workspace")
                if not workspace:
                    workspace = self._mosaic_home / 'nodes' / node.node_id
                else:
                    workspace = Path(workspace)
                if not workspace.is_absolute():
                    return Response(
                        success=False, 
                        message="Workspace must be an absolute path"
                    )

                cc_nodes: List[Node] = \
                    await db.list_nodes_by_type(NodeType.CLAUDE_CODE)
                for cc_node in cc_nodes:
                    if Path(cc_node.config.get("workspace")).resolve() \
                        == workspace.resolve():
                        return Response(
                            success=False, 
                            message=f"Workspace {workspace} is already used by "
                                    f"node {cc_node.node_id}"
                        )

                workspace.mkdir(parents=True, exist_ok=True)
                if workspace != self._mosaic_home / 'nodes' / node.node_id:
                    os.symlink(
                        workspace, 
                        self._mosaic_home / 'nodes' / node.node_id
                    )

                node.config["workspace"] = workspace.as_posix()
            
            await db.create_node(node)
            return Response(success=True)
        except Exception as e:
            logger.error(
                f"Failed to create node: {e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))


    async def get_node(self, node_id: str):
        try:
            node: Optional[Node] = await db.get_node(node_id)
            if not node:
                return Response(
                    success=False, message=f"Node not found: {node_id}"
                )
            return Response(success=True, data=node.model_dump_json())
        except Exception as e:
            logger.error(
                f"Failed to get node {node_id}: {e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))

    
    async def list_nodes(self):
        try:
            nodes: List[Node] = await db.list_nodes()
            return Response(
                success=True, data=[node.model_dump_json() for node in nodes]
            )
        except Exception as e:
            logger.error(
                f"Failed to list nodes: {e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))


    async def delete_node(self, node_id: str):
        try:
            # Stop the node if it is running
            if node_id in self._running_nodes:
                mosaic_node = self._running_nodes[node_id]
                await mosaic_node.stop()
                del self._running_nodes[node_id]
        
            # Delete the related connections
            await db.delete_connections_by_source_id(node_id)
            await db.delete_connections_by_target_id(node_id)

            # Delete the related subscriptions
            await db.delete_subscriptions_by_source_id(node_id)
            await db.delete_subscriptions_by_target_id(node_id)

            # Delete the node
            await db.delete_node(node_id)
            return Response(success=True)
        except Exception as e:
            logger.error(
                f"Failed to delete node {node_id}: {e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))


    async def update_node(self, node_id: str, node: Dict[str, Any]):
        try:
            node_id = node.get("node_id")
            existing_node: Optional[Node] = await db.get_node(node_id)
            if not existing_node:
                return Response(
                    success=False, message=f"Node not found: {node_id}"
                )
            
            config = node.get("config")
            # Workspace is not allowed to be updated
            config.pop("workspace", None)
            existing_node.config.update(config)
            await db.update_node(existing_node)
            return Response(success=True)
        except Exception as e:
            logger.error(
                f"Failed to update node {node_id}: {e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))


    async def create_connection(
        self, 
        source_id: str, 
        target_id: str,
        config: Dict[str, Any]
    ):
        try:
            source_node: Optional[Node] = await db.get_node(source_id)
            if source_node is None:
                return Response(
                    success=False, message=f"Node not found: {source_id}"
                )
            target_node: Optional[Node] = await db.get_node(target_id)
            if target_node is None:
                return Response(
                    success=False, message=f"Node not found: {target_id}"
                )
            
            if await db.get_connection(source_id, target_id):
                return Response(
                    success=False, message=f"Connection already exists"
                )
            if await db.get_connection(target_id, source_id):
                return Response(
                    success=False, message=f"Connection already exists"
                )
            await db.create_connection(Connection(
                source_id=source_id,
                target_id=target_id,
                config=config
            ))
            return Response(success=True)

        except Exception as e:
            logger.error(
                "Failed to create connection from "
                f"source node {source_id} to target node {target_id}: "
                f"{e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))


    async def delete_connection(self, source_id: str, target_id: str):
        try:
            source_node: Optional[Node] = await db.get_node(source_id)
            if source_node is None:
                return Response(
                    success=False, message=f"Node not found: {source_id}"
                )
            target_node: Optional[Node] = await db.get_node(target_id)
            if target_node is None:
                return Response(
                    success=False, message=f"Node not found: {target_id}"
                )

            if not await db.get_connection(source_id, target_id):
                return Response(
                    success=False, message=f"Connection not found"
                )

            await db.delete_subscriptions_by_source_id_and_target_id(
                source_id, target_id
            )
            await db.delete_connection(source_id, target_id)
            return Response(success=True)
        
        except Exception as e:
            logger.error(
                "Failed to delete connection from "
                f"source node {source_id} to target node {target_id}: "
                f"{e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))


    async def list_connections(self):
        try:
            connections: List[Connection] = await db.list_connections()
            return Response(
                success=True, 
                data=[connection.model_dump_json() 
                        for connection in connections]
            )
        except Exception as e:
            logger.error(
                f"Failed to list connections: {e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))


    async def start_node(self, node_id: str):
        mosaic_node = None
        try:
            node: Optional[Node] = await db.get_node(node_id)
            if node is None:
                return Response(
                    success=False, message=f"Node not found: {node_id}"
                )
            if node.node_id in self._running_nodes:
                return Response(
                    success=False, message=f"Node already running: {node_id}"
                )
            mosaic_node: MosaicNode = _NODES[node.type](
                node.node_id, 
                node.config,
                self._zmq_server_pull_host,
                self._zmq_server_pull_port,
                self._zmq_server_pub_host,
                self._zmq_server_pub_port
            )
            await mosaic_node.start()
            self._running_nodes[node.node_id] = mosaic_node
            return Response(success=True)
        except Exception as e:
            logger.error(
                f"Failed to start node {node_id}: {e}\n{traceback.format_exc()}"
            )
            if mosaic_node is not None:
                await mosaic_node.stop()
            if node_id in self._running_nodes:
                del self._running_nodes[node_id]
            return Response(success=False, message=str(e))


    async def stop_node(self, node_id: str):
        mosaic_node = None
        try:
            node: Optional[Node] = await db.get_node(node_id)
            if node is None:
                return Response(
                    success=False, message=f"Node not found: {node_id}"
                )
            if node.node_id not in self._running_nodes:
                return Response(
                    success=False, message=f"Node not running: {node_id}"
                )
            mosaic_node = self._running_nodes[node.node_id]
            await mosaic_node.stop()
            del self._running_nodes[node.node_id]
            return Response(success=True)
        except Exception as e:
            logger.error(
                f"Failed to stop node {node_id}: {e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))


    async def restart_node(self, node_id: str):
        try:
            node: Optional[Node] = await db.get_node(node_id)
            if node is None:
                return Response(
                    success=False, message=f"Node not found: {node_id}"
                )
            if node.node_id in self._running_nodes:
                mosaic_node = self._running_nodes[node.node_id]
                await mosaic_node.stop()
                del self._running_nodes[node.node_id]
                
            mosaic_node: MosaicNode = _NODES[node.type](
                node.node_id, 
                node.config,
                self._zmq_server_pull_host,
                self._zmq_server_pull_port,
                self._zmq_server_pub_host,
                self._zmq_server_pub_port
            )
            await mosaic_node.start()
            self._running_nodes[node.node_id] = mosaic_node
            return Response(success=True)
        except Exception as e:
            logger.error(
                f"Failed to restart node {node_id}: {e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))
                

    async def restart_all_nodes(self):
        try:
            # Stop all running nodes
            for node in self._running_nodes.values():
                await node.stop()

            self._running_nodes.clear()

            nodes: List[Node] = await db.list_nodes()
            for node in nodes:
                mosaic_node: MosaicNode = _NODES[node.type](
                    node.node_id, 
                    node.config,
                    self._zmq_server_pull_host,
                    self._zmq_server_pull_port,
                    self._zmq_server_pub_host,
                    self._zmq_server_pub_port
                )
                await mosaic_node.start()
                self._running_nodes[node.node_id] = mosaic_node
            return Response(success=True)
        except Exception as e:
            logger.error(
                f"Failed to restart all nodes: {e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))

    
    async def send_event(self, node_id: str, event: Dict[str, Any]):
        try:
            node: Optional[Node] = await db.get_node(node_id)
            if node is None:
                return Response(
                    success=False, message=f"Node not found: {node_id}"
                )
            if node.node_id not in self._running_nodes:
                return Response(
                    success=False, message=f"Node not running: {node_id}"
                )
            await self._zmq_client.send(node.node_id, event)
            return Response(success=True)
        except Exception as e:
            logger.error(
                f"Failed to send event to node {node_id}: "
                f"{e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))

        
    async def create_subscription(self, subscription: Dict[str, Any]):
        try:
            subscription: Subscription = Subscription(**subscription)
            if not await db.get_node(subscription.source_id):
                return Response(
                    success=False, 
                    message=f"Source node not found: {subscription.source_id}"
                )
            if not await db.get_node(subscription.target_id):
                return Response(
                    success=False, 
                    message=f"Target node not found: {subscription.target_id}"
                )
            if not await db.get_connection(
                subscription.source_id, subscription.target_id
            ):
                return Response(
                    success=False,
                    message=f"Connection not found between {subscription.source_id} and {subscription.target_id}"
                )
            if await db.get_subscription(
                subscription.source_id, 
                subscription.target_id, 
                subscription.event_type
            ):
                return Response(
                    success=False, message=f"Subscription already exists"
                )
            await db.create_subscription(subscription)
            return Response(success=True)
        except Exception as e:
            logger.error(
                f"Failed to create subscription: {e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))


    async def list_subscriptions(self):
        try:
            subscriptions: List[Subscription] = await db.list_subscriptions()
            return Response(
                success=True, 
                data=[subscription.model_dump_json() 
                        for subscription in subscriptions]
            )
        except Exception as e:
            logger.error(
                f"Failed to list subscriptions: {e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))


    async def get_session(self, node_id: str, session_id: str):
        try:
            node: Optional[Node] = await db.get_node(node_id)
            if node is None:
                return Response(
                    success=False, message=f"Node not found: {node_id}"
                )
            if node.node_id not in self._running_nodes:
                return Response(
                    success=False, message=f"Node not running: {node_id}"
                )

            mosaic_node = self._running_nodes[node.node_id]
            mosaic_session = mosaic_node.get_session(session_id)
            if mosaic_session is None:
                return Response(
                    success=False, message=f"Session not found: {session_id}"
                )
            return Response(
                success=True, 
                data=mosaic_session.session.model_dump_json()
            )
        except Exception as e:
            logger.error(
                f"Failed to get session {session_id} for node {node_id}: "
                f"{e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))


    async def create_session(self, node_id: str, config: Dict[str, Any]):
        try:
            node: Optional[Node] = await db.get_node(node_id)
            if node is None:
                return Response(
                    success=False, message=f"Node not found: {node_id}"
                )
            if node.node_id not in self._running_nodes:
                return Response(
                    success=False, message=f"Node not running: {node_id}"
                )
            mosaic_node = self._running_nodes[node.node_id]
            mosaic_session = await mosaic_node.create_session(config=config)
            return Response(
                success=True, 
                data=mosaic_session.session.model_dump_json()
            )
        except Exception as e:
            logger.error(
                f"Failed to create session for node {node_id}: "
                f"{e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))

        
    async def close_session(self, node_id: str, session_id: str):
        try:
            node: Optional[Node] = await db.get_node(node_id)
            if node is None:
                return Response(
                    success=False, message=f"Node not found: {node_id}"
                )
            if node.node_id not in self._running_nodes:
                return Response(
                    success=False, message=f"Node not running: {node_id}"
                )
            mosaic_node = self._running_nodes[node.node_id]
            await mosaic_node.close_session(session_id)
            return Response(success=True)
        except Exception as e:
            logger.error(
                f"Failed to close session {session_id} for node {node_id}: "
                f"{e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))

        
    async def list_sessions(self, node_id: str):
        try:
            node: Optional[Node] = await db.get_node(node_id)
            if node is None:
                return Response(
                    success=False, message=f"Node not found: {node_id}"
                )
            if node.node_id not in self._running_nodes:
                return Response(
                    success=False, message=f"Node not running: {node_id}"
                )
            mosaic_node = self._running_nodes[node.node_id]
            return Response(
                success=True, 
                data=[session.session.model_dump_json() 
                            for session in mosaic_node.sessions]
            )
        except Exception as e:
            logger.error(
                f"Failed to list sessions for node {node_id}: {e}"
                f"\n{traceback.format_exc()}")


    def run(self):
        uvicorn.run(self._app, host=self._host, port=self._port)