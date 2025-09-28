"""Multi-level caching layer to offload database reads."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional

from cachetools import TTLCache


class MultiLevelCache:
    def __init__(self, hot_ttl: int, warm_ttl: int, cold_ttl: int) -> None:
        self.hot_cache = TTLCache(maxsize=1000, ttl=hot_ttl)
        self.warm_cache = TTLCache(maxsize=500, ttl=warm_ttl)
        self.cold_cache = TTLCache(maxsize=200, ttl=cold_ttl)
        self.lock = asyncio.Lock()

    async def get_or_set(
        self,
        key: str,
        loader: Callable[[], Awaitable[Any]],
        level: str = "hot",
    ) -> Any:
        cache = self._pick_cache(level)
        async with self.lock:
            if key in cache:
                return cache[key]
            value = await loader()
            cache[key] = value
            return value

    def invalidate(self, key: str) -> None:
        for cache in (self.hot_cache, self.warm_cache, self.cold_cache):
            cache.pop(key, None)

    def _pick_cache(self, level: str) -> TTLCache:
        if level == "hot":
            return self.hot_cache
        if level == "warm":
            return self.warm_cache
        if level == "cold":
            return self.cold_cache
        raise ValueError(f"Unknown cache level: {level}")


cache_instance: Optional[MultiLevelCache] = None


def init_cache(hot_ttl: int, warm_ttl: int, cold_ttl: int) -> MultiLevelCache:
    global cache_instance
    cache_instance = MultiLevelCache(hot_ttl=hot_ttl, warm_ttl=warm_ttl, cold_ttl=cold_ttl)
    return cache_instance


def get_cache() -> MultiLevelCache:
    if cache_instance is None:
        raise RuntimeError("Cache is not initialized")
    return cache_instance

