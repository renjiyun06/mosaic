import json
import aiosqlite
from contextlib import asynccontextmanager
from typing import AsyncIterator
from typing import List, Optional

from mosaic.core.util import mosaic_db_path
from mosaic.core.models import Mesh, Node, Subscription
from mosaic.core.enums import NodeType
from mosaic.nodes.agent.enums import SessionRoutingStrategy

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
    session_routing_strategy TEXT,
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
            (
                node.node_id, 
                node.mesh_id, 
                str(node.type), 
                json.dumps(node.config, ensure_ascii=False)
            )
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
                mesh_id=row["mesh_id"], 
                type=NodeType(row["type"]), 
                config=json.loads(row["config"])
            ) for row in rows
        ]
    

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


async def create_subscription(subscription: Subscription):
    async with _get_conn() as conn:
        await conn.execute(
            "INSERT INTO subscriptions \
             (mesh_id, source_id, target_id, event_pattern, \
              is_blocking, session_routing_strategy, \
              session_routing_strategy_config) VALUES \
             (?, ?, ?, ?, ?, ?, ?)",
            (
                subscription.mesh_id, 
                subscription.source_id, 
                subscription.target_id, 
                subscription.event_pattern, 
                subscription.is_blocking, 
                subscription.session_routing_strategy, 
                json.dumps(
                    subscription.session_routing_strategy_config,
                    ensure_ascii=False
                ) if subscription.session_routing_strategy_config else None
            )
        )
        await conn.commit()


async def get_subscription(
    mesh_id: str, 
    source_id: str, 
    target_id: str, 
    event_pattern: str
) -> Optional[Subscription]:
    async with _get_conn() as conn:
        result = await conn.execute(
            "SELECT * FROM subscriptions WHERE \
             mesh_id = ? AND source_id = ? AND target_id = ? AND \
             event_pattern = ?",
            (mesh_id, source_id, target_id, event_pattern)
        )
        row = await result.fetchone()
        if row:
            return Subscription(
                mesh_id=row["mesh_id"], 
                source_id=row["source_id"], 
                target_id=row["target_id"], 
                event_pattern=row["event_pattern"], 
                is_blocking=row["is_blocking"], 
                session_routing_strategy=\
                    SessionRoutingStrategy(row["session_routing_strategy"]) \
                        if row["session_routing_strategy"] else None, 
                session_routing_strategy_config=\
                    json.loads(row["session_routing_strategy_config"]) \
                        if row["session_routing_strategy_config"] else None
            )
        return None


async def delete_subscription(
    mesh_id: str,
    source_id: str,
    target_id: str,
    event_pattern: str
):
    async with _get_conn() as conn:
        await conn.execute(
            "DELETE FROM subscriptions WHERE \
                mesh_id = ? AND \
                source_id = ? AND \
                target_id = ? AND \
                event_pattern = ?",
            (mesh_id, source_id, target_id, event_pattern)
        )
        await conn.commit()


async def list_subscriptions(
    mesh_id: str, 
    source_id: Optional[str] = None, 
    target_id: Optional[str] = None
) -> List[Subscription]:
    async with _get_conn() as conn:
        sql = "SELECT * FROM subscriptions WHERE mesh_id = ?"
        params = [mesh_id]
        if source_id:
            sql += " AND source_id = ?"
            params.append(source_id)
        if target_id:
            sql += " AND target_id = ?"
            params.append(target_id)
        result = await conn.execute(sql, params)
        rows = await result.fetchall()
        return [
            Subscription(
                mesh_id=row["mesh_id"], 
                source_id=row["source_id"], 
                target_id=row["target_id"], 
                event_pattern=row["event_pattern"], 
                is_blocking=row["is_blocking"], 
                session_routing_strategy=\
                    SessionRoutingStrategy(row["session_routing_strategy"]) \
                        if row["session_routing_strategy"] else None,    
                session_routing_strategy_config=\
                    json.loads(row["session_routing_strategy_config"]) \
                    if row["session_routing_strategy_config"] else None
            ) for row in rows
        ]


async def list_subscribers(
    mesh_id: str,
    target_id: str,
    event_pattern: Optional[str] = None
) -> List[Subscription]:
    async with _get_conn() as conn:
        result = None
        if event_pattern:
            result = await conn.execute(
                "SELECT * FROM subscriptions WHERE \
                mesh_id = ? AND target_id = ? AND event_pattern = ?",
                (mesh_id, target_id, event_pattern)
            )
        else:
            result = await conn.execute(
                "SELECT * FROM subscriptions WHERE \
                mesh_id = ? AND target_id = ?",
                (mesh_id, target_id)
            )
        
        rows = await result.fetchall()
        return [
            Subscription(
                mesh_id=row["mesh_id"], 
                source_id=row["source_id"], 
                target_id=row["target_id"], 
                event_pattern=row["event_pattern"], 
                is_blocking=row["is_blocking"], 
                session_routing_strategy=\
                    SessionRoutingStrategy(row["session_routing_strategy"])\
                        if row["session_routing_strategy"] else None, 
                session_routing_strategy_config=\
                    json.loads(row["session_routing_strategy_config"]) \
                        if row["session_routing_strategy_config"] else None
            ) for row in rows
        ]