"""Валидация callback_data для соблюдения лимитов Telegram API."""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

MAX_CALLBACK_DATA_LENGTH = 64  # Telegram API limit


def validate_callback_data(callback_data: str) -> str:
    """
    Валидирует и обрезает callback_data до лимита Telegram.
    
    Args:
        callback_data: Строка для проверки
        
    Returns:
        Валидная строка callback_data
        
    Raises:
        ValueError: Если callback_data пустая или None
    """
    if not callback_data:
        raise ValueError("callback_data не может быть пустой")
    
    # Encode to bytes to check actual size (UTF-8)
    encoded = callback_data.encode('utf-8')
    
    if len(encoded) <= MAX_CALLBACK_DATA_LENGTH:
        return callback_data
    
    # Truncate to fit within limit
    truncated = encoded[:MAX_CALLBACK_DATA_LENGTH]
    
    # Ensure we don't break UTF-8 characters
    try:
        result = truncated.decode('utf-8')
        logger.warning(f"Callback data truncated: '{callback_data}' -> '{result}'")
        return result
    except UnicodeDecodeError:
        # Remove incomplete character at the end
        for i in range(1, 4):  # UTF-8 char can be max 4 bytes
            try:
                result = truncated[:-i].decode('utf-8')
                logger.warning(f"Callback data truncated (with fix): '{callback_data}' -> '{result}'")
                return result
            except UnicodeDecodeError:
                continue
        
        # Fallback - shouldn't happen with proper UTF-8
        raise ValueError(f"Не удалось обрезать callback_data: {callback_data}")


def create_safe_callback(action: str, data: str = "", separator: ":") -> str:
    """
    Создает безопасную callback_data строку.
    
    Args:
        action: Основное действие (например, "edit", "view")
        data: Дополнительные данные (например, ID)
        separator: Разделитель между частями
        
    Returns:
        Валидная callback_data строка
    """
    if not action:
        raise ValueError("action не может быть пустым")
    
    if data:
        callback_data = f"{action}{separator}{data}"
    else:
        callback_data = action
    
    return validate_callback_data(callback_data)


class CallbackRegistry:
    """Реестр для отслеживания всех callback_data в приложении."""
    
    def __init__(self):
        self._callbacks: Dict[str, str] = {}
        self._handlers: Dict[str, str] = {}
    
    def register_callback(self, callback_data: str, handler_name: str, description: str = ""):
        """Регистрирует callback_data с описанием."""
        validated = validate_callback_data(callback_data)
        self._callbacks[validated] = description
        self._handlers[validated] = handler_name
        logger.debug(f"Registered callback: {validated} -> {handler_name}")
    
    def get_unhandled_callbacks(self) -> List[str]:
        """Возвращает список callback_data без обработчиков."""
        # Это можно использовать в тестах для проверки покрытия
        return [cb for cb in self._callbacks.keys() if cb not in self._handlers]
    
    def validate_all(self) -> Dict[str, List[str]]:
        """Валидирует все зарегистрированные callbacks."""
        issues = {
            "long_callbacks": [],
            "unhandled_callbacks": [],
            "duplicate_callbacks": []
        }
        
        # Check for long callbacks
        for callback_data in self._callbacks.keys():
            if len(callback_data.encode('utf-8')) > MAX_CALLBACK_DATA_LENGTH:
                issues["long_callbacks"].append(callback_data)
        
        # Check for unhandled
        issues["unhandled_callbacks"] = self.get_unhandled_callbacks()
        
        return issues


# Global registry instance
callback_registry = CallbackRegistry()


def safe_inline_button(text: str, callback_data: str) -> Dict[str, str]:
    """
    Создает безопасную inline кнопку с валидацией.
    
    Returns:
        Dict для передачи в InlineKeyboardButton
    """
    validated_data = validate_callback_data(callback_data)
    callback_registry.register_callback(validated_data, "unknown", f"Button: {text}")
    
    return {
        "text": text,
        "callback_data": validated_data
    }
