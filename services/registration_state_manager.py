"""Service for managing registration state with auto-save."""

from __future__ import annotations

import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from core import get_logger
from database.connection import get_db_pool

logger = get_logger(__name__)


class RegistrationStateManager:
    """Manager for registration state persistence."""
    
    # Auto-save timeout in minutes
    STATE_TIMEOUT = 30
    
    @staticmethod
    async def save_state(
        user_id: int,
        state_data: Dict[str, Any]
    ) -> bool:
        """Save registration state for user.
        
        Args:
            user_id: Telegram user ID
            state_data: State data to save
            
        Returns:
            True if saved successfully
        """
        try:
            pool = get_db_pool()
            async with pool.connection() as conn:
                # Serialize state data
                state_json = json.dumps(state_data, ensure_ascii=False)
                
                await conn.execute(
                    """
                    INSERT INTO registration_states (user_id, state_data, updated_at)
                    VALUES (?, ?, datetime('now'))
                    ON CONFLICT(user_id) DO UPDATE SET
                        state_data=excluded.state_data,
                        updated_at=datetime('now')
                    """,
                    (user_id, state_json)
                )
                await conn.commit()
            
            logger.info(
                f"Saved registration state for user {user_id}",
                extra={"user_id": user_id}
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to save registration state for user {user_id}: {e}",
                exc_info=True,
                extra={"user_id": user_id}
            )
            return False
    
    @staticmethod
    async def load_state(user_id: int) -> Optional[Dict[str, Any]]:
        """Load registration state for user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            State data or None if not found or expired
        """
        try:
            pool = get_db_pool()
            async with pool.connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT state_data, updated_at
                    FROM registration_states
                    WHERE user_id = ?
                    """,
                    (user_id,)
                )
                row = await cursor.fetchone()
            
            if not row:
                return None
            
            state_json, updated_at = row
            
            # Check if state is expired
            if updated_at:
                try:
                    updated_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    if datetime.now() - updated_time > timedelta(minutes=RegistrationStateManager.STATE_TIMEOUT):
                        logger.info(
                            f"Registration state expired for user {user_id}",
                            extra={"user_id": user_id}
                        )
                        await RegistrationStateManager.clear_state(user_id)
                        return None
                except ValueError:
                    pass  # Invalid datetime, proceed anyway
            
            # Deserialize state data
            state_data = json.loads(state_json)
            
            logger.info(
                f"Loaded registration state for user {user_id}",
                extra={"user_id": user_id}
            )
            return state_data
        except Exception as e:
            logger.error(
                f"Failed to load registration state for user {user_id}: {e}",
                exc_info=True,
                extra={"user_id": user_id}
            )
            return None
    
    @staticmethod
    async def clear_state(user_id: int) -> bool:
        """Clear registration state for user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if cleared successfully
        """
        try:
            pool = get_db_pool()
            async with pool.connection() as conn:
                await conn.execute(
                    "DELETE FROM registration_states WHERE user_id = ?",
                    (user_id,)
                )
                await conn.commit()
            
            logger.info(
                f"Cleared registration state for user {user_id}",
                extra={"user_id": user_id}
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to clear registration state for user {user_id}: {e}",
                exc_info=True,
                extra={"user_id": user_id}
            )
            return False
    
    @staticmethod
    async def has_saved_state(user_id: int) -> bool:
        """Check if user has saved registration state.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if state exists and not expired
        """
        state = await RegistrationStateManager.load_state(user_id)
        return state is not None
    
    @staticmethod
    async def create_confirmation_message(state_data: Dict[str, Any]) -> str:
        """Create confirmation message from state data.
        
        Args:
            state_data: Registration state data
            
        Returns:
            Formatted confirmation message
        """
        message = "📋 **Проверьте ваши данные:**\n\n"
        
        if "full_name" in state_data:
            message += f"👤 **Имя:** {state_data['full_name']}\n"
        
        if "phone_number" in state_data:
            message += f"📱 **Телефон:** {state_data['phone_number']}\n"
        
        if "loyalty_card" in state_data:
            message += f"💳 **Карта лояльности:** {state_data['loyalty_card']}\n"
        
        if "photo_path" in state_data:
            message += f"📸 **Фото:** загружено\n"
        
        message += (
            "\n✅ Все верно?\n"
            "• Нажмите **Подтвердить** для отправки\n"
            "• Нажмите **Редактировать**, чтобы исправить данные\n"
            "• Нажмите **Отмена**, чтобы начать заново"
        )
        
        return message


async def ensure_registration_table() -> None:
    """Ensure registration_states table exists."""
    try:
        pool = get_db_pool()
        async with pool.connection() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS registration_states (
                    user_id INTEGER PRIMARY KEY,
                    state_data TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await conn.commit()
        logger.info("Registration states table ensured")
    except Exception as e:
        logger.error(f"Failed to create registration_states table: {e}", exc_info=True)

