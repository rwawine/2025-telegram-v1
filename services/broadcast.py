"""Broadcast service capable of handling 10k recipients with media content support."""

from __future__ import annotations

import asyncio
import os
from enum import Enum
from typing import Iterable, List, Optional

from aiogram import Bot
from aiogram.types import FSInputFile

from core import get_logger, TelegramLimits, BroadcastDefaults
from core.exceptions import BroadcastError
from database.repositories import (
    store_broadcast_results,
    mark_broadcast_sent,
    mark_broadcast_failed,
    set_broadcast_job_completed,
)

logger = get_logger(__name__)


class MediaType(Enum):
    """Media types supported by Telegram."""
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    AUDIO = "audio"


class BroadcastService:
    """Service for sending mass messages to multiple recipients.
    
    Supports:
    - Text messages with automatic chunking for long texts
    - Media attachments (photo, video, document, audio)
    - Retry mechanism with exponential backoff
    - Rate limiting to comply with Telegram limits
    - Job-based status tracking
    """
    
    def __init__(
        self, 
        bot: Bot, 
        rate_limit: int = BroadcastDefaults.RATE_LIMIT,
        batch_size: int = BroadcastDefaults.BATCH_SIZE,
        retry_attempts: int = BroadcastDefaults.RETRY_ATTEMPTS
    ) -> None:
        """Initialize broadcast service.
        
        Args:
            bot: Aiogram Bot instance
            rate_limit: Maximum messages per second
            batch_size: Number of messages to send in parallel
            retry_attempts: Number of retry attempts for failed messages
        """
        self.bot = bot
        self.rate_limit = rate_limit
        self.batch_size = batch_size
        self.retry_attempts = retry_attempts
        
        logger.info(
            f"BroadcastService initialized: "
            f"rate_limit={rate_limit}, batch_size={batch_size}, "
            f"retry_attempts={retry_attempts}"
        )
    
    @staticmethod
    def _split_text(text: str, limit: int) -> List[str]:
        """Split text into chunks respecting Telegram limits.
        
        Args:
            text: Text to split
            limit: Maximum length per chunk
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        parts: List[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + limit)
            parts.append(text[start:end])
            start = end
        return parts

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
        """Send message with retry mechanism.
        
        Args:
            telegram_id: Recipient's Telegram ID
            message: Message text
            media_path: Optional path to media file
            media_type: Type of media
            caption: Caption for media
            job_id: Optional broadcast job ID for tracking
        """
        # Pre-split message into chunks
        message_parts = self._split_text(message, TelegramLimits.MESSAGE_MAX_LENGTH)
        
        # For media captions, use smaller limit
        caption_text = caption or message
        caption_head = self._split_text(caption_text, TelegramLimits.CAPTION_MAX_LENGTH)[:1]
        caption_tail = self._split_text(
            caption_text[len(caption_head[0]) if caption_head else 0:],
            TelegramLimits.MESSAGE_MAX_LENGTH
        )

        for attempt in range(self.retry_attempts):
            try:
                if media_path and media_type and os.path.exists(media_path):
                    # Send media with safe caption head (<= caption_limit)
                    safe_caption = caption_head[0] if caption_head else None
                    await self._send_media(telegram_id, media_path, media_type, safe_caption)
                    # Send remaining caption/body text parts as follow-up messages
                    for part in caption_tail:
                        await self.bot.send_message(telegram_id, part)
                else:
                    # Send message in chunks (<=4096)
                    if not message_parts:
                        message_parts = [""]
                    for idx, part in enumerate(message_parts):
                        await self.bot.send_message(telegram_id, part)
                # Mark sent in queue if job_id provided
                if job_id is not None:
                    try:
                        await mark_broadcast_sent(job_id, telegram_id)
                    except Exception:
                        pass
                return
            except Exception as e:
                if attempt < self.retry_attempts - 1:
                    delay = BroadcastDefaults.RETRY_DELAY ** attempt
                    logger.warning(
                        f"Failed to send to {telegram_id}, attempt {attempt + 1}/{self.retry_attempts}. "
                        f"Retrying in {delay}s. Error: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to send to {telegram_id} after {self.retry_attempts} attempts: {e}")
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
        media_file = FSInputFile(media_path)
        
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

