import uuid
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple

import mosaic.core.meta as meta
from mosaic.core.node import BaseNode
from mosaic.core.types import MeshID, NodeID, TransportType, SessionRoutingStrategy as Strategy, AgentRunningMode
from mosaic.core.models import MeshEvent, Subscription
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class Session(ABC):
    def __init__(self, node: 'AgentNode', session_id: str, mode: AgentRunningMode):
        self.node = node
        self.session_id = session_id
        self.mode = mode
    
    @abstractmethod
    async def start(self): ...
    @abstractmethod
    async def close(self): ...
    @abstractmethod
    async def process_event(self, event: MeshEvent): ...
    @abstractmethod
    async def chat(self): ...
    @abstractmethod
    async def program(self): ...

class SessionManager:
    def __init__(self, node: 'AgentNode'):
        self._node = node
        self._sessions: Dict[Strategy, Dict[str, Dict[str, Session]]] = {}  # strategy -> topic -> upstream_session_id -> session
        self._session_id_to_session: Dict[str, Tuple[Strategy, str, str, Session]] = {}  # session_id -> (strategy, topic, upstream_session_id, session)
     
    def get_session(
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

    async def create_session(
        self, 
        strategy: 'SessionRoutingStrategy', 
        upstream_session_id: str,
        topic: Optional[str] = None
    ) -> Session:
        logger.info(
            f"Creating session for node {self._node.node_id} in mesh {self._node.mesh_id}, "
            f"strategy: {strategy}, upstream_session_id: {upstream_session_id}, topic: {topic}"
        )
        if strategy not in self._sessions:
            self._sessions[strategy] = {}
        
        if topic not in self._sessions[strategy]:
            self._sessions[strategy][topic] = {}
        
        session = await self._node.create_session(str(uuid.uuid4()), AgentRunningMode.BACKGROUND)
        logger.info(f"Session created for node {self._node.node_id} in mesh {self._node.mesh_id}, session_id: {session.session_id}")
        await session.start()
        logger.info(f"Session started for node {self._node.node_id} in mesh {self._node.mesh_id}, session_id: {session.session_id}")
        self._sessions[strategy][topic][upstream_session_id] = session
        self._session_id_to_session[session.session_id] = (strategy, topic, upstream_session_id, session)
        return session

    async def close_session(self, session: Session):
        logger.info(f"Closing session for node {self._node.node_id} in mesh {self._node.mesh_id}, session_id: {session.session_id}")
        await session.close()
        logger.info(f"Session closed for node {self._node.node_id} in mesh {self._node.mesh_id}, session_id: {session.session_id}")
        strategy, topic, upstream_session_id, _ = self._session_id_to_session[session.session_id]
        del self._sessions[strategy][topic][upstream_session_id]
        del self._session_id_to_session[session.session_id]


class SessionRoutingStrategy(ABC):
    @abstractmethod
    async def route(self, event: MeshEvent, subscription: Subscription) -> Session: ...

class MirroringStrategy(SessionRoutingStrategy):
    def __init__(self, session_manager: 'SessionManager'):
        self._session_manager = session_manager

    async def route(self, event: MeshEvent, subscription: Subscription) -> Session:
        config = subscription.session_routing_strategy_config
        topic = config.get("topic", "default")
        session = self._session_manager.get_session(
            Strategy.MIRRORING,
            topic,
            event.session_trace.upstream_session_id
        )
        if session:
            logger.info(
                f"Event {event.type}[{event.event_id}] from {event.source_id} to {event.target_id} in mesh {event.mesh_id} "
                f"is routed to existing session {session.session_id}"
            )
            return session

        logger.info(
            f"Event {event.type}[{event.event_id}] from {event.source_id} to {event.target_id} in mesh {event.mesh_id} "
            f"will be routed to a new session"
        )
        return await self._session_manager.create_session(
            Strategy.MIRRORING,
            topic,
            event.session_trace.upstream_session_id
        )

class TaskingStrategy(SessionRoutingStrategy):
    def __init__(self, session_manager: 'SessionManager'):
        self._session_manager = session_manager

    async def route(self, event: MeshEvent, subscription: Subscription) -> Session:
        return await self._session_manager.create_session(
            Strategy.TASKING,
            event.session_trace.upstream_session_id,
            "default"
        )

class StatefulStrategy(SessionRoutingStrategy): ...


class AgentNode(BaseNode):
    def __init__(self, mesh_id: MeshID, node_id: NodeID, transport: TransportType, config: Dict[str, str]):
        super().__init__(mesh_id, node_id, transport)
        self.config = config
        self._session_manager = SessionManager(self)
        
    async def process_event(self, event: MeshEvent):
        if self.node_id != event.target_id:
            logger.warning(f"Node {self.node_id} received event {event.type} from {event.source_id} but is not the target node")
            return
        
        subscription: Subscription = None
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
            
        session = await session_routing_strategy.route(event, subscription)
        session_retained = await session.process_event(event)
        if not session_retained:
            await self._session_manager.close_session(session)
    

    @abstractmethod
    async def on_start(self): ...
    @abstractmethod
    async def on_shutdown(self): ...
    @abstractmethod
    async def create_session(self, session_id: str, mode: AgentRunningMode) -> Session: ...
    @abstractmethod
    async def program(self): ...
    @abstractmethod
    async def chat(self): ...

