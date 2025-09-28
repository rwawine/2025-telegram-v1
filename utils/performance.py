"""Performance monitoring utilities using Prometheus metrics."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterable

import psutil
from prometheus_client import Counter, Gauge, Histogram


request_count = Counter("bot_requests_total", "Total bot requests")
request_duration = Histogram("bot_request_duration_seconds", "Bot request duration")
active_users = Gauge("bot_active_users", "Active users count")
db_connections = Gauge("db_connection_pool_size", "DB connection pool size")
queue_size = Gauge("message_queue_size", "Message queue size")
broadcast_jobs_total = Gauge("broadcast_jobs_total", "Total broadcast jobs", labelnames=("status",))


class PerformanceMonitor:
    def __init__(self) -> None:
        self.metrics = {
            "request_count": request_count,
            "request_duration": request_duration,
            "active_users": active_users,
            "db_connections": db_connections,
            "queue_size": queue_size,
            "broadcast_jobs_total": broadcast_jobs_total,
        }

    @contextmanager
    def track_request(self):
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            request_count.inc()
            request_duration.observe(duration)

    def record_active_users(self, users_count: int) -> None:
        active_users.set(users_count)

    def record_queue_size(self, size: int) -> None:
        queue_size.set(size)

    def record_db_pool(self, pool_size: int) -> None:
        db_connections.set(pool_size)

    def record_broadcast_stats(self, stats: Iterable[tuple[str, int]]) -> None:
        for status, value in stats:
            broadcast_jobs_total.labels(status=status).set(value)

    def gather_host_metrics(self) -> dict:
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            "memory_rss": memory_info.rss,
            "cpu_percent": process.cpu_percent(interval=None),
        }

