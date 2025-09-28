"""Application entrypoint orchestrating bot, web server, and monitoring."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from pathlib import Path

from aiohttp import web as aiohttp_web
from aiohttp_wsgi import WSGIHandler
import os

from bot import OptimizedBot
# Импорт handlers перенесен в init_bot после инициализации кеша
from config import load_config
from database import init_db_pool, run_migrations
from services import BroadcastService, SecureLottery, set_main_loop
from services.backup_service import init_backup_service
from services.cache import init_cache
from utils.performance import PerformanceMonitor
from web import create_app
from web.routes import register_routes


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_bot(config, cache):
    # Импортируем handlers здесь, после инициализации кеша
    from bot.handlers import (
        setup_common_handlers,
        setup_registration_handlers,
        setup_support_handlers,
        setup_fallback_handlers,
    )
    from bot.context_manager import init_context_manager
    
    # Инициализируем context manager
    init_context_manager()
    
    bot = OptimizedBot(
        token=config.bot_token,
        rate_limit=config.bot_rate_limit,
        worker_threads=config.bot_worker_threads,
        message_queue_size=config.message_queue_size,
    )
    setup_common_handlers(bot.dispatcher)
    setup_support_handlers(bot.dispatcher)
    upload_path = Path(config.upload_folder)
    upload_path.mkdir(parents=True, exist_ok=True)
    setup_registration_handlers(
        bot.dispatcher,
        upload_dir=upload_path,
        cache=cache,
        bot=bot.bot,
    )
    # Fallback обработчики должны быть последними (наименьший приоритет)
    setup_fallback_handlers(bot.dispatcher)
    return bot


async def main() -> None:
    # Initialize system on first run
    from pathlib import Path
    if not Path("data").exists() or not Path(".env").exists():
        print("🚀 First-time setup detected. Initializing system...")
        from system_initializer import initialize_system
        if not initialize_system():
            logger.error("System initialization failed")
            return
        print("✅ System initialized. Starting application...")
    
    config = load_config()
    if not config.enable_bot or not config.bot_token or config.bot_token == "your_bot_token_here":
        if not config.enable_bot:
            logger.info("ENABLE_BOT is false. Running in admin-only mode (web interface only).")
        else:
            logger.warning("BOT_TOKEN is not set properly. Running in admin-only mode (web interface only).")
        # Don't return, allow web interface to run without bot

    loop = asyncio.get_running_loop()
    set_main_loop(loop)

    db_pool = await init_db_pool(
        database_path=config.database_path,
        pool_size=config.db_pool_size,
        busy_timeout_ms=config.db_busy_timeout,
    )
    await run_migrations(db_pool)

    cache = init_cache(
        hot_ttl=config.cache_ttl_hot,
        warm_ttl=config.cache_ttl_warm,
        cold_ttl=config.cache_ttl_cold,
    )

    # Initialize bot only if token is properly configured
    bot = None
    broadcast_service = None
    
    if config.enable_bot and config.bot_token and config.bot_token != "your_bot_token_here":
        try:
            bot = await init_bot(config, cache)
            broadcast_service = BroadcastService(
                bot.bot,
                rate_limit=config.broadcast_rate_limit,
                batch_size=config.broadcast_batch_size,
            )
            logger.info("Bot initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            logger.info("Continuing with web interface only...")
    else:
        logger.info("Running in admin-only mode (web interface only)")

    monitor = PerformanceMonitor()
    
    # Initialize backup service
    backup_service = init_backup_service(
        db_path=config.database_path,
        backup_dir=config.backup_folder,
        max_age_days=2,  # Keep backups for 2 days only
        backup_interval_hours=6  # Backup every 6 hours
    )

    flask_app = create_app(config)
    flask_app.config["BROADCAST_SERVICE"] = broadcast_service
    flask_app.config["BACKUP_SERVICE"] = backup_service
    
    # Add additional configuration
    flask_app.config.update({
        "UPLOAD_FOLDER": "uploads",
        "EXPORT_FOLDER": "exports", 
        "LOG_FOLDER": "logs",
        "MAX_PARTICIPANTS": 10000,
        "WEB_HOST": config.web_host,
        "WEB_PORT": config.web_port,
        "BOT_TOKEN": config.bot_token,
        "ADMIN_IDS": getattr(config, 'admin_ids', []),
    })

    loop = asyncio.get_running_loop()

    # Create WSGI handler for Flask app
    wsgi_handler = WSGIHandler(flask_app)
    
    # Create aiohttp app and add Flask routes
    aio_app = aiohttp_web.Application()
    aio_app.router.add_route("*", "/{path_info:.*}", wsgi_handler)
    
    runner = aiohttp_web.AppRunner(aio_app)
    await runner.setup()
    # Bind to PORT env var if present (Render/Heroku)
    effective_port = int(os.getenv("PORT", str(config.web_port)))
    site = aiohttp_web.TCPSite(runner, config.web_host, effective_port)
    await site.start()
    
    logger.info(f"🚀 Web server started on http://{config.web_host}:{effective_port}")
    logger.info("🔗 Admin panel: http://localhost:5000")
    logger.info("💻 Default login: admin / 123456")
    
    # Start backup service
    await backup_service.start()
    logger.info("💾 Automatic backup service started (every 6 hours, keep 2 days)")

    # Start bot if available
    bot_task = None
    if bot:
        bot_task = asyncio.create_task(bot.start())
        logger.info("🤖 Telegram bot started")

    try:
        if bot_task:
            await bot_task
        else:
            # Keep the web server running indefinitely
            logger.info("⚡ Admin-only mode: web interface running...")
            while True:
                await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        with suppress(Exception):
            if bot:
                await bot.stop()
        with suppress(Exception):
            await backup_service.stop()
        with suppress(Exception):
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())