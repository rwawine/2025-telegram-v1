"""Bot initialization module."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from core.logger import get_logger

if TYPE_CHECKING:
    from config import Config
    from services.cache import Cache

logger = get_logger(__name__)


class BotInitializer:
    """Handles bot initialization and handler registration."""
    
    def __init__(self, config: Config, cache):
        self.config = config
        self.cache = cache
        
    async def initialize(self):
        """Initialize bot with proper handler registration order."""
        from bot import OptimizedBot
        from bot.context_manager import init_context_manager
        from bot.handlers import (
            setup_common_handlers,
            setup_registration_handlers,
            setup_support_handlers,
        )
        from bot.handlers.global_commands import setup_global_commands
        from bot.handlers.fallback_fixed import setup_fixed_fallback_handlers
        from bot.middleware.fsm_logger import setup_fsm_middleware
        from bot.middleware import setup_rate_limit_middleware
        from services import init_notification_service, init_photo_upload_service, init_fraud_detection_service
        
        # Initialize context manager
        init_context_manager()
        
        # Create bot instance
        bot = OptimizedBot(
            token=self.config.bot_token,
            rate_limit=self.config.bot_rate_limit,
            worker_threads=self.config.bot_worker_threads,
            message_queue_size=self.config.message_queue_size,
        )
        
        # Initialize services that require bot instance
        init_notification_service(bot.bot)
        
        upload_path = Path(self.config.upload_folder)
        upload_path.mkdir(parents=True, exist_ok=True)
        init_photo_upload_service(bot.bot, upload_path)
        
        init_fraud_detection_service()
        logger.info("✅ Services initialized")
        
        # Register handlers in priority order
        # В aiogram последний зарегистрированный роутер имеет ПРИОРИТЕТ
        # Поэтому регистрируем в обратном порядке: сначала fallback (низкий приоритет),
        # затем специфичные обработчики (высокий приоритет)
        
        # IMPORTANT about priority:
        # In practice, routers registered EARLIER tend to see updates earlier.
        # We want global commands and concrete feature handlers to win over
        # generic fallback handlers and only use fallback as a last resort.

        # 1. Specific handlers (registration/common/support)
        setup_common_handlers(bot.dispatcher)
        setup_support_handlers(bot.dispatcher)

        # Use already created upload_path
        setup_registration_handlers(
            bot.dispatcher,
            upload_dir=upload_path,
            cache=self.cache,
            bot=bot.bot,
        )
        logger.info("✅ Specific handlers registered")

        # 2. Global commands (should work from ANY state, including before fallback)
        setup_global_commands(bot.dispatcher)
        logger.info("✅ Global commands registered")

        # 3. Fallback handlers (lowest priority – register LAST)
        setup_fixed_fallback_handlers(bot.dispatcher)
        logger.info("✅ Fallback handlers registered")

        # 4. Middleware
        setup_fsm_middleware(bot.dispatcher)
        setup_rate_limit_middleware(
            bot.dispatcher,
            max_messages=5,
            max_callbacks=3,
            window_seconds=2.0
        )
        logger.info("✅ Middleware configured")
        
        return bot

