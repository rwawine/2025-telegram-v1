"""Personalization service for adaptive user experience."""

from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from core import get_logger
from database.connection import get_db_pool

logger = get_logger(__name__)


class PersonalizationService:
    """Service for personalizing user experience."""
    
    @staticmethod
    async def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
        """Get user profile data for personalization.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            User profile dictionary or None
        """
        try:
            pool = get_db_pool()
            async with pool.connection() as conn:
                # Get participant data
                cursor = await conn.execute(
                    """
                    SELECT full_name, username, created_at, status
                    FROM participants
                    WHERE telegram_id = ?
                    """,
                    (user_id,)
                )
                participant_row = await cursor.fetchone()
                
                if not participant_row:
                    return None
                
                full_name, username, created_at, status = participant_row
                
                # Get activity stats
                cursor = await conn.execute(
                    """
                    SELECT 
                        COUNT(*) as event_count,
                        MAX(timestamp) as last_active
                    FROM analytics_events
                    WHERE user_id = ?
                    """,
                    (user_id,)
                )
                activity_row = await cursor.fetchone()
                event_count, last_active = activity_row if activity_row else (0, None)
                
                # Get support tickets count
                cursor = await conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM support_tickets t
                    JOIN participants p ON p.id = t.participant_id
                    WHERE p.telegram_id = ?
                    """,
                    (user_id,)
                )
                tickets_row = await cursor.fetchone()
                tickets_count = tickets_row[0] if tickets_row else 0
                
                return {
                    "full_name": full_name,
                    "first_name": full_name.split()[0] if full_name else username or "Участник",
                    "username": username,
                    "created_at": created_at,
                    "status": status,
                    "event_count": event_count,
                    "last_active": last_active,
                    "tickets_count": tickets_count,
                }
        except Exception as e:
            logger.error(
                f"Failed to get user profile: {e}",
                exc_info=True,
                extra={"user_id": user_id}
            )
            return None
    
    @staticmethod
    async def get_personalized_greeting(user_id: int) -> str:
        """Get personalized greeting for user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Personalized greeting message
        """
        profile = await PersonalizationService.get_user_profile(user_id)
        
        if not profile:
            return "👋 Здравствуйте!"
        
        first_name = profile["first_name"]
        
        # Check if returning user
        if profile["last_active"]:
            try:
                last_active = datetime.fromisoformat(profile["last_active"].replace('Z', '+00:00'))
                if datetime.now() - last_active > timedelta(days=7):
                    return f"👋 Рады видеть вас снова, {first_name}!"
                elif datetime.now() - last_active > timedelta(days=1):
                    return f"👋 С возвращением, {first_name}!"
            except (ValueError, AttributeError):
                pass
        
        return f"👋 Здравствуйте, {first_name}!"
    
    @staticmethod
    async def get_personalized_status_message(
        user_id: int,
        status: str
    ) -> str:
        """Get personalized status message.
        
        Args:
            user_id: Telegram user ID
            status: User status
            
        Returns:
            Personalized status message
        """
        profile = await PersonalizationService.get_user_profile(user_id)
        first_name = profile["first_name"] if profile else "Участник"
        
        status_messages = {
            "approved": (
                f"🎉 {first_name}, поздравляем!\n\n"
                f"✅ Вы участвуете в розыгрыше призов\n"
                f"🎲 Следите за обновлениями\n"
                f"🍀 Желаем удачи!"
            ),
            "pending": (
                f"⏳ {first_name}, ваша заявка на рассмотрении\n\n"
                f"📝 Модераторы проверяют данные\n"
                f"⏱️ Обычно это занимает до 24 часов\n"
                f"🔔 Мы обязательно уведомим вас о результате"
            ),
            "rejected": (
                f"❌ {first_name}, к сожалению заявка отклонена\n\n"
                f"💡 Вы можете:\n"
                f"• Подать заявку снова с корректными данными\n"
                f"• Обратиться в техподдержку для уточнений"
            ),
        }
        
        return status_messages.get(
            status,
            f"{first_name}, ваш статус: {status}"
        )
    
    @staticmethod
    async def get_contextual_help(
        user_id: int,
        context: str
    ) -> str:
        """Get contextual help based on user history.
        
        Args:
            user_id: Telegram user ID
            context: Current context (registration, support, etc.)
            
        Returns:
            Contextual help message
        """
        profile = await PersonalizationService.get_user_profile(user_id)
        
        if not profile:
            return "💡 Нужна помощь? Используйте /help"
        
        first_name = profile["first_name"]
        
        # Registration context
        if context == "registration":
            if profile["event_count"] == 0:
                # First time user
                return (
                    f"📝 {first_name}, это ваша первая регистрация!\n\n"
                    f"💡 Подсказка: введите данные точно как в документах\n"
                    f"📞 Если возникнут вопросы, используйте /support"
                )
            else:
                # Returning user
                return (
                    f"🔄 {first_name}, рады видеть вас снова!\n\n"
                    f"💡 Заполните все поля для участия в розыгрыше"
                )
        
        # Support context
        elif context == "support":
            if profile["tickets_count"] == 0:
                return (
                    f"💬 {first_name}, мы рады помочь!\n\n"
                    f"💡 Опишите вашу проблему подробно\n"
                    f"📎 При необходимости приложите фото"
                )
            else:
                return (
                    f"💬 {first_name}, создаем новое обращение\n\n"
                    f"📋 У вас уже есть {profile['tickets_count']} обращений\n"
                    f"💡 Посмотреть их: /support → Мои обращения"
                )
        
        return f"💡 {first_name}, чем могу помочь?"
    
    @staticmethod
    async def get_adaptive_message(
        user_id: int,
        message_type: str,
        **kwargs
    ) -> str:
        """Get adaptive message based on user behavior.
        
        Args:
            user_id: Telegram user ID
            message_type: Type of message
            **kwargs: Additional parameters
            
        Returns:
            Adaptive message
        """
        profile = await PersonalizationService.get_user_profile(user_id)
        
        if not profile:
            # Default non-personalized messages
            default_messages = {
                "welcome": "👋 Добро пожаловать!",
                "error": "❌ Произошла ошибка",
                "success": "✅ Успешно!",
            }
            return default_messages.get(message_type, "")
        
        first_name = profile["first_name"]
        
        # Adaptive messages based on user activity
        if message_type == "welcome":
            if profile["event_count"] > 50:
                return f"👋 {first_name}, рады видеть постоянного участника!"
            elif profile["event_count"] > 10:
                return f"👋 Приветствуем, {first_name}!"
            else:
                return f"👋 Здравствуйте, {first_name}!"
        
        elif message_type == "error":
            if kwargs.get("retry_count", 0) > 2:
                return (
                    f"❌ {first_name}, похоже возникли трудности\n\n"
                    f"💡 Попробуйте:\n"
                    f"• Повторить позже\n"
                    f"• Обратиться в поддержку: /support"
                )
            else:
                return f"❌ {first_name}, что-то пошло не так. Попробуйте еще раз"
        
        elif message_type == "success":
            return f"✅ {first_name}, отлично! Все готово"
        
        return ""


# Singleton instance
_personalization_service: Optional[PersonalizationService] = None


def get_personalization_service() -> PersonalizationService:
    """Get personalization service instance.
    
    Returns:
        Personalization service instance
    """
    global _personalization_service
    if _personalization_service is None:
        _personalization_service = PersonalizationService()
    return _personalization_service

