import aiosqlite
import json
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional, List
from mosaic.core.type import Node, Subscription, NodeType

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    config TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
            "SELECT * FROM nodes"
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
            "SELECT * FROM nodes WHERE type = ?",
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