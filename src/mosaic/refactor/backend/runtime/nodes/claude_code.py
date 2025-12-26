"""Claude Code node implementation"""

import asyncio
import json
import uuid
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Callable, Awaitable, Any, TYPE_CHECKING

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    HookMatcher,
    tool,
    create_sdk_mcp_server
)

from ..node import MosaicNode
from ..session import MosaicSession
from ..system_prompt import generate_system_prompt
from ...models.subscription import Subscription
from ...models.connection import Connection
from ...models.session_routing import SessionRouting
from ...database import engine
from ...logger import get_logger

if TYPE_CHECKING:
    from ...models.node import Node
    from ..event import MosaicEvent

logger = get_logger(__name__)


class ClaudeCodeNode(MosaicNode):
    """
    Claude Code node - manages Claude Agent SDK sessions.

    Key responsibilities:
    - Manage multiple ClaudeCodeSession instances
    - Provide event publishing capability to sessions
    - Integrate with Event Mesh via inherited ZMQ client
    """

    def __init__(self, node: 'Node', workspace: Path):
        """
        Initialize Claude Code node.

        Args:
            node: Database Node instance
            workspace: Working directory for Claude Code
        """
        super().__init__(node, workspace)

        logger.info(
            f"Initialized ClaudeCodeNode: "
            f"mosaic={self.node.mosaic_id}, node={self.node.node_id}, workspace={workspace}"
        )

    async def on_start(self):
        """Node startup hook (called by base class)"""
        logger.info(f"ClaudeCodeNode {self.node.node_id} started")

    async def on_stop(self):
        """Node cleanup hook (called by base class)"""
        logger.info(f"ClaudeCodeNode {self.node.node_id} stopped")

    async def start_mosaic_session(
        self,
        session_id: str,
        config: Dict[str, Any] | None = None
    ) -> MosaicSession:
        """
        Create and start a Claude Code session.

        This is the base class interface implementation.

        Args:
            session_id: Session UUID
            config: Session configuration (must include 'user_id')

        Returns:
            ClaudeCodeSession instance
        """
        config = config or {}

        # Get user_id from config, or use node's user_id for auto-created sessions
        user_id = config.get('user_id')
        if not user_id:
            # For auto-created sessions (from events), use node's user_id
            user_id = self.node.user_id
            logger.debug(
                f"Using node's user_id={user_id} for auto-created session {session_id}"
            )

        # Create new session
        session = ClaudeCodeSession(
            node=self,
            session_id=session_id,
            config=config,
            user_id=user_id
        )

        # Session will be started and registered by base class
        logger.info(f"Created Claude Code session {session_id} for node {self.node.node_id}")

        return session

    async def publish_event(
        self,
        session_id: str,
        event_type: str,
        payload: dict,
        target_node_id: Optional[int] = None
    ):
        """
        Publish event to Event Mesh.

        This method handles:
        - Direct messaging (when target_node_id is specified)
        - Publish-subscribe (when target_node_id is None)
        - Session routing and alignment

        Args:
            session_id: Source session ID
            event_type: Event type (from EventType enum)
            payload: Event payload
            target_node_id: Optional target node ID for direct messaging
        """
        logger.info(
            f"[EVENT_PUBLISH] publish_event called: event_type={event_type}, "
            f"session_id={session_id}, source_node_id={self.node.id}, "
            f"target_node_id={target_node_id}, payload={payload}"
        )

        from sqlmodel.ext.asyncio.session import AsyncSession as AsyncSessionType

        async with AsyncSessionType(engine) as db:
            events = []

            if target_node_id is not None:
                # Direct messaging to specific node
                logger.debug(
                    f"[EVENT_PUBLISH] Direct messaging mode to node {target_node_id}"
                )
                event = await self._create_direct_event(
                    db,
                    session_id,
                    event_type,
                    payload,
                    target_node_id
                )
                if event:
                    events.append(event)
                else:
                    logger.warning(
                        f"[EVENT_PUBLISH] Direct event creation failed for node {target_node_id}"
                    )

            else:
                # Publish-subscribe: find all subscribers
                logger.info(
                    f"[EVENT_PUBLISH] Pub-sub mode: finding subscribers for event_type={event_type}"
                )
                events = await self._create_subscriber_events(
                    db,
                    session_id,
                    event_type,
                    payload
                )
                logger.info(
                    f"[EVENT_PUBLISH] Found {len(events)} subscriber events"
                )

        # Send events via ZMQ
        logger.info(f"[EVENT_PUBLISH] Sending {len(events)} events via ZMQ")
        for event in events:
            target_mosaic_id = str(self.node.mosaic_id)
            target_node_id_str = str(event["target_id"])

            logger.info(
                f"[EVENT_PUBLISH] Sending event {event['event_id']} to "
                f"topic {target_mosaic_id}#{target_node_id_str}: {event}"
            )

            await self._zmq_client.send(
                target_mosaic_id,
                target_node_id_str,
                event
            )

            logger.info(
                f"[EVENT_PUBLISH] Event {event_type} sent successfully from session {session_id} "
                f"to node {target_node_id_str}"
            )

    async def _create_direct_event(
        self,
        db: AsyncSession,
        session_id: str,
        event_type: str,
        payload: dict,
        target_node_id: int
    ) -> Optional[dict]:
        """Create event for direct messaging"""
        # Check if connection exists (using database IDs)
        result = await db.execute(
            select(Connection).where(
                Connection.source_node_id == self.node.id,
                Connection.target_node_id == target_node_id,
                Connection.deleted_at.is_(None)
            )
        )
        connection = result.scalar_one_or_none()

        if not connection:
            logger.warning(
                f"No connection from node {self.node.id} to {target_node_id}"
            )
            return None

        # TODO: Implement session routing logic
        # For now, use simple session ID propagation
        downstream_session_id = session_id

        return {
            "event_id": str(uuid.uuid4()),
            "source_id": str(self.node.id),  # Convert to string for event model
            "target_id": str(target_node_id),  # Convert to string for event model
            "event_type": event_type,
            "upstream_session_id": session_id,
            "downstream_session_id": downstream_session_id,
            "payload": payload,
            "created_at": datetime.now().isoformat()
        }

    async def _create_subscriber_events(
        self,
        db: AsyncSession,
        session_id: str,
        event_type: str,
        payload: dict
    ) -> list:
        """Create events for all subscribers"""
        logger.info(
            f"[SUBSCRIPTION_QUERY] Querying subscriptions: "
            f"source_node_id={self.node.id}, event_type={event_type}"
        )

        # Find all subscribers for this event type (using database ID)
        result = await db.execute(
            select(Subscription).where(
                Subscription.source_node_id == self.node.id,
                Subscription.event_type == event_type,
                Subscription.deleted_at.is_(None)
            )
        )
        subscriptions = result.scalars().all()

        logger.info(
            f"[SUBSCRIPTION_QUERY] Found {len(subscriptions)} subscriptions for "
            f"event_type={event_type} from source_node_id={self.node.id}"
        )

        if not subscriptions:
            logger.warning(
                f"[SUBSCRIPTION_QUERY] No subscribers for event {event_type} from node {self.node.id}"
            )
            return []

        events = []
        for subscription in subscriptions:
            # Extract values to avoid lazy loading after commit
            target_node_id = subscription.target_node_id

            logger.info(
                f"[SUBSCRIPTION_QUERY] Processing subscription {subscription.id}: "
                f"source={subscription.source_node_id}, target={target_node_id}, "
                f"event_type={subscription.event_type}"
            )
            # Get connection for session alignment strategy
            result = await db.execute(
                select(Connection).where(
                    Connection.source_node_id == self.node.id,
                    Connection.target_node_id == target_node_id,
                    Connection.deleted_at.is_(None)
                )
            )
            connection = result.scalar_one_or_none()

            # Determine session alignment
            session_alignment = "mirroring"  # Default
            if connection:
                session_alignment = connection.session_alignment

            logger.debug(
                f"[SUBSCRIPTION_QUERY] Connection found, session_alignment={session_alignment}"
            )

            # Query SessionRouting to find existing mapping
            routing_result = await db.execute(
                select(SessionRouting).where(
                    SessionRouting.mosaic_id == self.node.mosaic_id,
                    SessionRouting.local_node_id == self.node.id,
                    SessionRouting.local_session_id == session_id,
                    SessionRouting.remote_node_id == target_node_id,
                    SessionRouting.deleted_at.is_(None)
                )
            )
            existing_routing = routing_result.scalar_one_or_none()

            new_routing_created = False
            if session_alignment == "tasking":
                # Tasking mode: Always generate new session ID
                downstream_session_id = str(uuid.uuid4())
                new_routing_created = True
                logger.info(
                    f"[SESSION_ROUTING] Tasking mode: Generated new downstream_session_id={downstream_session_id}"
                )
            else:
                # Mirroring mode: Reuse or create new session ID
                if existing_routing:
                    downstream_session_id = existing_routing.remote_session_id
                    logger.info(
                        f"[SESSION_ROUTING] Mirroring mode: Reusing existing downstream_session_id={downstream_session_id}"
                    )
                else:
                    downstream_session_id = str(uuid.uuid4())
                    new_routing_created = True
                    logger.info(
                        f"[SESSION_ROUTING] Mirroring mode: Generated new downstream_session_id={downstream_session_id}"
                    )

            # Create bidirectional routing if new
            if new_routing_created:
                # Forward routing: local -> remote
                forward_routing = SessionRouting(
                    user_id=self.node.user_id,
                    mosaic_id=self.node.mosaic_id,
                    local_node_id=self.node.id,
                    local_session_id=session_id,
                    remote_node_id=target_node_id,
                    remote_session_id=downstream_session_id
                )
                db.add(forward_routing)

                # Backward routing: remote -> local
                backward_routing = SessionRouting(
                    user_id=self.node.user_id,
                    mosaic_id=self.node.mosaic_id,
                    local_node_id=target_node_id,
                    local_session_id=downstream_session_id,
                    remote_node_id=self.node.id,
                    remote_session_id=session_id
                )
                db.add(backward_routing)

                await db.commit()
                logger.info(
                    f"[SESSION_ROUTING] Created bidirectional routing: "
                    f"({self.node.id}, {session_id}) <-> ({target_node_id}, {downstream_session_id})"
                )

            event = {
                "event_id": str(uuid.uuid4()),
                "source_id": str(self.node.id),  # Convert to string for event model
                "target_id": str(target_node_id),  # Convert to string for event model
                "event_type": event_type,
                "upstream_session_id": session_id,
                "downstream_session_id": downstream_session_id,
                "payload": payload,
                "created_at": datetime.now().isoformat()
            }
            logger.info(
                f"[SUBSCRIPTION_QUERY] Created event: event_id={event['event_id']}, "
                f"source_id={event['source_id']}, target_id={event['target_id']}, "
                f"event_type={event['event_type']}"
            )
            events.append(event)

        logger.info(
            f"[SUBSCRIPTION_QUERY] Created {len(events)} events for subscribers of {event_type}"
        )

        return events


class ClaudeCodeSession(MosaicSession):
    """
    Claude Code session with user-level WebSocket messaging.

    Key features:
    - Inherits from MosaicSession base class
    - Integrates Claude Agent SDK
    - Pushes messages to user via UserMessageBroker (thread-safe)
    - Database integration for message persistence
    """

    def __init__(
        self,
        node: ClaudeCodeNode,
        session_id: str,
        config: dict,
        user_id: int
    ):
        """
        Initialize Claude Code session.

        Args:
            node: Parent ClaudeCodeNode (provides publish_event capability)
            session_id: Session UUID
            config: Session configuration
            user_id: User ID (for WebSocket message routing)
        """
        # Initialize base class
        super().__init__(session_id, node, config)

        # User ID for message routing
        self.user_id = user_id

        # Session mode
        self.mode = config.get("mode", "background")

        # Model selection (priority: session config > node config > default)
        self.model = config.get("model") or node.node.get_config_value("model") or "sonnet"

        # Message queue for processing
        self._queue: asyncio.Queue = asyncio.Queue()

        # Claude SDK client
        self._cc_client: Optional[ClaudeSDKClient] = None

        # Background task
        self._run_task: Optional[asyncio.Task] = None

        # Statistics (in-memory, synced to DB on result)
        self._total_cost_usd = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        # Interrupt flag
        self._is_interrupted = False

        logger.debug(
            f"Initialized ClaudeCodeSession: "
            f"session={session_id}, mode={self.mode}, model={self.model}"
        )

    async def start(self):
        """Start the Claude Code session"""
        logger.info(
            f"Starting Claude Code session {self.session_id} "
            f"in {self.mode} mode with model {self.model}"
        )

        # Generate system prompt
        system_prompt = await generate_system_prompt(
            node=self.node.node,
            session_id=self.session_id
        )

        # Log system prompt for debugging
        logger.info(
            f"System prompt for session {self.session_id}:\n"
            f"{'=' * 80}\n"
            f"{system_prompt}\n"
            f"{'=' * 80}"
        )

        # Configure MCP servers
        mcp_servers = self.config.get("mcp_servers", {})
        mcp_servers["mosaic-mcp-server"] = self._create_mosaic_mcp_server()

        # Configure Claude SDK
        cc_options = ClaudeAgentOptions(
            model=self.model,
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": system_prompt
            },
            cwd=str(self.node.workspace),
            permission_mode="bypassPermissions",
            hooks={
                "PreToolUse": [
                    HookMatcher(hooks=[self._pre_tool_use_hook])
                ],
            },
            mcp_servers=mcp_servers,
            allowed_tools=["*"],
            setting_sources=["project"],
            max_thinking_tokens=2000
        )

        self._cc_client = ClaudeSDKClient(cc_options)
        await self._cc_client.connect()

        # Start background processing task
        self._run_task = asyncio.create_task(self._run_forever())

        # Publish SESSION_START event (if background mode)
        if self.mode == "background":
            logger.info(
                f"[EVENT_PUBLISH] Session {self.session_id} in background mode, "
                f"publishing session_start event from node {self.node.node.id} ({self.node.node.node_id})"
            )
            await self.node.publish_event(
                session_id=self.session_id,
                event_type="session_start",
                payload={}
            )
        else:
            logger.info(
                f"[EVENT_PUBLISH] Session {self.session_id} in {self.mode} mode, "
                f"NOT publishing session_start event"
            )

        logger.info(f"Claude Code session {self.session_id} started")

    async def close(self, force: bool = False):
        """
        Close the Claude Code session.

        Args:
            force: Force close without cleanup
        """
        logger.info(f"Closing Claude Code session {self.session_id}")

        # Reset statistics
        self._total_cost_usd = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        # Cancel background task
        if self._run_task:
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass
            self._run_task = None

        # Disconnect Claude SDK
        if self._cc_client:
            try:
                await self._cc_client.query("/exit")
                async for _ in self._cc_client.receive_response():
                    pass
                await self._cc_client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting Claude SDK: {e}")
            self._cc_client = None

        # Publish SESSION_END event (if background mode and not forced)
        if self.mode == "background" and not force:
            await self.node.publish_event(
                session_id=self.session_id,
                event_type="session_end",
                payload={}
            )

        logger.info(f"Claude Code session {self.session_id} closed")

    async def process_event(self, event: 'MosaicEvent') -> asyncio.Future | None:
        """
        Process an incoming event from Event Mesh.

        This is the MosaicSession interface implementation.
        Events are converted to user messages and queued for Claude processing.

        Args:
            event: Event to process

        Returns:
            None (events are processed asynchronously)
        """
        # For now, convert event payload to a message
        # TODO: Implement more sophisticated event handling based on event type
        payload = event.payload
        message_text = payload.get("message", str(payload))

        # Queue the message for processing
        await self.send_user_message(message_text)

        logger.debug(
            f"ClaudeCodeSession {self.session_id} queued event {event.event_type}"
        )

        return None

    async def send_user_message(self, message: str):
        """
        Send user message to Claude.

        Called from WebSocket endpoint when user sends a message.

        Args:
            message: User input text

        Returns:
            Future that completes when message is processed
        """
        future = asyncio.get_event_loop().create_future()
        await self._queue.put((message, future))
        return future

    async def interrupt(self):
        """Interrupt current Claude operation"""
        if self._cc_client:
            await self._cc_client.interrupt()
            self._is_interrupted = True
            logger.info(f"Session {self.session_id} interrupted by user")

    async def _run_forever(self):
        """
        Main processing loop.

        Waits for user messages, sends to Claude, and forwards responses via callback.
        """
        try:
            while True:
                # Wait for user message
                message, future = await self._queue.get()

                # Echo user message to WebSocket (for confirmation)
                await self._send_to_websocket(
                    role="user",
                    message_type="user_message",
                    content={"message": message}
                )

                # Publish user_prompt_submit event (if background mode)
                if self.mode == "background":
                    await self.node.publish_event(
                        session_id=self.session_id,
                        event_type="user_prompt_submit",
                        payload={"prompt": message}
                    )

                # Send to Claude
                logger.debug(f"Sending query to Claude: {message}")
                await self._cc_client.query(message)

                # Receive and forward Claude's response
                await self._receive_assistant_response()

                # Reset interrupt flag
                self._is_interrupted = False

                # Mark future as done
                future.set_result(None)

        except asyncio.CancelledError:
            logger.info(f"Run loop cancelled for session {self.session_id}")
            raise
        except Exception as e:
            logger.error(
                f"Error in run loop for session {self.session_id}: {e}\n"
                f"{traceback.format_exc()}"
            )

    async def _receive_assistant_response(self):
        """
        Receive Claude's response and forward to WebSocket.

        This processes AssistantMessage and ResultMessage blocks.
        """
        async for message in self._cc_client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        # Send assistant text to WebSocket
                        await self._send_to_websocket(
                            role="assistant",
                            message_type="assistant_text",
                            content={"message": block.text}
                        )

                    elif isinstance(block, ThinkingBlock):
                        # Send thinking to WebSocket
                        await self._send_to_websocket(
                            role="assistant",
                            message_type="assistant_thinking",
                            content={"message": block.thinking}
                        )

                    elif isinstance(block, ToolUseBlock):
                        # Send tool use to WebSocket
                        await self._send_to_websocket(
                            role="assistant",
                            message_type="assistant_tool_use",
                            content={
                                "tool_name": block.name,
                                "tool_input": block.input
                            }
                        )

            elif isinstance(message, ResultMessage):
                # Update statistics
                self._total_cost_usd += message.total_cost_usd or 0.0
                self._total_input_tokens += message.usage.get("input_tokens", 0)
                self._total_output_tokens += message.usage.get("output_tokens", 0)

                # Send result to WebSocket
                await self._send_to_websocket(
                    role="assistant",
                    message_type="assistant_result",
                    content={
                        "message": message.result,
                        "total_cost_usd": self._total_cost_usd,
                        "total_input_tokens": self._total_input_tokens,
                        "total_output_tokens": self._total_output_tokens,
                        "cost_usd": message.total_cost_usd,
                        "usage": message.usage
                    },
                    update_stats=True
                )

                # Publish session_response event (if background mode and not interrupted)
                if self.mode == "background" and not self._is_interrupted:
                    await self.node.publish_event(
                        session_id=self.session_id,
                        event_type="session_response",
                        payload={"response": message.result}
                    )

                # Break after result (end of response)
                break

    async def _send_to_websocket(
        self,
        role: str,
        message_type: str,
        content: dict,
        update_stats: bool = False
    ):
        """
        Send message to WebSocket via direct callback.

        Also saves to database and updates session statistics.

        Args:
            role: Message role (user/assistant/system)
            message_type: Message type (user_message, assistant_text, etc.)
            content: Message content dict (will be JSON serialized)
            update_stats: Whether to update session statistics in DB
        """
        timestamp = datetime.now()

        # Save to database and send via WebSocket
        from sqlmodel.ext.asyncio.session import AsyncSession
        from ...services.message_service import MessageService
        from ...services.session_service import SessionService

        # Initialize variables outside try block
        msg_id = ""
        msg_seq = 0

        # Use expire_on_commit=False to prevent lazy loading issues after commit
        async with AsyncSession(engine, expire_on_commit=False) as db:
            try:
                # Save message to database
                message = await MessageService.create_message(
                    db=db,
                    session_id=self.session_id,
                    role=role,
                    message_type=message_type,
                    content=json.dumps(content, ensure_ascii=False)
                )

                # Update session activity
                await SessionService.update_activity(db, self.session_id)

                # Update session statistics if this is a result message
                if update_stats:
                    await SessionService.update_statistics(
                        db=db,
                        session_id=self.session_id,
                        total_input_tokens=self._total_input_tokens,
                        total_output_tokens=self._total_output_tokens,
                        total_cost_usd=self._total_cost_usd
                    )

                # Extract attributes while session is still open
                # Note: expire_on_commit=False prevents lazy loading issues
                msg_id = message.message_id
                msg_seq = message.sequence

            except Exception as e:
                logger.error(
                    f"Failed to save message to database: {e}\n{traceback.format_exc()}"
                )
                return

        # Send to WebSocket via user_broker (thread-safe)
        try:
            from ...websocket.user_broker import user_broker
            user_broker.push_from_worker(self.user_id, {
                "type": message_type,
                "role": role,
                "content": content,
                "message_id": msg_id,
                "sequence": msg_seq,
                "timestamp": timestamp.isoformat(),
                "session_id": self.session_id  # For message routing
            })
        except Exception as e:
            logger.error(
                f"Failed to send message to WebSocket: {e}\n{traceback.format_exc()}"
            )

    async def _pre_tool_use_hook(
        self,
        hook_input: Dict[str, Any],
        tool_use_id: Optional[str],
        context: Any
    ):
        """
        Hook called before tool use.

        Publishes PRE_TOOL_USE event in background mode.

        Args:
            hook_input: Tool use information
            tool_use_id: Tool use ID
            context: Hook context

        Returns:
            Hook response allowing tool use
        """
        if self.mode == "background":
            await self.node.publish_event(
                session_id=self.session_id,
                event_type="pre_tool_use",
                payload={
                    "tool_name": hook_input.get("tool_name"),
                    "tool_input": hook_input.get("tool_input")
                }
            )

        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "",
            }
        }

    def _create_mosaic_mcp_server(self):
        """
        Create Mosaic MCP server with tools for inter-node communication.

        Provides:
        - send_message: Send message to another node
        - send_email: Send email via email node
        """

        @tool(
            "send_message",
            "Send a message to a node",
            {
                "target_node_id": str,
                "message": str
            }
        )
        async def send_message(args):
            try:
                target_node_id = args['target_node_id']
                message = args['message']

                await self.node.publish_event(
                    session_id=self.session_id,
                    event_type="node_message",
                    payload={"message": message},
                    target_node_id=int(target_node_id)
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
                    f"Failed to send message to node {target_node_id}: {e}\n"
                    f"{traceback.format_exc()}"
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

                await self.node.publish_event(
                    session_id=self.session_id,
                    event_type="system_message",
                    payload={
                        "to": to,
                        "subject": subject,
                        "text": text
                    },
                    target_node_id=int(email_node_id)
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
                logger.error(f"Failed to send email: {e}\n{traceback.format_exc()}")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to send email: {str(e)}"
                        }
                    ]
                }

        return create_sdk_mcp_server(
            name="mosaic-mcp-server",
            tools=[send_message, send_email]
        )
