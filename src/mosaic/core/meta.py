import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator, List, Optional

from mosaic.core.types import MeshID, MeshStatus, NodeID, NodeType, SessionRoutingStrategy
from mosaic.core.models import Mesh, Node, Subscription

_DB_PATH = Path.home() / ".mosaic" / "mosaic.db"
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

def _ensure_initialized():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    conn.close()

_ensure_initialized()

def reset():
    _DB_PATH.unlink(missing_ok=True)
    _ensure_initialized()

@contextmanager
def _get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def create_mesh(mesh: Mesh):
    with _get_conn() as conn:
        conn.execute("INSERT INTO meshes (mesh_id) VALUES (?)", (mesh.mesh_id,))
        conn.commit()

def get_mesh(mesh_id: MeshID) -> Optional[Mesh]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM meshes WHERE mesh_id = ?", (mesh_id,)).fetchone()
        if row:
            return Mesh(mesh_id=row["mesh_id"])

def list_meshes() -> List[Mesh]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM meshes").fetchall()
        return [Mesh(mesh_id=row["mesh_id"], status=MeshStatus(row["status"])) for row in rows]


def create_node(node: Node):
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO nodes (node_id, mesh_id, type, config) VALUES (?, ?, ?, ?)", 
            (node.node_id, node.mesh_id, node.type, json.dumps(node.config))
        )
        conn.commit()

def get_node(mesh_id: MeshID, node_id: NodeID) -> Optional[Node]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM nodes WHERE mesh_id = ? AND node_id = ?", (mesh_id, node_id)).fetchone()
        if row:
            return Node(
                node_id=row["node_id"], 
                mesh_id=row["mesh_id"], 
                type=NodeType(row["type"]), 
                config=json.loads(row["config"]), 
            )
        return None

def list_nodes(mesh_id: MeshID) -> List[Node]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM nodes WHERE mesh_id = ?", (mesh_id,)).fetchall()
        return [
            Node(
                node_id=row["node_id"], 
                mesh_id=row["mesh_id"], 
                type=NodeType(row["type"]), 
                config=json.loads(row["config"]), 
            ) for row in rows
        ]

def add_subscription(sub: Subscription):
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO subscriptions (mesh_id, source_id, target_id, event_pattern, is_blocking, session_routing_strategy, session_routing_strategy_config) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sub.mesh_id, sub.source_id, sub.target_id, sub.event_pattern, sub.is_blocking, sub.session_routing_strategy, json.dumps(sub.session_routing_strategy_config))
        )
        conn.commit()

def get_subscriptions_by_source(mesh_id: MeshID, source_id: NodeID) -> List[Subscription]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM subscriptions WHERE mesh_id = ? AND source_id = ?", (mesh_id, source_id)).fetchall()
        return [
            Subscription(mesh_id=row["mesh_id"], source_id=row["source_id"], target_id=row["target_id"], event_pattern=row["event_pattern"], is_blocking=row["is_blocking"], session_routing_strategy=SessionRoutingStrategy(row["session_routing_strategy"]), session_routing_strategy_config=json.loads(row["session_routing_strategy_config"]))
            for row in rows
        ]

def delete_subscription(mesh_id: MeshID, source_id: NodeID, target_id: NodeID):
    with _get_conn() as conn:
        conn.execute("DELETE FROM subscriptions WHERE mesh_id = ? AND source_id = ? AND target_id = ?", (mesh_id, source_id, target_id))
        conn.commit()