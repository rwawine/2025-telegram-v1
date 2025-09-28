"""Flask application factory with caching and security defaults."""

from __future__ import annotations

from flask import Flask, render_template
from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect

from web.auth import AdminCredentials, init_login_manager
from web.routes import register_routes
from web.csrf_helpers import init_csrf_helpers
from web.performance_middleware import init_performance_middleware


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
        # Fix CSRF issues with aiohttp-wsgi integration
        WTF_CSRF_TIME_LIMIT=None,
        WTF_CSRF_CHECK_DEFAULT=False,  # Disable CSRF for WSGI compatibility
    )
    cache.init_app(app, config={"CACHE_TYPE": "simple"})
    # Conditionally enable CSRF based on testing mode
    if not testing:
        csrf.init_app(app)
        
    # Initialize CSRF helpers
    init_csrf_helpers(app)
    
    # Initialize performance middleware
    init_performance_middleware(app)
    
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
            db_path = app.config.get("DATABASE_PATH", "data/lottery_bot.sqlite")
            db = AdminDatabase(db_path=db_path)
            stats = db.get_statistics()
            return {"global_stats": stats}
        except Exception as e:
            app.logger.warning(f"Failed to inject global stats: {e}")
            return {"global_stats": {
                "total_participants": 0,
                "total_winners": 0,
                "open_tickets": 0,
                "approved_participants": 0,
                "pending_participants": 0,
                "rejected_participants": 0
            }}
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal server error: {error}")
        return render_template('500.html'), 500
    
    return app