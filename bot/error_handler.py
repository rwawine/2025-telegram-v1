"""Centralized error handling for bot handlers."""

from __future__ import annotations

from functools import wraps
from typing import Callable, Any

from aiogram import types
from aiogram.fsm.context import FSMContext

from core import get_logger

logger = get_logger(__name__)


def handle_bot_errors(
    error_message: str = "Произошла ошибка",
    log_context: bool = True
):
    """Decorator для обработки ошибок в хендлерах бота.
    
    Args:
        error_message: Сообщение для пользователя при ошибке
        log_context: Логировать ли контекст ошибки
        
    Usage:
        @handle_bot_errors("Не удалось обработать имя")
        async def enter_name(self, message, state):
            # ... логика
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, message_or_callback: Any, *args, **kwargs):
            try:
                return await func(self, message_or_callback, *args, **kwargs)
            except Exception as e:
                # Определяем тип события
                if isinstance(message_or_callback, types.Message):
                    event = message_or_callback
                    user_id = event.from_user.id
                    chat_id = event.chat.id
                elif isinstance(message_or_callback, types.CallbackQuery):
                    event = message_or_callback.message
                    user_id = message_or_callback.from_user.id
                    chat_id = message_or_callback.message.chat.id
                else:
                    event = None
                    user_id = None
                    chat_id = None
                
                # Логируем ошибку с контекстом
                log_extra = {}
                if log_context:
                    log_extra = {
                        "handler": func.__name__,
                        "user_id": user_id,
                        "chat_id": chat_id,
                    }
                
                logger.error(
                    f"Error in {func.__name__}: {e}",
                    exc_info=True,
                    extra=log_extra
                )
                
                # Отправляем сообщение пользователю
                if event:
                    try:
                        await event.answer(
                            f"❌ {error_message}\n\n"
                            "🔄 Попробуйте еще раз или обратитесь в поддержку.\n\n"
                            "💡 Используйте /start для возврата в главное меню.",
                            parse_mode="Markdown"
                        )
                    except Exception as send_error:
                        logger.error(f"Failed to send error message: {send_error}")
                
        return wrapper
    return decorator


async def handle_validation_error(
    message: types.Message,
    field_name: str,
    expected_format: str,
    example: str,
    keyboard: Any = None
):
    """Отправить стандартное сообщение об ошибке валидации.
    
    Args:
        message: Telegram message
        field_name: Название поля (имя, телефон, карта)
        expected_format: Ожидаемый формат
        example: Пример правильного формата
        keyboard: Клавиатура для повтора
    """
    await message.answer(
        f"❌ **Неверный формат: {field_name}**\n\n"
        f"📐 Ожидается: {expected_format}\n"
        f"✅ Пример: {example}\n\n"
        f"💡 Попробуйте еще раз",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def handle_rate_limit_error(message: types.Message):
    """Обработать ошибку превышения rate limit."""
    await message.answer(
        "⏱️ **Слишком много запросов**\n\n"
        "Пожалуйста, подождите несколько секунд и попробуйте снова.\n\n"
        "💡 Мы защищаем систему от перегрузки.",
        parse_mode="Markdown"
    )


async def handle_database_error(message: types.Message):
    """Обработать ошибку базы данных."""
    await message.answer(
        "💾 **Временные проблемы с базой данных**\n\n"
        "Мы уже работаем над устранением проблемы.\n"
        "Попробуйте через несколько минут.\n\n"
        "💡 Ваши данные в безопасности.",
        parse_mode="Markdown"
    )


class ErrorContext:
    """Контекст для сбора информации об ошибках."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def add_error(self, error: str, context: dict = None):
        """Добавить ошибку."""
        self.errors.append({
            "message": error,
            "context": context or {}
        })
    
    def add_warning(self, warning: str, context: dict = None):
        """Добавить предупреждение."""
        self.warnings.append({
            "message": warning,
            "context": context or {}
        })
    
    def has_errors(self) -> bool:
        """Проверить наличие ошибок."""
        return len(self.errors) > 0
    
    def clear(self):
        """Очистить контекст."""
        self.errors.clear()
        self.warnings.clear()

