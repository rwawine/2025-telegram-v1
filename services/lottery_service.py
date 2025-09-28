"""Lottery management service combining business logic and caching."""

from __future__ import annotations

from typing import List

from database.admin_queries import AdminDatabase
from services.cache import get_cache
from services.lottery import SecureLottery


class LotteryManager:
    def __init__(self, db: AdminDatabase, lottery: SecureLottery) -> None:
        self.db = db
        self.lottery = lottery

    async def run_lottery(self, winners_count: int) -> int:
        run_id, _ = await self.lottery.select_winners(winners_count)
        cache = get_cache()
        cache.invalidate("lottery:runs")
        return run_id

    def get_runs(self, limit: int = 50):
        cache = get_cache()

        async def load():
            # synchronous DB operations - wrap in coroutine
            return self.db.list_lottery_runs(limit=limit)

        return cache.get_or_set("lottery:runs", lambda: load(), level="warm")

