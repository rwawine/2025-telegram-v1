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
    """Validate Russian phone numbers in formats: +79xxxxxxxxx, 79xxxxxxxxx, 89xxxxxxxxx"""
    if not value:
        return False
    
    # Очищаем номер от пробелов, дефисов и скобок
    clean_phone = re.sub(r'[\s\-\(\)]', '', value)
    
    # Проверяем российские форматы
    # +79xxxxxxxxx, 79xxxxxxxxx, 89xxxxxxxxx
    if re.match(r'^(\+7|7|8)[0-9]{10}$', clean_phone):
        # Дополнительная проверка: после кода страны должна быть 9
        if clean_phone.startswith('+7'):
            return clean_phone[2] == '9'
        elif clean_phone.startswith('7'):
            return clean_phone[1] == '9'
        elif clean_phone.startswith('8'):
            return clean_phone[1] == '9'
    
    return False


def normalize_phone(value: str) -> str:
    """Normalize Russian phone number to +79xxxxxxxxx format"""
    if not value:
        return value
    
    # Очищаем номер от пробелов, дефисов и скобок
    clean_phone = re.sub(r'[\s\-\(\)]', '', value)
    
    # Нормализуем к формату +79xxxxxxxxx
    if clean_phone.startswith('+7'):
        return clean_phone
    elif clean_phone.startswith('7') and len(clean_phone) == 11:
        return '+' + clean_phone
    elif clean_phone.startswith('8') and len(clean_phone) == 11:
        return '+7' + clean_phone[1:]
    
    return value  # возвращаем как есть, если не удалось нормализовать


def validate_loyalty_card(value: str) -> bool:
    return bool(value and LOYALTY_RE.match(value))

