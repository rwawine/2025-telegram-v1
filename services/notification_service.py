"""Service for sending notifications to users."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING
from datetime import datetime

from core import get_logger
from core.constants import TelegramLimits

if TYPE_CHECKING:
    from aiogram import Bot

logger = get_logger(__name__)


class NotificationService:
    """Service for managing user notifications."""
    
    def __init__(self, bot: Bot):
        """Initialize notification service.
        
        Args:
            bot: Telegram bot instance
        """
        self.bot = bot
    
    async def notify_ticket_status_change(
        self,
        user_id: int,
        ticket_id: int,
        old_status: str,
        new_status: str,
        admin_comment: Optional[str] = None
    ) -> bool:
        """Notify user about ticket status change.
        
        Args:
            user_id: Telegram user ID
            ticket_id: Support ticket ID
            old_status: Previous status
            new_status: New status
            admin_comment: Optional comment from admin
            
        Returns:
            True if notification sent successfully
        """
        status_emoji = {
            "open": "🟡",
            "in_progress": "🔵",
            "closed": "🟢",
        }
        
        status_text = {
            "open": "Открыто",
            "in_progress": "В работе",
            "closed": "Закрыто",
        }
        
        emoji = status_emoji.get(new_status, "⚪")
        status = status_text.get(new_status, new_status)
        
        message = (
            f"🔔 **Обновление по обращению #{ticket_id}**\n\n"
            f"{emoji} Статус изменен: **{status}**\n"
        )
        
        if admin_comment:
            message += f"\n💬 Комментарий администратора:\n{admin_comment}\n"
        
        message += (
            f"\n📝 Посмотреть детали: /support → Мои обращения"
        )
        
        try:
            await self.bot.send_message(
                user_id,
                message,
                parse_mode="Markdown"
            )
            logger.info(
                f"Notification sent to user {user_id} for ticket {ticket_id}",
                extra={"user_id": user_id, "ticket_id": ticket_id}
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to send notification to user {user_id}: {e}",
                exc_info=True,
                extra={"user_id": user_id, "ticket_id": ticket_id}
            )
            return False
    
    async def notify_ticket_reply(
        self,
        user_id: int,
        ticket_id: int,
        reply_text: str,
        sender_name: str = "Администратор"
    ) -> bool:
        """Notify user about new reply to their ticket.
        
        Args:
            user_id: Telegram user ID
            ticket_id: Support ticket ID
            reply_text: Reply text
            sender_name: Name of sender
            
        Returns:
            True if notification sent successfully
        """
        # Truncate long replies
        if len(reply_text) > TelegramLimits.MESSAGE_LENGTH - 200:
            reply_text = reply_text[:TelegramLimits.MESSAGE_LENGTH - 230] + "..."
        
        message = (
            f"💬 **Новый ответ на обращение #{ticket_id}**\n\n"
            f"👨‍💼 От: {sender_name}\n"
            f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Сообщение:\n{reply_text}\n\n"
            f"📝 Посмотреть полную переписку: /support → Мои обращения"
        )
        
        try:
            await self.bot.send_message(
                user_id,
                message,
                parse_mode="Markdown"
            )
            logger.info(
                f"Reply notification sent to user {user_id} for ticket {ticket_id}",
                extra={"user_id": user_id, "ticket_id": ticket_id}
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to send reply notification to user {user_id}: {e}",
                exc_info=True,
                extra={"user_id": user_id, "ticket_id": ticket_id}
            )
            return False
    
    async def notify_registration_status(
        self,
        user_id: int,
        status: str,
        reason: Optional[str] = None
    ) -> bool:
        """Notify user about registration status change.
        
        Args:
            user_id: Telegram user ID
            status: New status (approved, rejected, pending)
            reason: Optional reason for rejection
            
        Returns:
            True if notification sent successfully
        """
        if status == "approved":
            message = (
                "🎉 **Поздравляем!**\n\n"
                "✅ Ваша заявка на участие в розыгрыше **одобрена**!\n\n"
                "🎲 Вы участвуете в розыгрыше призов\n"
                "🔔 Мы сообщим вам о результатах\n\n"
                "💡 Следите за обновлениями!"
            )
        elif status == "rejected":
            message = (
                "❌ **Заявка отклонена**\n\n"
                "К сожалению, ваша заявка не была одобрена.\n"
            )
            if reason:
                message += f"\n📝 Причина: {reason}\n"
            message += (
                "\n💡 Вы можете:\n"
                "• Подать заявку снова с корректными данными\n"
                "• Обратиться в техподдержку для разъяснений\n"
            )
        else:
            message = (
                "⏳ **Статус заявки обновлен**\n\n"
                f"Текущий статус: {status}\n\n"
                "🔔 Мы уведомим вас о дальнейших изменениях"
            )
        
        try:
            await self.bot.send_message(
                user_id,
                message,
                parse_mode="Markdown"
            )
            logger.info(
                f"Registration status notification sent to user {user_id}: {status}",
                extra={"user_id": user_id, "status": status}
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to send registration notification to user {user_id}: {e}",
                exc_info=True,
                extra={"user_id": user_id, "status": status}
            )
            return False
    
    async def notify_lottery_winner(
        self,
        user_id: int,
        prize_description: str
    ) -> bool:
        """Notify user that they won the lottery.
        
        Args:
            user_id: Telegram user ID
            prize_description: Description of prize
            
        Returns:
            True if notification sent successfully
        """
        message = (
            "🎊 **ПОЗДРАВЛЯЕМ! ВЫ ПОБЕДИТЕЛЬ!** 🎊\n\n"
            f"🏆 Вы выиграли: {prize_description}\n\n"
            "📞 С вами свяжутся администраторы для уточнения деталей получения приза\n\n"
            "🎉 Спасибо за участие!"
        )
        
        try:
            await self.bot.send_message(
                user_id,
                message,
                parse_mode="Markdown"
            )
            logger.info(
                f"Winner notification sent to user {user_id}",
                extra={"user_id": user_id}
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to send winner notification to user {user_id}: {e}",
                exc_info=True,
                extra={"user_id": user_id}
            )
            return False


# Singleton instance
_notification_service: Optional[NotificationService] = None


def init_notification_service(bot: Bot) -> NotificationService:
    """Initialize global notification service.
    
    Args:
        bot: Telegram bot instance
        
    Returns:
        Initialized notification service
    """
    global _notification_service
    _notification_service = NotificationService(bot)
    return _notification_service


def get_notification_service() -> NotificationService:
    """Get global notification service.
    
    Returns:
        Global notification service
        
    Raises:
        RuntimeError: If service is not initialized
    """
    if _notification_service is None:
        raise RuntimeError("Notification service is not initialized")
    return _notification_service

