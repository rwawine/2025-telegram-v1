"""Secure, deterministic lottery selection service."""

from __future__ import annotations

import hashlib
import os
import random
from datetime import datetime
from typing import List, Optional

from core import get_logger, LotteryDefaults
from core.exceptions import LotteryError, InsufficientParticipantsError
from database.repositories import get_approved_participants
from services.lottery_run import save_lottery_run

logger = get_logger(__name__)


class SecureLottery:
    """Cryptographically secure lottery service with deterministic selection.
    
    Uses SHA-256 based seed generation and deterministic random selection
    to ensure fair and verifiable lottery results.
    """
    
    def __init__(self) -> None:
        """Initialize lottery service."""
        self.seed: Optional[str] = None
        self._random_bytes_size = LotteryDefaults.SEED_RANDOM_BYTES

    def generate_seed(self) -> str:
        """Generate cryptographically secure seed for lottery.
        
        Returns:
            str: SHA-256 hex digest of timestamp and random bytes
        """
        timestamp = datetime.utcnow().isoformat()
        random_bytes = os.urandom(self._random_bytes_size)
        combined = f"{timestamp}{random_bytes.hex()}"
        self.seed = hashlib.sha256(combined.encode()).hexdigest()
        
        logger.info(f"Generated new lottery seed: {self.seed[:16]}...")
        return self.seed

    async def select_winners(
        self, 
        num_winners: int,
        allow_fewer: bool = True
    ) -> tuple[int, List[int]]:
        """Select lottery winners deterministically.
        
        Args:
            num_winners: Number of winners to select
            allow_fewer: If True, allow fewer winners if not enough participants
            
        Returns:
            Tuple of (run_id, winner_participant_ids)
            
        Raises:
            InsufficientParticipantsError: If not enough participants and allow_fewer=False
            ValueError: If num_winners is invalid
        """
        if num_winners < 1:
            raise ValueError("Number of winners must be at least 1")
        
        # Generate seed if not already set
        if self.seed is None:
            self.generate_seed()
        
        # Get approved participants
        participants = await get_approved_participants()
        participant_ids = [row[0] for row in participants]
        
        logger.info(f"Selecting {num_winners} winners from {len(participant_ids)} participants")
        
        # Validate participant count
        if len(participant_ids) < LotteryDefaults.MIN_PARTICIPANTS:
            raise InsufficientParticipantsError(
                f"Need at least {LotteryDefaults.MIN_PARTICIPANTS} approved participants"
            )
        
        if len(participant_ids) < num_winners and not allow_fewer:
            raise InsufficientParticipantsError(
                f"Not enough participants: have {len(participant_ids)}, need {num_winners}"
            )
        
        # Select winners deterministically
        random.seed(int(self.seed, 16))
        sample_size = min(num_winners, len(participant_ids))
        winners = random.sample(participant_ids, sample_size) if sample_size else []
        
        # Save lottery run
        run_id = await save_lottery_run(self.seed, winners)
        
        logger.info(f"Selected {len(winners)} winners. Run ID: {run_id}")
        return run_id, winners
    
    def verify_winner(self, participant_id: int, winners: List[int]) -> bool:
        """Verify if a participant is a winner.
        
        Args:
            participant_id: Participant ID to check
            winners: List of winner IDs
            
        Returns:
            True if participant is a winner
        """
        return participant_id in winners

