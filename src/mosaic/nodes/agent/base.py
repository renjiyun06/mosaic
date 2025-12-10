from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List

import mosaic.core.util as core_util
from mosaic.core.node import BaseNode
from mosaic.core.client import MeshClient
from mosaic.core.models import MeshEvent, Subscription
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
            return session
        else:
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
    ):
        super().__init__(mesh_id, node_id, config, client)
        self._program_session = None
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
                await self.client.mark_processing(event)
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

    
    async def start_chat(self, session_id: Optional[str]) -> str:
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
            raise RuntimeError(f"Session {session_id} not found")
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