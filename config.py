"""Application configuration module.

Reads settings from environment variables with sane defaults to satisfy
performance requirements (500-1000 concurrent users, 10000+ participants).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, List

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: tuple[int, ...]
    admin_username: str
    admin_password: str
    environment: str
    debug: bool
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
    """Load application configuration from environment variables."""
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    admin_ids = tuple(int(id_str) for id_str in admin_ids_str.split(",") if id_str.strip())
    
    return Config(
        bot_token=os.getenv("BOT_TOKEN", "8030052876:AAFy39ctXzW90ht4JA0XyR9Ykg6pHM9QiG0"),
        admin_ids=admin_ids,
        admin_username=os.getenv("ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("ADMIN_PASSWORD", "123456"),
        environment=os.getenv("ENVIRONMENT", "development"),
        debug=_get_bool("DEBUG", False),
        web_host=os.getenv("WEB_HOST", "0.0.0.0"),
        web_port=_get_int("WEB_PORT", 5000),
        secret_key=os.getenv("SECRET_KEY", "change_me"),
        database_path=os.getenv("DATABASE_PATH", "data/lottery_bot.sqlite"),
        upload_folder=os.getenv("UPLOAD_FOLDER", "uploads"),
        export_folder=os.getenv("EXPORT_FOLDER", "exports"),
        log_folder=os.getenv("LOG_FOLDER", "logs"),
        backup_folder=os.getenv("BACKUP_FOLDER", "backups"),
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
        duckdb_path=os.getenv("DUCKDB_PATH", "data/analytics.duckdb"),
        prometheus_port=_get_int("PROMETHEUS_PORT", 8000),
        broadcast_batch_size=_get_int("BROADCAST_BATCH_SIZE", 30),
        broadcast_rate_limit=_get_int("BROADCAST_RATE_LIMIT", 30),
        
        # Sharding configuration
        sharding_enabled=_get_bool("SHARDING_ENABLED", True),
        sharding_base_path=os.getenv("SHARDING_BASE_PATH", "data"),
        sharding_num_shards=_get_int("SHARDING_NUM_SHARDS", 4),
        shard_size_threshold=_get_int("SHARD_SIZE_THRESHOLD", 1000000),
        shard_performance_threshold=_get_int("SHARD_PERFORMANCE_THRESHOLD", 100),
        shard_cache_max_size=_get_int("SHARD_CACHE_MAX_SIZE", 10000),
        shard_cache_ttl=_get_int("SHARD_CACHE_TTL", 300),
    )