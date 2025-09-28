"""High-performance Telegram bot wrapper around aiogram."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Iterable

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
try:
    # aiogram >=3.7.0
    from aiogram.client.bot import DefaultBotProperties  # type: ignore
    _DEFAULT_KW = {"default": DefaultBotProperties(parse_mode=ParseMode.HTML)}
except Exception:  # pragma: no cover
    _DEFAULT_KW = {"parse_mode": ParseMode.HTML}
from aiogram.fsm.storage.memory import MemoryStorage
from asyncio_throttle import Throttler


class OptimizedBot:
    def __init__(
        self,
        token: str,
        rate_limit: int,
        worker_threads: int,
        message_queue_size: int,
    ) -> None:
        # Support both aiogram 3.3 and 3.7+ initializer signatures
        self.bot = Bot(token=token, **_DEFAULT_KW)
        self.storage = MemoryStorage()
        self.dispatcher = Dispatcher(storage=self.storage)
        self.rate_limit = rate_limit
        self.worker_threads = worker_threads
        self.message_queue: asyncio.Queue[Callable[[], Awaitable[None]]] = asyncio.Queue(
            maxsize=message_queue_size
        )
        self.throttler = Throttler(rate_limit=rate_limit, period=1.0)

    async def start(self) -> None:
        self.workers = [asyncio.create_task(self._worker_loop()) for _ in range(self.worker_threads)]
        await self.dispatcher.start_polling(self.bot)

    async def stop(self) -> None:
        for worker in getattr(self, "workers", []):
            worker.cancel()
        await self.dispatcher.storage.close()
        await self.bot.session.close()

    async def enqueue(self, task: Callable[[], Awaitable[None]]) -> None:
        await self.message_queue.put(task)

    async def _worker_loop(self) -> None:
        while True:
            task = await self.message_queue.get()
            try:
                async with self.throttler:
                    await task()
            finally:
                self.message_queue.task_done()

