"""Claude Code node and session implementation"""
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    HookMatcher,
    tool,
    create_sdk_mcp_server
)

from ..mosaic_node import MosaicNode
from ..mosaic_session import MosaicSession
from ...enum import (
    SessionStatus,
    SessionMode,
    SessionAlignment,
    LLMModel,
    EventType,
    MessageRole,
    MessageType,
    RuntimeStatus
)
from ...websocket import UserMessageBroker
from ...exception import SessionNotFoundError, SessionConflictError

if TYPE_CHECKING:
    from ...model.node import Node
    from ...model.session import Session

logger = logging.getLogger(__name__)


class ClaudeCodeNode(MosaicNode):
    """
    Claude Code node - manages Claude Agent SDK sessions.

    This node type provides:
    - Claude Agent SDK integration for AI coding assistance
    - WebSocket-based real-time communication with frontend
    - Database persistence for sessions and messages
    - Event mesh integration for inter-node communication
    - MCP tools for Mosaic-specific operations

    Architecture:
    - Each session runs independently with its own Claude SDK client
    - Sessions can be in different modes (background/interactive)
    - Events are published to the mesh for monitoring and collaboration
    """

    def __init__(
        self,
        node: 'Node',
        node_path: Path,
        mosaic_instance,
        async_session_factory,
        config: dict
    ):
        """
        Initialize Claude Code node.

        Args:
            node: Node model object from database
            node_path: Node working directory path
            mosaic_instance: Parent MosaicInstance reference
            async_session_factory: AsyncSession factory for database access
            config: Configuration dict (must contain 'zmq')
        """
        super().__init__(node, node_path, mosaic_instance, async_session_factory, config)

        # System prompt template (generated during startup, cached for all sessions)
        # Contains {session_id} placeholder to be filled per session
        self._system_prompt_template: Optional[str] = None

        logger.info(
            f"Initialized ClaudeCodeNode: node_id={node.node_id}, path={node_path}"
        )

    # ========== Lifecycle Hooks ==========

    async def _on_start(self) -> None:
        """
        Node startup hook.

        For Claude Code nodes, we generate the system prompt template during startup.
        This template contains network topology and event definitions, and will be
        cached for all sessions to avoid repeated database queries.
        """
        logger.info(f"ClaudeCodeNode {self.node.node_id} starting...")

        # Generate system prompt template (with {session_id} placeholder)
        from ..system_prompt import generate_system_prompt_template

        self._system_prompt_template = await generate_system_prompt_template(
            node=self.node,
            mosaic_id=self.mosaic_instance.mosaic.id,
            async_session_factory=self.async_session_factory
        )

        logger.info(
            f"ClaudeCodeNode {self.node.node_id} started, "
            f"system_prompt_length={len(self._system_prompt_template)}"
        )

    async def _on_stop(self) -> None:
        """
        Node cleanup hook.

        For Claude Code nodes, all cleanup is session-level.
        No node-level cleanup is needed - just log the shutdown.
        """
        logger.info(f"ClaudeCodeNode {self.node.node_id} stopped")

    # ========== Session Management ==========

    async def create_session(
        self,
        session_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> 'MosaicSession':
        """
        Create a Claude Code session.

        This is an agent node, so sessions are persisted to database.

        Strategy:
        1. Check runtime conflict (self._sessions)
        2. Check database conflict (if session_id already exists)
        3. Create runtime session instance
        4. Register in self._sessions
        5. Initialize session (starts worker task, connects to Claude SDK)
        6. Create database session record (only after successful initialization)

        Args:
            session_id: Session identifier (UUID string)
            config: Session configuration (optional)
                - mode: SessionMode value (BACKGROUND, PROGRAM, CHAT)
                - model: LLMModel value (SONNET, OPUS, HAIKU)
                - mcp_servers: Additional MCP server configurations

        Returns:
            ClaudeCodeSession instance

        Raises:
            SessionConflictError: If session already exists in runtime or database
        """
        logger.info(
            f"Creating Claude Code session: session_id={session_id}, "
            f"node_id={self.node.node_id}"
        )

        # 1. Check if session already exists in runtime
        if session_id in self._sessions:
            raise SessionConflictError(
                f"Session {session_id} already exists in runtime for node {self.node.node_id}"
            )

        # 2. Check if session already exists in database
        from ...model.session import Session
        from sqlmodel import select

        async with self.async_session_factory() as db_session:
            stmt = select(Session).where(Session.session_id == session_id)
            result = await db_session.execute(stmt)
            db_session_obj = result.scalar_one_or_none()

            if db_session_obj:
                raise SessionConflictError(
                    f"Session {session_id} already exists in database"
                )

        # 3. Create runtime session instance
        session = ClaudeCodeSession(
            session_id=session_id,
            node=self,
            async_session_factory=self.async_session_factory,
            config=config or {}
        )

        # 4. Register in session map
        self._sessions[session_id] = session

        # 5. Initialize session (starts worker task, connects to Claude SDK)
        await session.initialize()

        # 6. Create database session record (only after successful initialization)
        async with self.async_session_factory() as db_session:
            db_session_obj = Session(
                session_id=session_id,
                user_id=self.node.user_id,
                mosaic_id=self.mosaic_instance.mosaic.id,
                node_id=self.node.node_id,
                mode=session.mode,
                model=session.model,
                status=SessionStatus.ACTIVE
            )
            db_session.add(db_session_obj)
            await db_session.commit()

            logger.info(
                f"Created database session: session_id={session_id}, "
                f"status={SessionStatus.ACTIVE}"
            )

        logger.info(
            f"Claude Code session created and initialized: session_id={session_id}"
        )

        return session

    async def close_session(self, session_id: str) -> None:
        """
        Close a Claude Code session.

        Updates database status and cleans up runtime resources.

        Args:
            session_id: Session identifier

        Raises:
            SessionNotFoundError: If session not found
        """
        logger.info(
            f"Closing Claude Code session: session_id={session_id}, "
            f"node_id={self.node.node_id}"
        )

        # Get session from map
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(
                f"Session {session_id} not found in node {self.node.node_id}"
            )

        # Call session cleanup (stops worker, calls _on_close hook)
        await session.close()

        # Update database status to CLOSED
        from ...model.session import Session

        async with self.async_session_factory() as db_session:
            from sqlmodel import select
            stmt = select(Session).where(Session.session_id == session_id)
            result = await db_session.execute(stmt)
            db_session_obj = result.scalar_one_or_none()

            if db_session_obj:
                now = datetime.now()
                db_session_obj.status = SessionStatus.CLOSED
                db_session_obj.closed_at = now
                db_session_obj.updated_at = now
                await db_session.commit()

                logger.debug(
                    f"Updated database session status to CLOSED: session_id={session_id}"
                )

        # Unregister from session map
        self._sessions.pop(session_id, None)

        logger.info(f"Claude Code session closed: session_id={session_id}")

    async def send_message(self, session_id: str, message: str) -> None:
        """
        Send a user message to a Claude Code session.

        This is called from the API layer (WebSocket or FastAPI) when user sends a message.

        Args:
            session_id: Session identifier
            message: User message content

        Raises:
            SessionNotFoundError: If session not found
        """
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(
                f"Session {session_id} not found in node {self.node.node_id}"
            )

        # Delegate to session's process_user_message method
        await session.process_user_message(message)

        logger.debug(
            f"User message sent to session: session_id={session_id}, "
            f"message_length={len(message)}"
        )


    def get_default_session_config(self) -> Optional[Dict[str, Any]]:
        return {
            "mode": self.node.config.get("mode", SessionMode.BACKGROUND),
            "model": self.node.config.get("model", LLMModel.SONNET),
            "token_threshold_enabled": self.node.config.get("token_threshold_enabled", False),
            "token_threshold": self.node.config.get("token_threshold", 30000),
            "inherit_threshold": self.node.config.get("inherit_threshold", True),
            "auto_generate_session_topic": self.node.config.get("auto_generate_session_topic", True),
            "topic_generation_token_threshold": self.node.config.get("topic_generation_token_threshold", 1500)
        }

class ClaudeCodeSession(MosaicSession):
    """
    Claude Code session with Claude Agent SDK integration.

    Key features:
    - Integrates Claude Agent SDK for AI coding assistance
    - Publishes events to the mesh for monitoring
    - Persists messages to database
    - Pushes real-time updates via WebSocket
    - Provides MCP tools for Mosaic operations

    Session lifecycle:
    1. Creation: __init__ (runtime flags initialized)
    2. Initialization: _on_initialize (Claude SDK setup, DB status update)
    3. Processing: _handle_event (process incoming events)
    4. Auto-close: _should_close_after_event (decide when to close)
    5. Cleanup: _on_close (disconnect Claude SDK, publish session_end)
    """

    def __init__(
        self,
        session_id: str,
        node: ClaudeCodeNode,
        async_session_factory,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Claude Code session.

        Args:
            session_id: Session identifier (UUID string)
            node: Parent ClaudeCodeNode reference
            async_session_factory: AsyncSession factory for database access
            config: Session configuration
        """
        super().__init__(session_id, node, async_session_factory, config)

        # Extract configuration
        config = config or {}
        self.mode = config.get("mode", SessionMode.BACKGROUND)
        self.model = config.get("model", LLMModel.SONNET)

        # Token threshold: force enable for LONG_RUNNING mode
        if self.mode == SessionMode.LONG_RUNNING:
            self.token_threshold_enabled = True
        else:
            self.token_threshold_enabled = config.get("token_threshold_enabled", False)
        self.token_threshold = config.get("token_threshold", 30000)
        self.inherit_threshold = config.get("inherit_threshold", True)
        self.auto_generate_session_topic = config.get("auto_generate_session_topic", True)
        self.topic_generation_token_threshold = config.get("topic_generation_token_threshold", 1500)
        self.mcp_servers = config.get("mcp_servers", {})  # Additional MCP servers

        # Claude SDK client (initialized in _on_initialize)
        self._cc_client: Optional[ClaudeSDKClient] = None

        # Statistics (in-memory, synced to DB on result)
        self._total_cost_usd = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        # Context window usage tracking
        self._context_usage = 0  # Actual context usage (input + cache tokens)
        self._context_percentage = 0.0  # Context usage percentage (0-100)

        # Session state (in-memory, synced to DB)
        self._message_count = 0
        self._last_activity_at: Optional[datetime] = None

        # Interrupt flag
        self._is_interrupted = False

        # Message sequence number (starts from 0, incremented for each message)
        self._message_sequence = 0

        # Token threshold notification tracking
        self._effective_threshold = self.token_threshold  # Dynamic threshold (updates after each notification)
        self._token_threshold_notified = False  # Notification flag

        # Task lifecycle flags (LONG_RUNNING mode only)
        self._task_started = False  # Whether task has been acknowledged as started
        self._task_acknowledged = False  # Whether current task has been acknowledged as finished

        # Background monitor task (LONG_RUNNING mode only)
        self._monitor_task: Optional[asyncio.Task] = None

        logger.debug(
            f"Initialized ClaudeCodeSession: session_id={session_id}, "
            f"mode={self.mode}, model={self.model}"
        )

    # ========== Lifecycle Hooks ==========

    async def _on_event_loop_started(self):
        """
        Initialize Claude Code session resources.

        Strategy:
        1. Initialize all runtime resources (Claude SDK, system prompt, MCP servers)
        2. Publish session_start event (all modes except PROGRAM)

        Note:
            Database session record is created in ClaudeCodeNode.create_session
            before this method is called.
        """
        logger.info(
            f"Initializing ClaudeCodeSession: session_id={self.session_id}, "
            f"mode={self.mode}, model={self.model}"
        )

        # 1. Get system prompt from node template (fill in session_id placeholder)
        system_prompt = self.node._system_prompt_template.replace("###session_id###", self.session_id)

        logger.debug(
            f"System prompt ready for session {self.session_id}, "
            f"length={len(system_prompt)}"
        )
        logger.debug(
            f"System prompt content for session {self.session_id}:\n{system_prompt}"
        )

        # 2. Configure MCP servers
        mcp_servers = self.mcp_servers.copy()
        mcp_servers["mosaic-mcp-server"] = self._create_mosaic_mcp_server()

        # 3. Configure Claude SDK
        cc_options = ClaudeAgentOptions(
            model=self.model,
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": system_prompt
            },
            cwd=str(self.node.node_path),
            permission_mode="bypassPermissions",
            hooks={
                "PreToolUse": [
                    HookMatcher(hooks=[self._pre_tool_use_hook])
                ],
                "PostToolUse": [
                    HookMatcher(hooks=[self._post_tool_use_hook])
                ],
            },
            mcp_servers=mcp_servers,
            allowed_tools=["*"],
            setting_sources=["project"],
            max_thinking_tokens=2000
        )

        # 4. Create and connect Claude SDK client
        self._cc_client = ClaudeSDKClient(cc_options)
        await self._cc_client.connect()

        logger.debug(f"Claude SDK client connected: session_id={self.session_id}")

        # 5. Publish session_start event (all modes except PROGRAM)
        if self.mode != SessionMode.PROGRAM:
            await self.node.send_event(
                source_session_id=self.session_id,
                event_type=EventType.SESSION_START,
                payload={}
                # target_node_id is None for broadcast
            )

            logger.info(
                f"Published session_start event: session_id={self.session_id}"
            )

        logger.info(f"ClaudeCodeSession initialized: session_id={self.session_id}")

        user_message_broker = UserMessageBroker.get_instance()
        user_message_broker.push_from_worker(self.node.node.user_id, {
            "role": MessageRole.NOTIFICATION,
            "message_type": MessageType.SESSION_STARTED,
            "session_id": self.session_id,
            "payload": {
                "session_id": self.session_id
            }
        })
        logger.info(f"Pushed session_started notification to WebSocket: session_id={self.session_id}")

        # 6. Start background task progress monitor (LONG_RUNNING mode only)
        if self.mode == SessionMode.LONG_RUNNING:
            self._monitor_task = asyncio.create_task(self._monitor_task_progress())
            logger.info(
                f"Started background task progress monitor: session_id={self.session_id}"
            )

        # 7. Send self-notification if session_start_notify is enabled (all modes except PROGRAM)
        if self.mode != SessionMode.PROGRAM and self.node.node.config.get("session_start_notify", False):
            self.enqueue_event({
                "event_type": EventType.SYSTEM_MESSAGE,
                "payload": {
                    "message": "Session started"
                }
            })
            logger.info(
                f"Enqueued session_start self-notification: session_id={self.session_id}"
            )

    async def _handle_event(self, event: dict) -> None:
        """
        Handle an incoming event.

        Event sources:
        1. Internal events (USER_MESSAGE_EVENT): From process_user_message via queue
        2. Network events: From Event Mesh via MosaicNode routing

        Processing flow:
        1. Format event to message string (via _format_event_for_claude)
        2. Store and echo message to WebSocket (role depends on event type)
        3. Publish user_prompt_submit event (if background mode)
        4. Send to Claude SDK
        5. Receive and forward Claude's response

        Args:
            event: Event data dict containing:
                - event_type (str): Event type (required)
                - payload (dict): Event-specific data (required)

                For network events, also contains:
                - event_id (str): Unique event identifier
                - source_node_id (str): Source node
                - source_session_id (str): Source session
                - target_node_id (str): Target node (excluded from Claude message)
                - target_session_id (str): Target session (excluded from Claude message)
        """
        event_type = event.get('event_type', 'UNKNOWN')

        logger.debug(
            f"Handling event: session_id={self.session_id}, event_type={event_type}"
        )

        # Special handling for TASK_COMPLETE_EVENT (internal event)
        if event_type == EventType.TASK_COMPLETE_EVENT:
            logger.info(
                f"Received task completion signal: session_id={self.session_id}"
            )
            # No business logic processing needed - just return
            # _should_close_after_event will handle the close decision
            return

        # LONG_RUNNING mode: Restart Claude client on self-referencing message
        if self.mode == SessionMode.LONG_RUNNING:
            source_node_id = event.get('source_node_id')
            source_session_id = event.get('source_session_id')

            if (source_node_id == self.node.node.node_id and
                source_session_id == self.session_id):
                logger.info(
                    f"LONG_RUNNING session detected self-referencing message, "
                    f"restarting Claude client to clear context: session_id={self.session_id}"
                )

                # Restart Claude client: disconnect old client and create new one
                await self._restart_claude_client()

                logger.info(
                    f"Claude client restarted successfully: session_id={self.session_id}"
                )

        # 1. Format event to message string
        message = self._format_event_for_claude(event)

        # 2. Determine message role and type based on event type
        if event_type == EventType.USER_MESSAGE_EVENT:
            # User message: role=user, type=user_message
            role = MessageRole.USER
            message_type = MessageType.USER_MESSAGE
        else:
            # Network events: role=system, type=system_message
            role = MessageRole.SYSTEM
            message_type = MessageType.SYSTEM_MESSAGE

        # 3. Store to database and push to WebSocket
        message_id, sequence, timestamp = await self._save_message_to_db(
            role=role,
            message_type=message_type,
            payload={"message": message}
        )
        self._push_to_websocket(
            role=role,
            message_type=message_type,
            message_id=message_id,
            sequence=sequence,
            timestamp=timestamp,
            payload={"message": message}
        )

        # 4. Publish user_prompt_submit event (all modes except PROGRAM)
        if self.mode != SessionMode.PROGRAM:
            await self.node.send_event(
                source_session_id=self.session_id,
                event_type=EventType.USER_PROMPT_SUBMIT,
                payload={"prompt": message}
            )

        # 5. Update runtime status to BUSY before processing
        await self._update_runtime_status_to_db(RuntimeStatus.BUSY)

        # Send WebSocket notification for BUSY status
        user_message_broker = UserMessageBroker.get_instance()
        user_message_broker.push_from_worker(self.node.node.user_id, {
            "role": MessageRole.NOTIFICATION,
            "message_type": MessageType.RUNTIME_STATUS_CHANGED,
            "session_id": self.session_id,
            "payload": {
                "session_id": self.session_id,
                "runtime_status": RuntimeStatus.BUSY.value
            }
        })
        logger.debug(
            f"Pushed runtime_status_changed notification to WebSocket: "
            f"session_id={self.session_id}, runtime_status=busy"
        )

        # 6. Send to Claude SDK
        logger.debug(f"Sending query to Claude: session_id={self.session_id}")
        await self._cc_client.query(message)

        # 7. Receive and forward Claude's response
        stats = await self._receive_assistant_response()

        # 8. Update runtime status back to IDLE after processing
        await self._update_runtime_status_to_db(RuntimeStatus.IDLE)

        # Send WebSocket notification for IDLE status
        user_message_broker = UserMessageBroker.get_instance()
        user_message_broker.push_from_worker(self.node.node.user_id, {
            "role": MessageRole.NOTIFICATION,
            "message_type": MessageType.RUNTIME_STATUS_CHANGED,
            "session_id": self.session_id,
            "payload": {
                "session_id": self.session_id,
                "runtime_status": RuntimeStatus.IDLE.value
            }
        })
        logger.debug(
            f"Pushed runtime_status_changed notification to WebSocket: "
            f"session_id={self.session_id}, runtime_status=idle"
        )

        # 9. Update session statistics
        if stats:
            self._total_cost_usd += stats["cost_usd"]
            self._total_input_tokens += stats["input_tokens"]
            self._total_output_tokens += stats["output_tokens"]
            self._context_usage = stats["context_usage"]
            self._context_percentage = stats["context_percentage"]

            # Sync session state to database
            await self._update_session_to_db()

        # Token threshold notification
        if (self.mode != SessionMode.PROGRAM and
            self.token_threshold_enabled and
            self._total_output_tokens >= self._effective_threshold and
            not self._token_threshold_notified):
            logger.warning(
                f"Token threshold reached: session_id={self.session_id}, "
                f"total_output_tokens={self._total_output_tokens}, "
                f"effective_threshold={self._effective_threshold}"
            )
            self.enqueue_event({
                "event_type": EventType.SYSTEM_MESSAGE,
                "payload": {
                    "message": f"Token threshold reached: {self._effective_threshold}"
                }
            })

            # Set flag to True - only reset on Claude client restart (LONG_RUNNING mode)
            self._token_threshold_notified = True

            logger.debug(
                f"Token notification sent: session_id={self.session_id}, "
                f"mode={self.mode.value}"
            )

        # Check if we should request session topic generation
        if (self.mode != SessionMode.PROGRAM and
            self.auto_generate_session_topic and
            self._total_output_tokens > self.topic_generation_token_threshold):
            # Check if topic has already been set
            from ...model.session import Session
            from sqlmodel import select

            async with self.async_session_factory() as db_session:
                stmt = select(Session).where(Session.session_id == self.session_id)
                result = await db_session.execute(stmt)
                db_session_obj = result.scalar_one_or_none()

                if db_session_obj and not db_session_obj.topic:
                    logger.info(
                        f"Topic generation threshold reached: session_id={self.session_id}, "
                        f"total_output_tokens={self._total_output_tokens}, "
                        f"threshold={self.topic_generation_token_threshold}"
                    )
                    self.enqueue_event({
                        "event_type": EventType.SYSTEM_MESSAGE,
                        "payload": {
                            "message": "Please provide a concise topic for this session using the set_session_topic tool (maximum 80 characters). IMPORTANT: Generate the topic in the same language as our current conversation."
                        }
                    })

        # Reset interrupt flag
        self._is_interrupted = False

    async def _should_close_after_event(self, event: dict) -> bool:
        """
        Determine if session should close after processing an event.

        Auto-close logic:
        - CHAT/PROGRAM mode: Never auto-close (user controls lifecycle)
        - BACKGROUND mode: Depends on connection's session_alignment strategy
          - If no connection exists: Don't close
          - If session_alignment is TASKING: Close after each event
          - If session_alignment is MIRRORING: Close only when upstream session ends (SESSION_END event)
          - If session_alignment is AGENT_DRIVEN: Close only when agent sends task_complete signal

        Args:
            event: The event that was just processed

        Returns:
            True if session should close, False to continue
        """
        # Interactive/Program sessions don't auto-close
        if self.mode in (SessionMode.CHAT, SessionMode.PROGRAM):
            return False

        # Background mode: Check connection configuration
        event_type = event.get('event_type')

        # Internal events (USER_MESSAGE_EVENT) don't trigger auto-close
        if event_type == EventType.USER_MESSAGE_EVENT:
            return False

        if event_type == EventType.TASK_COMPLETE_EVENT:
            # This event has already been validated by the task_complete MCP tool
            # (verified SessionRouting exists and Connection is AGENT_DRIVEN)
            upstream_session_id = event.get('payload', {}).get('upstream_session_id', 'UNKNOWN')
            upstream_node_id = event.get('payload', {}).get('upstream_node_id', 'UNKNOWN')
            logger.info(
                f"AGENT_DRIVEN session {self.session_id} received validated task_complete signal "
                f"from upstream_session={upstream_session_id}, upstream_node={upstream_node_id}, "
                f"will auto-close"
            )
            return True

        from ...model.connection import Connection
        from sqlmodel import select

        # Get source_node_id from event
        source_node_id = event.get('source_node_id')
        if not source_node_id:
            logger.warning(
                f"Network event missing source_node_id: event_type={event_type}, "
                f"session {self.session_id} will not auto-close"
            )
            return False

        # Query connection from source_node to current node
        async with self.async_session_factory() as db_session:
            stmt = select(Connection).where(
                Connection.mosaic_id == self.node.mosaic_instance.mosaic.id,
                Connection.source_node_id == source_node_id,
                Connection.target_node_id == self.node.node.node_id,
                Connection.deleted_at.is_(None)
            )
            result = await db_session.execute(stmt)
            connection = result.scalar_one_or_none()

        # If no connection exists, don't auto-close
        if not connection:
            logger.debug(
                f"No connection found from {source_node_id} to {self.node.node.node_id}, "
                f"session {self.session_id} will not auto-close"
            )
            return False

        # Check session alignment strategy
        if connection.session_alignment == SessionAlignment.TASKING:
            # TASKING: Close after each event (one session per task)
            logger.info(
                f"TASKING session {self.session_id} completed event, will auto-close"
            )
            return True

        elif connection.session_alignment == SessionAlignment.MIRRORING:
            # MIRRORING: Close only when upstream session ends
            should_close = (event_type == EventType.SESSION_END)

            if should_close:
                logger.info(
                    f"MIRRORING session {self.session_id} received SESSION_END, will auto-close"
                )

            return should_close

        # Unknown alignment strategy, don't auto-close
        logger.warning(
            f"Unknown session_alignment {connection.session_alignment} for connection "
            f"{source_node_id} -> {self.node.node.node_id}, session {self.session_id} will not auto-close"
        )
        return False

    async def _on_event_loop_exited(self):
        """
        Clean up session resources.

        Called after worker task is cancelled.
        """
        logger.info(f"Cleaning up ClaudeCodeSession: session_id={self.session_id}")

        # Cancel background monitor task if running (LONG_RUNNING mode)
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            logger.info(
                f"Background monitor task cancelled: session_id={self.session_id}"
            )

        # Sync final session state to database
        try:
            await self._update_session_to_db()
        except Exception as e:
            logger.error(
                f"Error updating session to DB during close: session_id={self.session_id}, error={e}",
                exc_info=True
            )

        # Disconnect Claude SDK client
        if self._cc_client:
            try:
                await self._cc_client.query("/exit")
                async for _ in self._cc_client.receive_response():
                    pass
                await self._cc_client.disconnect()
                logger.info(f"Claude SDK client disconnected: session_id={self.session_id}")
            except Exception as e:
                logger.error(
                    f"Error disconnecting Claude SDK: session_id={self.session_id}, error={e}",
                    exc_info=True
                )
            self._cc_client = None

        # Publish session_end event (all modes except PROGRAM)
        if self.mode != SessionMode.PROGRAM:
            try:
                await self.node.send_event(
                    source_session_id=self.session_id,
                    event_type=EventType.SESSION_END,
                    payload={}
                )
                logger.info(
                    f"Published session_end event: session_id={self.session_id}"
                )
            except Exception as e:
                logger.error(
                    f"Error publishing session_end event: {e}",
                    exc_info=True
                )

        # Reset statistics and session state
        self._total_cost_usd = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._context_usage = 0
        self._context_percentage = 0.0
        self._message_count = 0
        self._last_activity_at = None

        logger.info(f"ClaudeCodeSession cleanup complete: session_id={self.session_id}")

        UserMessageBroker.get_instance().push_from_worker(self.node.node.user_id, {
            "role": MessageRole.NOTIFICATION,
            "message_type": MessageType.SESSION_ENDED,
            "session_id": self.session_id,
            "payload": {
                "session_id": self.session_id
            }
        })
        logger.info(f"Pushed session_ended notification to WebSocket: session_id={self.session_id}")

    async def _on_initialize(self):
        pass

    async def _on_close(self):
        pass

    # ========== Task Progress Monitoring (LONG_RUNNING mode) ==========

    async def _monitor_task_progress(self):
        """
        Background task that monitors progress for LONG_RUNNING sessions.

        This task runs continuously and checks every 10 seconds:
        - If runtime_status is IDLE
        - If task has been started (acknowledge_task_started called)
        - If task has NOT been acknowledged as finished

        If all conditions are met, it sends a reminder to the agent to continue working.

        This ensures the agent doesn't get stuck waiting and continues until
        the task is explicitly marked as complete.
        """
        logger.info(
            f"Task progress monitor started for LONG_RUNNING session: session_id={self.session_id}"
        )

        try:
            while True:
                # Wait 10 seconds before next check
                await asyncio.sleep(10)

                # Check if session should be monitored
                from ...model.session import Session
                from sqlmodel import select

                async with self.async_session_factory() as db_session:
                    stmt = select(Session).where(Session.session_id == self.session_id)
                    result = await db_session.execute(stmt)
                    db_session_obj = result.scalar_one_or_none()

                    if not db_session_obj:
                        logger.warning(
                            f"Session not found in database, stopping monitor: session_id={self.session_id}"
                        )
                        break

                    runtime_status = db_session_obj.runtime_status

                # Check conditions: IDLE, task started, and task not finished
                if (runtime_status == RuntimeStatus.IDLE and
                    self._task_started and
                    not self._task_acknowledged):
                    logger.info(
                        f"LONG_RUNNING session is IDLE and task not finished, sending reminder: "
                        f"session_id={self.session_id}"
                    )

                    # Send reminder event to continue working
                    self.enqueue_event({
                        "event_type": EventType.SYSTEM_MESSAGE,
                        "payload": {
                            "message": (
                                "Task progress check: You are currently idle. "
                                "If you have completed all tasks, please call the acknowledge_task_finished tool. "
                                "Otherwise, please continue working on the current task."
                            )
                        }
                    })

        except asyncio.CancelledError:
            logger.info(
                f"Task progress monitor cancelled: session_id={self.session_id}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Error in task progress monitor: session_id={self.session_id}, error={e}",
                exc_info=True
            )

    # ========== Claude Client Management ==========

    async def _restart_claude_client(self) -> None:
        """
        Restart Claude SDK client to clear conversation context.

        This is used when the session receives a self-referencing message,
        allowing the session to continue with a fresh context while maintaining
        the same session_id.

        Steps:
        1. Reset notification flags
        2. Disconnect old client (send /exit, receive remaining messages, disconnect)
        3. Create and connect new client with same configuration
        """
        # Step 1: Reset notification tracking
        # After restart, reset flag and update effective threshold
        self._token_threshold_notified = False
        self._effective_threshold = self._total_output_tokens + self.token_threshold
        logger.debug(
            f"Reset notification tracking: session_id={self.session_id}, "
            f"current_tokens={self._total_output_tokens}, "
            f"effective_threshold={self._effective_threshold}, "
            f"base_threshold={self.token_threshold}"
        )

        # Step 2: Disconnect old client
        if self._cc_client:
            try:
                logger.debug(f"Disconnecting old Claude client: session_id={self.session_id}")
                await self._cc_client.query("/exit")
                async for _ in self._cc_client.receive_response():
                    pass
                await self._cc_client.disconnect()
                logger.debug(f"Old Claude client disconnected: session_id={self.session_id}")
            except Exception as e:
                logger.error(
                    f"Error disconnecting old Claude client: session_id={self.session_id}, error={e}",
                    exc_info=True
                )
            self._cc_client = None

        # Step 3: Create new client with same configuration
        logger.debug(f"Creating new Claude client: session_id={self.session_id}")

        # Get system prompt from node template
        system_prompt = self.node._system_prompt_template.replace("###session_id###", self.session_id)

        # Configure MCP servers
        mcp_servers = self.mcp_servers.copy()
        mcp_servers["mosaic-mcp-server"] = self._create_mosaic_mcp_server()

        # Configure Claude SDK
        cc_options = ClaudeAgentOptions(
            model=self.model,
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": system_prompt
            },
            cwd=str(self.node.node_path),
            permission_mode="bypassPermissions",
            hooks={
                "PreToolUse": [
                    HookMatcher(hooks=[self._pre_tool_use_hook])
                ],
                "PostToolUse": [
                    HookMatcher(hooks=[self._post_tool_use_hook])
                ],
            },
            mcp_servers=mcp_servers,
            allowed_tools=["*"],
            setting_sources=["project"],
            max_thinking_tokens=2000
        )

        # Create and connect new client
        self._cc_client = ClaudeSDKClient(cc_options)
        await self._cc_client.connect()

        logger.debug(f"New Claude client connected: session_id={self.session_id}")

    # ========== User Message Handling ==========

    async def interrupt(self) -> None:
        """
        Interrupt current Claude operation.

        This calls the Claude SDK interrupt method.
        """
        if self._cc_client:
            await self._cc_client.interrupt()
            self._is_interrupted = True
            logger.info(f"Session {self.session_id} interrupted by user")
        else:
            logger.warning(
                f"Cannot interrupt session {self.session_id}: Claude SDK not connected"
            )

    # ========== Claude SDK Processing ==========

    async def process_user_message(self, message: str):
        """
        Enqueue a user message for processing.

        This method wraps the user input into an internal event and enqueues it
        to the session's event queue. The actual processing happens in _handle_event.

        This method is called:
        - From node.send_message (WebSocket/API entry point)

        Args:
            message: User input text
        """
        # Wrap message into internal event
        event = {
            "event_type": EventType.USER_MESSAGE_EVENT,
            "payload": {"message": message}
        }

        # Enqueue for processing by worker loop
        self.enqueue_event(event)

        logger.debug(
            f"User message enqueued: session_id={self.session_id}, "
            f"message_length={len(message)}"
        )

    async def _receive_assistant_response(self) -> Optional[Dict[str, Any]]:
        """
        Receive Claude's response and forward to WebSocket.

        Processes AssistantMessage and ResultMessage blocks:
        - TextBlock -> assistant_text message
        - ThinkingBlock -> assistant_thinking message
        - ToolUseBlock -> assistant_tool_use message
        - ResultMessage -> assistant_result message

        Returns:
            Statistics dict with cost_usd, input_tokens, output_tokens if ResultMessage received,
            None otherwise
        """
        async for message in self._cc_client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        message_id, sequence, timestamp = await self._save_message_to_db(
                            role=MessageRole.ASSISTANT,
                            message_type=MessageType.ASSISTANT_TEXT,
                            payload={"message": block.text}
                        )
                        self._push_to_websocket(
                            role=MessageRole.ASSISTANT,
                            message_type=MessageType.ASSISTANT_TEXT,
                            message_id=message_id,
                            sequence=sequence,
                            timestamp=timestamp,
                            payload={"message": block.text}
                        )

                    elif isinstance(block, ThinkingBlock):
                        message_id, sequence, timestamp = await self._save_message_to_db(
                            role=MessageRole.ASSISTANT,
                            message_type=MessageType.ASSISTANT_THINKING,
                            payload={"message": block.thinking}
                        )
                        self._push_to_websocket(
                            role=MessageRole.ASSISTANT,
                            message_type=MessageType.ASSISTANT_THINKING,
                            message_id=message_id,
                            sequence=sequence,
                            timestamp=timestamp,
                            payload={"message": block.thinking}
                        )
            elif isinstance(message, SystemMessage):
                logger.debug(f"System message received: {json.dumps(message.data, ensure_ascii=False)}")

            elif isinstance(message, ResultMessage):
                # Collect statistics for return
                cost_usd = message.total_cost_usd or 0.0
                input_tokens = message.usage.get("input_tokens", 0)
                output_tokens = message.usage.get("output_tokens", 0)

                # Calculate context window usage
                cache_creation_tokens = message.usage.get("cache_creation_input_tokens", 0)
                cache_read_tokens = message.usage.get("cache_read_input_tokens", 0)
                context_usage = input_tokens + cache_creation_tokens + cache_read_tokens
                context_percentage = (context_usage / 200000) * 100  # 200k token window

                # Save result message to database and push to WebSocket
                message_id, sequence, timestamp = await self._save_message_to_db(
                    role=MessageRole.ASSISTANT,
                    message_type=MessageType.ASSISTANT_RESULT,
                    payload={
                        "message": message.result,
                        "total_cost_usd": self._total_cost_usd + cost_usd,
                        "total_input_tokens": self._total_input_tokens + input_tokens,
                        "total_output_tokens": self._total_output_tokens + output_tokens,
                        "cost_usd": cost_usd,
                        "usage": message.usage,
                        "context_usage": context_usage,
                        "context_percentage": context_percentage
                    }
                )
                self._push_to_websocket(
                    role=MessageRole.ASSISTANT,
                    message_type=MessageType.ASSISTANT_RESULT,
                    message_id=message_id,
                    sequence=sequence,
                    timestamp=timestamp,
                    payload={
                        "message": message.result,
                        "total_cost_usd": self._total_cost_usd + cost_usd,
                        "total_input_tokens": self._total_input_tokens + input_tokens,
                        "total_output_tokens": self._total_output_tokens + output_tokens,
                        "cost_usd": cost_usd,
                        "usage": message.usage,
                        "context_usage": context_usage,
                        "context_percentage": context_percentage
                    }
                )

                # Publish session_response event (all modes except PROGRAM, and not interrupted)
                if self.mode != SessionMode.PROGRAM and not self._is_interrupted:
                    await self.node.send_event(
                        source_session_id=self.session_id,
                        event_type=EventType.SESSION_RESPONSE,
                        payload={"response": message.result}
                    )

                # Return statistics
                return {
                    "cost_usd": cost_usd,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "context_usage": context_usage,
                    "context_percentage": context_percentage
                }

        # Return None if no ResultMessage received
        return None

    async def _save_message_to_db(
        self,
        role: MessageRole,
        message_type: MessageType,
        payload: dict
    ) -> tuple[str, int, datetime]:
        """
        Save message to database.

        This method performs:
        1. Generate message ID and increment sequence number
        2. Update in-memory session state (message count, last activity time)
        3. Create message record in database

        Args:
            role: Message role enum
            message_type: Message type enum
            payload: Message payload dict (structure depends on message_type)

        Returns:
            Tuple of (message_id, sequence, timestamp)
        """
        import uuid
        from ...model.message import Message

        # 1. Generate message metadata
        message_id = str(uuid.uuid4())
        timestamp = datetime.now()

        # 2. Increment sequence number and update session state
        self._message_sequence += 1
        sequence = self._message_sequence
        self._message_count += 1
        self._last_activity_at = timestamp

        # 3. Save message to database
        async with self.async_session_factory() as db_session:
            db_message = Message(
                message_id=message_id,
                user_id=self.node.node.user_id,
                mosaic_id=self.node.mosaic_instance.mosaic.id,
                node_id=self.node.node.node_id,
                session_id=self.session_id,
                role=role,
                message_type=message_type,
                payload=payload,
                sequence=sequence
            )
            db_session.add(db_message)
            await db_session.commit()

        logger.debug(
            f"Message saved to database: session_id={self.session_id}, "
            f"message_id={message_id}, type={message_type.value}, sequence={sequence}"
        )

        return message_id, sequence, timestamp

    async def _update_session_to_db(self):
        """
        Update session record in database.

        This method syncs in-memory session state to database:
        - message_count: Total number of messages
        - last_activity_at: Last activity timestamp
        - total_input_tokens, total_output_tokens, total_cost_usd: Token/cost statistics
        - context_usage, context_percentage: Context window usage statistics
        - updated_at: Current timestamp

        This method should be called:
        - After receiving ASSISTANT_RESULT (to update statistics)
        - Periodically or at session close (to sync state)
        """
        from ...model.session import Session
        from sqlmodel import select

        async with self.async_session_factory() as db_session:
            # Query session record
            stmt = select(Session).where(Session.session_id == self.session_id)
            result = await db_session.execute(stmt)
            db_session_obj = result.scalar_one_or_none()

            if db_session_obj:
                # Update session state
                db_session_obj.message_count = self._message_count
                db_session_obj.last_activity_at = self._last_activity_at
                db_session_obj.total_input_tokens = self._total_input_tokens
                db_session_obj.total_output_tokens = self._total_output_tokens
                db_session_obj.total_cost_usd = self._total_cost_usd
                db_session_obj.context_usage = self._context_usage
                db_session_obj.context_percentage = self._context_percentage
                db_session_obj.updated_at = datetime.now()

                await db_session.commit()

                logger.debug(
                    f"Session updated in database: session_id={self.session_id}, "
                    f"message_count={self._message_count}, "
                    f"total_cost={self._total_cost_usd:.4f}"
                )
            else:
                logger.warning(
                    f"Session record not found for update: session_id={self.session_id}"
                )

    async def _update_runtime_status_to_db(self, runtime_status: RuntimeStatus):
        """
        Update runtime_status in database.

        This method updates the runtime processing status of the session.

        Args:
            runtime_status: New runtime status (IDLE or BUSY)
        """
        from ...model.session import Session
        from sqlmodel import select

        async with self.async_session_factory() as db_session:
            # Query session record
            stmt = select(Session).where(Session.session_id == self.session_id)
            result = await db_session.execute(stmt)
            db_session_obj = result.scalar_one_or_none()

            if db_session_obj:
                # Update runtime status
                db_session_obj.runtime_status = runtime_status
                db_session_obj.updated_at = datetime.now()

                await db_session.commit()

                logger.debug(
                    f"Runtime status updated in database: session_id={self.session_id}, "
                    f"runtime_status={runtime_status.value}"
                )
            else:
                logger.warning(
                    f"Session record not found for runtime status update: session_id={self.session_id}"
                )

    def _push_to_websocket(
        self,
        role: MessageRole,
        message_type: MessageType,
        message_id: str,
        sequence: int,
        timestamp: datetime,
        payload: dict
    ):
        """
        Push message to WebSocket.

        This method only handles WebSocket push, caller is responsible for:
        - Saving message to database (_save_message_to_db)
        - Updating session state (_update_session_to_db)

        Args:
            role: Message role enum
            message_type: Message type enum
            message_id: Message ID
            sequence: Message sequence number
            timestamp: Message timestamp
            payload: Message payload dict

        Note:
            This method is called from worker thread (Loop B).
            WebSocket push uses call_soon_threadsafe for thread-safe delivery.
        """
        ws_message = {
            "session_id": self.session_id,
            "role": role.value,
            "message_type": message_type.value,
            "message_id": message_id,
            "sequence": sequence,
            "timestamp": timestamp.isoformat(),
            "payload": payload
        }

        # Get user ID and push via UserMessageBroker
        user_id = self.node.node.user_id

        user_message_broker = UserMessageBroker.get_instance()
        user_message_broker.push_from_worker(user_id, ws_message)

        logger.debug(
            f"Message pushed to WebSocket: session_id={self.session_id}, "
            f"user_id={user_id}, type={message_type.value}, sequence={sequence}"
        )

    # ========== MCP Tools and Hooks ==========

    async def _pre_tool_use_hook(
        self,
        hook_input: Dict[str, Any],
        tool_use_id: Optional[str],
        context: Any
    ):
        """
        Hook called before tool use.

        Publishes pre_tool_use event in background mode.

        Args:
            hook_input: Tool use information
            tool_use_id: Tool use ID
            context: Hook context

        Returns:
            Hook response allowing tool use
        """
        tool_name = hook_input.get("tool_name")
        tool_input = hook_input.get("tool_input")

        message_id, sequence, timestamp = await self._save_message_to_db(
            role=MessageRole.ASSISTANT,
            message_type=MessageType.ASSISTANT_TOOL_USE,
            payload={
                "tool_name": tool_name,
                "tool_input": tool_input
            }
        )
        self._push_to_websocket(
            role=MessageRole.ASSISTANT,
            message_type=MessageType.ASSISTANT_TOOL_USE,
            message_id=message_id,
            sequence=sequence,
            timestamp=timestamp,
            payload={
                "tool_name": tool_name,
                "tool_input": tool_input
            }
        )
        if self.mode != SessionMode.PROGRAM:
            await self.node.send_event(
                source_session_id=self.session_id,
                event_type=EventType.PRE_TOOL_USE,
                payload={
                    "tool_name": tool_name,
                    "tool_input": tool_input
                }
            )

        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "",
            }
        }

    async def _post_tool_use_hook(
        self,
        hook_input: Dict[str, Any],
        tool_use_id: Optional[str],
        context: Any
    ):
        tool_name = hook_input.get("tool_name")
        tool_output = hook_input.get("tool_response")
        
        message_id, sequence, timestamp = await self._save_message_to_db(
            role=MessageRole.ASSISTANT,
            message_type=MessageType.ASSISTANT_TOOL_OUTPUT,
            payload={
                "tool_name": tool_name,
                "tool_output": tool_output
            }
        )
        self._push_to_websocket(
            role=MessageRole.ASSISTANT,
            message_type=MessageType.ASSISTANT_TOOL_OUTPUT,
            message_id=message_id,
            sequence=sequence,
            timestamp=timestamp,
            payload={
                "tool_name": tool_name,
                "tool_output": tool_output
            }
        )
        if self.mode != SessionMode.PROGRAM:
            await self.node.send_event(
                source_session_id=self.session_id,
                event_type=EventType.POST_TOOL_USE,
                payload={
                    "tool_name": tool_name,
                    "tool_output": tool_output
                }
            )
        
        return {}

    def _create_mosaic_mcp_server(self):
        """
        Create Mosaic MCP server with tools for inter-node communication.

        Provides:
        - send_message: Send message to another node
        - send_email: Send email via email node
        - task_complete: Signal that the current task has been completed
        """
        @tool(
            "send_message",
            "Send a message to a node",
            {
                "type": "object",
                "properties": {
                    "target_node_id": {
                        "type": "string",
                        "description": "The ID of the node to send the message to"
                    },
                    "target_session_id": {
                        "type": "string",
                        "description": "The ID of the session to send the message to"
                    },
                    "message": {
                        "type": "string",
                        "description": "The message to send"
                    }
                },
                "required": ["target_node_id", "message"]
            }
        )
        async def send_message(args):
            try:
                target_node_id = args['target_node_id']
                target_session_id = args.get('target_session_id', None)
                message = args['message']

                # Auto-fill target_session_id for LONG_RUNNING mode when sending to self
                if (self.mode == SessionMode.LONG_RUNNING and
                    target_node_id == self.node.node.node_id):
                    target_session_id = self.session_id
                    logger.debug(
                        f"LONG_RUNNING mode: Auto-filled target_session_id for self-referencing message: "
                        f"session_id={self.session_id}"
                    )

                await self.node.send_event(
                    source_session_id=self.session_id,
                    event_type=EventType.NODE_MESSAGE,
                    payload={"message": message},
                    target_node_id=target_node_id,
                    target_session_id=target_session_id
                )

                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Successfully sent message to node {target_node_id}"
                        }
                    ]
                }
            except Exception as e:
                logger.error(
                    f"Failed to send message to node {target_node_id}: {e}",
                    exc_info=True
                )
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to send message to node {target_node_id}: {str(e)}"
                        }
                    ]
                }

        @tool(
            "send_email",
            "Send email through the email node",
            {
                "email_node_id": str,
                "to": str,
                "subject": str,
                "text": str
            }
        )
        async def send_email(args):
            try:
                email_node_id = args['email_node_id']
                to = args['to']
                subject = args['subject']
                text = args['text']

                await self.node.send_event(
                    source_session_id=self.session_id,
                    event_type=EventType.EMAIL_MESSAGE,
                    payload={
                        "to": to,
                        "subject": subject,
                        "text": text
                    },
                    target_node_id=email_node_id
                )

                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Successfully sent email to {to}"
                        }
                    ]
                }
            except Exception as e:
                logger.error(f"Failed to send email: {e}", exc_info=True)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to send email: {str(e)}"
                        }
                    ]
                }

        @tool(
            "set_session_topic",
            "Set the topic/title for the current session",
            {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic/title that summarizes this session's content (maximum 80 characters). Use the same language as the current conversation."
                    }
                },
                "required": ["topic"]
            }
        )
        async def set_session_topic(args):
            """
            Set the topic/title for the current session.

            This tool allows the agent to provide a descriptive topic for the session,
            which will be stored in the database for easy reference and organization.
            The topic should be in the same language as the conversation.
            """
            try:
                topic = args.get('topic')

                if not topic:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": "Error: topic is required"
                            }
                        ]
                    }

                # Validate topic length (max 80 characters)
                if len(topic) > 80:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error: topic is too long ({len(topic)} characters). Maximum length is 80 characters."
                            }
                        ]
                    }

                # Update session topic in database
                from ...model.session import Session
                from sqlmodel import select

                async with self.async_session_factory() as db_session:
                    stmt = select(Session).where(Session.session_id == self.session_id)
                    result = await db_session.execute(stmt)
                    db_session_obj = result.scalar_one_or_none()

                    if not db_session_obj:
                        logger.error(
                            f"Session not found when setting topic: session_id={self.session_id}"
                        )
                        return {
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Error: Session not found in database"
                                }
                            ]
                        }

                    # Update topic
                    db_session_obj.topic = topic
                    db_session_obj.updated_at = datetime.now()
                    await db_session.commit()

                    logger.info(
                        f"Session topic updated: session_id={self.session_id}, topic='{topic}'"
                    )

                # Send WebSocket notification to frontend
                from ...websocket import UserMessageBroker
                user_message_broker = UserMessageBroker.get_instance()
                user_message_broker.push_from_worker(self.node.node.user_id, {
                    "role": MessageRole.NOTIFICATION,
                    "message_type": MessageType.TOPIC_UPDATED,
                    "session_id": self.session_id,
                    "payload": {
                        "session_id": self.session_id,
                        "topic": topic
                    }
                })
                logger.info(
                    f"Pushed topic_updated notification to WebSocket: "
                    f"session_id={self.session_id}, topic='{topic}'"
                )

                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Successfully set session topic to: {topic}"
                        }
                    ]
                }
            except Exception as e:
                logger.error(
                    f"Failed to set session topic: session_id={self.session_id}, error={e}",
                    exc_info=True
                )
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to set session topic: {str(e)}"
                        }
                    ]
                }

        @tool(
            "task_complete",
            "Signal that the current task has been completed.",
            {
                "type": "object",
                "properties": {
                    "upstream_session_id": {
                        "type": "string",
                        "description": (
                            "The session ID that assigned this task to you. "
                            "When you receive an event, look for the 'source_session_id' field - "
                            "use that value here to signal you've completed that session's task."
                        )
                    }
                },
                "required": ["upstream_session_id"]
            }
        )
        async def task_complete(args):
            """
            Signal task completion for AGENT_DRIVEN sessions.

            When called, this validates that:
            1. There is a SessionRouting between upstream_session and current session
            2. The Connection has session_alignment = AGENT_DRIVEN

            If validation passes, enqueues TASK_COMPLETE_EVENT which triggers session closure.
            """
            try:
                upstream_session_id = args.get('upstream_session_id')

                if not upstream_session_id:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": "Error: upstream_session_id is required"
                            }
                        ]
                    }

                # === Validation: Check SessionRouting and Connection ===
                from ...model.session_routing import SessionRouting
                from ...model.connection import Connection
                from ...enum import SessionAlignment
                from sqlmodel import select

                async with self.async_session_factory() as db_session:
                    # 1. Query SessionRouting: Find upstream node via routing table
                    stmt = select(SessionRouting).where(
                        SessionRouting.mosaic_id == self.node.mosaic_instance.mosaic.id,
                        SessionRouting.local_session_id == upstream_session_id,
                        SessionRouting.remote_node_id == self.node.node.node_id,
                        SessionRouting.remote_session_id == self.session_id,
                        SessionRouting.deleted_at.is_(None)
                    )
                    result = await db_session.execute(stmt)
                    routing = result.scalar_one_or_none()

                    if not routing:
                        logger.warning(
                            f"Invalid task_complete call: No routing found for "
                            f"upstream_session={upstream_session_id}, current_session={self.session_id}"
                        )
                        return {
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        f"Invalid task_complete call: No routing relationship found with "
                                        f"upstream session {upstream_session_id}. Make sure you received an "
                                        f"event from that session."
                                    )
                                }
                            ]
                        }

                    # 2. Check Connection: Validate session_alignment is AGENT_DRIVEN
                    upstream_node_id = routing.local_node_id

                    stmt = select(Connection).where(
                        Connection.mosaic_id == self.node.mosaic_instance.mosaic.id,
                        Connection.source_node_id == upstream_node_id,
                        Connection.target_node_id == self.node.node.node_id,
                        Connection.deleted_at.is_(None)
                    )
                    result = await db_session.execute(stmt)
                    connection = result.scalar_one_or_none()

                    if not connection:
                        logger.warning(
                            f"Invalid task_complete call: No connection found from "
                            f"upstream_node={upstream_node_id} to current_node={self.node.node.node_id}"
                        )
                        return {
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        f"Invalid task_complete call: No connection found from upstream node. "
                                        f"This tool can only be used when there is a valid connection."
                                    )
                                }
                            ]
                        }

                    if connection.session_alignment != SessionAlignment.AGENT_DRIVEN:
                        # Not an error - just a no-op for non-AGENT_DRIVEN connections
                        logger.info(
                            f"task_complete called on non-AGENT_DRIVEN connection "
                            f"(session_alignment={connection.session_alignment.value}), "
                            f"treating as no-op: session_id={self.session_id}, "
                            f"upstream_session={upstream_session_id}"
                        )
                        return {
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        f"Task completion acknowledged for upstream session {upstream_session_id}. "
                                        f"Session lifecycle is managed by the upstream session."
                                    )
                                }
                            ]
                        }

                # === Validation passed: Enqueue task completion event ===
                event = {
                    "event_type": EventType.TASK_COMPLETE_EVENT,
                    "payload": {
                        "upstream_session_id": upstream_session_id,
                        "upstream_node_id": upstream_node_id
                    }
                }

                self.enqueue_event(event)

                logger.info(
                    f"Task completion signal sent: session_id={self.session_id}, "
                    f"upstream_session={upstream_session_id}, upstream_node={upstream_node_id}"
                )

                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Task marked as complete for upstream session {upstream_session_id}. "
                                f"Session will close after current processing."
                            )
                        }
                    ]
                }
            except Exception as e:
                logger.error(
                    f"Failed to signal task completion: session_id={self.session_id}, error={e}",
                    exc_info=True
                )
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to signal task completion: {str(e)}"
                        }
                    ]
                }

        # Build tools list based on session mode
        tools = [send_message, send_email, set_session_topic, task_complete]

        # Add LONG_RUNNING mode specific tools
        if self.mode == SessionMode.LONG_RUNNING:
            @tool(
                "acknowledge_task_started",
                "Acknowledge that you have understood the task and are ready to start working on it.",
                {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            )
            async def acknowledge_task_started(args):
                """
                Acknowledge task start for LONG_RUNNING sessions.

                This tool allows the agent to signal that it has understood the task
                and is ready to start working. After calling this tool, the monitoring
                system will start checking progress and send reminders if the agent
                becomes idle without finishing the task.
                """
                try:
                    # Set task started flag
                    self._task_started = True

                    logger.info(
                        f"Task acknowledged as started: session_id={self.session_id}"
                    )

                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": "Task acknowledged as started. Progress monitoring is now active."
                            }
                        ]
                    }
                except Exception as e:
                    logger.error(
                        f"Failed to acknowledge task start: session_id={self.session_id}, error={e}",
                        exc_info=True
                    )
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Failed to acknowledge task start: {str(e)}"
                            }
                        ]
                    }

            @tool(
                "acknowledge_task_finished",
                "Acknowledge that the current task has been finished.",
                {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            )
            async def acknowledge_task_finished(args):
                """
                Acknowledge task completion for LONG_RUNNING sessions.

                This tool allows the agent to signal that it has finished the current task
                and is ready to accept new tasks. The session continues to run.
                """
                try:
                    # Set task acknowledgment flag
                    self._task_acknowledged = True

                    logger.info(
                        f"Task acknowledged as finished: session_id={self.session_id}"
                    )

                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": "Task acknowledged as finished. Ready for next task."
                            }
                        ]
                    }
                except Exception as e:
                    logger.error(
                        f"Failed to acknowledge task: session_id={self.session_id}, error={e}",
                        exc_info=True
                    )
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Failed to acknowledge task: {str(e)}"
                            }
                        ]
                    }

            tools.append(acknowledge_task_started)
            tools.append(acknowledge_task_finished)

        return create_sdk_mcp_server(
            name="mosaic-mcp-server",
            tools=tools
        )

    # ========== Helper Methods ==========

    def _format_event_for_claude(self, event: dict) -> str:
        """
        Format an event for Claude.

        For USER_MESSAGE_EVENT (internal):
            - Extract and return the message content directly

        For network events (from Event Mesh):
            - Format as JSON following [Event Message Format] in system prompt
            - Exclude target_node_id and target_session_id (receiver already knows)

        Args:
            event: Event dict

        Returns:
            Formatted message string
        """
        event_type = event.get("event_type")

        # Internal event: User message (direct input)
        if event_type == EventType.USER_MESSAGE_EVENT:
            payload = event.get("payload", {})
            return payload.get("message", "")

        if event_type == EventType.SYSTEM_MESSAGE:
            formatted_event = {
                "event_type": EventType.SYSTEM_MESSAGE,
                "payload": event.get("payload", {})
            }
        else:
            # Network events: Format as structured event
            formatted_event = {
                "event_id": event.get("event_id", "unknown"),
                "event_type": event.get("event_type", "unknown"),
                "source_node_id": event.get("source_node_id", "unknown"),
                "source_session_id": event.get("source_session_id", "unknown"),
                "payload": event.get("payload", {})
            }

        # Convert to formatted JSON string
        message = f"{json.dumps(formatted_event, indent=2, ensure_ascii=False)}"

        return message
