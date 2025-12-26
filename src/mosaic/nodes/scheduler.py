import asyncio
import uuid
import traceback
from datetime import datetime
from typing import Dict, Optional, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import mosaic.core.db as db
from mosaic.core.node import MosaicNode, MosaicSession
from mosaic.core.type import Session
from mosaic.core.event import MosaicEvent, EventType
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class SchedulerSession(MosaicSession):
    def __init__(self, session: Session, node: 'SchedulerNode'):
        super().__init__(session, node)

    async def start(self): ...

    async def close(self, force: bool = False): ...

    async def process_event(self, event: MosaicEvent) -> asyncio.Future | None:
        return None


class SchedulerNode(MosaicNode):
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
        self._cron = self.config.get("cron")
        self._message = self.config.get("message")
        self._scheduler = AsyncIOScheduler()
    

    async def send_scheduler_message(self, message: str):
        try:
            subscribers = await db.list_subscribers(
                source_id=self.node_id,
                event_type=EventType.SCHEDULER_MESSAGE
            )
            for subscriber in subscribers:
                session_id = str(uuid.uuid4())
                await self.create_session(
                    session_id=session_id,
                )
                await self.publish_event(
                    session_id=session_id,
                    event_type=EventType.SCHEDULER_MESSAGE,
                    payload={
                        "message": message
                    },
                    target_node_id=subscriber.target_id
                )
        except Exception as e:
            logger.error(
                f"Failed to send scheduler message: {e}"
                f"\n{traceback.format_exc()}"
            )
            raise e
    

    async def on_start(self):
        self._scheduler.start()
        if self._cron:
            self._scheduler.add_job(
                self.send_scheduler_message,
                trigger=CronTrigger.from_crontab(self._cron),
                args=[self._message]
            )


    async def on_stop(self):
        self._scheduler.shutdown()


    async def start_mosaic_session(
        self, 
        session_id: Optional[str] = None, 
        config: Dict[str, Any] = {}
    ) -> MosaicSession:
        if not session_id:
            session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            node_id=self.node_id,
            config=config,
            pull_host=None,
            pull_port=None,
            pub_host=None,
            pub_port=None,
            status="open",
            created_at=datetime.now().isoformat()
        )
        return SchedulerSession(session, self)