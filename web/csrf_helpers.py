"""CSRF helpers for better template compatibility."""

from flask import current_app


def csrf_token():
    """Safe CSRF token function that returns empty string if CSRF is disabled."""
    try:
        from flask_wtf.csrf import generate_csrf
        # Check if CSRF is enabled for this app
        if current_app.config.get('WTF_CSRF_CHECK_DEFAULT', True):
            return generate_csrf()
        return ""
    except Exception:
        # If CSRF generation fails, return empty string
        return ""


def init_csrf_helpers(app):
    """Initialize CSRF helpers for Jinja templates."""
    app.jinja_env.globals['csrf_token'] = csrf_token
