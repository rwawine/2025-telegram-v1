"""Broadcast service capable of handling 10k recipients with media content support."""

from __future__ import annotations

import asyncio
import os
from enum import Enum
from typing import Iterable, List, Dict, Any, Optional, Union

from aiogram import Bot
from aiogram.types import InputFile

from database.repositories import (
    store_broadcast_results,
    mark_broadcast_sent,
    mark_broadcast_failed,
    set_broadcast_job_completed,
)


class MediaType(Enum):
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    AUDIO = "audio"


class BroadcastService:
    def __init__(self, bot: Bot, rate_limit: int = 30, batch_size: int = 30, retry_attempts: int = 3) -> None:
        self.bot = bot
        self.rate_limit = rate_limit
        self.batch_size = batch_size
        self.retry_attempts = retry_attempts

    async def send_broadcast(
        self,
        message: str,
        recipient_ids: Iterable[int],
        media_path: Optional[str] = None,
        media_type: Optional[str] = None,
        caption: Optional[str] = None,
        job_id: Optional[int] = None,
    ) -> None:
        """
        Send broadcast message with optional media attachment.
        
        Args:
            message: Text message to send
            recipient_ids: List of recipient Telegram IDs
            media_path: Optional path to media file
            media_type: Type of media (photo, video, document, audio)
            caption: Optional caption for media content
        """
        recipients = list(recipient_ids)
        for start in range(0, len(recipients), self.batch_size):
            batch = recipients[start : start + self.batch_size]
            await self._send_batch(message, batch, media_path, media_type, caption, job_id=job_id)
            await asyncio.sleep(1.0)
        # Mark job completed when all batches processed
        if job_id is not None:
            try:
                await set_broadcast_job_completed(job_id)
            except Exception:
                pass

    async def _send_batch(
        self,
        message: str,
        batch: List[int],
        media_path: Optional[str] = None,
        media_type: Optional[str] = None,
        caption: Optional[str] = None,
        job_id: Optional[int] = None,
    ) -> None:
        tasks = [
            self._send_with_retry(recipient_id, message, media_path, media_type, caption, job_id=job_id)
            for recipient_id in batch
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_with_retry(
        self,
        telegram_id: int,
        message: str,
        media_path: Optional[str] = None,
        media_type: Optional[str] = None,
        caption: Optional[str] = None,
        job_id: Optional[int] = None,
    ) -> None:
        for attempt in range(self.retry_attempts):
            try:
                if media_path and media_type and os.path.exists(media_path):
                    await self._send_media(telegram_id, media_path, media_type, caption or message)
                else:
                    await self.bot.send_message(telegram_id, message)
                # Mark sent in queue if job_id provided
                if job_id is not None:
                    try:
                        await mark_broadcast_sent(job_id, telegram_id)
                    except Exception:
                        pass
                return
            except Exception:
                await asyncio.sleep(2 ** attempt)
        # Mark failed in queue if job_id provided; fallback to legacy store
        if job_id is not None:
            try:
                await mark_broadcast_failed(job_id, telegram_id)
                return
            except Exception:
                pass
        await store_broadcast_results([telegram_id], message, status="failed")
        
    async def _send_media(
        self, 
        telegram_id: int, 
        media_path: str, 
        media_type: str,
        caption: str
    ) -> None:
        """Send media content based on type."""
        media_file = InputFile(media_path)
        
        if media_type == MediaType.PHOTO.value:
            await self.bot.send_photo(telegram_id, media_file, caption=caption)
        elif media_type == MediaType.VIDEO.value:
            await self.bot.send_video(telegram_id, media_file, caption=caption)
        elif media_type == MediaType.DOCUMENT.value:
            await self.bot.send_document(telegram_id, media_file, caption=caption)
        elif media_type == MediaType.AUDIO.value:
            await self.bot.send_audio(telegram_id, media_file, caption=caption)
        else:
            # Fallback to regular message if media type is unknown
            await self.bot.send_message(telegram_id, caption)

