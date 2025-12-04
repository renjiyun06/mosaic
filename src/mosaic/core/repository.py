import json
import aiosqlite
from contextlib import asynccontextmanager
from typing import AsyncIterator
from typing import List, Optional

from mosaic.core.util import mosaic_db_path
from mosaic.core.models import Mesh, Node
from mosaic.core.types import NodeType

_DB_PATH = mosaic_db_path()
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meshes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mesh_id TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    mesh_id TEXT NOT NULL,
    type TEXT NOT NULL,
    config TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mesh_id, node_id)
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mesh_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    event_pattern TEXT NOT NULL,
    is_blocking BOOLEAN NOT NULL,
    session_routing_strategy TEXT NOT NULL,
    session_routing_strategy_config TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mesh_id, source_id, target_id, event_pattern)
);
"""

async def initialize():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with _get_conn() as conn:
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.executescript(_SCHEMA_SQL)
        await conn.commit()

async def reset():
    _DB_PATH.unlink(missing_ok=True)
    await initialize()


@asynccontextmanager
async def _get_conn() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(_DB_PATH)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()


async def create_mesh(mesh: Mesh):
    async with _get_conn() as conn:
        await conn.execute(
            "INSERT INTO meshes (mesh_id) VALUES (?)", (mesh.mesh_id,)
        )
        await conn.commit()

async def get_mesh(mesh_id: str) -> Optional[Mesh]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM meshes WHERE mesh_id = ?", (mesh_id,)
        )
        row = await result.fetchone()
        if row:
            return Mesh(mesh_id=row["mesh_id"])
        return None
    

async def list_meshes() -> List[Mesh]:
    async with _get_conn() as conn:
        result = await conn.execute("SELECT * FROM meshes")
        rows = await result.fetchall()
        return [Mesh(mesh_id=row["mesh_id"]) for row in rows]


async def create_node(node: Node):
    async with _get_conn() as conn:
        await conn.execute(
            "INSERT INTO nodes \
            (node_id, mesh_id, type, config) VALUES \
            (?, ?, ?, ?)",
            (node.node_id, node.mesh_id, str(node.type), json.dumps(node.config))
        )
        await conn.commit()


async def get_node(mesh_id: str, node_id: str) -> Optional[Node]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM nodes WHERE mesh_id = ? AND node_id = ?",
            (mesh_id, node_id)
        )
        row = await result.fetchone()
        if row:
            return Node(
                node_id=row["node_id"], 
                mesh_id=row["mesh_id"], 
                type=NodeType(row["type"]), 
                config=json.loads(row["config"])
            )
        return None


async def list_nodes(mesh_id: str) -> List[Node]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM nodes WHERE mesh_id = ?",
            (mesh_id,)
        )
        rows = await result.fetchall()
        return [
            Node(
                node_id=row["node_id"], 
                mesh_id=row["mesh_id"], 
                type=NodeType(row["type"]), 
                config=json.loads(row["config"])
            ) for row in rows
        ]