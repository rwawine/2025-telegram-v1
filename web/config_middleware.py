"""Flask application configuration and middleware setup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Flask
from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect
from prometheus_client import Counter, Histogram

if TYPE_CHECKING:
    from config import Config

# Global instances
cache = Cache()
csrf = CSRFProtect()

# Prometheus metrics
REQUEST_LATENCY = Histogram(
    "http_request_latency_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
REQUEST_ERRORS = Counter(
    "http_request_errors_total",
    "Total number of 5xx responses",
    ["method", "path"],
)


def configure_app(app: Flask, config: Config, testing: bool = False) -> None:
    """Configure Flask application settings.
    
    Args:
        app: Flask application instance
        config: Application configuration
        testing: Whether running in testing mode
    """
    app.config.update(
        SECRET_KEY=config.secret_key,
        MAX_CONTENT_LENGTH=config.max_file_size,
        SEND_FILE_MAX_AGE_DEFAULT=3600,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=(config.environment != 'development'),
        SESSION_COOKIE_SAMESITE='Lax',
        DATABASE_PATH=config.database_path,
        TESTING=testing,
        WTF_CSRF_TIME_LIMIT=None,
        WTF_CSRF_CHECK_DEFAULT=False,
    )
    
    # Warn if insecure defaults detected
    if config.environment == 'production':
        if config.admin_username == "admin" and config.admin_password in {"123456", "secure_password_change_me"}:
            app.logger.warning("Insecure admin credentials detected in production")
        if not config.bot_token or config.bot_token == "your_bot_token_here":
            app.logger.warning("BOT_TOKEN is not set properly")


def setup_extensions(app: Flask, testing: bool = False) -> None:
    """Setup Flask extensions.
    
    Args:
        app: Flask application instance
        testing: Whether running in testing mode
    """
    # Initialize cache
    cache.init_app(app, config={"CACHE_TYPE": "simple"})
    
    # Initialize CSRF protection (disabled in testing)
    if not testing:
        csrf.init_app(app)
    
    # Initialize CSRF helpers
    from web.csrf_helpers import init_csrf_helpers
    init_csrf_helpers(app)
    
    # Initialize performance middleware
    from web.performance_middleware import init_performance_middleware
    init_performance_middleware(app)


def setup_security_headers(app: Flask) -> None:
    """Setup security headers middleware.
    
    Args:
        app: Flask application instance
    """
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""
        try:
            # Content Security Policy
            csp = (
                "default-src 'self'; "
                "img-src 'self' data: blob:; "
                "font-src 'self' https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com data:; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com"
            )
            if not response.headers.get('Content-Security-Policy'):
                response.headers['Content-Security-Policy'] = csp
            
            # Additional hardening headers
            response.headers.setdefault('X-Content-Type-Options', 'nosniff')
            response.headers.setdefault('X-Frame-Options', 'DENY')
            response.headers.setdefault('Referrer-Policy', 'same-origin')
            response.headers.setdefault('Permissions-Policy', "camera=(), microphone=(), geolocation=()")
        except Exception:
            pass
        return response


def setup_metrics(app: Flask) -> None:
    """Setup Prometheus metrics middleware.
    
    Args:
        app: Flask application instance
    """
    @app.before_request
    def before_metrics():
        """Store request start time."""
        from flask import g
        g._metrics_start = g.get('_metrics_start', None) or __import__('time').time()
    
    @app.after_request
    def after_metrics(response):
        """Record request metrics."""
        try:
            from flask import request, g
            start = getattr(g, '_metrics_start', None)
            if start is not None:
                duration = __import__('time').time() - start
                path = getattr(request.url_rule, 'rule', request.path)
                REQUEST_LATENCY.labels(method=request.method, path=path).observe(duration)
            
            # Record 5xx errors
            if response.status_code >= 500:
                path = getattr(request.url_rule, 'rule', request.path)
                REQUEST_ERRORS.labels(method=request.method, path=path).inc()
        except Exception:
            pass
        return response

