"""Middleware для логирования переходов состояний FSM."""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import TelegramObject, Update, Message, CallbackQuery

from bot.context_manager import get_context_manager


logger = logging.getLogger(__name__)


class FSMLoggingMiddleware(BaseMiddleware):
    """Middleware для логирования и контроля FSM состояний"""
    
    def __init__(self, log_level: int = logging.INFO):
        self.log_level = log_level
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        state: FSMContext = data.get("state")
        user_id = None
        event_text = ""
        
        # Определяем пользователя и текст события
        if isinstance(event, Message):
            user_id = event.from_user.id
            event_text = event.text or f"[{event.content_type}]"
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id  
            event_text = f"callback:{event.data}"
        
        if not state or not user_id:
            return await handler(event, data)
        
        # Получаем состояние до обработки
        current_state = await state.get_state()
        
        try:
            # Выполняем handler
            result = await handler(event, data)
            
            # Получаем состояние после обработки
            new_state = await state.get_state()
            
            # Логируем переход состояния
            if current_state != new_state:
                logger.log(
                    self.log_level,
                    f"FSM Transition | User {user_id} | {current_state} → {new_state} | Event: {event_text[:50]}"
                )
                
                # Обновляем контекст менеджер
                context_manager = get_context_manager()
                if context_manager and user_id in context_manager.sessions:
                    session = context_manager.sessions[user_id]
                    session.breadcrumbs.append(f"{current_state}→{new_state}")
                    if len(session.breadcrumbs) > 20:  # Ограничиваем историю
                        session.breadcrumbs = session.breadcrumbs[-20:]
            
            return result
            
        except Exception as e:
            # Логируем ошибки в FSM
            logger.error(
                f"FSM Error | User {user_id} | State: {current_state} | Event: {event_text[:50]} | Error: {str(e)}"
            )
            
            # Увеличиваем счетчик ошибок
            context_manager = get_context_manager()
            if context_manager:
                await context_manager.increment_error_count(user_id)
            
            raise


class FSMCleanupMiddleware(BaseMiddleware):
    """Middleware для автоматической очистки старых FSM состояний"""
    
    def __init__(self, session_timeout_hours: int = 24):
        self.session_timeout_hours = session_timeout_hours
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        # Очищаем старые сессии периодически
        context_manager = get_context_manager()
        if context_manager:
            await self._cleanup_old_sessions(context_manager)
        
        return await handler(event, data)
    
    async def _cleanup_old_sessions(self, context_manager):
        """Очистка старых неактивных сессий"""
        from datetime import datetime, timedelta
        
        cutoff_time = datetime.now() - timedelta(hours=self.session_timeout_hours)
        expired_sessions = []
        
        for user_id, session in context_manager.sessions.items():
            if session.last_message_time < cutoff_time:
                expired_sessions.append(user_id)
        
        for user_id in expired_sessions:
            context_manager.sessions.pop(user_id, None)
            logger.info(f"Cleaned up expired session for user {user_id}")


def setup_fsm_middleware(dispatcher) -> None:
    """Настройка FSM middleware"""
    
    # Middleware для логирования (внешний слой)
    dispatcher.message.middleware(FSMLoggingMiddleware())
    dispatcher.callback_query.middleware(FSMLoggingMiddleware())
    
    # Middleware для очистки (внутренний слой)
    dispatcher.message.middleware(FSMCleanupMiddleware())
    dispatcher.callback_query.middleware(FSMCleanupMiddleware())
    
    logger.info("FSM middleware configured")
