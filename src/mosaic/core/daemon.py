import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from mosaic.core.catalog import NODE_CATALOG
from mosaic.core.models import Node
from mosaic.core.types import NodeType, NodeStatus, MeshID, NodeID
from mosaic.core.meta import list_nodes
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

SIGNULL = 0

@dataclass
class NodeState:
    node_id: NodeID
    node_type: NodeType
    pid: Optional[int]
    status: NodeStatus
    last_heartbeat: float
    crash_count: int

class ProcessManager:
    def spawn_node(self, node: Node) -> int:
        entry_module = NODE_CATALOG[node.type]["entry"]
        
        cmd = [
            sys.executable,
            "-m",
            entry_module,
            "--mesh-id", 
            node.mesh_id,
            "--node-id", 
            node.node_id,
            "--config",
            json.dumps(node.config or {})
        ]
        
        process = subprocess.Popen(cmd, cwd=os.getcwd())
        return process.pid

    def kill_node(self, pid: int, force: bool = False):
        if not self.is_running(pid):
            return
            
        try:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
        except ProcessLookupError:
            pass

    def is_running(self, pid: int) -> bool:
        try:
            os.kill(pid, SIGNULL)
            return True
        except OSError as e:
            return False

class NodeMonitor:
    def __init__(self, timeout_seconds: float = 30.0):
        self._nodes: Dict[NodeID, NodeState] = {}
        self._timeout = timeout_seconds
        
    def register_node(self, node: Node):
        self._nodes[node.node_id] = NodeState(
            node_id=node.node_id,
            node_type=node.type,
            pid=None,
            status=NodeStatus.STOPPED,
            last_heartbeat=0,
            crash_count=0
        )
        
    def update_pid(self, node_id: NodeID, pid: int):
        if node_id in self._nodes:
            self._nodes[node_id].pid = pid
            self._nodes[node_id].status = NodeStatus.RUNNING
            self._nodes[node_id].last_heartbeat = time.time()

    def record_heartbeat(self, node_id: str):
        if node_id in self._nodes:
            self._nodes[node_id].last_heartbeat = time.time()
            
    def get_node_state(self, node_id: NodeID) -> Optional[NodeState]:
        return self._nodes.get(node_id)

class RecoveryManager:
    def should_restart(self, state: NodeState) -> bool:
        return state.crash_count < 5

    def get_backoff_delay(self, crash_count: int) -> float:
        return min(30, 2 ** crash_count)

class DaemonControlServer:
    def __init__(self, mesh_id: MeshID, daemon: 'Daemon', socket_path: Path):
        self._mesh_id = mesh_id
        self._daemon = daemon
        self._socket_path = socket_path
        self._server = None

    async def start(self):
        logger.info(f"Starting daemon control server at {self._socket_path}")
        if self._socket_path.exists():
            self._socket_path.unlink()
            
        self._server = await asyncio.start_unix_server(
            self.handle_client,
            str(self._socket_path)
        )

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self._socket_path.exists():
            self._socket_path.unlink()

    async def handle_client(self, reader, writer):
        try:
            data = await reader.readline()
            if not data:
                return
                
            try:
                request = json.loads(data.decode().strip())
                response = await self._dispatch_command(request)
            except json.JSONDecodeError:
                response = {"status": "error", "error": "Invalid JSON"}
            except Exception as e:
                response = {"status": "error", "error": str(e)}
            
            writer.write(json.dumps(response).encode() + b'\n')
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()

    async def _dispatch_command(self, request: Dict[str, str]) -> Dict[str, str]:
        cmd_type = request.get("type")
        
        if cmd_type == "heartbeat":
            logger.info(f"Received heartbeat command for node {request.get('node_id')} in mesh {self._mesh_id}")
            node_id = request.get("node_id")
            if node_id:
                self._daemon._monitor.record_heartbeat(node_id)
            return {"status": "ok"}
            
        elif cmd_type == "stop":
            logger.info(f"Received stop command for mesh {self._mesh_id}")
            asyncio.create_task(self._daemon.stop())
            return {"status": "ok"}
            
        return {"status": "error", "error": f"Unknown command: {cmd_type}"}

class Daemon:
    def __init__(self, mesh_id: MeshID):
        self._mesh_id = mesh_id
        self._root_dir = Path.home() / ".mosaic" / mesh_id
        self._root_dir.mkdir(parents=True, exist_ok=True)
        
        self._process_manager = ProcessManager()
        self._monitor = NodeMonitor()
        self._recovery = RecoveryManager()
        self._server = DaemonControlServer(self._mesh_id, self, self._root_dir / "daemon.sock")
        self._running = False
        self._stop_event = asyncio.Event()
        self._monitor_task = None

    async def start(self):
        logger.info(f"Starting daemon for mesh {self._mesh_id}")
        self._running = True
        
        await self._server.start()
        
        all_nodes = list_nodes(self._mesh_id)
        for node in all_nodes:
            await self.start_node(node)
        
        logger.info(f"Starting monitor task for mesh {self._mesh_id}")
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Daemon for mesh {self._mesh_id} started")
        await self._stop_event.wait()
        logger.info(f"Daemon for mesh {self._mesh_id} stopped")

    async def stop(self):
        logger.info(f"Stopping daemon for mesh {self._mesh_id}")
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
            logger.info(f"Monitor task cancelled for mesh {self._mesh_id}")
        
        await self._server.stop()
        
        all_nodes = list_nodes(self._mesh_id)
        for node in all_nodes:
            self.stop_node(node.node_id)
        
        self._stop_event.set()

    async def start_node(self, node: Node):
        logger.info(f"Starting node {node.node_id} for mesh {self._mesh_id}")
        self._monitor.register_node(node)
        
        try:
            pid = self._process_manager.spawn_node(node)
            self._monitor.update_pid(node.node_id, pid)
            logger.info(f"Node {node.node_id} for mesh {self._mesh_id} started with PID {pid}")
        except Exception as e:
            logger.error(f"Failed to start node {node.node_id} for mesh {self._mesh_id}: {e}")
            state = self._monitor.get_node_state(node.node_id)
            if state:
                state.status = NodeStatus.FAILED

    def stop_node(self, node_id: NodeID):
        logger.info(f"Stopping node {node_id} for mesh {self._mesh_id}")
        state = self._monitor.get_node_state(node_id)
        if state and state.pid:
            self._process_manager.kill_node(state.pid)
            state.status = NodeStatus.STOPPED
            state.pid = None

    async def _monitor_loop(self):
        while self._running:
            logger.info(f"Monitoring nodes for mesh {self._mesh_id}")
            for node_id, state in self._monitor._nodes.items():
                
                if state.status != NodeStatus.RUNNING:
                    continue

                if not self._process_manager.is_running(state.pid):
                    logger.info(f"Node {node_id} for mesh {self._mesh_id} crashed")
                    state.status = NodeStatus.CRASHED
                    await self._handle_crash(node_id)
                    
                now = time.time()
                if now - state.last_heartbeat > self._monitor._timeout:
                    await self._handle_crash(node_id)
                    continue
            
            await asyncio.sleep(1.0) 

    async def _handle_crash(self, node_id: NodeID):
        state = self._monitor.get_node_state(node_id)
        if not state:
            return
            
        state.crash_count += 1
        if self._recovery.should_restart(state):
            delay = self._recovery.get_backoff_delay(state.crash_count)
            state.status = NodeStatus.BACKOFF
            await asyncio.sleep(delay)
            await self.start_node(node_id, state.node_type, state.config)
        else:
            state.status = NodeStatus.FAILED

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-id", required=True)
    args = parser.parse_args()
    
    daemon = Daemon(args.mesh_id)
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        asyncio.run(daemon.stop())