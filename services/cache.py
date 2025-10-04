"""Multi-level caching layer to offload database reads."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional, Dict

from cachetools import TTLCache


class CacheLevel:
    """Cache level configuration."""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class MultiLevelCache:
    """Multi-level cache with hot, warm, and cold tiers.
    
    Hot tier: Fast access, short TTL, frequently accessed data
    Warm tier: Medium access, medium TTL, occasionally accessed data
    Cold tier: Slow access, long TTL, rarely accessed data
    """
    
    def __init__(
        self, 
        hot_ttl: int, 
        warm_ttl: int, 
        cold_ttl: int,
        hot_size: int = 1000,
        warm_size: int = 500,
        cold_size: int = 200
    ) -> None:
        """Initialize multi-level cache.
        
        Args:
            hot_ttl: Time-to-live for hot cache in seconds
            warm_ttl: Time-to-live for warm cache in seconds
            cold_ttl: Time-to-live for cold cache in seconds
            hot_size: Maximum size of hot cache
            warm_size: Maximum size of warm cache
            cold_size: Maximum size of cold cache
        """
        self.hot_cache = TTLCache(maxsize=hot_size, ttl=hot_ttl)
        self.warm_cache = TTLCache(maxsize=warm_size, ttl=warm_ttl)
        self.cold_cache = TTLCache(maxsize=cold_size, ttl=cold_ttl)
        self._locks: Dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()
    
    async def _get_key_lock(self, key: str) -> asyncio.Lock:
        """Get or create a lock for a specific key."""
        async with self._locks_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]
    
    async def get(self, key: str, level: str = CacheLevel.HOT) -> Optional[Any]:
        """Get value from cache without loading.
        
        Args:
            key: Cache key
            level: Cache level to check
            
        Returns:
            Cached value or None if not found
        """
        cache = self._pick_cache(level)
        return cache.get(key)
    
    async def set(self, key: str, value: Any, level: str = CacheLevel.HOT) -> None:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            level: Cache level to use
        """
        cache = self._pick_cache(level)
        lock = await self._get_key_lock(key)
        async with lock:
            cache[key] = value
    
    async def get_or_set(
        self,
        key: str,
        loader: Callable[[], Awaitable[Any]],
        level: str = CacheLevel.HOT,
    ) -> Any:
        """Get value from cache or load and cache it.
        
        Args:
            key: Cache key
            loader: Async function to load value if not cached
            level: Cache level to use
            
        Returns:
            Cached or loaded value
        """
        cache = self._pick_cache(level)
        
        # Quick check without lock
        if key in cache:
            return cache[key]
        
        # Acquire lock for this specific key to avoid thundering herd
        lock = await self._get_key_lock(key)
        async with lock:
            # Double-check after acquiring lock
            if key in cache:
                return cache[key]
            
            # Load and cache
            value = await loader()
            cache[key] = value
            return value
    
    def invalidate(self, key: str) -> None:
        """Invalidate a key across all cache levels.
        
        Args:
            key: Cache key to invalidate
        """
        for cache in (self.hot_cache, self.warm_cache, self.cold_cache):
            cache.pop(key, None)
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern.
        
        Args:
            pattern: Pattern to match (simple prefix matching)
            
        Returns:
            Number of keys invalidated
        """
        count = 0
        for cache in (self.hot_cache, self.warm_cache, self.cold_cache):
            keys_to_delete = [k for k in cache if k.startswith(pattern)]
            for key in keys_to_delete:
                cache.pop(key, None)
                count += 1
        return count
    
    def clear(self) -> None:
        """Clear all cache levels."""
        self.hot_cache.clear()
        self.warm_cache.clear()
        self.cold_cache.clear()
        self._locks.clear()
    
    def stats(self) -> Dict[str, Dict[str, Any]]:
        """Get cache statistics.
        
        Returns:
            Dictionary with statistics for each cache level
        """
        return {
            "hot": {
                "size": len(self.hot_cache),
                "maxsize": self.hot_cache.maxsize,
                "ttl": self.hot_cache.ttl,
            },
            "warm": {
                "size": len(self.warm_cache),
                "maxsize": self.warm_cache.maxsize,
                "ttl": self.warm_cache.ttl,
            },
            "cold": {
                "size": len(self.cold_cache),
                "maxsize": self.cold_cache.maxsize,
                "ttl": self.cold_cache.ttl,
            },
        }
    
    def _pick_cache(self, level: str) -> TTLCache:
        """Pick cache by level."""
        if level == CacheLevel.HOT:
            return self.hot_cache
        if level == CacheLevel.WARM:
            return self.warm_cache
        if level == CacheLevel.COLD:
            return self.cold_cache
        raise ValueError(f"Unknown cache level: {level}")


_cache_instance: Optional[MultiLevelCache] = None


def init_cache(
    hot_ttl: int, 
    warm_ttl: int, 
    cold_ttl: int,
    hot_size: int = 1000,
    warm_size: int = 500,
    cold_size: int = 200
) -> MultiLevelCache:
    """Initialize global cache instance.
    
    Args:
        hot_ttl: Time-to-live for hot cache in seconds
        warm_ttl: Time-to-live for warm cache in seconds
        cold_ttl: Time-to-live for cold cache in seconds
        hot_size: Maximum size of hot cache
        warm_size: Maximum size of warm cache
        cold_size: Maximum size of cold cache
        
    Returns:
        Initialized cache instance
    """
    global _cache_instance
    _cache_instance = MultiLevelCache(
        hot_ttl=hot_ttl,
        warm_ttl=warm_ttl,
        cold_ttl=cold_ttl,
        hot_size=hot_size,
        warm_size=warm_size,
        cold_size=cold_size
    )
    return _cache_instance


def get_cache() -> MultiLevelCache:
    """Get global cache instance.
    
    Returns:
        Global cache instance
        
    Raises:
        RuntimeError: If cache is not initialized
    """
    if _cache_instance is None:
        raise RuntimeError("Cache is not initialized")
    return _cache_instance

