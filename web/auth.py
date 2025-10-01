"""Authentication utilities for Flask admin panel.

This module implements a simple username/password authentication system
for the admin panel. It does NOT require users to participate in any lottery
or have any Telegram account to access the admin interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from flask_login import LoginManager, UserMixin
from werkzeug.security import check_password_hash, generate_password_hash


@dataclass
class AdminCredentials:
    """Admin credentials for accessing the admin panel.
    
    Note: These credentials are completely independent from any participant
    data or Telegram accounts. Admin access is granted solely based on
    these username/password credentials.
    """
    username: str
    password_hash: str


login_manager = LoginManager()


class AdminUser(UserMixin):
    """Represents an authenticated admin user."""
    def __init__(self, username: str) -> None:
        self.id = username
        self.username = username


def init_login_manager(app, credentials: AdminCredentials) -> AdminCredentials:
    """Initialize the Flask-Login manager with admin credentials.
    
    Args:
        app: Flask application instance
        credentials: Admin credentials containing username and password hash
        
    Returns:
        Updated credentials with properly hashed password
    """
    import logging
    logger = logging.getLogger(__name__)
    # Avoid logging sensitive secrets in production
    logger.info(
        "Initializing login manager with credentials: username='%s', password_hash='<hidden>'",
        credentials.username,
    )
    
    login_manager.init_app(app)
    login_manager.login_view = "admin.login_page"

    @login_manager.user_loader
    def load_user(user_id: str) -> Optional[AdminUser]:
        """Load user by ID for Flask-Login.
        
        This function only checks if the user_id matches the configured admin username.
        No database lookup or participant verification is performed.
        """
        if user_id == credentials.username:
            return AdminUser(username=user_id)
        return None

    # Check if password needs to be hashed (only if it's not already hashed)
    if not credentials.password_hash.startswith("pbkdf2:") and not credentials.password_hash.startswith("scrypt:"):
        logger.info("Password not hashed, hashing password")
        credentials.password_hash = generate_password_hash(credentials.password_hash)
        logger.info("Password hashed for admin user '%s'", credentials.username)
    else:
        logger.info("Password already hashed for admin user '%s'", credentials.username)
    
    app.config["ADMIN_CREDENTIALS"] = credentials
    logger.info("Stored admin credentials for username '%s' in app config", credentials.username)
    
    return credentials


def validate_credentials(credentials: AdminCredentials, username: str, password: str) -> bool:
    """Validate admin credentials.
    
    This function performs a simple username/password check against the
    configured admin credentials. No participant data or Telegram verification
    is required or performed.
    
    Args:
        credentials: Admin credentials to validate against
        username: Username provided by user
        password: Password provided by user
        
    Returns:
        True if credentials are valid, False otherwise
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Validating credentials: username='%s'", username)
    
    if username.lower() != credentials.username.lower():
        logger.info("Username mismatch")
        return False
    
    result = check_password_hash(credentials.password_hash, password)
    logger.info("Password check result: %s", result)
    return result