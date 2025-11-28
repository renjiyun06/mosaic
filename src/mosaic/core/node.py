import asyncio
from pathlib import Path
from abc import ABC, abstractmethod
from mosaic.core.models import MeshEvent
from mosaic.core.client import MeshClient
from mosaic.core.types import MeshID, NodeID, TransportType
from mosaic.transport.sqlite import SqliteTransportBackend

class BaseNode(ABC):
    def __init__(self, mesh_id: MeshID, node_id: NodeID, transport: TransportType):
        self._node_id = node_id
        self._mesh_id = mesh_id

        transport_backend = None
        if transport == TransportType.SQLITE:
            transport_backend = SqliteTransportBackend(mesh_id=mesh_id, node_id=node_id)
        else:
            raise ValueError(f"Unsupported transport: {transport}")
        
        self._client = MeshClient(transport_backend)
        self._running = False
        self._daemon_sock = Path.home() / ".mosaic" / self._mesh_id / "daemon.sock"
    
    @abstractmethod
    async def process_event(self, event: MeshEvent): ...
    @abstractmethod
    async def on_start(self): ...
    @abstractmethod
    async def on_shutdown(self): ...
    async def start(self): ...
    async def _run_forever(self): ...
    async def _heartbeat_loop(self):
        while self._running:
            try:
                if self._daemon_sock.exists():
                    _, writer = await asyncio.open_unix_connection(str(self._daemon_sock))
                    writer.write(b"PING\n")
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
            except Exception:
                pass
            
            await asyncio.sleep(5)
    
    async def _handle_stop_signal(self): ...