"""Base repository pattern for database operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, TypeVar

from database.connection import get_db_pool

T = TypeVar('T')


class BaseRepository:
    """Base repository with common database operations."""
    
    @staticmethod
    async def execute(query: str, params: Sequence[Any] = ()) -> None:
        """Execute a query without returning results."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            await conn.execute(query, params)
            await conn.commit()
    
    @staticmethod
    async def execute_many(query: str, params: Sequence[Sequence[Any]]) -> None:
        """Execute a query multiple times with different parameters."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            await conn.executemany(query, params)
            await conn.commit()
    
    @staticmethod
    async def fetch_one(query: str, params: Sequence[Any] = ()) -> Optional[Tuple]:
        """Fetch a single row."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            cursor = await conn.execute(query, params)
            return await cursor.fetchone()
    
    @staticmethod
    async def fetch_all(query: str, params: Sequence[Any] = ()) -> List[Tuple]:
        """Fetch all rows."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            cursor = await conn.execute(query, params)
            return [row async for row in cursor]
    
    @staticmethod
    async def fetch_value(query: str, params: Sequence[Any] = ()) -> Optional[Any]:
        """Fetch a single value from a single row."""
        row = await BaseRepository.fetch_one(query, params)
        return row[0] if row else None
    
    @staticmethod
    async def fetch_column(query: str, params: Sequence[Any] = ()) -> List[Any]:
        """Fetch first column from all rows."""
        rows = await BaseRepository.fetch_all(query, params)
        return [row[0] for row in rows]
    
    @staticmethod
    async def transaction(queries: Sequence[Tuple[str, Sequence[Any]]]) -> None:
        """Execute multiple queries in a transaction."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            await conn.execute("BEGIN")
            try:
                for query, params in queries:
                    await conn.execute(query, params)
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise
    
    @staticmethod
    async def batch_insert(
        table: str,
        columns: Sequence[str],
        records: Sequence[Sequence[Any]],
        on_conflict: Optional[str] = None
    ) -> None:
        """Batch insert records into a table.
        
        Args:
            table: Table name
            columns: Column names
            records: List of value tuples
            on_conflict: Optional ON CONFLICT clause
        """
        if not records:
            return
        
        placeholders = ', '.join(['?'] * len(columns))
        columns_str = ', '.join(columns)
        query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
        
        if on_conflict:
            query += f" {on_conflict}"
        
        pool = get_db_pool()
        async with pool.connection() as conn:
            await conn.execute("BEGIN")
            try:
                for record in records:
                    await conn.execute(query, record)
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

