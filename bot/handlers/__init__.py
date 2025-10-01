"""Aggregate bot handlers for dispatch registration."""

from .registration import RegistrationHandler, setup_registration_handlers
from .support import setup_support_handlers
from .common import setup_common_handlers
from .fallback import setup_fallback_handlers
from .global_commands import setup_global_commands  # NEW
from .fallback_fixed import setup_fixed_fallback_handlers  # FIXED VERSION

__all__ = [
    "RegistrationHandler", 
    "setup_registration_handlers",
    "setup_support_handlers",
    "setup_common_handlers",
    "setup_fallback_handlers",  # DEPRECATED - use setup_fixed_fallback_handlers
    "setup_global_commands",  # NEW
    "setup_fixed_fallback_handlers",  # FIXED VERSION
]

