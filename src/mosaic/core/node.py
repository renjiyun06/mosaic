import uuid
import json
import asyncio
import traceback
from datetime import datetime
from abc import ABC, abstractmethod
from jsonschema import validate
from typing import Dict, Any, Literal, Optional, List

import mosaic.core.db as db
from mosaic.core.zmq import ZmqClient
from mosaic.core.event import EVENTS, MosaicEvent, EventType
from mosaic.core.type import Session, SessionRouting
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class MosaicSession(ABC):
    def __init__(self, session: Session, node: 'MosaicNode'):
        self.session = session
        self.node = node


    @abstractmethod
    async def start(self): ...
    @abstractmethod
    async def close(self, force: bool = False): ...
    @abstractmethod
    async def process_event(
        self, event: MosaicEvent
    ) -> asyncio.Future | None: ...


class MosaicNode(ABC):
    def __init__(
        self, 
        node_id: str, 
        config: Dict[str, Any],
        zmq_server_pull_host: str,
        zmq_server_pull_port: int,
        zmq_server_pub_host: str,
        zmq_server_pub_port: int
    ):
        self.node_id = node_id
        self.config = config
        self.zmq_server_pull_host = zmq_server_pull_host
        self.zmq_server_pull_port = zmq_server_pull_port
        self.zmq_server_pub_host = zmq_server_pub_host
        self.zmq_server_pub_port = zmq_server_pub_port
        self._zmq_client = ZmqClient(
            zmq_server_pull_host,
            zmq_server_pull_port,
            zmq_server_pub_host,
            zmq_server_pub_port,
            self.node_id,
            self.process_event,
            debug_message=f"{self.node_id}"
        )

        self._status: Literal["stopped", "running"] = "stopped"
        self._sessions: Dict[str, MosaicSession] = {}


    @property
    def sessions(self) -> List[MosaicSession]:
        return list(self._sessions.values())


    async def start(self):
        logger.info(f"Starting node {self.node_id}")
        if self._status == "stopped":
            await self.on_start()
            self._zmq_client.connect()
            self._status = "running"
        logger.info(f"Node {self.node_id} started")


    async def stop(self):
        logger.info(f"Stopping node {self.node_id}")
        if self._status == "running":
            for session_id in list(self._sessions.keys()):
                await self.close_session(session_id, force=True)
            self._zmq_client.disconnect()
            await self.on_stop()
            self._status = "stopped"
        logger.info(f"Node {self.node_id} stopped")


    async def process_event(self, event: Dict[str, Any]):
        event_type = event.get("event_type")
        event_cls = EVENTS.get(event_type)
        if not event_cls:
            logger.warning(f"Unknown event type: {event_type}")
            return
        
        payload = event.get("payload")
        payload_schema = event_cls.payload_schema()
        if payload_schema:
            validate(payload, payload_schema)
        mosaic_event: MosaicEvent = event_cls.model_validate(event)
        logger.debug(
            f"Processing event {event_type} from "
            f"{mosaic_event.source_id}#{mosaic_event.upstream_session_id}: "
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
        assert self.node_id == mosaic_event.target_id
        downstream_session_id = mosaic_event.downstream_session_id
        downstream_session = self.get_session(downstream_session_id)
        connection = await db.get_connection(
            source_id=mosaic_event.source_id,
            target_id=mosaic_event.target_id
        )
        if not downstream_session:
            if not connection:
                # This indicates that the upstream node's session has been closed,
                # but the downstream node is still sending messages to the upstream node
                logger.warning(
                    f"No downstream session found for "
                    f"{mosaic_event.source_id}#{mosaic_event.upstream_session_id} -> {mosaic_event.target_id}#{downstream_session_id}"
                    f"and no connection found from {mosaic_event.source_id} "
                    f"to {mosaic_event.target_id}"
                )
                return

            try:
                downstream_session = await self.create_session(
                    session_id=downstream_session_id
                )
            except Exception as e:
                logger.error(
                    f"Failed to create downstream session "
                    f"{downstream_session_id} for node {self.node_id}: {e}"
                    f"\n{traceback.format_exc()}"
                )
                return

        logger.debug(
            f"Session {downstream_session.session} will process event "
            f"{event_type}: {mosaic_event.model_dump_json()}"
        )
        future = await downstream_session.process_event(mosaic_event)
        if future:
            await future

        if connection:
            session_alignment = connection.config.get(
                "session_alignment", 
                "mirroring"
            )
            if session_alignment == "tasking":
                await self.close_session(downstream_session_id)
            elif event_type == EventType.SESSION_END:
                await self.close_session(downstream_session_id)

    
    async def publish_event(
        self,
        session_id: str,
        event_type: EventType, 
        payload: Dict[str, Any],
        target_node_id: Optional[str] = None
    ):
        event_cls = EVENTS.get(event_type)
        if not event_cls:
            raise RuntimeError(f"Unknown event type: {event_type}")

        payload_schema = event_cls.payload_schema()
        if payload_schema:
            validate(payload, payload_schema)
        logger.info(
            f"Publishing event {event_type} from {self.node_id}#{session_id}: "
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
        events = None
        if target_node_id:
            downstream_session_id = None
            session_routing = await db.get_session_routing_by_a(
                a_node_id=self.node_id,
                a_session_id=session_id,
                b_node_id=target_node_id
            )
            if session_routing:
                downstream_session_id = session_routing.b_session_id
            else:
                connection = await db.get_connection(
                    source_id=self.node_id,
                    target_id=target_node_id
                )
                if connection:
                    downstream_session_id = str(uuid.uuid4())
                    await db.create_session_routing(
                        SessionRouting(
                            a_node_id=self.node_id,
                            a_session_id=session_id,
                            b_node_id=target_node_id,
                            b_session_id=downstream_session_id
                        )
                    )
                    await db.create_session_routing(
                        SessionRouting(
                            a_node_id=target_node_id,
                            a_session_id=downstream_session_id,
                            b_node_id=self.node_id,
                            b_session_id=session_id
                        )
                    )
                else:
                    logger.warning(
                        f"Connection not found from {self.node_id} to {target_node_id}"
                    )
                    return

            events = [
                event_cls(
                    event_id=str(uuid.uuid4()),
                    source_id=self.node_id,
                    target_id=target_node_id,
                    event_type=event_type,
                    upstream_session_id=session_id,
                    downstream_session_id=downstream_session_id,
                    payload=payload,
                    created_at=datetime.now().isoformat()
                )
            ]

        else:
            subscribers = await db.list_subscribers(
                source_id=self.node_id,
                event_type=event_type
            )
            logger.debug(
                f"Event {event_type} from {self.node_id}#{session_id} has "
                f"{len(subscribers)} subscribers: "
                f"{json.dumps([subscriber.target_id for subscriber in subscribers], ensure_ascii=False)}"
            )
            events = []
            for subscriber in subscribers:
                downstream_session_id = None
                connection = await db.get_connection(
                    source_id=self.node_id,
                    target_id=subscriber.target_id
                )
                session_alignment = connection.config.get(
                    "session_alignment", 
                    "mirroring"
                )
                
                new_session_routing = False
                if session_alignment == "tasking":
                    downstream_session_id = str(uuid.uuid4())
                    new_session_routing = True
                else:
                    session_routing = await db.get_session_routing_by_a(
                        a_node_id=self.node_id,
                        a_session_id=session_id,
                        b_node_id=subscriber.target_id
                    )
                    if session_routing:
                        downstream_session_id = session_routing.b_session_id
                    else:
                        downstream_session_id = str(uuid.uuid4())
                        new_session_routing = True
                
                if new_session_routing:
                    await db.create_session_routing(
                        SessionRouting(
                            a_node_id=self.node_id,
                            a_session_id=session_id,
                            b_node_id=subscriber.target_id,
                            b_session_id=downstream_session_id
                        )
                    )
                    await db.create_session_routing(
                        SessionRouting(
                            a_node_id=subscriber.target_id,
                            a_session_id=downstream_session_id,
                            b_node_id=self.node_id,
                            b_session_id=session_id
                        )
                    )
                
                events.append(
                    event_cls(
                        event_id=str(uuid.uuid4()),
                        source_id=self.node_id,
                        target_id=subscriber.target_id,
                        event_type=event_type,
                        upstream_session_id=session_id,
                        downstream_session_id=downstream_session_id,
                        payload=payload,
                        created_at=datetime.now().isoformat()
                    )
                )

        for event in events:
            await self._zmq_client.send(
                event.target_id, event.model_dump()
            )


    def get_session(self, session_id: str) -> Optional[MosaicSession]:
        session = self._sessions.get(session_id, None)
        if session:
            return session
        else:
            return None


    async def create_session(
        self,
        session_id: Optional[str] = None,
        config: Dict[str, Any] = {}
    ) -> MosaicSession:
        mosaic_session = await self.start_mosaic_session(session_id, config)
        self._sessions[mosaic_session.session.session_id] = mosaic_session
        return mosaic_session


    async def close_session(self, session_id: str, force: bool = False):
        try:
            mosaic_session = self._sessions.get(session_id, None)
            if mosaic_session:
                await mosaic_session.close(force=force)
                del self._sessions[session_id]
        except Exception as e:
            logger.error(
                f"Failed to close session {session_id} for node {self.node_id}: "
                f"{e}\n{traceback.format_exc()}"
            )


    @abstractmethod
    async def on_start(self): ...
    @abstractmethod
    async def on_stop(self): ...
    @abstractmethod
    async def start_mosaic_session(
        self,
        session_id: Optional[str] = None,
        config: Dict[str, Any] = {}
    ) -> MosaicSession: ...