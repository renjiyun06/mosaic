import uuid
from abc import ABC, abstractmethod
from typing import Dict, Optional

import mosaic.core.meta as meta
from mosaic.core.node import BaseNode
from mosaic.core.types import MeshID, NodeID, TransportType, SessionRoutingStrategy as Strategy
from mosaic.core.models import MeshEvent, Subscription
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class SessionRoutingStrategy(ABC):
    @abstractmethod
    def route(self, event: MeshEvent, subscription: Subscription) -> 'Session': ...

class MirroringStrategy(SessionRoutingStrategy):
    def __init__(self, session_manager: 'SessionManager'):
        self._session_manager = session_manager

    def route(self, event: MeshEvent, subscription: Subscription) -> 'Session':
        config = subscription.session_routing_strategy_config
        topic = config.get("topic", "default")
        session = self._session_manager.get_session(
            Strategy.MIRRORING,
            topic,
            event.session_trace.upstream_session_id
        )
        if session:
            return session

        return self._session_manager.create_session(
            Strategy.MIRRORING,
            topic,
            event.session_trace.upstream_session_id
        )

class TaskingStrategy(SessionRoutingStrategy):
    def __init__(self, session_manager: 'SessionManager'):
        self._session_manager = session_manager

    def route(self, event: MeshEvent, subscription: Subscription) -> 'Session':
        return self._session_manager.create_session(
            Strategy.TASKING,
            event.session_trace.upstream_session_id,
            "default"
        )

class StatefulStrategy(SessionRoutingStrategy): ...

class Session:
    def __init__(self, node: 'AgentNode'):
        self._node = node
        self._session_id = str(uuid.uuid4())

    async def process_event(self, event: MeshEvent): ...


class SessionManager:
    def __init__(self, node: 'AgentNode'):
        self._node = node
        self._sessions: Dict[Strategy, Dict[str, Dict[str, Session]]] = {}  # strategy -> topic -> upstream_session_id -> session
     
    def get_session(
        self, 
        strategy: SessionRoutingStrategy, 
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

    def create_session(
        self, 
        strategy: SessionRoutingStrategy, 
        upstream_session_id: str,
        topic: Optional[str] = None
    ) -> Session:
        if strategy not in self._sessions:
            self._sessions[strategy] = {}
        
        if topic not in self._sessions[strategy]:
            self._sessions[strategy][topic] = {}
        
        session = Session(self._node)
        self._sessions[strategy][topic][upstream_session_id] = session
        return session


class AgentNode(BaseNode):
    def __init__(self, mesh_id: MeshID, node_id: NodeID, transport: TransportType, config: Dict[str, str]):
        super().__init__(mesh_id, node_id, transport)
        self.config = config
        self._session_manager = SessionManager(self)
        
    async def process_event(self, event: MeshEvent):
        if self.node_id != event.target_id:
            logger.warning(f"Node {self.node_id} received event {event.type} from {event.source_id} but is not the target node")
            return
        
        subscription = None
        for sub in meta.get_subscriptions_by_source(self.mesh_id, self.node_id):
            if sub.event_pattern == event.type:
                subscription = sub
                break
        
        if not subscription and not event.reply_to:
            logger.warning(f"Node {self.node_id} received event {event.type} from {event.source_id} but no subscription found")
            return
        
        if event.reply_to:
            # TODO
            pass
        else:
            session_routing_strategy = None
            strategy = subscription.session_routing_strategy
            if strategy == Strategy.MIRRORING:
                session_routing_strategy = MirroringStrategy(self._session_manager)
            elif strategy == Strategy.TASKING:
                session_routing_strategy = TaskingStrategy(self._session_manager)
            elif strategy == Strategy.STATEFUL:
                session_routing_strategy = StatefulStrategy(self._session_manager)
            else:
                logger.warning(f"Unknown session routing strategy: {strategy}")
                return
            
        session = session_routing_strategy.route(event, subscription)
        await session.process_event(event)
        
    @abstractmethod
    async def on_start(self): ...
    @abstractmethod
    async def on_shutdown(self): ...
    @abstractmethod
    async def chat(self): ...