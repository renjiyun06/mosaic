import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator


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