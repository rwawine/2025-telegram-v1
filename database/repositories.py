"""Database access layer helpers."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from database.connection import get_db_pool


async def insert_participants_batch(batch: List[Dict[str, Any]]) -> None:
    pool = get_db_pool()
    async with pool.connection() as conn:
        await conn.execute("BEGIN")
        try:
            for record in batch:
                await conn.execute(
                    """
                    INSERT INTO participants (telegram_id, username, full_name, phone_number, loyalty_card, photo_path, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending')
                    ON CONFLICT(telegram_id) DO UPDATE SET
                        username=excluded.username,
                        full_name=excluded.full_name,
                        phone_number=excluded.phone_number,
                        loyalty_card=excluded.loyalty_card,
                        photo_path=excluded.photo_path,
                        status='pending',
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        record["telegram_id"],
                        record.get("username"),
                        record["full_name"],
                        record["phone_number"],
                        record["loyalty_card"],
                        record.get("photo_path"),
                    ),
                )
        except Exception:
            await conn.rollback()
            raise
        else:
            await conn.commit()


async def get_participant_status(telegram_id: int) -> Optional[str]:
    pool = get_db_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "SELECT status FROM participants WHERE telegram_id=?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_broadcast_recipients(status: str = "approved") -> List[int]:
    pool = get_db_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "SELECT telegram_id FROM participants WHERE status=?",
            (status,),
        )
        return [row[0] async for row in cursor]


async def store_broadcast_results(participant_ids: Sequence[int], message: str, status: str) -> None:
    pool = get_db_pool()
    async with pool.connection() as conn:
        await conn.executemany(
            """
            INSERT INTO broadcast_queue (participant_id, telegram_id, message_text, status)
            VALUES ((SELECT id FROM participants WHERE telegram_id=?), ?, ?, ?)
            """,
            [(telegram_id, telegram_id, message, status) for telegram_id in participant_ids],
        )
        await conn.commit()


async def get_approved_participants(limit: Optional[int] = None) -> List[Tuple[int, int]]:
    pool = get_db_pool()
    query = "SELECT id, telegram_id FROM participants WHERE status='approved'"
    if limit is not None:
        query += " LIMIT ?"
        params: Sequence[Any] = (limit,)
    else:
        params = ()
    async with pool.connection() as conn:
        cursor = await conn.execute(query, params)
        return [tuple(row) async for row in cursor]


# ---------------------- Broadcast helpers (job-aware) ----------------------

async def get_telegram_ids_for_participant_ids(participant_ids: Sequence[int]) -> List[int]:
    """Resolve Telegram IDs for given participant IDs (skips NULLs)."""
    if not participant_ids:
        return []
    pool = get_db_pool()
    placeholders = ",".join(["?"] * len(participant_ids))
    async with pool.connection() as conn:
        cursor = await conn.execute(
            f"SELECT telegram_id FROM participants WHERE id IN ({placeholders}) AND telegram_id IS NOT NULL",
            tuple(participant_ids),
        )
        return [row[0] async for row in cursor]


async def set_broadcast_job_started(job_id: int) -> None:
    pool = get_db_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE broadcast_jobs SET status='sending', started_at=CURRENT_TIMESTAMP WHERE id=?",
            (job_id,),
        )
        await conn.commit()


async def set_broadcast_job_completed(job_id: int) -> None:
    pool = get_db_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE broadcast_jobs SET status='completed', finished_at=CURRENT_TIMESTAMP WHERE id=?",
            (job_id,),
        )
        await conn.commit()


async def set_broadcast_job_failed(job_id: int) -> None:
    pool = get_db_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE broadcast_jobs SET status='failed', finished_at=CURRENT_TIMESTAMP WHERE id=?",
            (job_id,),
        )
        await conn.commit()


async def mark_broadcast_sent(job_id: int, telegram_id: int) -> None:
    """Mark a broadcast queue row as sent for (job_id, telegram_id)."""
    pool = get_db_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE broadcast_queue
            SET status='sent'
            WHERE job_id=? AND telegram_id=?
            """,
            (job_id, telegram_id),
        )
        await conn.commit()


async def mark_broadcast_failed(job_id: int, telegram_id: int) -> None:
    """Mark a broadcast queue row as failed and increment attempts."""
    pool = get_db_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE broadcast_queue
            SET status='failed', attempts = COALESCE(attempts, 0) + 1
            WHERE job_id=? AND telegram_id=?
            """,
            (job_id, telegram_id),
        )
        await conn.commit()


async def get_job_recipient_telegram_ids(job_id: int) -> List[int]:
    """Fetch pending recipient telegram IDs for a given broadcast job."""
    pool = get_db_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "SELECT telegram_id FROM broadcast_queue WHERE job_id=? AND status='pending' AND telegram_id IS NOT NULL",
            (job_id,),
        )
        return [row[0] async for row in cursor]
