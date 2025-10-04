"""Route registration for the Flask app."""

from __future__ import annotations

from flask import Flask

from .admin import admin_bp
from .health import health_bp
from .admin_new_features import admin_new_bp


def register_routes(app: Flask) -> None:
    app.register_blueprint(admin_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(admin_new_bp)

