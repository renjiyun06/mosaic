from typing import Optional
from abc import ABC, abstractmethod

from mosaic.core.models import MeshEvent

class TransportBackend(ABC):
    @abstractmethod
    async def connect(self): ...
    @abstractmethod
    async def disconnect(self): ...
    @abstractmethod
    async def send(self, event: MeshEvent): ...
    @abstractmethod
    async def send_blocking(
        self, 
        event: MeshEvent, 
        timeout: float
    ) -> MeshEvent: ...
    @abstractmethod
    async def receive(self) -> MeshEvent:...
    @abstractmethod
    async def ack(self, event: MeshEvent): ...
    @abstractmethod
    async def nack(self, event: MeshEvent, reason: Optional[str] = None): ...