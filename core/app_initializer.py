"""Application initialization orchestrator."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Optional

from aiohttp import web as aiohttp_web
from aiohttp_wsgi import WSGIHandler

from config import Config, load_config
from core.logger import get_logger
from database import init_db_pool, run_migrations
from services.cache import init_cache
from utils.performance import PerformanceMonitor

logger = get_logger(__name__)


class ApplicationInitializer:
    """Orchestrates application initialization and lifecycle."""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or load_config()
        self.db_pool = None
        self.cache = None
        self.bot = None
        self.broadcast_service = None
        self.backup_service = None
        self.web_runner = None
        self.monitor = PerformanceMonitor()
        
    async def initialize(self) -> None:
        """Initialize all application components."""
        # Check first-time setup
        await self._check_first_time_setup()
        
        # Initialize database
        await self._init_database()
        
        # Initialize cache
        self._init_cache()
        
        # Initialize bot if enabled
        if self._should_enable_bot():
            await self._init_bot()
        else:
            logger.info("Running in admin-only mode (web interface only)")
        
        # Initialize backup service
        await self._init_backup_service()
        
        # Initialize web server
        await self._init_web_server()
        
    async def run(self) -> None:
        """Run the application."""
        # Start backup service
        await self.backup_service.start()
        logger.info("💾 Automatic backup service started")
        
        # Start bot if available
        bot_task = None
        if self.bot:
            bot_task = asyncio.create_task(self.bot.start())
            logger.info("🤖 Telegram bot started")
        
        try:
            if bot_task:
                await bot_task
            else:
                # Keep web server running
                logger.info("⚡ Admin-only mode: web interface running...")
                while True:
                    await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await self.cleanup()
            
    async def cleanup(self) -> None:
        """Cleanup resources."""
        with suppress(Exception):
            if self.bot:
                await self.bot.stop()
        with suppress(Exception):
            if self.backup_service:
                await self.backup_service.stop()
        with suppress(Exception):
            if self.web_runner:
                await self.web_runner.cleanup()
                
    async def _check_first_time_setup(self) -> None:
        """Check and run first-time system initialization."""
        if not Path("data").exists() or not Path(".env").exists():
            logger.info("🚀 First-time setup detected. Initializing system...")
            from system_initializer import initialize_system
            if not initialize_system():
                raise RuntimeError("System initialization failed")
            logger.info("✅ System initialized")
            
    async def _init_database(self) -> None:
        """Initialize database pool and run migrations."""
        self.db_pool = await init_db_pool(
            database_path=self.config.database_path,
            pool_size=self.config.db_pool_size,
            busy_timeout_ms=self.config.db_busy_timeout,
        )
        await run_migrations(self.db_pool)
        logger.info("✅ Database initialized")
        
    def _init_cache(self) -> None:
        """Initialize cache service."""
        self.cache = init_cache(
            hot_ttl=self.config.cache_ttl_hot,
            warm_ttl=self.config.cache_ttl_warm,
            cold_ttl=self.config.cache_ttl_cold,
        )
        logger.info("✅ Cache initialized")
        
    def _should_enable_bot(self) -> bool:
        """Check if bot should be enabled."""
        return (
            self.config.enable_bot 
            and self.config.bot_token 
            and self.config.bot_token != "your_bot_token_here"
        )
        
    async def _init_bot(self) -> None:
        """Initialize Telegram bot."""
        try:
            from bot.initializer import BotInitializer
            bot_init = BotInitializer(self.config, self.cache)
            self.bot = await bot_init.initialize()
            
            from services import BroadcastService
            self.broadcast_service = BroadcastService(
                self.bot.bot,
                rate_limit=self.config.broadcast_rate_limit,
                batch_size=self.config.broadcast_batch_size,
            )
            logger.info("✅ Bot initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            logger.info("Continuing with web interface only...")
            
    async def _init_backup_service(self) -> None:
        """Initialize backup service."""
        from services.backup_service import init_backup_service
        self.backup_service = init_backup_service(
            db_path=self.config.database_path,
            backup_dir=self.config.backup_folder,
            max_age_days=2,
            backup_interval_hours=6
        )
        
    async def _init_web_server(self) -> None:
        """Initialize web server."""
        from web import create_app
        
        flask_app = create_app(self.config)
        flask_app.config["BROADCAST_SERVICE"] = self.broadcast_service
        flask_app.config["BACKUP_SERVICE"] = self.backup_service
        flask_app.config.update({
            "UPLOAD_FOLDER": "uploads",
            "EXPORT_FOLDER": "exports",
            "LOG_FOLDER": "logs",
            "MAX_PARTICIPANTS": 10000,
            "WEB_HOST": self.config.web_host,
            "WEB_PORT": self.config.web_port,
            "BOT_TOKEN": self.config.bot_token,
            "ADMIN_IDS": self.config.admin_ids,
        })
        
        # Create WSGI handler for Flask app
        wsgi_handler = WSGIHandler(flask_app)
        
        # Create aiohttp app and add Flask routes
        aio_app = aiohttp_web.Application()
        aio_app.router.add_route("*", "/{path_info:.*}", wsgi_handler)
        
        self.web_runner = aiohttp_web.AppRunner(aio_app)
        await self.web_runner.setup()
        
        # Bind to PORT env var if present (Render/Heroku)
        import os
        effective_port = int(os.getenv("PORT", str(self.config.web_port)))
        effective_host = "0.0.0.0" if os.getenv("PORT") else self.config.web_host
        
        site = aiohttp_web.TCPSite(self.web_runner, effective_host, effective_port)
        await site.start()
        
        logger.info(f"🚀 Web server started on http://{effective_host}:{effective_port}")
        logger.info(f"🔗 Admin panel: http://{effective_host}:{effective_port}/admin")

