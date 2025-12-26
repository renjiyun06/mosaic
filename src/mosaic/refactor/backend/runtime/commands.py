"""Command system for FastAPI <-> Mosaic Instance communication.

This module defines the unified command interface for cross-thread communication
between the FastAPI main event loop and Mosaic worker threads.

Design principles:
- All runtime operations from FastAPI are submitted as commands
- Commands are processed asynchronously in worker threads
- Optional callbacks provide async responses
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Awaitable, Any


class CommandType(Enum):
    """Types of commands that can be submitted to Mosaic instances."""

    # Session lifecycle
    CREATE_SESSION = "create_session"
    CLOSE_SESSION = "close_session"

    # Session interaction
    SEND_MESSAGE = "send_message"
    INTERRUPT_SESSION = "interrupt_session"

    # Node lifecycle
    START_NODE = "start_node"
    STOP_NODE = "stop_node"
    RESTART_NODE = "restart_node"


@dataclass
class Command:
    """
    Base command class.

    All commands submitted from FastAPI to Mosaic instances inherit from this.
    """
    type: CommandType
    mosaic_id: int

    # Optional callback for async response
    # Callback will be called in worker thread with result dict
    callback: Optional[Callable[[Any], Awaitable[None]]] = None

    # Unique request ID for tracking
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class SendMessageCommand(Command):
    """
    Command to send user message to a Claude Code session.

    Flow:
    1. FastAPI receives WebSocket message
    2. Creates SendMessageCommand
    3. Submits to Mosaic's command queue (cross-thread)
    4. Worker thread processes command
    5. Sends message to ClaudeCodeSession
    """

    def __init__(
        self,
        mosaic_id: int,
        session_id: str,
        message: str,
        user_id: int,
        callback: Optional[Callable[[Any], Awaitable[None]]] = None
    ):
        super().__init__(CommandType.SEND_MESSAGE, mosaic_id, callback)
        self.session_id = session_id
        self.message = message
        self.user_id = user_id


class InterruptSessionCommand(Command):
    """
    Command to interrupt a running Claude Code session.

    This cancels any ongoing processing in the session.
    """

    def __init__(
        self,
        mosaic_id: int,
        session_id: str,
        user_id: int,
        callback: Optional[Callable[[Any], Awaitable[None]]] = None
    ):
        super().__init__(CommandType.INTERRUPT_SESSION, mosaic_id, callback)
        self.session_id = session_id
        self.user_id = user_id


class CreateSessionCommand(Command):
    """
    Command to create a Claude Code session.

    This initializes the runtime session object and registers it in the mosaic.
    Flow:
    1. Database session record is created first
    2. CreateSessionCommand is submitted to worker thread
    3. Worker thread creates runtime session object
    4. Session is registered in mosaic for command routing
    """

    def __init__(
        self,
        mosaic_id: int,
        node_id: int,
        session_id: str,
        user_id: int,
        config: dict,
        callback: Optional[Callable[[Any], Awaitable[None]]] = None
    ):
        super().__init__(CommandType.CREATE_SESSION, mosaic_id, callback)
        self.node_id = node_id  # Database primary key
        self.session_id = session_id
        self.user_id = user_id
        self.config = config


class CloseSessionCommand(Command):
    """
    Command to close a Claude Code session.

    This releases resources and marks the session as closed.
    Note: Database status is updated before submitting this command.
    """

    def __init__(
        self,
        mosaic_id: int,
        session_id: str,
        node_id: int,
        user_id: int,
        force: bool = False,
        callback: Optional[Callable[[Any], Awaitable[None]]] = None
    ):
        super().__init__(CommandType.CLOSE_SESSION, mosaic_id, callback)
        self.session_id = session_id
        self.node_id = node_id
        self.user_id = user_id
        self.force = force


class StartNodeCommand(Command):
    """
    Command to start a node in the Mosaic.

    The node will be initialized and added to the Mosaic's running nodes.
    """

    def __init__(
        self,
        mosaic_id: int,
        node_id: str,
        callback: Optional[Callable[[Any], Awaitable[None]]] = None
    ):
        super().__init__(CommandType.START_NODE, mosaic_id, callback)
        self.node_id = node_id


class StopNodeCommand(Command):
    """
    Command to stop a node in the Mosaic.

    This will close all sessions and release node resources.
    """

    def __init__(
        self,
        mosaic_id: int,
        node_id: str,
        callback: Optional[Callable[[Any], Awaitable[None]]] = None
    ):
        super().__init__(CommandType.STOP_NODE, mosaic_id, callback)
        self.node_id = node_id


class RestartNodeCommand(Command):
    """
    Command to restart a node in the Mosaic.

    This is equivalent to stop + start.
    """

    def __init__(
        self,
        mosaic_id: int,
        node_id: str,
        callback: Optional[Callable[[Any], Awaitable[None]]] = None
    ):
        super().__init__(CommandType.RESTART_NODE, mosaic_id, callback)
        self.node_id = node_id
