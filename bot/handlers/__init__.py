"""Aggregate bot handlers for dispatch registration."""

from .registration import RegistrationHandler, setup_registration_handlers
from .support import setup_support_handlers
from .common import setup_common_handlers
from .fallback import setup_fallback_handlers

__all__ = [
    "RegistrationHandler", 
    "setup_registration_handlers",
    "setup_support_handlers",
    "setup_common_handlers",
    "setup_fallback_handlers",
]

