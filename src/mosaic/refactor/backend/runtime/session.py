"""Mosaic session base class"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Any
import asyncio

if TYPE_CHECKING:
    from .node import MosaicNode
    from .event import MosaicEvent


class MosaicSession(ABC):
    """
    Base class for mosaic sessions.

    A session represents a stateful interaction context within a node.
    Each session has a unique ID and manages its own lifecycle.
    """

    def __init__(
        self,
        session_id: str,
        node: 'MosaicNode',
        config: Dict[str, Any] | None = None
    ):
        """
        Initialize a session.

        Args:
            session_id: Unique session identifier
            node: Parent node instance
            config: Session-specific configuration
        """
        self.session_id = session_id
        self.node = node
        self.config = config or {}

    @abstractmethod
    async def start(self):
        """
        Start the session.

        This method should initialize any session-specific resources
        (e.g., event queues, background tasks).
        """
        ...

    @abstractmethod
    async def close(self, force: bool = False):
        """
        Close the session.

        Args:
            force: If True, forcefully close without cleanup
        """
        ...

    @abstractmethod
    async def process_event(self, event: 'MosaicEvent') -> asyncio.Future | None:
        """
        Process an incoming event.

        Args:
            event: The event to process

        Returns:
            Optional future that completes when event is processed
        """
        ...
