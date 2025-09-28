"""Secure, deterministic lottery selection service."""

from __future__ import annotations

import hashlib
import os
import random
from datetime import datetime
from typing import List

from database.repositories import get_approved_participants
from services.lottery_run import save_lottery_run


class SecureLottery:
    def __init__(self) -> None:
        self.seed = None

    def generate_seed(self) -> str:
        timestamp = datetime.utcnow().isoformat()
        random_bytes = os.urandom(32)
        combined = f"{timestamp}{random_bytes.hex()}"
        self.seed = hashlib.sha256(combined.encode()).hexdigest()
        return self.seed

    async def select_winners(self, num_winners: int) -> tuple[int, List[int]]:
        if self.seed is None:
            self.generate_seed()
        participants = await get_approved_participants()
        participant_ids = [row[0] for row in participants]
        random.seed(int(self.seed, 16))
        sample_size = min(num_winners, len(participant_ids))
        winners = random.sample(participant_ids, sample_size) if sample_size else []
        run_id = await save_lottery_run(self.seed, winners)
        return run_id, winners

