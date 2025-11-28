from typing import Optional
from mosaic.core.models import MeshEvent
from mosaic.core.transport import TransportBackend

class EventEnvelope:
    async def ack(self):...
    async def nack(self, reason: Optional[str] = None): ...

class MeshInbox:
    def __init__(self, transport: TransportBackend):
        self._transport = transport
    
    def __aiter__(self): ...
    async def __anext__(self) -> EventEnvelope: ...

class MeshOutbox:
    def __init__(self, transport: TransportBackend):
        self._transport = transport
    
    async def send(self, event: MeshEvent): ...

class MeshClient:
    def __init__(self, transport: TransportBackend):
        self._transport = transport
        self.inbox = MeshInbox(transport)
        self.outbox = MeshOutbox(transport)
    
    async def connect(self): ...
    async def disconnect(self): ...