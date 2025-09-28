"""Health check blueprint."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from database.connection import get_db_pool
from utils.performance import PerformanceMonitor


health_bp = Blueprint("health", __name__)
monitor = PerformanceMonitor()


@health_bp.route("/health")
def health_check():
    db_pool = get_db_pool()
    host_metrics = monitor.gather_host_metrics()
    broadcast_metrics = current_app.config.get("BROADCAST_METRICS", {})

    data = {
        "status": "ok",
        "db_pool_size": len(db_pool._connections),
        "host": host_metrics,
        "broadcast_jobs": broadcast_metrics,
    }
    return jsonify(data)

