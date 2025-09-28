"""Application entrypoint orchestrating bot, web server, and monitoring."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from pathlib import Path

from aiohttp import web as aiohttp_web
from aiohttp_wsgi import WSGIHandler
from prometheus_client import start_http_server

from bot import OptimizedBot
from bot.handlers import (
    setup_common_handlers,
    setup_registration_handlers,
    setup_support_handlers,
    setup_fallback_handlers,
)
from config import load_config
from database import init_db_pool, run_migrations
from services import BroadcastService, SecureLottery, set_main_loop
from services.cache import init_cache
from utils.performance import PerformanceMonitor
from web import create_app
from web.routes import register_routes


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_bot(config, cache):
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
    config = load_config()
    if not config.bot_token:
        logger.error("BOT_TOKEN is not set")
        return

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

    bot = await init_bot(config, cache)
    broadcast_service = BroadcastService(
        bot.bot,
        rate_limit=config.broadcast_rate_limit,
        batch_size=config.broadcast_batch_size,
    )

    monitor = PerformanceMonitor()
    start_http_server(port=config.prometheus_port)

    flask_app = create_app(config)
    flask_app.config["BROADCAST_SERVICE"] = broadcast_service
    
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
    site = aiohttp_web.TCPSite(runner, config.web_host, config.web_port)
    await site.start()

    bot_task = asyncio.create_task(bot.start())

    try:
        await bot_task
    finally:
        with suppress(Exception):
            await bot.stop()
        with suppress(Exception):
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())