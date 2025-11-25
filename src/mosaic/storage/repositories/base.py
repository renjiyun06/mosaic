"""
Mosaic Storage - Base Repository

This module provides the base class for all repositories.
It encapsulates common database operations and provides
consistent error handling.

Design Principles:
1. REPOSITORY PATTERN: Encapsulates data access logic
2. ASYNC-NATIVE: All operations are async
3. MESH ISOLATION: Operations are scoped to mesh_id
4. TYPE-SAFE: Uses Pydantic models for input/output
"""

import logging
from typing import Any, Optional, TypeVar, Generic
from abc import ABC, abstractmethod

from pydantic import BaseModel

from ..database import DatabaseManager


logger = logging.getLogger(__name__)


# Type variable for model types
T = TypeVar("T", bound=BaseModel)


class BaseRepository(ABC, Generic[T]):
    """
    Base class for all repositories.
    
    Provides common functionality:
    - Database connection access
    - Common query patterns
    - Error handling
    - Logging
    
    Subclasses must implement:
    - _table_name: The database table name
    - _model_from_row(): Convert a database row to a model
    - _model_to_row(): Convert a model to database values
    
    Usage:
        class NodeRepository(BaseRepository[Node]):
            _table_name = "nodes"
            
            def _model_from_row(self, row) -> Node:
                return Node(**dict(row))
    
    Attributes:
        db: The database manager instance
    """
    
    _table_name: str  # Must be set by subclass
    
    def __init__(self, db: DatabaseManager) -> None:
        """
        Initialize the repository.
        
        Args:
            db: Database manager instance
        """
        self._db = db
        logger.debug(f"{self.__class__.__name__} initialized")
    
    @property
    def db(self) -> DatabaseManager:
        """The database manager."""
        return self._db
    
    @abstractmethod
    def _model_from_row(self, row: Any) -> T:
        """
        Convert a database row to a model instance.
        
        Args:
            row: Database row (aiosqlite.Row)
        
        Returns:
            Model instance
        """
        pass
    
    @abstractmethod
    def _model_to_row(self, model: T) -> dict[str, Any]:
        """
        Convert a model instance to database column values.
        
        Args:
            model: Model instance
        
        Returns:
            Dict of column name -> value
        """
        pass
    
    async def _fetch_one(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> Optional[T]:
        """
        Execute a query and return one model instance.
        
        Args:
            query: SQL query
            params: Query parameters
        
        Returns:
            Model instance if found, None otherwise
        """
        row = await self._db.fetch_one(query, params)
        if row is None:
            return None
        return self._model_from_row(row)
    
    async def _fetch_all(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> list[T]:
        """
        Execute a query and return all model instances.
        
        Args:
            query: SQL query
            params: Query parameters
        
        Returns:
            List of model instances
        """
        rows = await self._db.fetch_all(query, params)
        return [self._model_from_row(row) for row in rows]
    
    async def _insert(
        self,
        model: T,
        columns: list[str],
    ) -> None:
        """
        Insert a model into the database.
        
        Args:
            model: Model to insert
            columns: List of column names to insert
        """
        values = self._model_to_row(model)
        
        placeholders = ", ".join(["?"] * len(columns))
        column_names = ", ".join(columns)
        
        query = f"INSERT INTO {self._table_name} ({column_names}) VALUES ({placeholders})"
        params = tuple(values[col] for col in columns)
        
        async with self._db.connection() as conn:
            await conn.execute(query, params)
            await conn.commit()
    
    async def _update(
        self,
        model: T,
        columns: list[str],
        where_clause: str,
        where_params: tuple[Any, ...],
    ) -> None:
        """
        Update a model in the database.
        
        Args:
            model: Model with new values
            columns: List of column names to update
            where_clause: WHERE clause (without WHERE keyword)
            where_params: Parameters for WHERE clause
        """
        values = self._model_to_row(model)
        
        set_clause = ", ".join([f"{col} = ?" for col in columns])
        query = f"UPDATE {self._table_name} SET {set_clause} WHERE {where_clause}"
        params = tuple(values[col] for col in columns) + where_params
        
        async with self._db.connection() as conn:
            await conn.execute(query, params)
            await conn.commit()
    
    async def _delete(
        self,
        where_clause: str,
        where_params: tuple[Any, ...],
    ) -> int:
        """
        Delete rows from the database.
        
        Args:
            where_clause: WHERE clause (without WHERE keyword)
            where_params: Parameters for WHERE clause
        
        Returns:
            Number of rows deleted
        """
        query = f"DELETE FROM {self._table_name} WHERE {where_clause}"
        
        async with self._db.connection() as conn:
            cursor = await conn.execute(query, where_params)
            await conn.commit()
            return cursor.rowcount
    
    async def _exists(
        self,
        where_clause: str,
        where_params: tuple[Any, ...],
    ) -> bool:
        """
        Check if a row exists.
        
        Args:
            where_clause: WHERE clause (without WHERE keyword)
            where_params: Parameters for WHERE clause
        
        Returns:
            True if at least one row exists
        """
        query = f"SELECT 1 FROM {self._table_name} WHERE {where_clause} LIMIT 1"
        row = await self._db.fetch_one(query, where_params)
        return row is not None
    
    async def _count(
        self,
        where_clause: str = "1=1",
        where_params: tuple[Any, ...] = (),
    ) -> int:
        """
        Count rows matching a condition.
        
        Args:
            where_clause: WHERE clause (without WHERE keyword)
            where_params: Parameters for WHERE clause
        
        Returns:
            Number of matching rows
        """
        query = f"SELECT COUNT(*) FROM {self._table_name} WHERE {where_clause}"
        row = await self._db.fetch_one(query, where_params)
        return row[0] if row else 0

