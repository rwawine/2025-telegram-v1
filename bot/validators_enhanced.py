"""Enhanced validators for bot input with detailed error messages."""

from __future__ import annotations

import re
from typing import Tuple, Optional

from core import get_logger

logger = get_logger(__name__)


class ValidationResult:
    """Result of validation with error details."""
    
    def __init__(self, is_valid: bool, error_message: str = None, suggestion: str = None):
        self.is_valid = is_valid
        self.error_message = error_message
        self.suggestion = suggestion
    
    def __bool__(self):
        return self.is_valid


def validate_name_enhanced(name: str) -> ValidationResult:
    """Enhanced name validation with detailed errors.
    
    Args:
        name: Full name to validate
        
    Returns:
        ValidationResult with details
    """
    if not name or not name.strip():
        return ValidationResult(
            False,
            "Имя не может быть пустым",
            "Введите ваше полное имя как в документе"
        )
    
    name = name.strip()
    
    # Check length
    if len(name) < 3:
        return ValidationResult(
            False,
            "Имя слишком короткое",
            "Введите полное имя (минимум 3 символа)"
        )
    
    if len(name) > 100:
        return ValidationResult(
            False,
            "Имя слишком длинное",
            "Введите имя без лишних деталей (до 100 символов)"
        )
    
    # Check for at least 2 words
    words = name.split()
    if len(words) < 2:
        return ValidationResult(
            False,
            "Введите полное имя (Фамилия Имя)",
            "Пример: Иванов Иван или Иванов Иван Иванович"
        )
    
    # Check for numbers
    if re.search(r'\d', name):
        return ValidationResult(
            False,
            "Имя не должно содержать цифры",
            "Введите имя только буквами"
        )
    
    # Check for special characters
    if re.search(r'[!@#$%^&*()+=\[\]{};:",<>?/\\|`~]', name):
        return ValidationResult(
            False,
            "Имя содержит недопустимые символы",
            "Используйте только буквы, пробелы и дефисы"
        )
    
    return ValidationResult(True)


def validate_phone_enhanced(phone: str) -> ValidationResult:
    """Enhanced phone validation with detailed errors.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        ValidationResult with details
    """
    if not phone or not phone.strip():
        return ValidationResult(
            False,
            "Номер телефона не может быть пустым",
            "Введите номер в формате +79001234567"
        )
    
    phone = phone.strip()
    
    # Remove common separators for validation
    digits_only = re.sub(r'[\s\-\(\)]+', '', phone)
    
    # Remove + if present
    if digits_only.startswith('+'):
        digits_only = digits_only[1:]
    
    # Check if only digits remain
    if not digits_only.isdigit():
        return ValidationResult(
            False,
            "Номер содержит недопустимые символы",
            "Используйте только цифры и знак + в начале"
        )
    
    # Check length
    if len(digits_only) < 7:
        return ValidationResult(
            False,
            "Номер телефона слишком короткий",
            "Минимум 7 цифр. Пример: +79001234567"
        )
    
    if len(digits_only) > 15:
        return ValidationResult(
            False,
            "Номер телефона слишком длинный",
            "Максимум 15 цифр. Проверьте правильность ввода"
        )
    
    return ValidationResult(True)


def validate_loyalty_card_enhanced(card: str) -> ValidationResult:
    """Enhanced loyalty card validation with detailed errors.
    
    Args:
        card: Loyalty card number to validate
        
    Returns:
        ValidationResult with details
    """
    if not card or not card.strip():
        return ValidationResult(
            False,
            "Номер карты не может быть пустым",
            "Введите номер карты лояльности"
        )
    
    card = card.strip()
    
    # Check length
    if len(card) < 6:
        return ValidationResult(
            False,
            "Номер карты слишком короткий",
            "Минимум 6 символов. Пример: ABC12345"
        )
    
    if len(card) > 20:
        return ValidationResult(
            False,
            "Номер карты слишком длинный",
            "Максимум 20 символов. Проверьте номер"
        )
    
    # Check format: only alphanumeric
    if not re.match(r'^[A-Za-z0-9]+$', card):
        return ValidationResult(
            False,
            "Номер карты содержит недопустимые символы",
            "Используйте только латинские буквы и цифры"
        )
    
    # Check if has at least one letter and one digit
    if not re.search(r'[A-Za-z]', card):
        return ValidationResult(
            False,
            "Номер карты должен содержать буквы",
            "Пример: ABC12345 или L98765"
        )
    
    if not re.search(r'\d', card):
        return ValidationResult(
            False,
            "Номер карты должен содержать цифры",
            "Пример: ABC12345 или L98765"
        )
    
    return ValidationResult(True)


def validate_file_size(file_size: int, max_size: int) -> ValidationResult:
    """Validate file size.
    
    Args:
        file_size: Size in bytes
        max_size: Maximum allowed size in bytes
        
    Returns:
        ValidationResult with details
    """
    if file_size > max_size:
        return ValidationResult(
            False,
            f"Файл слишком большой: {file_size // (1024*1024)} МБ",
            f"Максимальный размер: {max_size // (1024*1024)} МБ. Сожмите изображение"
        )
    
    return ValidationResult(True)


def suggest_correction(input_value: str, field_type: str) -> Optional[str]:
    """Suggest correction for common mistakes.
    
    Args:
        input_value: User input
        field_type: Type of field (name, phone, card)
        
    Returns:
        Suggestion string or None
    """
    if field_type == "phone":
        # Try to extract digits
        digits = re.sub(r'\D', '', input_value)
        if len(digits) >= 7:
            # Format as Russian number if starts with 7 or 8
            if digits.startswith('8') and len(digits) == 11:
                return f"+7{digits[1:]}"
            elif digits.startswith('7') and len(digits) == 11:
                return f"+{digits}"
            elif len(digits) == 10:
                return f"+7{digits}"
    
    elif field_type == "card":
        # Remove spaces and dashes
        cleaned = re.sub(r'[\s\-]', '', input_value)
        if re.match(r'^[A-Za-z0-9]{6,20}$', cleaned):
            return cleaned.upper()
    
    return None

