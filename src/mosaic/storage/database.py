"""
Mosaic Storage - Database Manager

This module provides the database connection management for the control plane.
It handles connection pooling, WAL mode configuration, and schema initialization.

Design Principles:
1. ASYNC-NATIVE: Uses aiosqlite for non-blocking database operations
2. WAL MODE: Enables concurrent reads with writes
3. SINGLETON: One manager instance per database file
4. AUTO-INIT: Schema is automatically created on first connection

Database Location:
- Default: ~/.mosaic/control.db
- Configurable via MOSAIC_DB_PATH environment variable

Thread Safety:
This manager is designed for single-process async usage. For multi-process
scenarios, SQLite's WAL mode provides the necessary isolation.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import aiosqlite

from .schema import get_full_schema, SCHEMA_VERSION


logger = logging.getLogger(__name__)


# =============================================================================
# Default Paths
# =============================================================================

def get_default_db_path() -> Path:
    """
    Get the default database path.
    
    Priority:
    1. MOSAIC_DB_PATH environment variable
    2. ~/.mosaic/control.db
    
    Returns:
        Path to the control plane database
    """
    env_path = os.environ.get("MOSAIC_DB_PATH")
    if env_path:
        return Path(env_path)
    return Path.home() / ".mosaic" / "control.db"


# =============================================================================
# Database Manager
# =============================================================================

class DatabaseManager:
    """
    Manages the control plane database connection.
    
    DatabaseManager provides:
    - Async connection management with aiosqlite
    - WAL mode for concurrent access
    - Schema initialization and versioning
    - Connection pooling (simple single-connection for now)
    
    Usage:
        db = DatabaseManager()
        await db.initialize()
        
        async with db.connection() as conn:
            cursor = await conn.execute("SELECT * FROM nodes")
            rows = await cursor.fetchall()
        
        await db.close()
    
    Or using context manager:
        async with DatabaseManager() as db:
            async with db.connection() as conn:
                ...
    
    Attributes:
        db_path: Path to the SQLite database file
        is_initialized: Whether the database has been initialized
    """
    
    def __init__(
        self,
        db_path: Optional[Path] = None,
        create_dirs: bool = True,
    ) -> None:
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the database file (default: ~/.mosaic/control.db)
            create_dirs: Whether to create parent directories if they don't exist
        """
        self._db_path = db_path or get_default_db_path()
        self._create_dirs = create_dirs
        self._connection: Optional[aiosqlite.Connection] = None
        self._is_initialized = False
        self._lock = asyncio.Lock()
        
        logger.debug(f"DatabaseManager created: db_path={self._db_path}")
    
    @property
    def db_path(self) -> Path:
        """Path to the SQLite database file."""
        return self._db_path
    
    @property
    def is_initialized(self) -> bool:
        """Whether the database has been initialized."""
        return self._is_initialized
    
    async def initialize(self) -> None:
        """
        Initialize the database.
        
        This:
        1. Creates parent directories if needed
        2. Opens the database connection
        3. Enables WAL mode
        4. Creates schema if not exists
        5. Checks/applies migrations
        
        Raises:
            IOError: If database cannot be created/opened
        """
        async with self._lock:
            if self._is_initialized:
                logger.debug("DatabaseManager already initialized")
                return
            
            logger.info(f"Initializing database: {self._db_path}")
            
            # Create parent directories
            if self._create_dirs:
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Open connection
            self._connection = await aiosqlite.connect(self._db_path)
            
            # Enable WAL mode for better concurrency
            await self._connection.execute("PRAGMA journal_mode=WAL")
            
            # Enable foreign keys
            await self._connection.execute("PRAGMA foreign_keys=ON")
            
            # Create schema
            await self._create_schema()
            
            self._is_initialized = True
            logger.info(f"Database initialized: {self._db_path}")
    
    async def _create_schema(self) -> None:
        """Create the database schema if it doesn't exist."""
        schema_sql = get_full_schema()
        
        # Execute schema as a script (handles multiple statements)
        await self._connection.executescript(schema_sql)
        await self._connection.commit()
        
        # Check/set schema version
        cursor = await self._connection.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        
        if row is None:
            # First time, set version
            await self._connection.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,)
            )
            await self._connection.commit()
            logger.info(f"Schema created at version {SCHEMA_VERSION}")
        else:
            current_version = row[0]
            if current_version < SCHEMA_VERSION:
                logger.warning(
                    f"Schema version mismatch: database={current_version}, "
                    f"expected={SCHEMA_VERSION}. Migrations may be needed."
                )
                # TODO: Apply migrations
            else:
                logger.debug(f"Schema version: {current_version}")
    
    async def close(self) -> None:
        """
        Close the database connection.
        
        After closing, the manager cannot be used until initialize() is called again.
        """
        async with self._lock:
            if self._connection is not None:
                await self._connection.close()
                self._connection = None
            self._is_initialized = False
            logger.debug("DatabaseManager closed")
    
    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """
        Get a database connection.
        
        This is a context manager that provides the connection.
        The connection is shared (not pooled) for simplicity.
        
        Yields:
            The database connection
        
        Raises:
            RuntimeError: If database is not initialized
        
        Example:
            async with db.connection() as conn:
                cursor = await conn.execute("SELECT * FROM nodes")
                rows = await cursor.fetchall()
        """
        if not self._is_initialized or self._connection is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        yield self._connection
    
    async def execute(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> aiosqlite.Cursor:
        """
        Execute a single SQL query.
        
        Args:
            query: SQL query string
            params: Query parameters
        
        Returns:
            Cursor with results
        
        Raises:
            RuntimeError: If database is not initialized
        """
        async with self.connection() as conn:
            return await conn.execute(query, params)
    
    async def execute_many(
        self,
        query: str,
        params_list: list[tuple[Any, ...]],
    ) -> None:
        """
        Execute a query with multiple parameter sets.
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
        
        Raises:
            RuntimeError: If database is not initialized
        """
        async with self.connection() as conn:
            await conn.executemany(query, params_list)
            await conn.commit()
    
    async def fetch_one(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> Optional[aiosqlite.Row]:
        """
        Execute a query and fetch one row.
        
        Args:
            query: SQL query string
            params: Query parameters
        
        Returns:
            Row if found, None otherwise
        """
        async with self.connection() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query, params)
            return await cursor.fetchone()
    
    async def fetch_all(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> list[aiosqlite.Row]:
        """
        Execute a query and fetch all rows.
        
        Args:
            query: SQL query string
            params: Query parameters
        
        Returns:
            List of rows
        """
        async with self.connection() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query, params)
            return await cursor.fetchall()
    
    async def commit(self) -> None:
        """Commit the current transaction."""
        async with self.connection() as conn:
            await conn.commit()
    
    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """
        Execute operations within a transaction.
        
        The transaction is automatically committed on success
        or rolled back on exception.
        
        Yields:
            The database connection
        
        Example:
            async with db.transaction() as conn:
                await conn.execute("INSERT ...")
                await conn.execute("UPDATE ...")
                # Commits automatically if no exception
        """
        async with self.connection() as conn:
            try:
                yield conn
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise
    
    # =========================================================================
    # Context Manager Protocol
    # =========================================================================
    
    async def __aenter__(self) -> "DatabaseManager":
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


# =============================================================================
# Global Instance (Optional)
# =============================================================================

_global_db: Optional[DatabaseManager] = None


async def get_database() -> DatabaseManager:
    """
    Get the global database manager instance.
    
    This creates and initializes the manager on first call.
    
    Returns:
        The global DatabaseManager instance
    """
    global _global_db
    
    if _global_db is None:
        _global_db = DatabaseManager()
        await _global_db.initialize()
    
    return _global_db


async def close_database() -> None:
    """
    Close the global database manager.
    
    Call this during application shutdown.
    """
    global _global_db
    
    if _global_db is not None:
        await _global_db.close()
        _global_db = None

