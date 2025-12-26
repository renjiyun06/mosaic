import asyncio
import uuid
import json
import traceback
from typing import Dict, Optional, Any, List
from datetime import datetime
from email_threads import (
    EmailThreadsMonitor, EmailAccount, EmailMessage, EmailSender
)

import mosaic.core.db as db
from mosaic.core.node import MosaicNode, MosaicSession
from mosaic.core.type import Session
from mosaic.core.event import MosaicEvent, EventType, NodeMessage, SystemMessage
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class EmailSession(MosaicSession):
    def __init__(self, session: Session, node: 'EmailNode'):
        super().__init__(session, node)

    async def start(self): ...

    async def close(self, force: bool = False): ...

    async def process_event(
        self, event: MosaicEvent
    ) -> asyncio.Future | None:
        logger.debug(
            f"Processing email reply event: {event.model_dump_json()}"
        )
        
        if isinstance(event, NodeMessage):
            message = event.payload.get("message")
            # the first line is the subject and the rest is the body
            subject = message.split("\n")[0]
            body = "\n".join(message.split("\n")[1:])
            reply_to_message = self.session.config.get("reply_to_message")
            self.node.send_message(
                to=reply_to_message.from_,
                subject=subject,
                text=body,
                reply_to_message=reply_to_message
            )
        elif isinstance(event, SystemMessage):
            to = event.payload.get("to")
            subject = event.payload.get("subject")
            text = event.payload.get("text")
            self.node.send_message(
                to=to,
                subject=subject,
                text=text
            )


class EmailNode(MosaicNode):
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

        self._account = self.config.get("account")
        self._main_account = None
        self._monitored_accounts = []
        monitored_accounts = self.config.get("monitored_accounts", [])
        for account in monitored_accounts:
            email_account = EmailAccount(
                email=account.get("email"),
                password=account.get("password"),
                imap_server=account.get("imap_server"),
                smtp_server=account.get("smtp_server")
            )
            self._monitored_accounts.append(email_account)
            if email_account.email == self._account:
                self._main_account = email_account

        assert self._main_account, "Main account not found"

        self._monitor = EmailThreadsMonitor(
            accounts=self._monitored_accounts,
            on_message_callback=self.on_message
        )

        self._sender = EmailSender(self._main_account)

        self._loop = asyncio.get_event_loop()


    def on_message(self, message: EmailMessage, thread: List[EmailMessage]):
        self._loop.create_task(self.on_message_async(message, thread))
    

    def send_message(
        self,
        to: str,
        subject: str,
        text: str,
        reply_to_message: EmailMessage = None,
    ):
        return self._sender.send(
            to=to,
            subject=subject,
            text=text,
            reply_to_message=reply_to_message
        )
    

    async def on_message_async(
        self, 
        message: EmailMessage, 
        thread: List[EmailMessage]
    ): 
        if self._account not in message.to:
            return

        current_message = {
            "subject": message.subject,
            "from": message.from_,
            "text": message.text,
            "date": message.date.isoformat()
        }
        thread = [
            {
                "subject": message.subject,
                "from": message.from_,
                "text": message.text,
                "date": message.date.isoformat()
            } for message in thread
        ]

        logger.debug(
            f"Received email message: "
            f"{json.dumps(current_message, ensure_ascii=False)}"
        )

        logger.debug(f"Thread: {json.dumps(thread, ensure_ascii=False)}")

        try:
            subscribers = await db.list_subscribers(
                source_id=self.node_id,
                event_type=EventType.EMAIL_MESSAGE
            )

            for subscriber in subscribers:
                session_id = str(uuid.uuid4())
                await self.create_session(
                    session_id=session_id,
                    config={
                        "reply_to_message": message
                    }
                )
                await self.publish_event(
                    session_id=session_id,
                    event_type=EventType.EMAIL_MESSAGE,
                    payload={
                        "current_message": current_message,
                        "thread": thread[:-1]
                    },
                    target_node_id=subscriber.target_id
                )
        except Exception as e:
            logger.error(
                f"Failed to publish email message: {e}"
                f"\n{traceback.format_exc()}"
            )
            raise e
        

    async def on_start(self):
        logger.info(
            f"Starting email node {self.node_id} with "
            f"{len(self._monitored_accounts)} monitored accounts"
        )
        self._monitor.start_async()
        logger.info(
            f"Email node {self.node_id} started with "
            f"{len(self._monitored_accounts)} monitored accounts"
        )


    async def on_stop(self): 
        logger.info(
            f"Stopping email node {self.node_id} with "
            f"{len(self._monitored_accounts)} monitored accounts"
        )
        self._monitor.stop()
        logger.info(
            f"Email node {self.node_id} stopped with "
            f"{len(self._monitored_accounts)} monitored accounts"
        )


    async def start_mosaic_session(
        self,
        session_id: Optional[str] = None,
        config: Dict[str, Any] = {}
    ) -> MosaicSession:
        if not session_id:
            session_id = str(uuid.uuid4())
        
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

        return EmailSession(session, self)