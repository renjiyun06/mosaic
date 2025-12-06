import asyncio
import uuid
import argparse
import json
from typing import Dict
from datetime import datetime

from mosaic.core.models import MeshEvent
from mosaic.core.client import MeshClient
from mosaic.core.node import BaseNode
from mosaic.core.enums import TransportType, NodeStatus
from mosaic.transport.sqlite import SqliteTransportBackend
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class DummyNode(BaseNode):
    def __init__(
        self, 
        mesh_id: str, 
        node_id: str, 
        config: Dict[str, str], 
        client: MeshClient
    ):
        super().__init__(mesh_id, node_id, config, client)
        self._send_events_task = None

    async def on_event(self, event: MeshEvent):
        logger.info(
            f"Dummy node {self.node_id} in mesh {self.mesh_id} "
            f"received event: {event.model_dump_json()}"
        )
        await self.client.ack(event)

    async def on_start(self):
        self._send_events_task = asyncio.create_task(self._send_events())
        logger.info(
            f"Dummy node {self.node_id} in mesh {self.mesh_id} started"
        )

    async def _send_events(self):
        while self._status == NodeStatus.RUNNING:
            logger.info(
                f"Dummy node {self.node_id} in mesh {self.mesh_id} "
                f"sending events"
            )
            subscriptions = await self.client.get_subscribers(
                mesh_id=self.mesh_id,
                target_id=self.node_id,
                event_pattern="dummy.dummy_event"
            )
            if subscriptions:
                for subscription in subscriptions:
                    logger.info(
                        f"Dummy node {self.node_id} in mesh {self.mesh_id} "
                        f"sending event to {subscription.source_id} "
                        f"in mesh {self.mesh_id}"
                    )
                    await self.client.send(MeshEvent(
                        event_id=str(uuid.uuid4()),
                        mesh_id=self.mesh_id,
                        source_id=self.node_id,
                        target_id=subscription.source_id,
                        type="dummy.dummy_event",
                        payload={"message": "Hello, world!"},
                        session_trace=None,
                        reply_to=None,
                        created_at=datetime.now()
                    ))
            else:
                logger.info(
                    f"Dummy node {self.node_id} in mesh {self.mesh_id} "
                    f"no subscriptions found for dummy.dummy_event"
                )
            
            await asyncio.sleep(20)


    async def on_shutdown(self):
        if self._send_events_task:
            self._send_events_task.cancel()
            self._send_events_task = None
        
        logger.info(
            f"Dummy node {self.node_id} in mesh {self.mesh_id} stopped"
        )


async def main(
    mesh_id: str, 
    node_id: str, 
    transport: TransportType, 
    config: Dict[str, str]
):
    transport_backend = None
    if transport == TransportType.SQLITE:
        transport_backend = SqliteTransportBackend(mesh_id, node_id)
    else:
        raise RuntimeError(f"Unsupported transport type: {transport}")
    
    dummy_node = DummyNode(
        mesh_id, 
        node_id, 
        config, 
        MeshClient(mesh_id, node_id, transport_backend),
    )
    await dummy_node.start()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh-id", type=str, required=True)
    parser.add_argument("--node-id", type=str, required=True)
    parser.add_argument("--transport", type=str, required=True)
    parser.add_argument("--config", type=str, required=True)
    args = parser.parse_args()
    asyncio.run(
        main(
            args.mesh_id, 
            args.node_id, 
            args.transport, 
            json.loads(args.config)
        )
    )