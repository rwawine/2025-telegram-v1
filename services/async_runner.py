"""Utilities to execute coroutines on the main asyncio loop from sync contexts."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future
from typing import Awaitable, Optional, TypeVar


_loop: Optional[asyncio.AbstractEventLoop] = None
T = TypeVar("T")


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def run_coroutine_sync(coro: Awaitable[T]) -> T:
    if _loop is None:
        raise RuntimeError("Asyncio loop is not initialized")
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()


def submit_coroutine(coro: Awaitable[T]) -> Future:
    if _loop is None:
        raise RuntimeError("Asyncio loop is not initialized")
    return asyncio.run_coroutine_threadsafe(coro, _loop)

