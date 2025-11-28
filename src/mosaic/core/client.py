from typing import Optional
from mosaic.core.models import MeshEvent
from mosaic.core.transport import TransportBackend

class EventEnvelope:
    def __init__(self, event: MeshEvent, transport: TransportBackend):
        self.event = event
        self._transport = transport
    
    async def ack(self):
        await self._transport.ack(self.event)

    async def nack(self, reason: Optional[str] = None):
        await self._transport.nack(self.event, reason)

class MeshInbox:
    def __init__(self, transport: TransportBackend):
        self._transport = transport
    
    def __aiter__(self):
        return self
    
    async def __anext__(self) -> EventEnvelope: ...

class MeshOutbox:
    def __init__(self, transport: TransportBackend):
        self._transport = transport
    
    async def send(self, event: MeshEvent):
        await self._transport.send(event)

class MeshClient:
    def __init__(self, transport: TransportBackend):
        self._transport = transport
        self.inbox = MeshInbox(transport)
        self.outbox = MeshOutbox(transport)
    
    async def connect(self):
        await self._transport.connect()
    
    async def disconnect(self):
        await self._transport.disconnect()