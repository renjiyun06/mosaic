import asyncio
import uuid
from typing import Dict, Optional, Any
from datetime import datetime

from mosaic.core.node import MosaicNode, MosaicSession
from mosaic.core.type import Session
from mosaic.core.event import MosaicEvent, EventType
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class AggregatorSession(MosaicSession):
    def __init__(self, session: Session, node: 'AggregatorNode'):
        super().__init__(session, node)

        self._queue = asyncio.Queue() 


    async def start(self): ...


    async def close(self, force: bool = False):
        if not force and not self._queue.empty():
            events = []
            while not self._queue.empty():
                mosaic_event: MosaicEvent = self._queue.get_nowait()
                events.append(mosaic_event.model_dump())

            await self.node.publish_event(
                self.session.session_id,
                EventType.EVENT_BATCH,
                {
                    "events": events
                }
            )

    
    async def process_event(self, event: MosaicEvent) -> asyncio.Future | None:
        await self._queue.put(event)


class AggregatorNode(MosaicNode):
    def __init__(
        self, 
        node_id: str, 
        config: Dict[str, Any],
        zmq_server_pull_host: str,
        zmq_server_pull_port: int,
        zmq_server_pub_host: str,
        zmq_server_pub_port: int
    ):
        super().__init__(
            node_id, 
            config,
            zmq_server_pull_host,
            zmq_server_pull_port,
            zmq_server_pub_host,
            zmq_server_pub_port
        )

    

    async def on_start(self): ...
    async def on_stop(self): ...


    async def start_mosaic_session(
        self,
        session_id: Optional[str] = None,
        config: Dict[str, Any] = {}
    ) -> MosaicSession:
        if not session_id:
            session_id = str(uuid.uuid4())
        
        session = Session(
            session_id=session_id or str(uuid.uuid4()),
            node_id=self.node_id,
            config=config,
            pull_host=None,
            pull_port=None,
            pub_host=None,
            pub_port=None,
            status="open",
            created_at=datetime.now().isoformat()
        )

        return AggregatorSession(session, self)