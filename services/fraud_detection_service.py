"""Service for detecting fraudulent behavior and bot activity."""

from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass

from core import get_logger
from database.connection import get_db_pool

logger = get_logger(__name__)


@dataclass
class FraudScore:
    """Fraud detection result."""
    score: float  # 0.0 (safe) to 1.0 (fraud)
    reasons: list[str]
    is_suspicious: bool
    should_block: bool


class FraudDetectionService:
    """Service for detecting fraudulent registrations and bot activity."""
    
    def __init__(self):
        self.user_activity: Dict[int, list[datetime]] = defaultdict(list)
        self.blocked_users: set[int] = set()
        
    async def check_registration(
        self,
        user_id: int,
        full_name: str,
        phone_number: str,
        loyalty_card: str,
        registration_time: float  # Время прохождения регистрации в секундах
    ) -> FraudScore:
        """Analyze registration for fraud indicators.
        
        Args:
            user_id: Telegram user ID
            full_name: User's full name
            phone_number: Phone number
            loyalty_card: Loyalty card number
            registration_time: Time taken to complete registration
            
        Returns:
            FraudScore with detection results
        """
        score = 0.0
        reasons = []
        
        # 1. Check if user already blocked
        if user_id in self.blocked_users:
            return FraudScore(
                score=1.0,
                reasons=["User is blocked"],
                is_suspicious=True,
                should_block=True
            )
        
        # 2. Check registration speed (too fast = bot)
        if registration_time < 15:  # Less than 15 seconds
            score += 0.3
            reasons.append(f"Registration too fast: {registration_time:.1f}s")
        
        # 3. Check for duplicate phone numbers
        pool = get_db_pool()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM participants WHERE phone_number = ?",
                (phone_number,)
            )
            phone_count = (await cursor.fetchone())[0]
            
            if phone_count > 0:
                score += 0.5
                reasons.append(f"Phone number already registered {phone_count} times")
            
            # 4. Check for duplicate loyalty cards
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM participants WHERE loyalty_card = ?",
                (loyalty_card,)
            )
            card_count = (await cursor.fetchone())[0]
            
            if card_count > 0:
                score += 0.5
                reasons.append(f"Loyalty card already used {card_count} times")
            
            # 5. Check if user tried to register multiple times recently
            cursor = await conn.execute(
                """
                SELECT COUNT(*) FROM participants 
                WHERE telegram_id = ? 
                AND registration_date > datetime('now', '-1 hour')
                """,
                (user_id,)
            )
            recent_attempts = (await cursor.fetchone())[0]
            
            if recent_attempts > 2:
                score += 0.4
                reasons.append(f"Multiple registration attempts: {recent_attempts}")
        
        # 6. Check name patterns (simple validation)
        if len(full_name.split()) < 2:
            score += 0.1
            reasons.append("Incomplete name (less than 2 words)")
        
        # Analyze suspicious patterns in name
        suspicious_patterns = ['test', 'qwerty', 'asdf', '123', 'admin', 'bot']
        if any(pattern in full_name.lower() for pattern in suspicious_patterns):
            score += 0.3
            reasons.append("Suspicious name pattern detected")
        
        # 7. Check activity rate
        now = datetime.now()
        self.user_activity[user_id].append(now)
        
        # Clean old activity (older than 1 hour)
        self.user_activity[user_id] = [
            t for t in self.user_activity[user_id]
            if now - t < timedelta(hours=1)
        ]
        
        activity_count = len(self.user_activity[user_id])
        if activity_count > 5:
            score += 0.3
            reasons.append(f"High activity rate: {activity_count} actions/hour")
        
        # Calculate final verdict
        is_suspicious = score >= 0.5
        should_block = score >= 0.8
        
        if should_block:
            self.blocked_users.add(user_id)
            logger.warning(
                f"User {user_id} blocked due to fraud score {score:.2f}",
                extra={"user_id": user_id, "reasons": reasons}
            )
        elif is_suspicious:
            logger.info(
                f"Suspicious registration from user {user_id}, score: {score:.2f}",
                extra={"user_id": user_id, "reasons": reasons}
            )
        
        return FraudScore(
            score=score,
            reasons=reasons,
            is_suspicious=is_suspicious,
            should_block=should_block
        )
    
    async def check_support_ticket_spam(
        self,
        user_id: int,
        message_text: str
    ) -> bool:
        """Check if support ticket is spam.
        
        Args:
            user_id: Telegram user ID
            message_text: Ticket message text
            
        Returns:
            True if message is likely spam
        """
        # Check for spam patterns
        spam_keywords = [
            'viagra', 'casino', 'bitcoin', 'lottery', 'prize',
            'winner', 'click here', 'buy now', 'limited offer'
        ]
        
        text_lower = message_text.lower()
        if any(keyword in text_lower for keyword in spam_keywords):
            logger.warning(
                f"Spam keywords detected in ticket from user {user_id}",
                extra={"user_id": user_id}
            )
            return True
        
        # Check ticket creation rate
        pool = get_db_pool()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT COUNT(*) FROM support_tickets t
                JOIN participants p ON p.id = t.participant_id
                WHERE p.telegram_id = ?
                AND t.created_at > datetime('now', '-10 minutes')
                """,
                (user_id,)
            )
            recent_tickets = (await cursor.fetchone())[0]
            
            if recent_tickets > 3:
                logger.warning(
                    f"User {user_id} creating too many tickets: {recent_tickets}",
                    extra={"user_id": user_id}
                )
                return True
        
        return False
    
    async def log_suspicious_activity(
        self,
        user_id: int,
        activity_type: str,
        details: Dict[str, Any]
    ) -> None:
        """Log suspicious activity to database for audit.
        
        Args:
            user_id: Telegram user ID
            activity_type: Type of suspicious activity
            details: Additional details as JSON
        """
        import json
        
        pool = get_db_pool()
        async with pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO fraud_log (user_id, activity_type, details, detected_at)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (user_id, activity_type, json.dumps(details))
            )
            await conn.commit()
        
        logger.info(
            f"Logged suspicious activity: {activity_type} from user {user_id}",
            extra={"user_id": user_id, "details": details}
        )


# Singleton instance
_fraud_detection_service: Optional[FraudDetectionService] = None


def init_fraud_detection_service() -> FraudDetectionService:
    """Initialize fraud detection service singleton."""
    global _fraud_detection_service
    if _fraud_detection_service is None:
        _fraud_detection_service = FraudDetectionService()
        logger.info("Fraud detection service initialized")
    return _fraud_detection_service


def get_fraud_detection_service() -> FraudDetectionService:
    """Get fraud detection service singleton."""
    if _fraud_detection_service is None:
        return init_fraud_detection_service()
    return _fraud_detection_service

