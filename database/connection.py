"""Optimized SQLite connection pool supporting high concurrency."""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional

import aiosqlite


@dataclass
class _PooledConnection:
    conn: aiosqlite.Connection
    in_use: bool = False


class OptimizedSQLitePool:
    """Connection pool tuned for 500-1000 concurrent users."""

    def __init__(self, database_path: str, pool_size: int = 20, busy_timeout_ms: int = 5000) -> None:
        self.database_path = Path(database_path)
        self.pool_size = pool_size
        self.busy_timeout_ms = busy_timeout_ms
        self._connections: deque[_PooledConnection] = deque()
        self._lock = asyncio.Lock()
        self._initialized = False

    async def init_pool(self) -> None:
        if self._initialized:
            return

        if not self.database_path.parent.exists():
            self.database_path.parent.mkdir(parents=True, exist_ok=True)

        for _ in range(self.pool_size):
            conn = await aiosqlite.connect(self.database_path.as_posix())
            await self._apply_pragma(conn)
            self._connections.append(_PooledConnection(conn=conn))

        self._initialized = True

    async def close(self) -> None:
        while self._connections:
            pooled = self._connections.popleft()
            await pooled.conn.close()
        self._initialized = False

    async def _apply_pragma(self, conn: aiosqlite.Connection) -> None:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA cache_size=-64000")
        await conn.execute("PRAGMA temp_store=MEMORY")
        await conn.execute("PRAGMA mmap_size=268435456")
        await conn.execute("PRAGMA locking_mode=NORMAL")
        await conn.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")

    async def _acquire(self) -> aiosqlite.Connection:
        async with self._lock:
            while True:
                for pooled in self._connections:
                    if not pooled.in_use:
                        pooled.in_use = True
                        return pooled.conn
                await asyncio.sleep(0.001)

    async def _release(self, conn: aiosqlite.Connection) -> None:
        async with self._lock:
            for pooled in self._connections:
                if pooled.conn == conn:
                    pooled.in_use = False
                    return

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        if not self._initialized:
            await self.init_pool()
        conn = await self._acquire()
        try:
            yield conn
        finally:
            await self._release(conn)


_db_pool: Optional[OptimizedSQLitePool] = None


def get_db_pool() -> OptimizedSQLitePool:
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return _db_pool


async def init_db_pool(database_path: str, pool_size: int, busy_timeout_ms: int) -> OptimizedSQLitePool:
    global _db_pool
    pool = OptimizedSQLitePool(database_path=database_path, pool_size=pool_size, busy_timeout_ms=busy_timeout_ms)
    await pool.init_pool()
    _db_pool = pool
    return pool

