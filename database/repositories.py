"""Database access layer helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from database.base_repository import BaseRepository


class ParticipantRepository(BaseRepository):
    """Repository for participant operations."""
    
    @staticmethod
    async def insert_batch(batch: List[Dict[str, Any]]) -> None:
        """Insert or update participants in batch."""
        records = [
            (
                record["telegram_id"],
                record.get("username"),
                record["full_name"],
                record["phone_number"],
                record["loyalty_card"],
                record.get("photo_path"),
            )
            for record in batch
        ]
        
        await BaseRepository.batch_insert(
            table="participants",
            columns=["telegram_id", "username", "full_name", "phone_number", 
                    "loyalty_card", "photo_path"],
            records=records,
            on_conflict="""
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username=excluded.username,
                    full_name=excluded.full_name,
                    phone_number=excluded.phone_number,
                    loyalty_card=excluded.loyalty_card,
                    photo_path=excluded.photo_path,
                    status='pending',
                    updated_at=CURRENT_TIMESTAMP
            """
        )
    
    @staticmethod
    async def get_status(telegram_id: int) -> Optional[str]:
        """Get participant status by telegram_id."""
        return await BaseRepository.fetch_value(
            "SELECT status FROM participants WHERE telegram_id=?",
            (telegram_id,)
        )
    
    @staticmethod
    async def get_approved(limit: Optional[int] = None) -> List[Tuple[int, int]]:
        """Get approved participants."""
        query = "SELECT id, telegram_id FROM participants WHERE status='approved'"
        params: Sequence[Any] = ()
        
        if limit is not None:
            query += " LIMIT ?"
            params = (limit,)
        
        return await BaseRepository.fetch_all(query, params)
    
    @staticmethod
    async def get_telegram_ids_by_status(status: str = "approved") -> List[int]:
        """Get telegram IDs by status."""
        return await BaseRepository.fetch_column(
            "SELECT telegram_id FROM participants WHERE status=?",
            (status,)
        )
    
    @staticmethod
    async def resolve_telegram_ids(participant_ids: Sequence[int]) -> List[int]:
        """Resolve Telegram IDs for given participant IDs."""
        if not participant_ids:
            return []
        
        placeholders = ",".join(["?"] * len(participant_ids))
        return await BaseRepository.fetch_column(
            f"SELECT telegram_id FROM participants "
            f"WHERE id IN ({placeholders}) AND telegram_id IS NOT NULL",
            tuple(participant_ids)
        )
    
    @staticmethod
    async def check_agreement_accepted(telegram_id: int) -> bool:
        """Check if user has accepted the agreement."""
        result = await BaseRepository.fetch_value(
            "SELECT telegram_id FROM user_agreements WHERE telegram_id=?",
            (telegram_id,)
        )
        # Если запись найдена, пользователь принял соглашение
        return result is not None
    
    @staticmethod
    async def set_agreement_accepted(telegram_id: int) -> None:
        """Mark that user has accepted the agreement."""
        await BaseRepository.execute(
            """INSERT OR IGNORE INTO user_agreements (telegram_id, accepted_at)
               VALUES (?, CURRENT_TIMESTAMP)
            """,
            (telegram_id,)
        )


class BroadcastRepository(BaseRepository):
    """Repository for broadcast operations."""
    
    @staticmethod
    async def store_results(
        participant_ids: Sequence[int], 
        message: str, 
        status: str
    ) -> None:
        """Store broadcast results."""
        records = [
            (telegram_id, telegram_id, message, status) 
            for telegram_id in participant_ids
        ]
        
        await BaseRepository.execute_many(
            """
            INSERT INTO broadcast_queue 
            (participant_id, telegram_id, message_text, status)
            VALUES (
                (SELECT id FROM participants WHERE telegram_id=?), 
                ?, ?, ?
            )
            """,
            records
        )
    
    @staticmethod
    async def update_job_status(
        job_id: int, 
        status: str, 
        timestamp_field: str = 'started_at'
    ) -> None:
        """Update broadcast job status."""
        await BaseRepository.execute(
            f"UPDATE broadcast_jobs "
            f"SET status=?, {timestamp_field}=CURRENT_TIMESTAMP "
            f"WHERE id=?",
            (status, job_id)
        )
    
    @staticmethod
    async def mark_message_status(
        job_id: int, 
        telegram_id: int, 
        status: str,
        increment_attempts: bool = False
    ) -> None:
        """Mark broadcast message status."""
        query = "UPDATE broadcast_queue SET status=?"
        params = [status]
        
        if increment_attempts:
            query += ", attempts = COALESCE(attempts, 0) + 1"
        
        query += " WHERE job_id=? AND telegram_id=?"
        params.extend([job_id, telegram_id])
        
        await BaseRepository.execute(query, tuple(params))
    
    @staticmethod
    async def get_pending_recipients(job_id: int) -> List[int]:
        """Get pending recipient telegram IDs for a broadcast job."""
        return await BaseRepository.fetch_column(
            "SELECT telegram_id FROM broadcast_queue "
            "WHERE job_id=? AND status='pending' AND telegram_id IS NOT NULL",
            (job_id,)
        )


# Backward compatibility aliases
async def insert_participants_batch(batch: List[Dict[str, Any]]) -> None:
    """Legacy: Insert participants batch."""
    await ParticipantRepository.insert_batch(batch)


async def get_participant_status(telegram_id: int) -> Optional[str]:
    """Legacy: Get participant status."""
    return await ParticipantRepository.get_status(telegram_id)


async def get_broadcast_recipients(status: str = "approved") -> List[int]:
    """Legacy: Get broadcast recipients."""
    return await ParticipantRepository.get_telegram_ids_by_status(status)


async def store_broadcast_results(
    participant_ids: Sequence[int], 
    message: str, 
    status: str
) -> None:
    """Legacy: Store broadcast results."""
    await BroadcastRepository.store_results(participant_ids, message, status)


async def get_approved_participants(limit: Optional[int] = None) -> List[Tuple[int, int]]:
    """Legacy: Get approved participants."""
    return await ParticipantRepository.get_approved(limit)


async def get_telegram_ids_for_participant_ids(participant_ids: Sequence[int]) -> List[int]:
    """Legacy: Resolve Telegram IDs."""
    return await ParticipantRepository.resolve_telegram_ids(participant_ids)


async def set_broadcast_job_started(job_id: int) -> None:
    """Legacy: Mark job started."""
    await BroadcastRepository.update_job_status(job_id, 'sending', 'started_at')


async def set_broadcast_job_completed(job_id: int) -> None:
    """Legacy: Mark job completed."""
    await BroadcastRepository.update_job_status(job_id, 'completed', 'finished_at')


async def set_broadcast_job_failed(job_id: int) -> None:
    """Legacy: Mark job failed."""
    await BroadcastRepository.update_job_status(job_id, 'failed', 'finished_at')


async def mark_broadcast_sent(job_id: int, telegram_id: int) -> None:
    """Legacy: Mark broadcast sent."""
    await BroadcastRepository.mark_message_status(job_id, telegram_id, 'sent')


async def mark_broadcast_failed(job_id: int, telegram_id: int) -> None:
    """Legacy: Mark broadcast failed."""
    await BroadcastRepository.mark_message_status(
        job_id, telegram_id, 'failed', increment_attempts=True
    )


async def get_job_recipient_telegram_ids(job_id: int) -> List[int]:
    """Legacy: Get job recipients."""
    return await BroadcastRepository.get_pending_recipients(job_id)


async def check_user_agreement(telegram_id: int) -> bool:
    """Check if user has accepted the agreement."""
    return await ParticipantRepository.check_agreement_accepted(telegram_id)


async def save_user_agreement(telegram_id: int) -> None:
    """Save that user has accepted the agreement."""
    return await ParticipantRepository.set_agreement_accepted(telegram_id)
