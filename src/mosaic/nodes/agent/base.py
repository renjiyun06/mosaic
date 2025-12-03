from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple

from mosaic.core.node import BaseNode
from mosaic.core.client import MeshClient
from mosaic.core.models import MeshEvent, Subscription
from mosaic.nodes.agent.types import (
    AgentNodeRunningMode,
    SessionRoutingStrategy as Strategy,
)
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class Session(ABC):
    def __init__(self, session_id: str, node: 'AgentNode'):
        self.session_id = session_id
        self.node = node
    
    @abstractmethod
    async def start(self): ...
    @abstractmethod
    async def close(self): ...
    @abstractmethod
    async def process_event(self, event: MeshEvent): ...


class SessionManager:
    def __init__(self, node: 'AgentNode'):
        self._node = node
        # strategy -> topic -> upstream_session_id -> session
        self._sessions: Dict[Strategy, Dict[str, Dict[str, Session]]] = {} 
        # session_id -> (strategy, topic, upstream_session_id, session)
        self._session_id_to_session: Dict[
            str, Tuple[Strategy, str, str, Session]
        ] = {}

    
    def get_session(self, session_id: str) -> Optional[Session]:
        if session_id not in self._session_id_to_session:
            return None
        return self._session_id_to_session[session_id][3]

    
    def get_session_for_upstream_session(
        self, 
        strategy: 'SessionRoutingStrategy', 
        topic: str,
        upstream_session_id: str,
    ) -> Optional[Session]:
        if strategy not in self._sessions:
            return None
        
        if topic not in self._sessions[strategy]:
            return None
        
        if upstream_session_id not in self._sessions[strategy][topic]:
            return None
        
        return self._sessions[strategy][topic][upstream_session_id]


    async def create_session_for_upstream_session(
        self, 
        strategy: Strategy, 
        topic: str,
        upstream_session_id: str
    ) -> Session:
        if strategy not in self._sessions:
            self._sessions[strategy] = {}
        
        if topic not in self._sessions[strategy]:
            self._sessions[strategy][topic] = {}
        
        session = await self._node.create_session()
        await session.start()
        self._sessions[strategy][topic][upstream_session_id] = session
        self._session_id_to_session[session.session_id] = (
            strategy, topic, upstream_session_id, session
        )
        return session


    async def close_session(self, session: Session):
        strategy, topic, upstream_session_id, _ = self._session_id_to_session[
            session.session_id
        ]
        del self._sessions[strategy][topic][upstream_session_id]
        del self._session_id_to_session[session.session_id]
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

    async def route(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ) -> Session:
        config = subscription.session_routing_strategy_config
        topic = config.get("topic", "default")
        session = await self._session_manager \
            .get_session_for_upstream_session(
                Strategy.MIRRORING,
                topic,
                event.session_trace.upstream_session_id
            )
        if session:
            return session
        else:
            return await self._session_manager \
                .create_session_for_upstream_session(
                    Strategy.MIRRORING,
                    topic,
                    event.session_trace.upstream_session_id
                )

    def session_retained(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ) -> bool: ...


class TaskingStrategy(SessionRoutingStrategy):
    def __init__(self, session_manager: SessionManager):
        self._session_manager = session_manager

    async def route(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ) -> Session:
        return await self._session_manager.create_session(
            Strategy.TASKING,
            "default",
            event.session_trace.upstream_session_id
        )
    
    def session_retained(
        self, 
        event: MeshEvent, 
        subscription: Subscription
    ) -> bool:
        return False


class StatefulStrategy(SessionRoutingStrategy): ...


class AgentNode(BaseNode):
    def __init__(
        self, 
        mesh_id: str, 
        node_id: str, 
        config: Dict[str, str],
        client: MeshClient,
        mode: AgentNodeRunningMode
    ):
        super().__init__(mesh_id, node_id, config, client)
        self.mode = mode
        self._chat_session = None
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
        if event.reply_to:
            session = None
            if self.mode == AgentNodeRunningMode.CHAT:
                session = self._chat_session
            elif self.mode == AgentNodeRunningMode.BACKGROUND:
                session = self._session_manager.get_session(
                    event.session_trace.downstream_session_id
                )
            else:
                return
            
            if session:
                await session.process_event(event)
        else:
            subscription = await self.client.get_subscription(event)
            routing_strategy = self._session_routing_strategies[
                subscription.session_routing_strategy
            ]
            session = await routing_strategy.route(event, subscription)
            await session.process_event(event)
            if not routing_strategy.session_retained(event, subscription):
                await self._session_manager.close_session(session)


    @abstractmethod
    async def create_session(self, mesh_id: str, node_id: str) -> Session: ...
    @abstractmethod
    async def chat(self): ...
    @abstractmethod
    async def program(self): ...
    @abstractmethod
    async def on_start(self): ...
    @abstractmethod
    async def on_shutdown(self): ...
    @abstractmethod
    async def start_chat_mode(self): ...
    @abstractmethod
    async def stop_chat_mode(self): ...
    @abstractmethod
    async def start_program_mode(self): ...
    @abstractmethod
    async def stop_program_mode(self): ...
