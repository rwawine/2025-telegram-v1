"""Database schema migrations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable

from .connection import OptimizedSQLitePool


SCHEMA_SQL: tuple[str, ...] = (
    "PRAGMA foreign_keys = ON;",
    """
    CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id BIGINT UNIQUE NOT NULL,
        username TEXT,
        full_name TEXT NOT NULL,
        phone_number TEXT UNIQUE NOT NULL,
        loyalty_card TEXT UNIQUE NOT NULL,
        photo_path TEXT,
        status TEXT DEFAULT 'pending',
        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        admin_notes TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_participants_status ON participants(status);",
    "CREATE INDEX IF NOT EXISTS idx_participants_telegram_id ON participants(telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_participants_phone ON participants(phone_number);",
    "CREATE INDEX IF NOT EXISTS idx_participants_registration_date ON participants(registration_date);",
    "CREATE INDEX IF NOT EXISTS idx_participants_composite ON participants(status, registration_date);",
    """
    CREATE TABLE IF NOT EXISTS lottery_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seed TEXT NOT NULL,
        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        winners_count INTEGER NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS winners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        participant_id INTEGER NOT NULL,
        lottery_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        position INTEGER,
        prize_description TEXT,
        claimed BOOLEAN DEFAULT FALSE,
        FOREIGN KEY(run_id) REFERENCES lottery_runs(id),
        FOREIGN KEY(participant_id) REFERENCES participants(id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_winners_participant ON winners(participant_id);",
    "CREATE INDEX IF NOT EXISTS idx_winners_lottery_date ON winners(lottery_date);",
    "CREATE INDEX IF NOT EXISTS idx_winners_run ON winners(run_id);",
    """
    CREATE TABLE IF NOT EXISTS broadcast_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_text TEXT NOT NULL,
        total_recipients INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        finished_at TIMESTAMP,
        media_path TEXT,
        media_type TEXT,
        media_caption TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS broadcast_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        participant_id INTEGER,
        telegram_id INTEGER,
        message_text TEXT,
        status TEXT DEFAULT 'pending',
        attempts INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        media_path TEXT,
        media_type TEXT,
        media_caption TEXT,
        FOREIGN KEY(job_id) REFERENCES broadcast_jobs(id),
        FOREIGN KEY(participant_id) REFERENCES participants(id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_broadcast_status ON broadcast_queue(status, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_broadcast_job ON broadcast_queue(job_id);",
    """
    CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        participant_id INTEGER,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'open',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        FOREIGN KEY(participant_id) REFERENCES participants(id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets(status, created_at);",
    """
    CREATE TABLE IF NOT EXISTS support_ticket_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        sender_type TEXT NOT NULL,
        message_text TEXT,
        attachment_path TEXT,
        attachment_file_id TEXT,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(ticket_id) REFERENCES support_tickets(id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket ON support_ticket_messages(ticket_id, sent_at);",
    """
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS media_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE NOT NULL,
        original_filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_type TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by INTEGER,
        FOREIGN KEY(created_by) REFERENCES admins(id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_media_files_type ON media_files(file_type);",
)


async def run_migrations(pool: OptimizedSQLitePool) -> None:
    migrations_path = Path("data/migrations")
    migrations_path.mkdir(parents=True, exist_ok=True)

    async with pool.connection() as conn:
        await conn.execute("BEGIN")
        try:
            for statement in SCHEMA_SQL:
                await conn.execute(statement)
            
            # Add admin_notes column if it doesn't exist (for existing databases)
            try:
                await conn.execute("ALTER TABLE participants ADD COLUMN admin_notes TEXT")
            except Exception:
                # Column already exists, ignore the error
                pass
            
            # Add media columns to broadcast_jobs if they don't exist
            for column in ["media_path TEXT", "media_type TEXT", "media_caption TEXT"]:
                try:
                    await conn.execute(f"ALTER TABLE broadcast_jobs ADD COLUMN {column}")
                except Exception:
                    # Column already exists, ignore the error
                    pass
                
        except Exception:
            await conn.rollback()
            raise
        else:
            await conn.commit()


def apply_migrations_sync(pool: OptimizedSQLitePool) -> None:
    asyncio.get_event_loop().run_until_complete(run_migrations(pool))

