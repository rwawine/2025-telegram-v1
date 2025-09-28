"""Input validation helpers."""

import re


PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")
LOYALTY_RE = re.compile(r"^[A-Z0-9]{6,20}$")


def validate_full_name(value: str) -> bool:
    if not value:
        return False
    stripped = value.strip()
    if not (2 <= len(stripped) <= 100):
        return False
    for char in stripped:
        if char.isalpha() or char in {" ", "-", "'"}:
            continue
        return False
    return True


def validate_phone(value: str) -> bool:
    return bool(value and PHONE_RE.match(value))


def validate_loyalty_card(value: str) -> bool:
    return bool(value and LOYALTY_RE.match(value))

