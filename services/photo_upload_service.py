"""Service for reliable photo uploads with retry mechanism."""

from __future__ import annotations

import uuid
import asyncio
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from core import get_logger
from core.constants import FileUploadLimits

if TYPE_CHECKING:
    from aiogram import Bot

logger = get_logger(__name__)


class PhotoUploadService:
    """Service for handling photo uploads with retry logic."""
    
    def __init__(self, bot: Bot, upload_dir: Path, max_retries: int = 3):
        """Initialize photo upload service.
        
        Args:
            bot: Telegram bot instance
            upload_dir: Directory for uploaded files
            max_retries: Maximum number of retry attempts
        """
        self.bot = bot
        self.upload_dir = upload_dir
        self.max_retries = max_retries
    
    async def download_photo_with_retry(
        self,
        file_id: str,
        retry_delay: float = 1.0
    ) -> Optional[str]:
        """Download photo with retry mechanism.
        
        Args:
            file_id: Telegram file ID
            retry_delay: Delay between retries in seconds
            
        Returns:
            Path to downloaded file or None if failed
        """
        last_error = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Attempting to download photo (attempt {attempt}/{self.max_retries})",
                    extra={"file_id": file_id, "attempt": attempt}
                )
                
                # Ensure upload directory exists
                self.upload_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate unique filename
                filename = f"{uuid.uuid4().hex}.jpg"
                destination = self.upload_dir / filename
                
                # Download file
                file = await self.bot.get_file(file_id)
                await self.bot.download_file(file.file_path, destination=str(destination))
                
                # Verify file was created
                if not destination.exists():
                    raise FileNotFoundError(f"Downloaded file not found: {destination}")
                
                # Verify file size
                file_size = destination.stat().st_size
                if file_size == 0:
                    raise ValueError("Downloaded file is empty")
                
                logger.info(
                    f"Photo downloaded successfully on attempt {attempt}",
                    extra={
                        "file_id": file_id,
                        "path": str(destination),
                        "size": file_size,
                        "attempt": attempt
                    }
                )
                
                return destination.as_posix()
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Photo download attempt {attempt} failed: {e}",
                    extra={"file_id": file_id, "attempt": attempt}
                )
                
                # Don't retry on last attempt
                if attempt < self.max_retries:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    # Increase delay for next retry (exponential backoff)
                    retry_delay *= 2
        
        # All attempts failed
        logger.error(
            f"Failed to download photo after {self.max_retries} attempts: {last_error}",
            exc_info=True,
            extra={"file_id": file_id, "max_retries": self.max_retries}
        )
        return None
    
    async def validate_photo_size(
        self,
        file_size: Optional[int],
        max_size: int = FileUploadLimits.MAX_PHOTO_SIZE
    ) -> tuple[bool, Optional[str]]:
        """Validate photo file size.
        
        Args:
            file_size: Size of file in bytes
            max_size: Maximum allowed size in bytes
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if file_size is None:
            return True, None  # Size unknown, allow
        
        if file_size > max_size:
            size_mb = file_size // (1024 * 1024)
            max_mb = max_size // (1024 * 1024)
            error_msg = (
                f"❌ **Фото слишком большое**\n\n"
                f"📊 Размер вашего фото: {size_mb} МБ\n"
                f"📐 Максимальный размер: {max_mb} МБ\n\n"
                f"💡 **Попробуйте:**\n"
                f"• Сжать фото в приложении камеры\n"
                f"• Уменьшить разрешение\n"
                f"• Выбрать другое фото"
            )
            return False, error_msg
        
        return True, None
    
    async def cleanup_old_photos(self, max_age_days: int = 30) -> int:
        """Clean up old photos from upload directory.
        
        Args:
            max_age_days: Maximum age of photos in days
            
        Returns:
            Number of files deleted
        """
        try:
            from datetime import datetime, timedelta
            
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            deleted_count = 0
            
            for photo_file in self.upload_dir.glob("*.jpg"):
                try:
                    file_time = datetime.fromtimestamp(photo_file.stat().st_mtime)
                    if file_time < cutoff_time:
                        photo_file.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted old photo: {photo_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete {photo_file.name}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old photos")
            
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup old photos: {e}", exc_info=True)
            return 0


# Singleton instance
_photo_upload_service: Optional[PhotoUploadService] = None


def init_photo_upload_service(
    bot: Bot,
    upload_dir: Path,
    max_retries: int = 3
) -> PhotoUploadService:
    """Initialize global photo upload service.
    
    Args:
        bot: Telegram bot instance
        upload_dir: Directory for uploaded files
        max_retries: Maximum number of retry attempts
        
    Returns:
        Initialized photo upload service
    """
    global _photo_upload_service
    _photo_upload_service = PhotoUploadService(bot, upload_dir, max_retries)
    return _photo_upload_service


def get_photo_upload_service() -> PhotoUploadService:
    """Get global photo upload service.
    
    Returns:
        Global photo upload service
        
    Raises:
        RuntimeError: If service is not initialized
    """
    if _photo_upload_service is None:
        raise RuntimeError("Photo upload service is not initialized")
    return _photo_upload_service

