"""Глобальные команды, которые работают в любом состоянии FSM."""

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.keyboards import get_main_menu_keyboard_for_user
from bot.context_manager import get_context_manager, UserContext, UserAction


class GlobalCommandsHandler:
    """Глобальные команды для работы во всех состояниях"""
    
    def __init__(self):
        self.router = Router()
        self.router.name = "global_commands"
        self._register_handlers()
    
    def setup(self, dispatcher) -> None:
        # Глобальные команды должны быть первыми (высший приоритет)
        dispatcher.include_router(self.router)
    
    def _register_handlers(self):
        """Регистрация глобальных команд с высшим приоритетом"""
        
        # Глобальные команды - работают в ЛЮБОМ состоянии
        self.router.message.register(self.handle_start, Command("start"))
        self.router.message.register(self.handle_cancel, Command("cancel"))
        self.router.message.register(self.handle_reset, Command("reset"))
        self.router.message.register(self.handle_help, Command("help"))
        
        # Экстренная навигация - работает везде
        self.router.message.register(self.emergency_menu, F.text == "🆘 МЕНЮ")
        self.router.message.register(self.emergency_cancel, F.text == "❌ ОТМЕНА")
    
    async def handle_start(self, message: types.Message, state: FSMContext) -> None:
        """Команда /start - сбрасывает состояние и показывает меню"""
        # КРИТИЧЕСКИ ВАЖНО: сбрасываем любое FSM состояние
        await state.clear()
        
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.update_context(
                message.from_user.id,
                UserContext.NAVIGATION,
                UserAction.BUTTON_CLICK
            )
        
        from database.repositories import get_participant_status
        from bot.messages import smart_messages
        
        # Проверяем статус регистрации пользователя
        registration_status = await get_participant_status(message.from_user.id)
        is_registered = registration_status is not None
        
        # Получаем умное приветственное сообщение
        welcome_msg = smart_messages.get_welcome_message(is_registered)
        
        keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
        await message.answer(
            f"🔄 **Перезапуск бота**\n\n{welcome_msg['text']}", 
            reply_markup=keyboard, 
            parse_mode="Markdown"
        )
    
    async def handle_cancel(self, message: types.Message, state: FSMContext) -> None:
        """Команда /cancel - отменяет текущее действие"""
        current_state = await state.get_state()
        
        if current_state:
            await state.clear()
            await message.answer(
                "❌ **Действие отменено**\n\n"
                "🏠 Возвращаемся в главное меню",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                "✅ Никаких активных действий для отмены нет\n\n"
                "🏠 Вы уже в главном меню"
            )
        
        keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
        await message.answer("Главное меню:", reply_markup=keyboard)
    
    async def handle_reset(self, message: types.Message, state: FSMContext) -> None:
        """Команда /reset - полный сброс сессии"""
        await state.clear()
        
        context_manager = get_context_manager()
        if context_manager:
            # Очищаем сессию пользователя
            context_manager.sessions.pop(message.from_user.id, None)
        
        await message.answer(
            "🔄 **Полный сброс выполнен**\n\n"
            "Все данные сессии очищены",
            parse_mode="Markdown"
        )
        
        # Перенаправляем на /start
        await self.handle_start(message, state)
    
    async def handle_help(self, message: types.Message, state: FSMContext) -> None:
        """Команда /help - экстренная помощь"""
        current_state = await state.get_state()
        
        help_text = (
            "🆘 **Экстренная помощь**\n\n"
            "**Доступные команды:**\n"
            "• `/start` - перезапуск бота\n"
            "• `/cancel` - отменить текущее действие\n"
            "• `/reset` - полный сброс\n\n"
        )
        
        if current_state:
            help_text += f"📍 **Текущее состояние:** `{current_state}`\n\n"
            help_text += "💡 **Рекомендация:** Используйте `/cancel` для выхода"
        else:
            help_text += "✅ Вы находитесь в главном меню"
        
        await message.answer(help_text, parse_mode="Markdown")
    
    async def emergency_menu(self, message: types.Message, state: FSMContext) -> None:
        """Экстренное возвращение в меню"""
        await state.clear()
        keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
        await message.answer(
            "🆘 **Экстренное возвращение в меню**",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    async def emergency_cancel(self, message: types.Message, state: FSMContext) -> None:
        """Экстренная отмена действия"""
        await self.handle_cancel(message, state)


def setup_global_commands(dispatcher) -> GlobalCommandsHandler:
    """Настройка глобальных команд"""
    handler = GlobalCommandsHandler()
    handler.setup(dispatcher)
    return handler
