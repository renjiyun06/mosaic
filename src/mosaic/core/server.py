import uvicorn
import traceback
import os
from contextlib import asynccontextmanager
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, APIRouter
from typing import Dict, Any, Optional, List

import mosaic.core.db as db
from mosaic.core.type import Node, NodeType
from mosaic.core.zmq import ZmqServer
from mosaic.core.node import MosaicNode
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

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

        self._zmq_server = ZmqServer(
            zmq_server_pull_host,
            zmq_server_pull_port,
            zmq_server_pub_host,
            zmq_server_pub_port
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


    async def _on_shutdown(self):
        self._zmq_server.stop()


    def _setup_routes(self):
        self._router.add_api_route("/nodes", self.create_node, methods=["POST"], response_model=Response)
        self._router.add_api_route("/nodes", self.list_nodes, methods=["GET"], response_model=Response)
        self._router.add_api_route("/nodes/{node_id}", self.get_node, methods=["GET"], response_model=Response)
        self._router.add_api_route("/nodes/{node_id}", self.delete_node, methods=["DELETE"], response_model=Response)
        self._router.add_api_route("/nodes/{node_id}", self.update_node, methods=["PUT"], response_model=Response)
        self._router.add_api_route("/nodes/{node_id}/start", self.start_node, methods=["POST"], response_model=Response)
        self._router.add_api_route("/nodes/{node_id}/stop", self.stop_node, methods=["POST"], response_model=Response)
        self._router.add_api_route("/nodes/{node_id}/chat", self.chat_node, methods=["POST"], response_model=Response)
        self._router.add_api_route("/nodes/{node_id}/program", self.program_node, methods=["POST"], response_model=Response)


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
        pass


    async def update_node(self, node_id: str, node: Dict[str, Any]):
        pass


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
            mosaic_node: MosaicNode = MosaicNode(
                node.node_id, node.type, node.config
            )
            await mosaic_node.start()
            self._running_nodes[node.node_id] = mosaic_node
            return Response(success=True)
        except Exception as e:
            logger.error(
                f"Failed to start node {node_id}: {e}\n{traceback.format_exc()}"
            )
            if mosaic_node is not None:
                await mosaic_node.shutdown()
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
            await mosaic_node.shutdown()
            del self._running_nodes[node.node_id]
            return Response(success=True)
        except Exception as e:
            logger.error(
                f"Failed to stop node {node_id}: {e}\n{traceback.format_exc()}"
            )
            return Response(success=False, message=str(e))


    async def chat_node(self, node_id: str):
        pass


    async def program_node(self, node_id: str):
        pass


    def run(self):
        uvicorn.run(self._app, host=self._host, port=self._port)


