"""Command definitions for cross-thread communication between RuntimeManager and MosaicInstance"""
from dataclasses import dataclass
from typing import Optional, Any, Dict, TYPE_CHECKING
import asyncio

if TYPE_CHECKING:
    from ..model.mosaic import Mosaic
    from ..model.node import Node
    from ..model.session import Session


@dataclass
class Command:
    """
    Base class for all commands sent to MosaicInstance.

    Commands are used for cross-thread communication from RuntimeManager (main thread)
    to MosaicInstance (worker thread event loop).

    Attributes:
        future: Optional Future for result synchronization.
                Set by RuntimeManager when waiting for result.
                None for fire-and-forget commands.
    """
    future: Optional[asyncio.Future] = None

    def set_result(self, result: Any = None) -> None:
        """
        Set the result of the command execution.

        Args:
            result: Command execution result (can be None for void operations)
        """
        if self.future and not self.future.done():
            self.future.get_loop().call_soon_threadsafe(
                self.future.set_result, result
            )

    def set_exception(self, exception: Exception) -> None:
        """
        Set an exception for the command execution.

        Args:
            exception: Exception raised during command execution
        """
        if self.future and not self.future.done():
            self.future.get_loop().call_soon_threadsafe(
                self.future.set_exception, exception
            )


# ========== Mosaic Lifecycle Commands ==========

@dataclass
class StopMosaicCommand(Command):
    """
    Command to stop a mosaic instance.

    This command triggers graceful shutdown of the mosaic:
    - Stop all running nodes
    - Cleanup ZMQ connections
    - Release resources

    Attributes:
        mosaic: Mosaic model object
    """
    mosaic: 'Mosaic' = None


# ========== Node Lifecycle Commands ==========

@dataclass
class StartNodeCommand(Command):
    """
    Command to start a node in the mosaic.

    Steps:
    - Create runtime node instance
    - Initialize ZMQ client for the node
    - Start event processing

    Attributes:
        node: Node model object (must have mosaic_id, node_id, node_type)
    """
    node: 'Node' = None


@dataclass
class StopNodeCommand(Command):
    """
    Command to stop a node in the mosaic.

    Steps:
    - Stop event processing
    - Cleanup ZMQ client
    - Release node resources

    Attributes:
        node: Node model object
    """
    node: 'Node' = None


# ========== Node Query Commands ==========

@dataclass
class GetNodeStatusCommand(Command):
    """
    Command to query node runtime status.

    This command returns the node's current status from MosaicInstance.

    Attributes:
        node: Node model object
    """
    node: 'Node' = None


# ========== Session Commands ==========

@dataclass
class CreateSessionCommand(Command):
    """
    Command to create a session in a node.

    Different node types handle session creation differently:
    - Agent nodes: Create database record + runtime instance
    - Scheduler/Email nodes: Create runtime instance only (no database)

    Attributes:
        node: Node model object (required, identifies which node to create session in)
        session_id: Session identifier (required)
        config: Session configuration (optional, subclass-specific, e.g., mode/model for agent nodes)
    """
    node: 'Node' = None
    session_id: str = None
    config: Optional[Dict[str, Any]] = None


@dataclass
class SendMessageCommand(Command):
    """
    Command to send a message in a session.

    This is typically a fire-and-forget operation (future=None).

    Attributes:
        node: Node model object (required)
        session: Session model object (required)
        message: User message content (required)
        context: Optional context data (e.g., GeoGebra states)
    """
    node: 'Node' = None
    session: 'Session' = None
    message: str = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class InterruptSessionCommand(Command):
    """
    Command to interrupt a running session.

    This sends an interrupt signal to the session (e.g., Claude SDK interrupt).

    Attributes:
        node: Node model object (required)
        session: Session model object (required)
    """
    node: 'Node' = None
    session: 'Session' = None


@dataclass
class CloseSessionCommand(Command):
    """
    Command to close a session.

    Steps:
    - Stop any ongoing operations
    - Cleanup session resources
    - Unregister from node's session map

    Attributes:
        node: Node model object (required)
        session_id: Session identifier (required)
    """
    node: 'Node' = None
    session_id: str = None


@dataclass
class ToolResponseCommand(Command):
    """
    Command to handle tool response from frontend.

    This command delivers a frontend response to a waiting tool execution.
    The response_id is used to match with a pending Future in the session.

    This is typically a fire-and-forget operation (future=None).

    Attributes:
        node: Node model object (required)
        session: Session model object (required)
        response_id: Unique identifier matching the pending response (required)
        result: Response data from frontend (can be any structure)
    """
    node: 'Node' = None
    session: 'Session' = None
    response_id: str = None
    result: Any = None