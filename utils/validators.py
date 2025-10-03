"""Input validation helpers."""

import re


PHONE_RE = re.compile(r"^(\+7|7|8)?[0-9]{10}$")
LOYALTY_RE = re.compile(r"^[A-Z0-9]{6,20}$")


def validate_full_name(value: str) -> bool:
    if not value:
        return False
    stripped = value.strip()
    if not (2 <= len(stripped) <= 100):
        return False
    
    # Проверяем, что используются только латиница, кириллица и разрешенные символы
    allowed_ranges = [
        (0x0041, 0x005A),  # A-Z
        (0x0061, 0x007A),  # a-z
        (0x0410, 0x044F),  # А-Я, а-я (кириллица)
        (0x0401, 0x0401),  # Ё
        (0x0451, 0x0451),  # ё
        (0x00C0, 0x00FF),  # Расширенная латиница (àáâ и т.д.)
    ]
    
    for char in stripped:
        if char in {" ", "-", "'"}:
            continue
        
        # Проверяем, входит ли символ в разрешенные диапазоны
        char_code = ord(char)
        is_allowed = any(start <= char_code <= end for start, end in allowed_ranges)
        
        if not is_allowed:
            return False
    
    return True


def validate_phone(value: str) -> bool:
    """Validate phone numbers - accepts any international format"""
    if not value:
        return False
    
    # Очищаем номер от пробелов, дефисов и скобок
    clean_phone = re.sub(r'[\s\-\(\)]', '', value)
    
    # Принимаем любые номера от 7 до 15 цифр (международный стандарт E.164)
    # Может начинаться с + или без него
    if re.match(r'^\+?[0-9]{7,15}$', clean_phone):
        return True
    
    return False


def normalize_phone(value: str) -> str:
    """Normalize phone number to international format"""
    if not value:
        return value
    
    # Очищаем номер от пробелов, дефисов и скобок
    clean_phone = re.sub(r'[\s\-\(\)]', '', value)
    
    # Если номер уже начинается с +, оставляем как есть
    if clean_phone.startswith('+'):
        return clean_phone
    
    # Если российский номер начинается с 8, заменяем на +7
    if clean_phone.startswith('8') and len(clean_phone) == 11:
        return '+7' + clean_phone[1:]
    
    # Если номер начинается с 7 и имеет 11 цифр, добавляем +
    if clean_phone.startswith('7') and len(clean_phone) == 11:
        return '+' + clean_phone
    
    # Для остальных номеров добавляем + если его нет
    if not clean_phone.startswith('+') and len(clean_phone) >= 7:
        return '+' + clean_phone
    
    return clean_phone


def validate_loyalty_card(value: str) -> bool:
    return bool(value and LOYALTY_RE.match(value))

