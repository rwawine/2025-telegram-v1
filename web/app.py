"""Flask application factory with caching and security defaults."""

from __future__ import annotations

from flask import Flask, render_template, redirect, url_for
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import Counter, Histogram
from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect

from web.auth import AdminCredentials, init_login_manager
from web.routes import register_routes
from web.csrf_helpers import init_csrf_helpers
from web.performance_middleware import init_performance_middleware


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


def create_app(config, testing=False) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=config.secret_key,
        MAX_CONTENT_LENGTH=config.max_file_size,
        SEND_FILE_MAX_AGE_DEFAULT=3600,
        SESSION_COOKIE_HTTPONLY=True,
        # Harden cookies for production
        SESSION_COOKIE_SECURE=(config.environment != 'development'),
        SESSION_COOKIE_SAMESITE='Lax',
        DATABASE_PATH=config.database_path,
        TESTING=testing,
        # Fix CSRF issues with aiohttp-wsgi integration
        WTF_CSRF_TIME_LIMIT=None,
        # Keep disabled under aiohttp-wsgi bridge; templates still include tokens safely
        WTF_CSRF_CHECK_DEFAULT=False,
    )
    cache.init_app(app, config={"CACHE_TYPE": "simple"})
    # Conditionally enable CSRF based on testing mode
    if not testing:
        csrf.init_app(app)
        
    # Initialize CSRF helpers
    init_csrf_helpers(app)
    
    # Initialize performance middleware
    init_performance_middleware(app)

    # Warn if insecure defaults detected
    try:
        if (config.admin_username == "admin" and config.admin_password in {"123456", "secure_password_change_me"}) or (not config.bot_token or config.bot_token == "your_bot_token_here"):
            app.logger.warning("Insecure defaults detected: change ADMIN credentials and BOT_TOKEN in .env before production")
    except Exception:
        pass
    
    credentials = AdminCredentials(username=config.admin_username, password_hash=config.admin_password)
    # Update credentials with hashed password
    credentials = init_login_manager(app, credentials)
    register_routes(app)
    
    # Root redirects to admin dashboard/login
    @app.route('/')
    def root():
        return redirect(url_for('admin.login_page'))
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
        try:
            REQUEST_ERRORS.labels(method=getattr(getattr(app, 'request_class', None), 'method', 'NA'), path='500').inc()
        except Exception:
            pass
        app.logger.error(f"Internal server error: {error}")
        return render_template('500.html'), 500
    
    # Expose Prometheus metrics at /metrics
    @app.route('/metrics')
    def metrics():
        data = generate_latest()
        return data, 200, {'Content-Type': CONTENT_TYPE_LATEST}

    # Wrap all requests to measure latency
    @app.before_request
    def _before_metrics():
        from flask import request, g
        g._metrics_start = g.get('_metrics_start', None) or __import__('time').time()

    @app.after_request
    def _after_metrics(response):
        try:
            from flask import request, g
            start = getattr(g, '_metrics_start', None)
            if start is not None:
                duration = __import__('time').time() - start
                # Use route rule or path
                path = getattr(request.url_rule, 'rule', request.path)
                REQUEST_LATENCY.labels(method=request.method, path=path).observe(duration)
        except Exception:
            pass
        # Add CSP with necessary permissions for Alpine.js and external resources
        try:
            # Allow unsafe-eval for Alpine.js, external CDNs, and font resources
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

    return app