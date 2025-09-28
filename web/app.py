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
    # Expose helper to Jinja: check if endpoint exists
    def has_endpoint(name: str) -> bool:
        return name in app.view_functions

    app.jinja_env.globals['has_endpoint'] = has_endpoint

    # Global stats injector for sidebar/header counters
    @app.context_processor
    def inject_global_stats():
        try:
            from database.admin_queries import AdminDatabase
            db = AdminDatabase(db_path=app.config["DATABASE_PATH"])
            stats = db.get_statistics()
            return {"global_stats": stats}
        except Exception:
            return {"global_stats": {}}
    return app