"""Command definitions for cross-thread communication between RuntimeManager and MosaicInstance"""
from dataclasses import dataclass
from typing import Optional, Any, TYPE_CHECKING
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


@dataclass
class RestartMosaicCommand(Command):
    """
    Command to restart a mosaic instance.

    This is equivalent to stop + start in the same event loop.

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


@dataclass
class RestartNodeCommand(Command):
    """
    Command to restart a node in the mosaic.

    This is equivalent to stop + start for the node.

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
    Command to create a runtime session in a node.

    Steps:
    - Create session runtime state
    - Initialize Claude SDK session (if node is claude-code type)
    - Register session in node's session map

    Attributes:
        session: Session model object (must have node relationship loaded)
    """
    session: 'Session' = None


@dataclass
class SendMessageCommand(Command):
    """
    Command to send a message in a session.

    This is typically a fire-and-forget operation (future=None).

    Attributes:
        session: Session model object
        message: User message content
    """
    session: 'Session' = None
    message: str = ""


@dataclass
class InterruptSessionCommand(Command):
    """
    Command to interrupt a running session.

    This sends an interrupt signal to the Claude SDK session.

    Attributes:
        session: Session model object
    """
    session: 'Session' = None


@dataclass
class CloseSessionCommand(Command):
    """
    Command to close a runtime session.

    Steps:
    - Stop any ongoing operations
    - Cleanup session resources
    - Unregister from node's session map

    Attributes:
        session: Session model object
        force: Force close even if session is busy
    """
    session: 'Session' = None
    force: bool = False
