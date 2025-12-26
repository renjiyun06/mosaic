import asyncio
import uuid
import traceback
from typing import Dict, Optional, Any
from datetime import datetime
from fastmcp import Client
from fastmcp.client.client import CallToolResult

from mosaic.core.node import MosaicNode, MosaicSession
from mosaic.core.type import Session
from mosaic.core.event import MosaicEvent, EventType
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class RedditScraperSession(MosaicSession):
    def __init__(self, session: Session, node: 'RedditScraperNode'):
        super().__init__(session, node)
        self._mcp_client = Client(
            {
                "mcpServers": {
                    "reddit_scraper": {
                        "transport": "stdio",
                        "command": "uv",
                        "args": [
                            "run",
                            "--directory",
                            "/home/tomato/my-mosaic/nodes/reddit-mcp-develop",
                            "python",
                            "main.py"
                        ]
                    }
                }
            }
        )

    async def start(self):
        ...

    async def close(self, force: bool = False):
        await self._mcp_client.close()


    async def process_event(
        self, event: MosaicEvent
    ) -> asyncio.Future | None:
        try:
            if self.node.subreddit is None:
                return
            
            if event.event_type == EventType.SCHEDULER_MESSAGE:
                async with self._mcp_client:
                    result: CallToolResult = await self._mcp_client.call_tool(
                        "scrape_reddit_posts", 
                        {
                            "subreddit": self.node.subreddit,
                            "num_posts": self.node.num_posts
                        }
                    )
                    posts = result.structured_content.get("posts", [])
                    for post in posts:
                        await self.node.publish_event(
                            self.session.session_id,
                            EventType.REDDIT_SCRAPER_MESSAGE,
                            post
                        )
        except Exception as e:
            logger.error(
                f"Failed to process event: {e}\n{traceback.format_exc()}"
            )
            raise e


class RedditScraperNode(MosaicNode):
    def __init__(
        self, 
        node_id: str, 
        config: Dict[str, Any],
        zmq_server_pull_host: str,
        zmq_server_pull_port: int,
        zmq_server_pub_host: str,
        zmq_server_pub_port: int
    ):
        super().__init__(
            node_id, 
            config,
            zmq_server_pull_host,
            zmq_server_pull_port,
            zmq_server_pub_host,
            zmq_server_pub_port
        )

        self.subreddit = config.get("subreddit", None)
        self.num_posts = config.get("num_posts", 10)


    async def on_start(self): ...
    async def on_stop(self): ...

    async def start_mosaic_session(
        self,
        session_id: Optional[str] = None,
        config: Dict[str, Any] = {}
    ) -> RedditScraperSession:
        session = Session(
            session_id=session_id or str(uuid.uuid4()),
            node_id=self.node_id,
            config=config,
            pull_host=None,
            pull_port=None,
            pub_host=None,
            pub_port=None,
            status="open",
            created_at=datetime.now().isoformat()
        )
        return RedditScraperSession(session, self)