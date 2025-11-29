import asyncio
import signal
import json
from pathlib import Path
from abc import ABC, abstractmethod
from mosaic.core.models import MeshEvent
from mosaic.core.client import MeshClient
from mosaic.core.types import MeshID, NodeID, TransportType
from mosaic.transport.sqlite import SqliteTransportBackend
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class BaseNode(ABC):
    def __init__(self, mesh_id: MeshID, node_id: NodeID, transport: TransportType):
        self.node_id = node_id
        self.mesh_id = mesh_id

        transport_backend = None
        if transport == TransportType.SQLITE:
            transport_backend = SqliteTransportBackend(mesh_id=mesh_id, node_id=node_id)
        else:
            raise ValueError(f"Unsupported transport: {transport}")
        
        self.client = MeshClient(transport_backend)
        self._running = False
        self._daemon_sock = Path.home() / ".mosaic" / self.mesh_id / "daemon.sock"
    

    @abstractmethod
    async def process_event(self, event: MeshEvent): ...
    @abstractmethod
    async def on_start(self): ...
    @abstractmethod
    async def on_shutdown(self): ...


    async def start(self):
        self._running = True
        loop = asyncio.get_running_loop()
        def signal_handler():
            asyncio.create_task(self._handle_stop_signal())

        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
        try:
            await self.client.connect()
            await self.on_start()
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            await self._run_forever()
        except Exception as e:
            logger.error(f"Error starting node {self.node_id} for mesh {self.mesh_id}: {e}")
        finally:
            self._running = False
            heartbeat_task.cancel()
            await self.on_shutdown()
            await self.client.disconnect()


    async def _run_forever(self):
        async for envelope in self.client.inbox:
            if not self._running:
                break
                
            try:
                await self.process_event(envelope.event)
                await envelope.ack()
            except Exception as e:
                await envelope.nack(reason=str(e))


    async def _heartbeat_loop(self):
        while self._running:
            try:
                if self._daemon_sock.exists():
                    reader, writer = await asyncio.open_unix_connection(str(self._daemon_sock))
                    
                    request = {
                        "type": "heartbeat",
                        "node_id": self.node_id
                    }
                    
                    writer.write(json.dumps(request).encode() + b'\n')
                    await writer.drain()
                    
                    # Wait for response (optional but good practice)
                    await reader.readline()
                    
                    writer.close()
                    await writer.wait_closed()
            except Exception:
                pass
            
            await asyncio.sleep(5)
    

    async def _handle_stop_signal(self):
        self._running = False
        await self.client.inbox.interrupt()