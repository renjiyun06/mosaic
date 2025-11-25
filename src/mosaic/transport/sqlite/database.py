"""
SQLite Database Management for Event Storage

This module manages the SQLite database used for event persistence.
It handles:
- Database initialization and schema creation
- Connection management with WAL mode
- Schema migrations

Design Decisions:
-----------------
1. WAL Mode: Enables concurrent reads and single writer for better performance
2. Per-Mesh Database: Each mesh has its own events.db file
3. Async Operations: Uses aiosqlite for non-blocking I/O
4. Connection Pool: Not needed for SQLite (file-based, single writer)

Schema Design:
--------------
The event_queue table stores all events with their current status.
Events progress through: PENDING -> PROCESSING -> COMPLETED/FAILED

Recovery Window:
----------------
Events stuck in PROCESSING status (due to node crash) become visible
again after the recovery window expires. This is implemented by
checking the updated_at timestamp during event retrieval.
"""

import asyncio
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional

from mosaic.core.types import MeshId


# =============================================================================
# Schema Definition
# =============================================================================

SCHEMA_VERSION = 1

CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS event_queue (
    -- Primary identification
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    
    -- Mesh isolation
    mesh_id TEXT NOT NULL,
    
    -- Routing information
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    
    -- Event content
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,  -- JSON serialized MeshEvent
    
    -- Delivery status
    status TEXT NOT NULL DEFAULT 'pending',
    delivery_count INTEGER NOT NULL DEFAULT 0,
    
    -- Timestamps (for recovery window and cleanup)
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for common queries
    -- Covered by separate CREATE INDEX statements below
    
    CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'expired'))
);
"""

CREATE_INDEXES = [
    # Primary query: pending/recoverable events for a target
    """
    CREATE INDEX IF NOT EXISTS idx_event_queue_target_status 
    ON event_queue(target_id, status, updated_at);
    """,
    
    # Cleanup query: completed events by age
    """
    CREATE INDEX IF NOT EXISTS idx_event_queue_status_updated 
    ON event_queue(status, updated_at);
    """,
    
    # Lookup by event_id (already covered by UNIQUE, but explicit for clarity)
    """
    CREATE INDEX IF NOT EXISTS idx_event_queue_event_id 
    ON event_queue(event_id);
    """,
]

CREATE_SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


# =============================================================================
# Database Manager
# =============================================================================

class EventDatabase:
    """
    Manages the SQLite database for event storage.
    
    This class handles:
    - Database initialization with schema
    - WAL mode configuration for concurrent access
    - Connection lifecycle management
    
    Usage:
        db = EventDatabase(config)
        await db.initialize()
        
        async with db.connection() as conn:
            # Use connection
            ...
        
        await db.close()
    
    Thread Safety:
        This class is NOT thread-safe. Each thread/process should
        have its own EventDatabase instance. SQLite with WAL mode
        allows concurrent reads from multiple processes.
    """
    
    def __init__(self, db_path: Path, mesh_id: MeshId) -> None:
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database file
            mesh_id: The mesh this database serves
        """
        self._db_path = db_path
        self._mesh_id = mesh_id
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
    
    @property
    def db_path(self) -> Path:
        """Path to the database file."""
        return self._db_path
    
    @property
    def mesh_id(self) -> MeshId:
        """The mesh this database serves."""
        return self._mesh_id
    
    async def initialize(self) -> None:
        """
        Initialize the database.
        
        Creates the database file and schema if they don't exist.
        Configures WAL mode for better concurrency.
        
        Raises:
            TransportConnectionError: If database cannot be created
        """
        # Ensure parent directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create connection
        self._connection = await aiosqlite.connect(str(self._db_path))
        
        # Enable WAL mode for concurrent access
        await self._connection.execute("PRAGMA journal_mode=WAL;")
        
        # Enable foreign keys (good practice even if not used yet)
        await self._connection.execute("PRAGMA foreign_keys=ON;")
        
        # Set reasonable busy timeout (5 seconds)
        await self._connection.execute("PRAGMA busy_timeout=5000;")
        
        # Create schema
        await self._create_schema()
        
        await self._connection.commit()
    
    async def _create_schema(self) -> None:
        """Create the database schema if it doesn't exist."""
        if self._connection is None:
            raise RuntimeError("Database not initialized")
        
        # Create schema version table
        await self._connection.execute(CREATE_SCHEMA_VERSION_TABLE)
        
        # Check current version
        async with self._connection.execute(
            "SELECT MAX(version) FROM schema_version"
        ) as cursor:
            row = await cursor.fetchone()
            current_version = row[0] if row and row[0] else 0
        
        # Apply migrations if needed
        if current_version < SCHEMA_VERSION:
            await self._apply_migrations(current_version)
    
    async def _apply_migrations(self, from_version: int) -> None:
        """
        Apply schema migrations.
        
        Args:
            from_version: Current schema version
        """
        if self._connection is None:
            raise RuntimeError("Database not initialized")
        
        # Version 1: Initial schema
        if from_version < 1:
            await self._connection.execute(CREATE_EVENTS_TABLE)
            for index_sql in CREATE_INDEXES:
                await self._connection.execute(index_sql)
            
            # Record version
            await self._connection.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (1,)
            )
        
        # Future migrations would go here:
        # if from_version < 2:
        #     ...
    
    async def close(self) -> None:
        """
        Close the database connection.
        
        Ensures all pending transactions are committed and
        resources are released.
        """
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
    
    async def get_connection(self) -> aiosqlite.Connection:
        """
        Get the database connection.
        
        Returns:
            The active database connection
        
        Raises:
            RuntimeError: If database is not initialized
        """
        if self._connection is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._connection
    
    async def execute(
        self,
        sql: str,
        parameters: tuple = (),
    ) -> aiosqlite.Cursor:
        """
        Execute a SQL statement.
        
        Args:
            sql: SQL statement to execute
            parameters: Query parameters
        
        Returns:
            Cursor for the executed statement
        """
        conn = await self.get_connection()
        return await conn.execute(sql, parameters)
    
    async def execute_many(
        self,
        sql: str,
        parameters_list: list[tuple],
    ) -> None:
        """
        Execute a SQL statement with multiple parameter sets.
        
        Args:
            sql: SQL statement to execute
            parameters_list: List of parameter tuples
        """
        conn = await self.get_connection()
        await conn.executemany(sql, parameters_list)
    
    async def commit(self) -> None:
        """Commit the current transaction."""
        conn = await self.get_connection()
        await conn.commit()
    
    async def vacuum(self) -> None:
        """
        Reclaim disk space after deletions.
        
        This should be called periodically after cleanup_completed()
        to reduce database file size.
        """
        conn = await self.get_connection()
        await conn.execute("VACUUM;")


# =============================================================================
# Utility Functions
# =============================================================================

def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.utcnow()


def format_timestamp(dt: datetime) -> str:
    """Format datetime for SQLite storage."""
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")


def parse_timestamp(ts_str: str) -> datetime:
    """Parse timestamp from SQLite storage."""
    # Handle both with and without microseconds
    try:
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")

