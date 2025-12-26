import aiosqlite
import json
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional, List
from mosaic.core.type import (
    Node, 
    Subscription, 
    NodeType, 
    EventType,
    Connection,
    SessionRouting
)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    config TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    config TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, target_id)
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    config TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS session_routing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    a_node_id TEXT NOT NULL,
    a_session_id TEXT NOT NULL,
    b_node_id TEXT NOT NULL,
    b_session_id TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(a_node_id, a_session_id, b_node_id, b_session_id)
)
"""

_DB__PATH: Path = None

async def ensure_initialized(db_path: Path):
    global _DB_PATH
    _DB_PATH = db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with _get_conn() as conn:
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.executescript(_SCHEMA_SQL)
        await conn.commit()


@asynccontextmanager
async def _get_conn() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(_DB_PATH)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()


async def get_node(node_id: str) -> Optional[Node]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM nodes WHERE node_id = ?",
            (node_id,)
        )
        row = await result.fetchone()
        if row:
            return Node(
                node_id=row["node_id"],
                type=NodeType(row["type"]),
                config=json.loads(row["config"]),
            )
        return None


async def list_nodes() -> List[Node]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM nodes ORDER BY node_id ASC"
        )
        rows = await result.fetchall()
        return [
            Node(
                node_id=row["node_id"],
                type=NodeType(row["type"]),
                config=json.loads(row["config"]),
            ) for row in rows
        ]


async def list_nodes_by_type(type: NodeType) -> List[Node]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM nodes WHERE type = ? ORDER BY node_id ASC",
            (str(type),)
        )
        rows = await result.fetchall()
        return [
            Node(
                node_id=row["node_id"],
                type=NodeType(row["type"]),
                config=json.loads(row["config"]),
            ) for row in rows
        ]


async def create_node(node: Node):
    async with _get_conn() as conn:
        await conn.execute(
            "INSERT INTO nodes (node_id, type, config) VALUES (?, ?, ?)",
            (
                node.node_id, 
                str(node.type), 
                json.dumps(node.config, ensure_ascii=False)
            )
        )
        await conn.commit()


async def update_node(node: Node):
    async with _get_conn() as conn:
        await conn.execute(
            "UPDATE nodes SET config = ? WHERE node_id = ?",
            (
                json.dumps(node.config, ensure_ascii=False),
                node.node_id
            )
        )
        await conn.commit()


async def delete_node(node_id: str):
    async with _get_conn() as conn:
        await conn.execute(
            "DELETE FROM nodes WHERE node_id = ?",
            (node_id,)
        )
        await conn.commit()


async def get_subscription(
    source_id: str, 
    target_id: str, 
    event_type: EventType
) -> Optional[Subscription]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM subscriptions WHERE source_id = ? \
                AND target_id = ? AND event_type = ?",
            (source_id, target_id, event_type)
        )
        row = await result.fetchone()
        if row:
            return Subscription(
                source_id=row["source_id"],
                target_id=row["target_id"],
                event_type=EventType(row["event_type"]),
                config=json.loads(row["config"]),
            )
        return None


async def create_subscription(subscription: Subscription):
    async with _get_conn() as conn:
        await conn.execute(
            "INSERT INTO subscriptions \
                (source_id, target_id, event_type, config) \
                    VALUES (?, ?, ?, ?)",
            (
                subscription.source_id,
                subscription.target_id,
                subscription.event_type,
                json.dumps(subscription.config, ensure_ascii=False)
            )
        )
        await conn.commit()


async def list_subscriptions() -> List[Subscription]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM subscriptions ORDER BY \
                source_id ASC, target_id ASC, event_type ASC"
        )
        rows = await result.fetchall()
        return [
            Subscription(
                source_id=row["source_id"],
                target_id=row["target_id"],
                event_type=EventType(row["event_type"]),
                config=json.loads(row["config"])
            ) for row in rows
        ]


async def list_subscribers(
    source_id: str,
    event_type: EventType
) -> List[Subscription]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM subscriptions WHERE source_id = ? \
                                                AND event_type = ?",
            (source_id, event_type)
        )
        rows = await result.fetchall()
        return [
            Subscription(
                source_id=row["source_id"],
                target_id=row["target_id"],
                event_type=EventType(row["event_type"]),
                config=json.loads(row["config"])) for row in rows
        ]


async def delete_subscriptions_by_source_id(source_id: str):
    async with _get_conn() as conn:
        await conn.execute(
            "DELETE FROM subscriptions WHERE source_id = ?",
            (source_id,)
        )
        await conn.commit()


async def delete_subscriptions_by_target_id(target_id: str):
    async with _get_conn() as conn:
        await conn.execute(
            "DELETE FROM subscriptions WHERE target_id = ?",
            (target_id,)
        )
        await conn.commit()


async def delete_subscriptions_by_source_id_and_target_id(
    source_id: str, target_id: str
):
    async with _get_conn() as conn:
        await conn.execute(
            "DELETE FROM subscriptions WHERE source_id = ? AND target_id = ?",
            (source_id, target_id)
        )
        await conn.commit()


async def get_session_routing_by_a(
    a_node_id: str,
    a_session_id: str,
    b_node_id: str,
) -> Optional[SessionRouting]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM session_routing WHERE a_node_id = ? \
                AND a_session_id = ? AND b_node_id = ?",
            (a_node_id, a_session_id, b_node_id)
        )
        row = await result.fetchone()
        if row:
            return SessionRouting(
                a_node_id=row["a_node_id"],
                a_session_id=row["a_session_id"],
                b_node_id=row["b_node_id"],
                b_session_id=row["b_session_id"]
            )
        return None


async def get_session_routing_by_b(
    a_node_id: str,
    b_node_id: str,
    b_session_id: str,
) -> Optional[SessionRouting]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM session_routing WHERE a_node_id = ? \
                AND b_node_id = ? AND b_session_id = ?",
            (a_node_id, b_node_id, b_session_id)
        )
        row = await result.fetchone()
        if row:
            return SessionRouting(
                a_node_id=row["a_node_id"],
                a_session_id=row["a_session_id"],
                b_node_id=row["b_node_id"],
                b_session_id=row["b_session_id"]
            )
        return None


async def create_session_routing(session_routing: SessionRouting):
    async with _get_conn() as conn:
        await conn.execute(
            "INSERT INTO session_routing \
                (a_node_id, a_session_id, b_node_id, b_session_id) \
                    VALUES (?, ?, ?, ?)",
            (
                session_routing.a_node_id, 
                session_routing.a_session_id, 
                session_routing.b_node_id, 
                session_routing.b_session_id, 
            )
        )
        await conn.commit()


async def create_connection(connection: Connection):
    async with _get_conn() as conn:
        await conn.execute(
            "INSERT INTO connections \
                (source_id, target_id, config) VALUES (?, ?, ?)",
            (
                connection.source_id,
                connection.target_id,
                json.dumps(connection.config, ensure_ascii=False)
            )
        )
        await conn.commit()


async def get_connection(
    source_id: str, target_id: str
) -> Optional[Connection]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM connections WHERE source_id = ? AND target_id = ?",
            (source_id, target_id)
        )
        row = await result.fetchone()
        if row:
            return Connection(
                source_id=row["source_id"],
                target_id=row["target_id"],
                config=json.loads(row["config"])
            )


async def delete_connections_by_source_id(source_id: str):
    async with _get_conn() as conn:
        await conn.execute(
            "DELETE FROM connections WHERE source_id = ?",
            (source_id,)
        )
        await conn.commit()


async def delete_connections_by_target_id(target_id: str):
    async with _get_conn() as conn:
        await conn.execute(
            "DELETE FROM connections WHERE target_id = ?",
            (target_id,)
        )
        await conn.commit()


async def delete_connection(source_id: str, target_id: str):
    async with _get_conn() as conn:
        await conn.execute(
            "DELETE FROM connections WHERE source_id = ? AND target_id = ?",
            (source_id, target_id)
        )
        await conn.commit()


async def list_connections() -> List[Connection]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM connections ORDER BY source_id ASC, target_id ASC"
        )
        rows = await result.fetchall()
        return [
            Connection(
                source_id=row["source_id"], 
                target_id=row["target_id"], 
                config=json.loads(row["config"])
            ) for row in rows
        ]