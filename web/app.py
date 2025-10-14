"""Flask application factory with caching and security defaults."""

from __future__ import annotations

from flask import Flask, render_template, redirect, url_for
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from web.auth import AdminCredentials, init_login_manager
from web.config_middleware import (
    configure_app,
    setup_extensions,
    setup_security_headers,
    setup_metrics,
    REQUEST_ERRORS,
)
from web.routes import register_routes


def create_app(config, testing=False) -> Flask:
    """Create and configure Flask application.
    
    Args:
        config: Application configuration
        testing: Whether running in testing mode
        
    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    
    # Configure application
    configure_app(app, config, testing)
    
    # Setup extensions
    setup_extensions(app, testing)
    
    # Setup middleware
    setup_security_headers(app)
    setup_metrics(app)
    
    # Initialize authentication
    credentials = AdminCredentials(
        username=config.admin_username,
        password_hash=config.admin_password
    )
    credentials = init_login_manager(app, credentials)
    
    # Register routes
    register_routes(app)
    
    # Setup additional handlers
    _setup_routes(app)
    _setup_context_processors(app)
    _setup_error_handlers(app)
    
    return app


def _setup_routes(app: Flask) -> None:
    """Setup basic application routes.
    
    Args:
        app: Flask application instance
    """
    @app.route('/')
    def root():
        """Root route redirects to admin panel."""
        return redirect(url_for('admin.login_page'))
    
    @app.route('/metrics')
    def metrics():
        """Expose Prometheus metrics."""
        data = generate_latest()
        return data, 200, {'Content-Type': CONTENT_TYPE_LATEST}
    
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        """Serve uploaded files (photos, etc)."""
        from flask import send_from_directory
        import os
        uploads_dir = os.path.join(app.root_path, '..', 'uploads')
        return send_from_directory(uploads_dir, filename)
    
    # Expose helper to Jinja: check if endpoint exists
    def has_endpoint(name: str) -> bool:
        return name in app.view_functions
    
    app.jinja_env.globals['has_endpoint'] = has_endpoint
    
    # Add Moscow timezone filter for datetime conversion
    def moscow_time(dt_string: str) -> str:
        """Convert UTC datetime string to Moscow time (UTC+3)."""
        if not dt_string:
            return ''
        try:
            from datetime import datetime, timedelta
            # Try different datetime formats
            formats = [
                '%Y-%m-%d %H:%M:%S',  # Standard format
                '%Y-%m-%d %H:%M:%S.%f',  # With microseconds
                '%Y-%m-%dT%H:%M:%S',  # ISO format without Z
                '%Y-%m-%dT%H:%M:%S.%f',  # ISO with microseconds
                '%Y-%m-%dT%H:%M:%SZ',  # ISO with Z
            ]
            dt = None
            for fmt in formats:
                try:
                    dt = datetime.strptime(dt_string, fmt)
                    break
                except ValueError:
                    continue
            
            if dt is None:
                return dt_string
            
            # Add 3 hours for Moscow timezone (UTC+3)
            moscow_dt = dt + timedelta(hours=3)
            return moscow_dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            app.logger.warning(f"Failed to convert time to Moscow: {e}")
            return dt_string
    
    app.jinja_env.filters['moscow_time'] = moscow_time


def _setup_context_processors(app: Flask) -> None:
    """Setup Jinja context processors.
    
    Args:
        app: Flask application instance
    """
    @app.context_processor
    def inject_global_stats():
        """Inject global statistics into templates."""
        try:
            from database.admin_queries import AdminDatabase
            db_path = app.config.get("DATABASE_PATH", "data/lottery_bot.sqlite")
            db = AdminDatabase(db_path=db_path)
            stats = db.get_statistics()
            return {"global_stats": stats}
        except Exception as e:
            app.logger.warning(f"Failed to inject global stats: {e}")
            return {
                "global_stats": {
                    "total_participants": 0,
                    "total_winners": 0,
                    "open_tickets": 0,
                    "approved_participants": 0,
                    "pending_participants": 0,
                    "rejected_participants": 0
                }
            }


def _setup_error_handlers(app: Flask) -> None:
    """Setup error handlers.
    
    Args:
        app: Flask application instance
    """
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        try:
            from flask import request
            path = getattr(request.url_rule, 'rule', '500')
            REQUEST_ERRORS.labels(method=request.method, path=path).inc()
        except Exception:
            pass
        app.logger.error(f"Internal server error: {error}")
        return render_template('500.html'), 500