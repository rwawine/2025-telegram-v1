"""Application-wide constants and configuration values."""

from __future__ import annotations

from enum import Enum


# Telegram limits
class TelegramLimits:
    """Telegram API limits."""
    MESSAGE_MAX_LENGTH = 4096
    CAPTION_MAX_LENGTH = 1024
    PHOTO_MAX_SIZE = 10 * 1024 * 1024  # 10MB
    
    
# Broadcast constants
class BroadcastDefaults:
    """Default values for broadcast operations."""
    RATE_LIMIT = 30  # messages per second
    BATCH_SIZE = 30
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 2  # seconds
    

# Cache constants
class CacheDefaults:
    """Default cache configuration."""
    HOT_TTL = 30  # seconds
    WARM_TTL = 300  # seconds
    COLD_TTL = 3600  # seconds
    HOT_SIZE = 1000
    WARM_SIZE = 500
    COLD_SIZE = 200


# Database constants
class DatabaseDefaults:
    """Default database configuration."""
    POOL_SIZE = 20
    BUSY_TIMEOUT = 5000  # milliseconds
    MAX_PARTICIPANTS = 10000


# Status enums
class ParticipantStatus(str, Enum):
    """Participant registration status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class BroadcastStatus(str, Enum):
    """Broadcast message status."""
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    COMPLETED = "completed"


class TicketStatus(str, Enum):
    """Support ticket status."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


# File validation
class FileValidation:
    """File upload validation constants."""
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}


# Lottery constants
class LotteryDefaults:
    """Lottery configuration."""
    SEED_RANDOM_BYTES = 32
    MIN_PARTICIPANTS = 1
    MAX_WINNERS_PERCENT = 0.3  # 30% of participants


# Rate limiting
class RateLimitDefaults:
    """Rate limiting configuration."""
    MAX_MESSAGES = 5  # per window
    MAX_CALLBACKS = 3  # per window
    WINDOW_SECONDS = 2.0
    
    
# Backup configuration
class BackupDefaults:
    """Backup service configuration."""
    MAX_AGE_DAYS = 2
    INTERVAL_HOURS = 6
    COMPRESSION = True


# File upload limits
class FileUploadLimits:
    """File upload size limits."""
    MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_DOCUMENT_SIZE = 20 * 1024 * 1024  # 20 MB
    MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB


# Registration defaults
class RegistrationDefaults:
    """Registration process defaults."""
    STATE_TIMEOUT_MINUTES = 30  # Auto-save timeout
    MAX_PHOTO_RETRIES = 3  # Max retries for photo upload
    PHOTO_RETRY_DELAY = 1.0  # Initial delay between retries
    CONFIRM_REQUIRED = True  # Require confirmation before submit


# Notification settings
class NotificationDefaults:
    """Notification service defaults."""
    MAX_MESSAGE_LENGTH = 4000  # Leave room for formatting
    TICKET_REPLY_TRUNCATE = 3800  # Truncate long ticket replies
    ENABLED = True  # Enable/disable notifications

