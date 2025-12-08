from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple, Any

from mosaic.core.node import BaseNode
from mosaic.core.client import MeshClient
from mosaic.core.models import MeshEvent, Subscription
from mosaic.nodes.agent.enums import (
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
    @abstractmethod
    async def chat(self): ...
    @abstractmethod
    async def program(self): ...


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
        
        session = await self._node.create_session(
            self._node.mesh_id,
            self._node.node_id
        )
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
        config = subscription.session_routing_strategy_config or {}
        topic = config.get("topic", "default")
        session = self._session_manager \
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
    ) -> bool:
        event_type = event.type
        if event_type == "cc.session_end":
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
        return await self._session_manager.create_session_for_upstream_session(
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
        logger.info(
            f"Node {self.node_id} in mesh {self.mesh_id} received event: "
            f"{event.model_dump_json()}"
        )
        if event.target_id != self.node_id:
            logger.warning(
                f"Event {event.type} from {event.source_id} to {event.target_id} "
                f"in mesh {self.mesh_id} is not for this node {self.node_id}"
            )
            return
        
        if event.reply_to:
            session = None
            if self.mode == AgentNodeRunningMode.CHAT:
                logger.info(
                    f"Event {event.event_id} is a reply to a chat session "
                    f"of node {self.node_id} in mesh {self.mesh_id}"
                )
                session = self._chat_session
            elif self.mode == AgentNodeRunningMode.BACKGROUND:
                logger.info(
                    f"Event {event.event_id} is a reply to a background session "
                    f"of node {self.node_id} in mesh {self.mesh_id}"
                )
                session = self._session_manager.get_session(
                    event.session_trace.downstream_session_id
                )
            else:
                logger.warning(
                    f"Current running mode {self.mode} is not supported for "
                    f"reply events"
                )
                return
            
            if session:
                await self.client.mark_processing(event)
                await session.process_event(event)
            else:
                logger.warning(
                    f"Cannot find session for event: "
                    f"{event.model_dump_json()}"
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
                    f"Node {self.node_id} in mesh {self.mesh_id} "
                    f"has no subscription for event {event.type} from "
                    f"{event.source_id}"
                )
                return
            routing_strategy = self._session_routing_strategies[
                subscription.session_routing_strategy
            ]
            
            try:
                session = await routing_strategy.route(event, subscription)
            except Exception as e:
                import traceback
                logger.error(
                    f"Error routing event {event.event_id} "
                    f"from {event.source_id}: "
                    f"{traceback.format_exc()}"
                )
                raise e
            
            logger.info(
                f"Routing event {event.event_id} from {event.source_id} to "
                f"session {session.session_id} of node {self.node_id} in mesh "
                f"{self.mesh_id}"
            )
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
    @abstractmethod
    async def assemble_system_prompt(self, session_id: str) -> str: ...