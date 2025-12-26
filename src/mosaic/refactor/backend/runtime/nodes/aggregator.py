"""Aggregator node implementation"""
import asyncio
import logging
from typing import Dict, Any

from ..node import MosaicNode
from ..session import MosaicSession
from ..event import MosaicEvent
from ...enums import EventType

logger = logging.getLogger(__name__)


class AggregatorSession(MosaicSession):
    """
    Aggregator session that collects events and batch-publishes them.

    Events are queued and published as a batch when the session closes.
    """

    def __init__(
        self,
        session_id: str,
        node: 'AggregatorNode',
        config: Dict[str, Any] | None = None
    ):
        super().__init__(session_id, node, config)
        self._queue = asyncio.Queue()

    async def start(self):
        """Start the session (no-op for aggregator)"""
        logger.debug(f"Aggregator session {self.session_id} started")

    async def close(self, force: bool = False):
        """
        Close the session and publish batched events.

        Args:
            force: If True, discard queued events without publishing
        """
        logger.debug(f"Closing aggregator session {self.session_id}")

        if not force and not self._queue.empty():
            # Collect all events
            events = []
            while not self._queue.empty():
                mosaic_event: MosaicEvent = self._queue.get_nowait()
                events.append(mosaic_event.model_dump())

            # Publish batch
            # TODO: Determine target from config or subscription
            # For now, this is a placeholder
            logger.info(
                f"Aggregator session {self.session_id} collected {len(events)} events"
            )

    async def process_event(self, event: MosaicEvent) -> asyncio.Future | None:
        """
        Process an event by adding it to the queue.

        Args:
            event: Event to queue

        Returns:
            None (events are processed on close)
        """
        await self._queue.put(event)
        logger.debug(
            f"Aggregator session {self.session_id} queued event {event.event_type}"
        )
        return None


class AggregatorNode(MosaicNode):
    """
    Aggregator node that collects and batches events.

    This node is useful for collecting multiple events from a source
    and publishing them as a single batch to downstream consumers.
    """

    async def on_start(self):
        """Node startup (no-op for aggregator)"""
        logger.info(f"Aggregator node {self.node.node_id} started")

    async def on_stop(self):
        """Node cleanup (no-op for aggregator)"""
        logger.info(f"Aggregator node {self.node.node_id} stopped")

    async def start_mosaic_session(
        self,
        session_id: str,
        config: Dict[str, Any] | None = None
    ) -> MosaicSession:
        """
        Create an aggregator session.

        Args:
            session_id: Session identifier
            config: Session configuration

        Returns:
            AggregatorSession instance
        """
        return AggregatorSession(session_id, self, config)
