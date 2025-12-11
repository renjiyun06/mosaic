import uuid
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List, Literal

import mosaic.core.util as core_util
from mosaic.core.events import get_event_definition
from mosaic.core.node import BaseNode
from mosaic.core.client import MeshClient
from mosaic.core.models import MeshEvent, SessionTrace, Subscription
from mosaic.nodes.agent.enums import (
    SessionMode,
    SessionRoutingStrategy as Strategy,
)
from mosaic.utils.zmq import BroadcastServer, BroadcastClient
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class Session(ABC):
    def __init__(self, session_id: str, node: 'AgentNode', mode: SessionMode):
        self.session_id = session_id
        self.node = node
        self.mode = mode
        self.broadcast_server = BroadcastServer(
            core_util.session_broadcast_server_pull_sock_path(
                node.mesh_id, node.node_id, session_id
            ),
            core_util.session_broadcast_server_pub_sock_path(
                node.mesh_id, node.node_id, session_id
            )
        )
        self.broadcast_client = BroadcastClient(
            core_util.session_broadcast_server_pull_sock_path(
                node.mesh_id, node.node_id, session_id
            ),
            core_util.session_broadcast_server_pub_sock_path(
                node.mesh_id, node.node_id, session_id
            ),
            self.process_message
        )


    async def start(self):
        await self.broadcast_server.start()
        await self.broadcast_client.connect()
        await self.on_start()


    async def close(self):
        await self.on_close()
        await self.broadcast_client.disconnect()
        await self.broadcast_server.stop()

    
    async def publish_event(
        self,
        event_type: str,
        payload: Dict[str, Any]
    ):
        subscriber_subscriptions = await self.node.client.get_subscribers(
            self.node.mesh_id,
            self.node.node_id,  # source id sub target id
            event_type
        )
        if not subscriber_subscriptions:
            return

        for subscription in subscriber_subscriptions:
            mesh_event = get_event_definition(event_type).to_mesh_event(
                event_id=str(uuid.uuid4()),
                mesh_id=self.node.mesh_id,
                source_id=self.node.node_id,
                target_id=subscription.source_id,
                payload=payload,
                session_trace=SessionTrace(
                    upstream_session_id=self.session_id,
                    downstream_session_id=None
                ),
                reply_to=None,
                created_at=datetime.now(),
            )
            await self.node.client.send(mesh_event)


    @abstractmethod
    async def on_start(self): ...
    @abstractmethod
    async def on_close(self): ...
    @abstractmethod
    async def process_event(self, event: MeshEvent): ...
    @abstractmethod
    async def process_message(self, message: Dict[str, Any]): ...

    def __str__(self):
        return f"{self.node.mesh_id}#{self.node.node_id}#{self.session_id}"


class SessionManager:
    def __init__(self, node: 'AgentNode'):
        self._node = node
        self.sessions: Dict[str, Session] = {}
    
    def get_session(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id, None)

    async def create_session(self, mode: SessionMode) -> Session:
        session = await self._node.create_session(mode)
        self.sessions[session.session_id] = session
        await session.start()
        return session

    async def close_session(self, session: Session):
        del self.sessions[session.session_id]
        await session.close()


class SessionRoutingStrategy(ABC):
    @abstractmethod
    async def route(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ) -> Session: ...

    @abstractmethod
    def session_retained(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ) -> bool: ...



class MirroringStrategy(SessionRoutingStrategy):
    def __init__(self, session_manager: SessionManager):
        self._session_manager = session_manager
        # topic -> upstream_session_id -> session
        self._sessions: Dict[str, Dict[str, Session]] = {} 


    async def route(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ) -> Session:
        config = subscription.session_routing_strategy_config or {}
        topic = config.get("topic", "default")
        upstream_session_id = event.session_trace.upstream_session_id
        session = self._sessions.get(topic, {}).get(upstream_session_id, None)
        if session:
            logger.info(
                f"Mirroring strategy: session {session} already exists for "
                f"topic {topic} and upstream session {upstream_session_id}"
            )
            return session
        else:
            logger.info(
                f"Mirroring strategy: creating new session for "
                f"topic {topic} and upstream session {upstream_session_id}"
            )
            session = await self._session_manager.create_session(
                SessionMode.BACKGROUND
            )
            if topic not in self._sessions:
                self._sessions[topic] = {}
            self._sessions[topic][upstream_session_id] = session
            return session
    

    def session_retained(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ) -> bool:
        config = subscription.session_routing_strategy_config or {}
        topic = config.get("topic", "default")
        upstream_session_id = event.session_trace.upstream_session_id
        event_type = event.type
        if event_type == "cc.session_end":
            del self._sessions[topic][upstream_session_id]
            return False
        else:
            return True


class TaskingStrategy(SessionRoutingStrategy):
    def __init__(self, session_manager: SessionManager):
        self._session_manager = session_manager


    async def route(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ) -> Session:
        return await self._session_manager.create_session(
            SessionMode.BACKGROUND
        )
    

    def session_retained(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ) -> bool:
        return False


class StatefulStrategy(SessionRoutingStrategy):
    def __init__(self, session_manager: SessionManager):
        self._session_manager = session_manager

    async def route(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ) -> Session: ...

    def session_retained(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ) -> bool: ...


class AgentNode(BaseNode):
    def __init__(
        self, 
        mesh_id: str, 
        node_id: str, 
        config: Dict[str, str],
        client: MeshClient,
        mode: Literal["default", "program"] = "default"
    ):
        super().__init__(mesh_id, node_id, config, client)
        self.mode = mode
        self._session_manager = SessionManager(self)
        self._session_routing_strategies: Dict[
            Strategy, SessionRoutingStrategy
        ] = {
            Strategy.MIRRORING: MirroringStrategy(self._session_manager),
            Strategy.TASKING: TaskingStrategy(self._session_manager),
            Strategy.STATEFUL: StatefulStrategy(self._session_manager),
        }

    
    async def on_event(self, event: MeshEvent):
        logger.info(f"{self} received event: {event.event_id}")
        await self.client.mark_processing(event)
        if event.reply_to:
            session_id = None
            if event.session_trace:
                session_id = event.session_trace.downstream_session_id
            if not session_id:
                logger.warning(
                    f"Event {event.event_id} has no downstream session id"
                )
                return
            session = self._session_manager.get_session(session_id)
            if session:
                await session.process_event(event)
            else:
                logger.warning(
                    f"Session {session_id} not found for event {event.event_id}"
                )
                return
        else:
            subscription = await self.client.get_subscription(
                self.mesh_id,
                self.node_id,
                event.source_id,
                event.type
            )
            if not subscription:
                logger.warning(
                    f"{self} has no subscription for event {event.type} from {event.source_id}"
                )
                return
            
            routing_strategy = self._session_routing_strategies[
                subscription.session_routing_strategy
            ]
            
            session = await routing_strategy.route(event, subscription)
            logger.info(
                f"Routing event {event.event_id} from {event.source_id} to {session}"
            )
            await session.process_event(event)
            if not routing_strategy.session_retained(event, subscription):
                await session.broadcast_client.send({
                    "type": "system",
                    "sub_type": "session_end",
                    "session_id": session.session_id
                })
                await self._session_manager.close_session(session)


    async def list_sessions(
        self, 
        mode: Optional[str]=None
    ) -> List[Dict[str, Any]]:
        sessions = [
            {
                "session_id": session.session_id,
                "mode": session.mode.value
            } for session in self._session_manager.sessions.values()
        ]
        if mode:
            sessions = [
                session for session in sessions if session["mode"] == mode
            ]
        return sessions

    
    async def start_chat(self, session_id: Optional[str]=None) -> str:
        if session_id:
            session = self._session_manager.get_session(session_id)
            if not session:
                raise RuntimeError(f"Session {session_id} not found")
            return session_id
        else:
            session = await self._session_manager.create_session(
                SessionMode.CHAT
            )
            return session.session_id
        
    
    async def stop_chat(self, session_id: str):
        session = self._session_manager.get_session(session_id)
        if not session:
            # TODO fix it
            logger.warning(f"Session {session_id} not found")
            return
        if session.mode == SessionMode.CHAT:
            await self._session_manager.close_session(session)


    @abstractmethod
    async def create_session(self, mode: SessionMode) -> Session: ...
    @abstractmethod
    async def program(self): ...
    @abstractmethod
    async def on_start(self): ...
    @abstractmethod
    async def on_shutdown(self): ...
    @abstractmethod
    async def start_program_mode(self): ...
    @abstractmethod
    async def stop_program_mode(self): ...

    def __str__(self):
        return f"{self.mesh_id}#{self.node_id}"