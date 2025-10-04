"""Application configuration module.

Reads settings from environment variables with sane defaults to satisfy
performance requirements (500-1000 concurrent users, 10000+ participants).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

# Load environment variables from .env file (optional in test env)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # Proceed without .env if python-dotenv is not available
    pass


def _get_bool(name: str, default: bool = False) -> bool:
    """Get boolean from environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    """Get integer from environment variable with fallback."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_str(name: str, default: str = "") -> str:
    """Get string from environment variable."""
    return os.getenv(name, default)


def _parse_int_list(value: str) -> tuple[int, ...]:
    """Parse comma-separated integers."""
    if not value:
        return ()
    return tuple(int(id_str) for id_str in value.split(",") if id_str.strip())


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: tuple[int, ...]
    admin_username: str
    admin_password: str
    environment: str
    debug: bool
    enable_bot: bool
    web_host: str
    web_port: int
    secret_key: str
    database_path: str
    upload_folder: str
    export_folder: str
    log_folder: str
    backup_folder: str
    max_file_size: int
    max_participants: int
    db_pool_size: int
    db_busy_timeout: int
    bot_rate_limit: int
    bot_worker_threads: int
    message_queue_size: int
    cache_ttl_hot: int
    cache_ttl_warm: int
    cache_ttl_cold: int
    enable_duckdb: bool
    duckdb_path: Optional[str]
    prometheus_port: int
    broadcast_batch_size: int
    broadcast_rate_limit: int
    
    # Sharding configuration
    sharding_enabled: bool
    sharding_base_path: str
    sharding_num_shards: int
    shard_size_threshold: int
    shard_performance_threshold: int
    shard_cache_max_size: int
    shard_cache_ttl: int


def load_config() -> Config:
    """Load application configuration from environment variables.
    
    Returns:
        Config: Application configuration with validated values
    """
    config = Config(
        bot_token=_get_str("BOT_TOKEN", "your_bot_token_here"),
        admin_ids=_parse_int_list(_get_str("ADMIN_IDS", "")),
        admin_username=_get_str("ADMIN_USERNAME", "admin"),
        admin_password=_get_str("ADMIN_PASSWORD", "123456"),
        environment=_get_str("ENVIRONMENT", "development"),
        debug=_get_bool("DEBUG", False),
        enable_bot=_get_bool("ENABLE_BOT", True),
        web_host=_get_str("WEB_HOST", "0.0.0.0"),
        web_port=_get_int("WEB_PORT", 5000),
        secret_key=_get_str(
            "SECRET_KEY",
            "production_secret_key_must_be_changed_in_production_environment"
        ),
        database_path=_get_str("DATABASE_PATH", "data/lottery_bot.sqlite"),
        upload_folder=_get_str("UPLOAD_FOLDER", "uploads"),
        export_folder=_get_str("EXPORT_FOLDER", "exports"),
        log_folder=_get_str("LOG_FOLDER", "logs"),
        backup_folder=_get_str("BACKUP_FOLDER", "backups"),
        max_file_size=_get_int("MAX_FILE_SIZE", 10 * 1024 * 1024),
        max_participants=_get_int("MAX_PARTICIPANTS", 10000),
        db_pool_size=_get_int("DB_POOL_SIZE", 20),
        db_busy_timeout=_get_int("DB_BUSY_TIMEOUT", 5000),
        bot_rate_limit=_get_int("BOT_RATE_LIMIT", 30),
        bot_worker_threads=_get_int("BOT_WORKER_THREADS", 10),
        message_queue_size=_get_int("MESSAGE_QUEUE_SIZE", 1000),
        cache_ttl_hot=_get_int("CACHE_TTL_HOT", 30),
        cache_ttl_warm=_get_int("CACHE_TTL_WARM", 300),
        cache_ttl_cold=_get_int("CACHE_TTL_COLD", 3600),
        enable_duckdb=_get_bool("ENABLE_DUCKDB", False),
        duckdb_path=_get_str("DUCKDB_PATH", "data/analytics.duckdb"),
        prometheus_port=_get_int("PROMETHEUS_PORT", 8000),
        broadcast_batch_size=_get_int("BROADCAST_BATCH_SIZE", 30),
        broadcast_rate_limit=_get_int("BROADCAST_RATE_LIMIT", 30),
        # Sharding configuration
        sharding_enabled=_get_bool("SHARDING_ENABLED", True),
        sharding_base_path=_get_str("SHARDING_BASE_PATH", "data"),
        sharding_num_shards=_get_int("SHARDING_NUM_SHARDS", 4),
        shard_size_threshold=_get_int("SHARD_SIZE_THRESHOLD", 1000000),
        shard_performance_threshold=_get_int("SHARD_PERFORMANCE_THRESHOLD", 100),
        shard_cache_max_size=_get_int("SHARD_CACHE_MAX_SIZE", 10000),
        shard_cache_ttl=_get_int("SHARD_CACHE_TTL", 300),
    )
    
    return config