"""Analytics service for tracking user events and metrics."""

from __future__ import annotations

from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

from core import get_logger
from database.connection import get_db_pool

logger = get_logger(__name__)


class AnalyticsEvent(str, Enum):
    """Analytics event types."""
    # Registration events
    REGISTRATION_STARTED = "registration_started"
    REGISTRATION_STEP_COMPLETED = "registration_step_completed"
    REGISTRATION_COMPLETED = "registration_completed"
    REGISTRATION_ABANDONED = "registration_abandoned"
    
    # Support events
    SUPPORT_TICKET_CREATED = "support_ticket_created"
    SUPPORT_TICKET_VIEWED = "support_ticket_viewed"
    SUPPORT_FAQ_VIEWED = "support_faq_viewed"
    
    # Navigation events
    MENU_OPENED = "menu_opened"
    BUTTON_CLICKED = "button_clicked"
    COMMAND_USED = "command_used"
    
    # Engagement events
    USER_ACTIVE = "user_active"
    USER_RETURNED = "user_returned"
    BROADCAST_RECEIVED = "broadcast_received"
    
    # Error events
    ERROR_OCCURRED = "error_occurred"
    VALIDATION_FAILED = "validation_failed"


class AnalyticsService:
    """Service for tracking and analyzing user events."""
    
    @staticmethod
    async def track_event(
        event_type: AnalyticsEvent,
        user_id: Optional[int] = None,
        properties: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Track an analytics event.
        
        Args:
            event_type: Type of event
            user_id: Optional Telegram user ID
            properties: Optional event properties
            
        Returns:
            True if tracked successfully
        """
        try:
            pool = get_db_pool()
            
            # Serialize properties
            import json
            properties_json = json.dumps(properties or {}, ensure_ascii=False)
            
            async with pool.connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO analytics_events 
                    (event_type, user_id, properties, timestamp)
                    VALUES (?, ?, ?, datetime('now'))
                    """,
                    (event_type.value, user_id, properties_json)
                )
                await conn.commit()
            
            logger.debug(
                f"Tracked event: {event_type.value}",
                extra={"event": event_type.value, "user_id": user_id}
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to track event {event_type.value}: {e}",
                exc_info=True,
                extra={"event": event_type.value, "user_id": user_id}
            )
            return False
    
    @staticmethod
    async def track_registration_step(
        user_id: int,
        step: str,
        success: bool,
        error: Optional[str] = None
    ) -> bool:
        """Track registration step completion.
        
        Args:
            user_id: Telegram user ID
            step: Step name (name, phone, card, photo)
            success: Whether step was successful
            error: Optional error message
            
        Returns:
            True if tracked successfully
        """
        properties = {
            "step": step,
            "success": success,
        }
        
        if error:
            properties["error"] = error
        
        return await AnalyticsService.track_event(
            AnalyticsEvent.REGISTRATION_STEP_COMPLETED,
            user_id=user_id,
            properties=properties
        )
    
    @staticmethod
    async def track_button_click(
        user_id: int,
        button_text: str,
        context: Optional[str] = None
    ) -> bool:
        """Track button click event.
        
        Args:
            user_id: Telegram user ID
            button_text: Text of clicked button
            context: Optional context (menu, registration, support)
            
        Returns:
            True if tracked successfully
        """
        properties = {
            "button": button_text,
        }
        
        if context:
            properties["context"] = context
        
        return await AnalyticsService.track_event(
            AnalyticsEvent.BUTTON_CLICKED,
            user_id=user_id,
            properties=properties
        )
    
    @staticmethod
    async def track_error(
        error_type: str,
        error_message: str,
        user_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Track error occurrence.
        
        Args:
            error_type: Type of error
            error_message: Error message
            user_id: Optional Telegram user ID
            context: Optional additional context
            
        Returns:
            True if tracked successfully
        """
        properties = {
            "error_type": error_type,
            "error_message": error_message,
        }
        
        if context:
            properties.update(context)
        
        return await AnalyticsService.track_event(
            AnalyticsEvent.ERROR_OCCURRED,
            user_id=user_id,
            properties=properties
        )
    
    @staticmethod
    async def get_event_count(
        event_type: AnalyticsEvent,
        hours: int = 24
    ) -> int:
        """Get count of events in last N hours.
        
        Args:
            event_type: Type of event to count
            hours: Number of hours to look back
            
        Returns:
            Count of events
        """
        try:
            pool = get_db_pool()
            async with pool.connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM analytics_events
                    WHERE event_type = ?
                    AND timestamp >= datetime('now', '-' || ? || ' hours')
                    """,
                    (event_type.value, hours)
                )
                row = await cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"Failed to get event count: {e}", exc_info=True)
            return 0
    
    @staticmethod
    async def get_user_event_history(
        user_id: int,
        limit: int = 100
    ) -> list[tuple[str, str, str]]:
        """Get user's event history.
        
        Args:
            user_id: Telegram user ID
            limit: Maximum number of events to return
            
        Returns:
            List of (event_type, properties, timestamp) tuples
        """
        try:
            pool = get_db_pool()
            async with pool.connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT event_type, properties, timestamp
                    FROM analytics_events
                    WHERE user_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (user_id, limit)
                )
                return await cursor.fetchall()
        except Exception as e:
            logger.error(
                f"Failed to get user event history: {e}",
                exc_info=True,
                extra={"user_id": user_id}
            )
            return []


async def ensure_analytics_table() -> None:
    """Ensure analytics_events table exists."""
    try:
        pool = get_db_pool()
        async with pool.connection() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    user_id INTEGER,
                    properties TEXT,
                    timestamp TEXT NOT NULL
                )
                """
            )
            # Create index for better query performance
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analytics_events_user_id 
                ON analytics_events(user_id)
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analytics_events_type_timestamp 
                ON analytics_events(event_type, timestamp)
                """
            )
            await conn.commit()
        logger.info("Analytics events table ensured")
    except Exception as e:
        logger.error(f"Failed to create analytics_events table: {e}", exc_info=True)

