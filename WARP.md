# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Common development commands

All commands assume the project root as the working directory.

### Environment setup

- Create a virtual environment and install dependencies:
  - Generic:
    - `python -m venv .venv`
    - Activate (PowerShell): `.venv\\Scripts\\Activate.ps1`
    - `pip install -r requirements.txt`

### Running the application

- Run full system (Telegram bot + admin web panel):
  - Ensure required environment variables (`BOT_TOKEN`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SECRET_KEY`, `DATABASE_PATH` at minimum) are set via `.env` or the environment.
  - `python main.py`
  - By default the web interface listens on `WEB_HOST`/`WEB_PORT` from `config.Config` (defaults: `0.0.0.0:5000`).

- Run in **admin-only mode** (web interface without Telegram bot), useful during web development or when `aiogram` is not available:
  - PowerShell:
    - `$env:ENABLE_BOT = "false"; python main.py`

### Health checks and tests

- Minimal web smoke test (no bot startup, uses Flask test client):
  - Optionally disable the bot to avoid Telegram dependencies: `$env:ENABLE_BOT = "false"`
  - `python scripts/smoke_test.py`

- Aggregated "test" entrypoint used for quick verification / CI-style checks:
  - `python scripts/run_tests.py`
  - This script forces `ENABLE_BOT=false` and runs the web smoke test.

- Deep health check of core subsystems (DB connectivity, callback validation, file limits, handler coverage, configuration sanity):
  - `python scripts/health_check.py`
  - Returns a non-zero exit code if critical issues are found (CI-friendly).

- Load and performance tests (500+ simulated users / high request volume):
  - `python scripts/load_test.py`

> There is no traditional `pytest`/`unittest` test suite in this repository; tests are script-based. To "run a single test", invoke the specific script you care about (e.g. `scripts/health_check.py` or a custom script you add under `scripts/`).

### Linting and formatting

- Static type checking:
  - `mypy .`

- Formatting:
  - `black .`
  - `isort .`

## High-level architecture

### Entry point and orchestration

- `main.py` is the single entry point. It configures logging via `core.setup_logger`, obtains the running asyncio loop, and delegates startup to `core.app_initializer.ApplicationInitializer`.
- `ApplicationInitializer` is responsible for:
  - Loading configuration from environment variables via `config.load_config()` / `Config`.
  - Ensuring first-time setup by calling `system_initializer.initialize_system()` when `data/` or `.env` are missing.
  - Initializing the SQLite connection pool and running schema migrations (`database.init_db_pool`, `database.run_migrations`).
  - Initializing the multi-level cache (`services.cache.init_cache`).
  - Conditionally initializing the Telegram bot via `bot.initializer.BotInitializer` when `ENABLE_BOT` is true and a real `BOT_TOKEN` is configured.
  - Initializing the backup service (`services.backup_service.init_backup_service`).
  - Creating and serving the Flask admin panel through an `aiohttp` server using `aiohttp_wsgi.WSGIHandler`.
- At runtime, `ApplicationInitializer.run()` starts the backup service, optionally starts the bot, and keeps the process alive (admin-only mode loops while only the web interface is running).

### Configuration model

- All runtime configuration flows through `config.Config` / `load_config()` and **environment variables**.
- Important fields include:
  - `BOT_TOKEN`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SECRET_KEY` for security.
  - `DATABASE_PATH`, `DB_POOL_SIZE`, `DB_BUSY_TIMEOUT` for persistence and performance.
  - `ENABLE_BOT`, `WEB_HOST`, `WEB_PORT`, `PROMETHEUS_PORT` for runtime mode and HTTP binding.
  - Cache TTLs (`CACHE_TTL_HOT/WARM/COLD`) and broadcast parameters (`BROADCAST_BATCH_SIZE`, `BROADCAST_RATE_LIMIT`).
  - Sharding controls (`SHARDING_ENABLED`, `SHARDING_NUM_SHARDS`, `SHARD_SIZE_THRESHOLD`, etc.).
- When adding new configurable behavior, extend the `Config` dataclass and its `load_config()` constructor rather than reading raw environment variables in feature code.

### Layered structure

The system follows a clear layered architecture (see `docs/ARCHITECTURE.md`):

1. **Presentation layer**
   - **Telegram bot** (`bot/`): aiogram 3.x handlers, states, keyboards, and middleware.
     - `bot/handlers/` – conversational flows (registration, status checks, support, global commands).
     - `bot/middleware/` – cross-cutting concerns like rate limiting (`RateLimitMiddleware`) and FSM logging.
     - `bot/keyboards/` – inline and reply keyboard builders.
   - **Admin web panel** (`web/`): Flask app exposing HTML admin UI and health/metrics endpoints.
     - `web/__init__.py` exposes `create_app(config, testing=False)`; routes live under `web/routes/` (admin dashboards, participants, lottery control, broadcasts, support tickets, health checks).

2. **Business logic / services layer** (`services/`)
   - Houses all non-trivial domain logic, shared between bot and web.
   - Key services (see also `docs/API_REFERENCE.md` and `services/__init__.py`):
     - `SecureLottery` (`services/lottery.py`) – cryptographically anchored, deterministic winner selection.
     - `BroadcastService` – queued, rate-limited mass messaging with retry semantics.
     - `MultiLevelCache` – hot/warm/cold caching strategy with different TTLs.
     - `AnalyticsService` / `AnalyticsEvent` – structured event tracking (registration funnel, button clicks, errors, etc.).
     - `FraudDetectionService` / `FraudScore` – registration-time fraud scoring and logging based on multiple heuristics.
     - `NotificationService` – encapsulates all user-facing notification flows (registration status, lottery wins, ticket updates).
     - `PhotoUploadService` – photo download/validation with retry and size limits.
     - `RegistrationStateManager` – durable FSM state for multi-step registration with autosave.
     - Additional utilities for personalization, async execution helpers, backup scheduling, and priority queues.
   - Many services expose `init_*` and `get_*` helpers to implement a controlled singleton pattern; initialization is typically performed during application startup and then accessed from handlers/routes.

3. **Data access layer** (`database/`)
   - `connection.py` – manages the optimized SQLite pool (WAL mode, pooling, busy timeout) exposed via `init_db_pool()` / `get_db_pool()`.
   - `migrations.py` – defines and runs schema migrations for core tables (participants, winners, lottery_runs, analytics_events, fraud_log, registration_states, etc.).
   - `repositories.py` and related modules – higher-level async functions for common queries (participant status, batch inserts, approved participant selection for lotteries, etc.), keeping SQL isolated from handlers and services.
   - `sharding.py` / `sharding_integration.py` – optional sharding logic for splitting data across multiple SQLite files once size/performance thresholds are exceeded.

4. **Core and utilities**
   - `core/` provides:
     - Central logging setup (`core.logger`) and access helpers (`get_logger`).
     - Cross-cutting constants and limits (`core.constants` – Telegram limits, cache defaults, validation rules, file upload limits, etc.).
     - Domain-specific exceptions (`core.exceptions`) used across layers.
     - The main application lifecycle orchestration (`core.app_initializer.ApplicationInitializer`).
   - `utils/` contains focused helpers:
     - `validators.py` – input validation (names, phone numbers, loyalty cards, etc.).
     - `callback_validators.py` – enforcing Telegram `callback_data` length constraints and registry coverage.
     - `file_validators.py` – centralized file size and type checks.
     - `performance.py` – `PerformanceMonitor` for measuring and reporting system performance.

### Telegram formatting conventions

- The project standard for bot messages is documented in `docs/TELEGRAM_FORMATTING.md`:
  - Prefer **Markdown** formatting with Telegram-compatible syntax (`*bold*`, `_italic_`, `` `code` ``) and always pass the appropriate `parse_mode` when sending messages.
  - Avoid mixing HTML and Markdown in a single message; choose one format consistently.
  - Carefully escape special characters required by Telegram Markdown when interpolating dynamic content.
- When adding or modifying bot text, follow these rules to avoid runtime formatting errors in Telegram clients.

### How to extend the system safely

- **New bot features:**
  - Implement conversation flow in a new or existing module under `bot/handlers/`.
  - Keep handlers thin; delegate non-trivial logic to services in `services/` and data access to `database/` repositories.
  - Reuse keyboards from `bot/keyboards/` and respect existing rate-limiting middleware.

- **New admin panel features:**
  - Add Flask views under `web/routes/` and corresponding templates/static assets under `web/templates/` and `web/static/` (structure matches typical Flask blueprints as described in `docs/ARCHITECTURE.md`).
  - Use existing services and repositories rather than talking to SQLite directly from view functions.

- **Database changes:**
  - Update schema/migrations in `database/migrations.py` and any relevant repositories instead of issuing ad-hoc SQL from handlers.
  - Consider sharding impact if you are adding large tables or significantly increasing write volume.

- **Configuration-driven behavior:**
  - Prefer new `Config` fields and environment variables over hard-coded constants, updating `config.load_config()` and, if needed, `core.constants`.

This summary is intentionally focused on cross-cutting patterns and entrypoints so that future Warp agents can quickly orient themselves, find the right layer for a change, and invoke the correct scripts/commands when developing or debugging the system.