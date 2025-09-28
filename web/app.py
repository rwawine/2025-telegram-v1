"""Flask application factory with caching and security defaults."""

from __future__ import annotations

from flask import Flask
from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect

from web.auth import AdminCredentials, init_login_manager
from web.routes import register_routes


cache = Cache()
csrf = CSRFProtect()


def create_app(config, testing=False) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=config.secret_key,
        MAX_CONTENT_LENGTH=config.max_file_size,
        SEND_FILE_MAX_AGE_DEFAULT=3600,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=False,
        SESSION_COOKIE_SAMESITE='Lax',
        DATABASE_PATH=config.database_path,
        TESTING=testing,
    )
    cache.init_app(app, config={"CACHE_TYPE": "simple"})
    csrf.init_app(app)
    credentials = AdminCredentials(username=config.admin_username, password_hash=config.admin_password)
    # Update credentials with hashed password
    credentials = init_login_manager(app, credentials)
    register_routes(app)
    return app