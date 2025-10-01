"""Aggregate bot handlers for dispatch registration."""

from .registration import RegistrationHandler, setup_registration_handlers
from .support import setup_support_handlers
from .common import setup_common_handlers
from .global_commands import setup_global_commands
from .fallback_fixed import setup_fixed_fallback_handlers

__all__ = [
    "RegistrationHandler", 
    "setup_registration_handlers",
    "setup_support_handlers",
    "setup_common_handlers",
    "setup_global_commands",
    "setup_fixed_fallback_handlers",
]

