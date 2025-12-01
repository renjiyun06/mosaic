import os
import asyncio
from pathlib import Path
from typing import List, Optional
from mosaic.core.models import MeshEvent
from mosaic.core.transport import TransportBackend
from mosaic.core.types import MeshID, NodeID

class EventRepository:
    def __init__(self, db_path: Path): ...
    async def save(self, event: MeshEvent): ...
    async def fetch_pending(self, target_id: NodeID, limit: int) -> List[MeshEvent]: ...

class SignalClient:
    def __init__(self, socket_dir: Path): ...
    async def notify(self, target_id: NodeID): ...

class SignalListener:
    def __init__(self, socket_path: Path):
        self._socket_path = socket_path
        self._server = None
        self._signal_received = asyncio.Event()


    async def start(self):
        if self._socket_path.exists():
            try:
                os.unlink(self._socket_path)
            except OSError:
                pass
        
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)

        self._server = await asyncio.start_unix_server(
            self._handle_client, 
            path=str(self._socket_path)
        )


    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            try:
                os.unlink(self._socket_path)
            except OSError:
                pass


    async def _handle_client(self, reader, writer):
        try:
            data = await reader.read(1024)
            if data:
                self._signal_received.set()
        except Exception:
            pass
        finally:
            writer.close()


    async def wait_for_signal(self):
        await self._signal_received.wait()
        self._signal_received.clear()


class SqliteTransportBackend(TransportBackend):
    def __init__(self, mesh_id: MeshID, node_id: NodeID):
        self._mesh_id = mesh_id
        self._node_id = node_id
        self._db_path = Path.home() / ".mosaic" / mesh_id / "events.db"
        self._socket_dir = Path.home() / ".mosaic" / mesh_id / "sockets" / "sqlite_transport"
        self._socket_path = self._socket_dir / f"{node_id}.sock"
        self._repo = EventRepository(self._db_path)
        self._signal_client = SignalClient(self._socket_dir)
        self._signal_listener = SignalListener(self._socket_path)

    async def connect(self):
        await self._signal_listener.start()

    async def disconnect(self):
        await self._signal_listener.stop()
    
    async def send(self, event: MeshEvent):
        await self._repository.save(event)
        await self._signal_client.notify(event.target_id)

    async def receive(self, stop_event: Optional[asyncio.Event] = None) -> Optional[MeshEvent]:
        while True:
            if stop_event and stop_event.is_set():
                return None

            events = await self._repo.fetch_pending(self._node_id, limit=1)
            if events:
                return events[0]
            
            wait_signal = asyncio.create_task(self._signal_listener.wait_for_signal())
            
            pending_tasks = [wait_signal]
            if stop_event:
                wait_stop = asyncio.create_task(stop_event.wait())
                pending_tasks.append(wait_stop)
            
            _, pending = await asyncio.wait(
                pending_tasks, 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in pending:
                task.cancel()
                
            if stop_event and stop_event.is_set():
                return None

        
    async def ack(self, event: MeshEvent): ...
    async def nack(self, event: MeshEvent, reason: Optional[str] = None): ...