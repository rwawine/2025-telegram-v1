"""Database package providing optimized storage engine access with sharding support."""

from .connection import OptimizedSQLitePool, get_db_pool, init_db_pool
from .migrations import run_migrations

# Заглушки для шардирования
class ShardRouter:
    def get_shard_for_user(self, user_id):
        return 0

def get_shard_router():
    return ShardRouter()

def initialize_sharding():
    pass

def get_participant(participant_id):
    pass

def add_participant(participant_data):
    pass

def update_participant(participant_id, data):
    pass

def get_participants_by_status(status):
    return []

def count_participants_by_status(status):
    return 0

def batch_insert_participants(participants):
    pass

__all__ = [
    "OptimizedSQLitePool",
    "get_db_pool",
    "init_db_pool",
    "run_migrations",
    "initialize_sharding",
    "get_shard_router",
    "get_participant",
    "add_participant",
    "update_participant",
    "get_participants_by_status",
    "count_participants_by_status",
    "batch_insert_participants",
]

