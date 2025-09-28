"""Lottery run persistence helpers."""

from __future__ import annotations

from typing import Iterable

from database.connection import get_db_pool


async def save_lottery_run(seed: str, winners: Iterable[int]) -> int:
    pool = get_db_pool()
    winner_list = list(winners)
    async with pool.connection() as conn:
        await conn.execute("BEGIN")
        try:
            cursor = await conn.execute(
                "INSERT INTO lottery_runs (seed, winners_count) VALUES (?, ?) RETURNING id",
                (seed, len(winner_list)),
            )
            row = await cursor.fetchone()
            run_id = row[0]
            await conn.executemany(
                """
                INSERT INTO winners (run_id, participant_id, position, prize_description)
                VALUES (?, ?, ?, '')
                """,
                [(run_id, participant_id, idx + 1) for idx, participant_id in enumerate(winner_list)],
            )
        except Exception:
            await conn.rollback()
            raise
        else:
            await conn.commit()
            return run_id

