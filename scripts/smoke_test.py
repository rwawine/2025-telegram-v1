"""Lightweight web smoke test (no aiogram required).

Run with bot disabled to avoid aiogram/pydantic installation:
  PowerShell:
    $env:ENABLE_BOT = "false"; python scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio

from config import load_config
from database.connection import init_db_pool
from database.migrations import run_migrations
from web import create_app


async def _prepare_database(config) -> None:
    pool = await init_db_pool(
        database_path=config.database_path,
        pool_size=config.db_pool_size,
        busy_timeout_ms=config.db_busy_timeout,
    )
    await run_migrations(pool)


def main() -> None:
    config = load_config()
    # Prepare DB and schema
    asyncio.run(_prepare_database(config))

    # Create Flask test client
    app = create_app(config, testing=True)
    client = app.test_client()

    # /metrics
    resp = client.get("/metrics")
    assert resp.status_code == 200, f"/metrics failed: {resp.status_code}"

    # root redirect to /admin/login
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (301, 302), f"/ redirect failed: {resp.status_code}"

    # /health (requires initialized db_pool)
    resp = client.get("/health")
    assert resp.status_code == 200, f"/health failed: {resp.status_code}"

    # /admin/login GET renders
    resp = client.get("/admin/login")
    assert resp.status_code == 200, f"/admin/login failed: {resp.status_code}"

    print("Smoke OK: /metrics, / (redirect), /health, /admin/login")


if __name__ == "__main__":
    main()




