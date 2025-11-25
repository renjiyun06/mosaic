"""
Mosaic Core Interfaces

This module defines the abstract interfaces (contracts) for the Mosaic event system.
These interfaces establish the boundaries between components and enable pluggable
implementations.

Architecture Overview:
======================

The interfaces are organized into three planes:

1. DATA PLANE - Event flow
   - MeshClient: Node's runtime interface to the mesh
   - MeshInbox: Receive events (async iterator)
   - MeshOutbox: Send events (fire-and-forget or blocking)
   - EventEnvelope: Event wrapper with ACK/NACK

2. CONTROL PLANE - Configuration
   - MeshAdmin: Node/subscription management

3. CONTEXT PLANE - Information
   - MeshContext: Topology and semantics queries

Dependency Rule:
================
This module (core.interfaces) has NO dependencies on other mosaic modules.
All other modules can depend on these interfaces.

Implementation Note:
====================
These are ABSTRACT interfaces. Concrete implementations live in:
- transport/: TransportBackend implementations
- runtime/: MeshClient, MeshInbox, MeshOutbox implementations
- storage/: Repository implementations (for MeshAdmin/MeshContext)
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional

from .models import (
    MeshEvent,
    Subscription,
    Node,
    TopologyContext,
    EventSemantics,
    NodeCapabilities,
    AggregatedDecision,
)
from .types import NodeId, MeshId, EventId


# =============================================================================
# DATA PLANE - Event Envelope
# =============================================================================

class EventEnvelope(ABC):
    """
    Wrapper around MeshEvent that provides ACK/NACK semantics.
    
    When a node receives an event from its inbox, it's wrapped in an
    envelope. The envelope provides methods to acknowledge successful
    processing or reject the event.
    
    At-Least-Once Delivery:
    -----------------------
    The envelope implements at-least-once delivery semantics:
    
    1. Event is delivered (status: PENDING -> PROCESSING)
    2. Node processes the event
    3. Node calls ack() (status: PROCESSING -> COMPLETED)
       OR nack() (status: PROCESSING -> PENDING for requeue,
                  or PROCESSING -> FAILED for discard)
    4. If neither is called and node crashes, the event becomes
       visible again after the recovery window (default 5 minutes)
    
    Usage:
        async for envelope in inbox:
            try:
                await process(envelope.event)
                await envelope.ack()
            except Exception as e:
                await envelope.nack(requeue=True)
    
    Attributes:
        event: The wrapped MeshEvent
        delivery_count: Number of times this event has been delivered
    """
    
    @property
    @abstractmethod
    def event(self) -> MeshEvent:
        """The wrapped event."""
        pass
    
    @property
    @abstractmethod
    def delivery_count(self) -> int:
        """
        Number of times this event has been delivered.
        
        A count > 1 indicates the event was redelivered after a
        failure or timeout. Nodes should implement idempotent
        processing.
        """
        pass
    
    @abstractmethod
    async def ack(self) -> None:
        """
        Acknowledge successful processing.
        
        After ack(), the event is marked as COMPLETED and will
        not be redelivered. This should be called only after
        the event has been fully processed.
        
        Raises:
            EventError: If acknowledgment fails
        """
        pass
    
    @abstractmethod
    async def nack(self, requeue: bool = True) -> None:
        """
        Reject the event.
        
        Args:
            requeue: If True, event goes back to PENDING and will
                    be redelivered. If False, event is marked FAILED.
        
        Use Cases:
            - requeue=True: Temporary failure, retry later
            - requeue=False: Permanent failure, don't retry
        
        Raises:
            EventError: If rejection fails
        """
        pass


# =============================================================================
# DATA PLANE - Inbox
# =============================================================================

class MeshInbox(ABC):
    """
    Event input channel for a node.
    
    The inbox provides events to a node as an async iterator. Events
    are delivered wrapped in EventEnvelopes for ACK/NACK handling.
    
    Design Decisions:
    -----------------
    1. Async Iterator Pattern: Allows natural "for event in inbox" usage
    2. EventEnvelope: Separates delivery semantics from event data
    3. No direct DB access: Inbox abstracts the transport layer
    
    Implementation Notes:
    --------------------
    - SQLite backend: Uses UDS signals to wake up when events arrive
    - Kafka backend: Uses consumer groups
    - Redis backend: Uses XREAD with blocking
    
    Example:
        async for envelope in inbox:
            event = envelope.event
            logger.info(f"Received {event.event_type} from {event.source_id}")
            
            if event.event_type == "PreToolUse":
                decision = await process_pre_tool_use(event)
                await outbox.reply(event.event_id, decision)
            
            await envelope.ack()
    """
    
    @abstractmethod
    def __aiter__(self) -> AsyncIterator[EventEnvelope]:
        """Return self as async iterator."""
        pass
    
    @abstractmethod
    async def __anext__(self) -> EventEnvelope:
        """
        Get the next event envelope.
        
        This method blocks until an event is available or the
        inbox is closed.
        
        Returns:
            EventEnvelope containing the next event
            
        Raises:
            StopAsyncIteration: When inbox is closed
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """
        Close the inbox.
        
        After closing:
        - __anext__ will raise StopAsyncIteration
        - No more events will be delivered
        - Resources are released
        """
        pass


# =============================================================================
# DATA PLANE - Outbox
# =============================================================================

class MeshOutbox(ABC):
    """
    Event output channel for a node.
    
    The outbox provides methods to send events and handle blocking
    subscriptions. It abstracts the complexity of event routing
    and waiting for responses.
    
    Three Sending Modes:
    --------------------
    1. send(): Fire-and-persist
       - Event is stored and routed
       - Returns immediately
       - No response expected
    
    2. send_blocking(): Send and wait for responses
       - For blocking subscriptions (!EventName)
       - Waits for all blocking subscribers to reply
       - Aggregates responses using one-vote-veto
    
    3. reply(): Respond to a received event
       - Used by subscribers to respond to blocking events
       - Wakes up the sender's waiter
    
    Implementation Notes:
    --------------------
    - send() uses EventRouter to find subscribers
    - send_blocking() uses WaiterRegistry to manage waits
    - reply() triggers the waiter in the sending node
    """
    
    @abstractmethod
    async def send(self, event: MeshEvent) -> None:
        """
        Send an event to all subscribers (fire-and-persist).
        
        The event is persisted and routed to all matching subscribers.
        This method returns immediately without waiting for processing.
        
        Args:
            event: The event to send (target_id will be set by router)
        
        Raises:
            EventDeliveryError: If event cannot be persisted
        
        Example:
            event = MeshEvent(
                event_id=generate_id(),
                mesh_id=client.mesh_id,
                source_id=client.node_id,
                event_type="StatusUpdate",
                payload={"status": "ready"}
            )
            await outbox.send(event)
        """
        pass
    
    @abstractmethod
    async def send_blocking(
        self,
        event: MeshEvent,
        timeout: float = 30.0,
    ) -> AggregatedDecision:
        """
        Send an event and wait for all blocking subscribers to respond.
        
        This is used for events that have blocking subscriptions
        (!EventName). The method:
        1. Finds all blocking subscribers
        2. Sends the event to each
        3. Waits for all responses (or timeout)
        4. Aggregates responses using one-vote-veto
        
        Args:
            event: The event to send
            timeout: Maximum seconds to wait for all responses
        
        Returns:
            AggregatedDecision with final decision and individual replies
        
        Raises:
            EventTimeoutError: If timeout expires before all responses
            EventDeliveryError: If event cannot be delivered
        
        Aggregation Rule (one-vote-veto):
            - Any DENY -> final DENY
            - Any ASK (no DENY) -> final ASK
            - All ALLOW -> final ALLOW
            - Timeout -> treat as DENY
        
        Example:
            event = MeshEvent(
                event_id=generate_id(),
                mesh_id=client.mesh_id,
                source_id=client.node_id,
                event_type="PreToolUse",
                payload={"tool_name": "bash", "args": {...}}
            )
            decision = await outbox.send_blocking(event, timeout=30.0)
            if decision.final_decision == "deny":
                logger.warning(f"Tool blocked: {decision.reasons}")
        """
        pass
    
    @abstractmethod
    async def reply(
        self,
        event_id: EventId,
        payload: dict[str, Any],
    ) -> None:
        """
        Reply to a blocking event.
        
        When a node receives a blocking event (!EventName), it must
        send a reply. This method:
        1. Creates a reply event
        2. Sends it to the original sender
        3. Triggers the sender's waiter
        
        Args:
            event_id: The event being replied to
            payload: Reply data (format depends on event type)
        
        Raises:
            EventNotFoundError: If the event_id doesn't exist
            EventDeliveryError: If reply cannot be delivered
        
        Example:
            # In subscriber receiving PreToolUse
            decision = await analyze_tool_use(event)
            await outbox.reply(
                event_id=event.event_id,
                payload={
                    "decision": "allow",
                    "reason": "Tool approved by security policy"
                }
            )
        """
        pass


# =============================================================================
# DATA PLANE - Client
# =============================================================================

class MeshClient(ABC):
    """
    Node's runtime interface to the Mosaic mesh.
    
    MeshClient is the main entry point for nodes to interact with
    the event system. It combines inbox, outbox, and context into
    a single interface.
    
    Lifecycle:
    ----------
    1. Create: MeshClient is created for a specific node
    2. Connect: connect() establishes transport connections
    3. Use: Node uses inbox/outbox/context for event handling
    4. Disconnect: disconnect() releases resources
    
    One Node, One Client:
    --------------------
    Each node has exactly one MeshClient instance. The client
    encapsulates:
    - Node identity (node_id, mesh_id)
    - Event channels (inbox, outbox)
    - Context queries (context)
    
    Example:
        client = await create_mesh_client(mesh_id="dev", node_id="worker")
        await client.connect()
        
        try:
            async for envelope in client.inbox:
                await process(envelope.event)
                await envelope.ack()
        finally:
            await client.disconnect()
    """
    
    @property
    @abstractmethod
    def node_id(self) -> NodeId:
        """This node's identifier."""
        pass
    
    @property
    @abstractmethod
    def mesh_id(self) -> MeshId:
        """The mesh this client belongs to."""
        pass
    
    @property
    @abstractmethod
    def inbox(self) -> MeshInbox:
        """Event input channel."""
        pass
    
    @property
    @abstractmethod
    def outbox(self) -> MeshOutbox:
        """Event output channel."""
        pass
    
    @property
    @abstractmethod
    def context(self) -> "MeshContext":
        """Topology and semantics queries."""
        pass
    
    @abstractmethod
    async def connect(self) -> None:
        """
        Connect to the mesh.
        
        This establishes connections to the transport layer and
        prepares the client for event handling.
        
        Raises:
            TransportConnectionError: If connection fails
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from the mesh.
        
        This releases transport resources and closes channels.
        After disconnect, the client cannot be used.
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the client is connected."""
        pass


# =============================================================================
# CONTROL PLANE - Admin
# =============================================================================

class MeshAdmin(ABC):
    """
    Administrative interface for mesh configuration.
    
    MeshAdmin provides methods to manage nodes, subscriptions, and
    capabilities. It operates on the control plane database.
    
    Operations:
    -----------
    - Node management: create, delete, update
    - Subscription management: subscribe, unsubscribe
    - Capability registration: declare produced/consumed events
    
    Usage:
        admin = MeshAdmin(mesh_id="dev")
        
        # Create nodes
        await admin.create_node(Node(
            mesh_id="dev",
            node_id="worker",
            node_type=NodeType.CLAUDE_CODE,
            workspace="/path/to/workspace"
        ))
        
        # Create subscriptions
        await admin.subscribe(Subscription(
            mesh_id="dev",
            source_id="auditor",
            target_id="worker",
            event_pattern="!PreToolUse"
        ))
    """
    
    @abstractmethod
    async def create_node(self, node: Node) -> None:
        """
        Create a new node in the mesh.
        
        Args:
            node: Node definition
        
        Raises:
            NodeAlreadyExistsError: If node_id already exists
        """
        pass
    
    @abstractmethod
    async def get_node(self, node_id: NodeId) -> Optional[Node]:
        """
        Get a node by ID.
        
        Args:
            node_id: The node to look up
        
        Returns:
            Node if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def delete_node(self, node_id: NodeId) -> None:
        """
        Delete a node from the mesh.
        
        This also deletes all subscriptions involving this node.
        
        Args:
            node_id: The node to delete
        
        Raises:
            NodeNotFoundError: If node doesn't exist
        """
        pass
    
    @abstractmethod
    async def list_nodes(self) -> list[Node]:
        """
        List all nodes in the mesh.
        
        Returns:
            List of all nodes
        """
        pass
    
    @abstractmethod
    async def subscribe(self, subscription: Subscription) -> None:
        """
        Create a subscription.
        
        Args:
            subscription: Subscription definition
        
        Raises:
            SubscriptionAlreadyExistsError: If subscription exists
            NodeNotFoundError: If source or target node doesn't exist
        """
        pass
    
    @abstractmethod
    async def unsubscribe(
        self,
        source_id: NodeId,
        target_id: NodeId,
        event_pattern: str,
    ) -> None:
        """
        Remove a subscription.
        
        Args:
            source_id: Subscribing node
            target_id: Subscribed node
            event_pattern: Event pattern to unsubscribe
        
        Raises:
            SubscriptionNotFoundError: If subscription doesn't exist
        """
        pass
    
    @abstractmethod
    async def get_subscriptions_by_source(
        self,
        source_id: NodeId,
    ) -> list[Subscription]:
        """
        Get all subscriptions where node is the subscriber.
        
        Args:
            source_id: The subscribing node
        
        Returns:
            List of subscriptions where source_id is the subscriber
        """
        pass
    
    @abstractmethod
    async def get_subscriptions_by_target(
        self,
        target_id: NodeId,
    ) -> list[Subscription]:
        """
        Get all subscriptions where node is being subscribed to.
        
        Args:
            target_id: The node being subscribed to
        
        Returns:
            List of subscriptions where target_id is the subscribed node
        """
        pass
    
    @abstractmethod
    async def register_capabilities(
        self,
        capabilities: NodeCapabilities,
    ) -> None:
        """
        Register node type capabilities.
        
        This declares what events a node type can produce or consume,
        along with semantic descriptions for agent prompts.
        
        Args:
            capabilities: Capability declaration
        """
        pass


# =============================================================================
# CONTEXT PLANE
# =============================================================================

class MeshContext(ABC):
    """
    Query interface for topology and event semantics.
    
    MeshContext provides read-only access to mesh information that
    nodes need for decision-making and prompt generation.
    
    Two Types of Information:
    -------------------------
    1. Topology: Who subscribes to whom
       - Used for understanding event flow
       - Can be injected into agent prompts
    
    2. Semantics: What events mean
       - Human-readable descriptions
       - Schema information
       - Used for agent prompt generation
    
    Example:
        context = client.context
        
        # Get topology
        topology = await context.get_topology_context()
        for sub in topology.subscribers:
            print(f"{sub.source_id} subscribes to me for {sub.event_pattern}")
        
        # Get event semantics
        semantics = await context.get_event_semantics(["PreToolUse", "PostToolUse"])
        for event_type, info in semantics.items():
            print(f"{event_type}: {info.description}")
    """
    
    @abstractmethod
    async def get_topology_context(self) -> TopologyContext:
        """
        Get topology information for this node.
        
        Returns:
            TopologyContext with subscription relationships
        """
        pass
    
    @abstractmethod
    async def get_event_semantics(
        self,
        event_types: list[str],
    ) -> dict[str, EventSemantics]:
        """
        Get semantic information for event types.
        
        Args:
            event_types: Event types to look up
        
        Returns:
            Dict mapping event type to its semantics
        """
        pass
    
    @abstractmethod
    async def get_all_node_capabilities(self) -> list[NodeCapabilities]:
        """
        Get capabilities of all registered node types.
        
        Returns:
            List of capability declarations
        """
        pass


# =============================================================================
# NODE RUNTIME INTERFACE
# =============================================================================

class NodeRuntime(ABC):
    """
    Abstract interface for node implementations.
    
    Each node type (CC, Scheduler, Webhook) implements this interface.
    The runtime is responsible for:
    - Processing incoming events
    - Producing outgoing events
    - Managing node-specific resources
    
    Lifecycle:
    ----------
    1. __init__: Receive MeshClient and configuration
    2. start(): Initialize resources, begin event loop
    3. process_event(): Handle each incoming event
    4. stop(): Clean up resources
    
    Example Implementation:
        class CCNodeRuntime(NodeRuntime):
            def __init__(self, client: MeshClient, config: dict):
                self.client = client
                self.config = config
            
            async def start(self):
                async for envelope in self.client.inbox:
                    await self.process_event(envelope)
                    await envelope.ack()
            
            async def process_event(self, envelope: EventEnvelope):
                # CC-specific event handling
                ...
            
            async def stop(self):
                await self.client.disconnect()
    """
    
    @abstractmethod
    async def start(self) -> None:
        """
        Start the node runtime.
        
        This should:
        - Initialize any required resources
        - Start the event processing loop
        - Begin producing events (if applicable)
        
        Raises:
            RuntimeError: If start fails
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the node runtime.
        
        This should:
        - Stop processing new events
        - Complete any in-flight processing
        - Release all resources
        """
        pass
    
    @abstractmethod
    async def process_event(self, envelope: EventEnvelope) -> None:
        """
        Process a single event.
        
        This is called for each event delivered to the node.
        Implementations should handle the event according to
        their node type's logic.
        
        Note: ACK/NACK should typically be handled by the caller,
        not within process_event.
        
        Args:
            envelope: The event to process
        """
        pass

