import aiosqlite
import json
import asyncio
from datetime import datetime
from typing import Optional

import mosaic.core.util as core_util
from mosaic.core.models import MeshEvent, SessionTrace
from mosaic.core.transport import TransportBackend
from mosaic.core.enums import EventStatus
from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    mesh_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    upstream_session_id TEXT,
    downstream_session_id TEXT,
    reply_to TEXT,
    status TEXT DEFAULT 'pending',
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

class SqliteTransportBackend(TransportBackend):
    def __init__(self, mesh_id: str, node_id: str):
        self._mesh_id = mesh_id
        self._node_id = node_id
        self._db_path = core_util.sqlite_transport_db_path(mesh_id)
        self._conn = None


    async def connect(self):
        logger.info(
            f"Connecting to SQLite transport database at {self._db_path} "
            f"for node {self._node_id} in mesh {self._mesh_id}"
        )
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(self._db_path)
        conn.row_factory = aiosqlite.Row

        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.executescript(_SCHEMA_SQL)
        await conn.commit()

        self._conn = conn
    
    async def disconnect(self):
        await self._conn.close()
        self._conn = None


    async def send(self, event: MeshEvent):
        try:
            payload = json.dumps(event.payload, ensure_ascii=False)
            await self._conn.execute(
                "INSERT INTO events \
                (event_id, mesh_id, source_id, target_id, \
                type, payload, upstream_session_id, downstream_session_id, \
                reply_to, status, error, created_at) VALUES \
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.mesh_id,
                    event.source_id,
                    event.target_id,
                    event.type,
                    payload,
                    event.session_trace.upstream_session_id \
                        if event.session_trace else None,
                    event.session_trace.downstream_session_id \
                        if event.session_trace else None,
                    event.reply_to,
                    EventStatus.PENDING,
                    None,
                    event.created_at
                )
            )
            await self._conn.commit()
        except Exception as e:
            logger.error(
                f"Error inserting event {event.model_dump_json()} into SQLite "
                f"transport database at {self._db_path} for node {self._node_id} "
                f"in mesh {self._mesh_id}: {e}"
            )
            raise e

    async def send_blocking(
        self, 
        event: MeshEvent, 
        timeout: float
    ) -> MeshEvent: ...


    async def receive(self) -> MeshEvent:
        while True:
            try:
                result = await self._conn.execute(
                    "SELECT * FROM events WHERE \
                    target_id = ? AND status = ? ORDER BY id ASC LIMIT 1",
                    (self._node_id, EventStatus.PENDING)
                )
                row = await result.fetchone()
                if row:
                    await self._conn.execute(
                        "UPDATE events SET status = ? WHERE event_id = ?",
                        (EventStatus.PROCESSING, row["event_id"])
                    )
                    await self._conn.commit()
                    logger.info(
                        f"Received event {row['event_id']} "
                        f"from SQLite transport database at {self._db_path} "
                        f"for node {self._node_id} in mesh {self._mesh_id}"
                    )
                    session_trace = None
                    if row["upstream_session_id"]:
                        session_trace = SessionTrace(
                            upstream_session_id=row["upstream_session_id"],
                            downstream_session_id=row["downstream_session_id"],
                        )
                    return MeshEvent(
                        event_id=row["event_id"],
                        mesh_id=row["mesh_id"],
                        source_id=row["source_id"],
                        target_id=row["target_id"],
                        type=row["type"],
                        payload=json.loads(row["payload"]),
                        session_trace=session_trace,
                        reply_to=row["reply_to"],
                        created_at=row["created_at"],
                    )
                else:
                    await asyncio.sleep(1.0)
            except Exception as e:
                logger.error(
                    f"Error receiving event from SQLite transport database "
                    f"at {self._db_path} "
                    f"for node {self._node_id} in mesh {self._mesh_id}: {e}"
                )
                raise e
        
    async def ack(self, event: MeshEvent):
        try:
            await self._conn.execute(
                "UPDATE events SET status = ?, updated_at = ? WHERE event_id = ?",
                (EventStatus.ACKED, datetime.now(), event.event_id)
            )
            await self._conn.commit()
        except Exception as e:
            logger.error(
                f"Error acknowledging event {event.event_id} "
                f"in SQLite transport database at {self._db_path} "
                f"for node {self._node_id} in mesh {self._mesh_id}: {e}"
            )
            raise e

    
    async def nack(self, event: MeshEvent, reason: Optional[str] = None):
        await self._conn.execute(
            "UPDATE events SET status = ?, error = ?, updated_at = ? \
             WHERE event_id = ?",
            (EventStatus.NACKED, reason, datetime.now(), event.event_id)
        )
        await self._conn.commit()