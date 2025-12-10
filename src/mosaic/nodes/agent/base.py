import json
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List, Literal
from datetime import datetime

import mosaic.core.util as core_util
from mosaic.core.node import BaseNode
from mosaic.core.client import MeshClient
from mosaic.core.models import MeshEvent, Subscription
from mosaic.nodes.agent.enums import (
    SessionMode,
    AgentNodeRunningMode,
    SessionRoutingStrategy as Strategy,
)
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class Session(ABC):
    def __init__(self, session_id: str, node: 'AgentNode'):
        self.session_id = session_id
        self.node = node
        self._messages: List[Dict[str, Any]] = []
        self._log_path = core_util.session_log_path(
            node.mesh_id, node.node_id, session_id
        )
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_path.touch(exist_ok=True)
        self._socket_path = core_util.session_socket_path(
            node.mesh_id, node.node_id, session_id
        )
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._socket_server = None
        self._connection_tasks: List[asyncio.Task] = []
        
    
    
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
    @abstractmethod
    async def send_message(self, message: str): ...

    async def start_socket_server(self):
        self._socket_server = await asyncio.start_unix_server(
            self._handle_connection,
            path=str(self._socket_path)
        )

    async def _handle_connection(self, reader, writer):
        task = asyncio.create_task(
            self._handle_connection_task(reader, writer)
        )
        self._connection_tasks.append(task)

        def cleanup_task(t):
            if t in self._connection_tasks:
                self._connection_tasks.remove(t)
        
        task.add_done_callback(cleanup_task)

    async def _handle_connection_task(self, reader, writer):
        try:
            while True:
                length = int.from_bytes(await reader.readexactly(4), 'big')
                user_message = (await reader.readexactly(length)).decode()
                logger.info(
                    f"Received user message for session {self.session_id} of "
                    f"node {self.node.node_id} in mesh {self.node.mesh_id}: {user_message}"
                )
                await self.send_message(user_message)
        except asyncio.CancelledError:
            logger.info(
                f"Connection to session {self.session_id} of "
                f"node {self.node.node_id} in mesh {self.node.mesh_id} cancelled"
            )
        
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            logger.error(
                f"Error closing writer for connection to session {self.session_id} "
                f"of node {self.node.node_id} in mesh {self.node.mesh_id}: {e}"
            )
            raise e

    async def stop_socket_server(self):
        logger.info(
            f"Stopping socket server for session {self.session_id} of "
            f"node {self.node.node_id} in mesh {self.node.mesh_id}"
        )
        if self._socket_server:
            self._socket_server.close()
            await self._socket_server.wait_closed()
        
        self._socket_server = None
       
        for task in self._connection_tasks:
            task.cancel()
        
        try:
            await asyncio.gather(*self._connection_tasks)
        except Exception as e:
            logger.error(
                f"Error stopping socket server for session {self.session_id} of "
                f"node {self.node.node_id} in mesh {self.node.mesh_id}: {e}"
            )
            raise e
        finally:
            self._connection_tasks = []
        
        logger.info(
            f"Socket server for session {self.session_id} of "
            f"node {self.node.node_id} in mesh {self.node.mesh_id} stopped"
        )


    async def record(
        self, 
        role: Literal["User", "Assistant", "System"], 
        message: str
    ): 
        self._messages.append({
            "role": role,
            "message": message,
            "created_at": datetime.now().isoformat()
        })
        with open(self._log_path, "a") as f:
            f.write(json.dumps({
                "role": role,
                "message": message,
                "created_at": datetime.now().isoformat()
            }, ensure_ascii=False) + "\n")


class SessionManager:
    def __init__(self, node: 'AgentNode'):
        self._node = node
        self._sessions: Dict[str, Session] = {}
    
    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id, None)

    async def create_session(self, mode: SessionMode) -> Session:
        session = await self._node.create_session(mode)
        self._sessions[session.session_id] = session
        await session.start()
        return session

    async def close_session(self, session: Session):
        del self._sessions[session.session_id]
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
        
        self._chat_sessions: Dict[str, Any] = {}
        self._background_sessions: Dict[str, Any] = {}

    
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
                logger.error(
                    f"Error routing event {event.event_id} "
                    f"from {event.source_id}: "
                    f"{e}"
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


    async def register_chat_session(self, session_id: str):
        self._chat_sessions[session_id] = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat()
        }
    
    async def unregister_chat_session(self, session_id: str):
        del self._chat_sessions[session_id]

    async def list_chat_sessions(self) -> List[str]:
        return list(self._chat_sessions.keys())

    async def register_background_session(self, session_id: str):
        self._background_sessions[session_id] = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat()
        }
    
    async def unregister_background_session(self, session_id: str):
        del self._background_sessions[session_id]

    async def list_background_sessions(self) -> List[Dict[str, Any]]:
        return list(self._background_sessions.values())


    @abstractmethod
    async def create_session(self, mode: SessionMode) -> Session: ...
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