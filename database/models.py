"""Data access layer models implemented with handcrafted queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class Participant:
    id: int
    telegram_id: int
    username: Optional[str]
    full_name: str
    phone_number: str
    loyalty_card: str
    photo_path: Optional[str]
    status: str
    registration_date: datetime
    updated_at: Optional[datetime]
    admin_notes: Optional[str] = None


@dataclass(slots=True)
class Winner:
    id: int
    participant_id: int
    lottery_date: datetime
    position: int
    prize_description: str
    claimed: bool


@dataclass(slots=True)
class BroadcastMessage:
    id: int
    participant_id: int
    message_text: str
    status: str
    attempts: int
    created_at: datetime


@dataclass(slots=True)
class SupportTicket:
    id: int
    participant_id: int
    subject: str
    message: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime]


@dataclass(slots=True)
class Admin:
    id: int
    username: str
    password_hash: str
    created_at: datetime


@dataclass(slots=True)
class LotteryRun:
    id: int
    seed: str
    executed_at: datetime
    winners_count: int

