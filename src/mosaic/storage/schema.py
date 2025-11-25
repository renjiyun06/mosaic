"""
Mosaic Storage - Database Schema

This module defines the SQL schema for the control plane database.
The control plane stores metadata about meshes, nodes, subscriptions,
and capabilities.

Design Principles:
1. CONTROL PLANE ONLY: This schema is for metadata, not events
2. MULTI-MESH: All tables include mesh_id for isolation
3. NORMALIZED: Proper foreign keys and indexes
4. EXTENSIBLE: JSON columns for flexible configuration

Database Location:
- Control plane: ~/.mosaic/control.db
- Event storage (data plane) is handled by transport module

Note: Event storage (data plane) is NOT in this schema.
Events are stored by the transport layer (e.g., transport/sqlite/events.db).
"""

# =============================================================================
# Schema Version
# =============================================================================

SCHEMA_VERSION = 1

# =============================================================================
# Table Creation SQL
# =============================================================================

MESHES_TABLE = """
CREATE TABLE IF NOT EXISTS meshes (
    mesh_id TEXT PRIMARY KEY,
    config TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

NODES_TABLE = """
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mesh_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    workspace TEXT,
    config TEXT DEFAULT '{}',
    restart_policy TEXT DEFAULT 'on-failure',
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(mesh_id, node_id),
    FOREIGN KEY (mesh_id) REFERENCES meshes(mesh_id) ON DELETE CASCADE
);
"""

NODES_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_nodes_mesh ON nodes(mesh_id);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(mesh_id, node_type);
"""

SUBSCRIPTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mesh_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    event_pattern TEXT NOT NULL,
    
    -- Session configuration (opaque to storage, interpreted by agent nodes)
    session_scope TEXT DEFAULT 'upstream-session',
    session_filter TEXT DEFAULT 'any',
    session_profile TEXT DEFAULT 'default',
    min_sessions INTEGER DEFAULT 1,
    max_sessions INTEGER DEFAULT 10,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(mesh_id, source_id, target_id, event_pattern),
    FOREIGN KEY (mesh_id) REFERENCES meshes(mesh_id) ON DELETE CASCADE
);
"""

SUBSCRIPTIONS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_subscriptions_mesh ON subscriptions(mesh_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_source ON subscriptions(mesh_id, source_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_target ON subscriptions(mesh_id, target_id);
"""

NODE_CAPABILITIES_TABLE = """
CREATE TABLE IF NOT EXISTS node_capabilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mesh_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    schema_def TEXT,
    description TEXT,
    examples TEXT DEFAULT '[]',
    
    UNIQUE(mesh_id, node_type, event_type, direction),
    FOREIGN KEY (mesh_id) REFERENCES meshes(mesh_id) ON DELETE CASCADE
);
"""

NODE_CAPABILITIES_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_capabilities_mesh ON node_capabilities(mesh_id);
CREATE INDEX IF NOT EXISTS idx_capabilities_type ON node_capabilities(mesh_id, node_type);
"""

SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# =============================================================================
# All Schema Statements (in order)
# =============================================================================

ALL_TABLES = [
    SCHEMA_VERSION_TABLE,
    MESHES_TABLE,
    NODES_TABLE,
    SUBSCRIPTIONS_TABLE,
    NODE_CAPABILITIES_TABLE,
]

ALL_INDEXES = [
    NODES_INDEXES,
    SUBSCRIPTIONS_INDEXES,
    NODE_CAPABILITIES_INDEXES,
]

# =============================================================================
# Helper Functions
# =============================================================================

def get_full_schema() -> str:
    """
    Get the complete schema as a single SQL string.
    
    Returns:
        SQL string that creates all tables and indexes
    """
    parts = []
    parts.extend(ALL_TABLES)
    parts.extend(ALL_INDEXES)
    return "\n".join(parts)


def get_table_names() -> list[str]:
    """
    Get list of all table names.
    
    Returns:
        List of table names in the schema
    """
    return [
        "schema_version",
        "meshes",
        "nodes",
        "subscriptions",
        "node_capabilities",
    ]

