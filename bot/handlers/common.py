"""Common bot commands and informational handlers."""

from aiogram import F, Router, types
from aiogram.filters import Command

from bot.keyboards import get_main_menu_keyboard_for_user, get_info_menu_keyboard
from bot.context_manager import get_context_manager, UserContext, UserAction
from bot.messages import smart_messages
from database.repositories import get_participant_status


class CommonHandlers:
    def __init__(self) -> None:
        self.router = Router()
        self._register()

    def setup(self, dispatcher) -> None:
        dispatcher.include_router(self.router)

    def _register(self) -> None:
        self.router.message.register(self.start, Command("start"))
        self.router.message.register(self.help_and_support_handler, F.text.in_(["❓ Помощь", "💬 Помощь", "💬 Техподдержка", "💬 Поддержка"]))
        self.router.message.register(self.status_handler, F.text.in_(["📋 Мой статус", "✅ Мой статус", "⏳ Мой статус", "❌ Мой статус"]))
        self.router.message.register(self.show_info_menu, F.text.contains("розыгрыш"))
        # Обработчик для старых результатов - перенаправляем на помощь
        self.router.message.register(self.handle_results_redirect, F.text.contains("🏆 Результаты"))
        self.router.callback_query.register(self.handle_info_callback, F.data.startswith("info_"))

    async def start(self, message: types.Message) -> None:
        # Обновляем контекст пользователя
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.update_context(
                message.from_user.id,
                UserContext.NAVIGATION,
                UserAction.BUTTON_CLICK
            )
        
        # Проверяем статус регистрации пользователя
        registration_status = await get_participant_status(message.from_user.id)
        is_registered = registration_status is not None
        
        # Получаем умное приветственное сообщение
        welcome_msg = smart_messages.get_welcome_message(is_registered)
        
        keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
        await message.answer(welcome_msg["text"], reply_markup=keyboard, parse_mode="Markdown")

    async def help_and_support_handler(self, message: types.Message) -> None:
        """Объединенный обработчик помощи и техподдержки"""
        from bot.keyboards.main_menu import get_faq_keyboard
        
        help_text = (
            "💬 Помощь и техподдержка\n\n"
            "🤔 Нужна помощь? Выберите подходящий вариант:\n\n"
            "📋 Часто задаваемые вопросы\n"
            "💬 Написать в техподдержку\n"
            "📞 Связаться с оператором\n\n"
            "Мы поможем решить любые вопросы!"
        )
        
        keyboard = get_faq_keyboard()
        await message.answer(help_text, reply_markup=keyboard)
    
    async def status_handler(self, message: types.Message) -> None:
        """Обработчик проверки статуса участника"""
        from bot.keyboards.main_menu import get_status_keyboard
        
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.update_context(
                message.from_user.id,
                UserContext.NAVIGATION,
                UserAction.BUTTON_CLICK
            )
        
        # Проверяем статус участника
        status = await get_participant_status(message.from_user.id)
        
        if status:
            status_text = {
                "pending": "⏳ На модерации",
                "approved": "✅ Одобрена", 
                "rejected": "❌ Отклонена"
            }.get(status, "❓ Неизвестен")
            
            text = f"✅ Ваш статус участия: {status_text}\n\n"
            
            if status == "approved":
                text += "🎉 Поздравляем! Вы участвуете в розыгрыше!"
            elif status == "pending":
                text += "⏳ Ваша заявка проверяется модераторами."
            elif status == "rejected":
                text += "❌ К сожалению, заявка отклонена. Обратитесь в поддержку."
        else:
            text = "❓ Вы еще не подавали заявку на участие.\n\n🚀 Нажмите 'Начать регистрацию' для участия в розыгрыше!"
            
        await message.answer(text, reply_markup=get_status_keyboard())

    async def handle_results_redirect(self, message: types.Message) -> None:
        """Перенаправление старой кнопки результатов на помощь"""
        await message.answer(
            "🔄 Эта функция была обновлена!\n\n"
            "Теперь для получения информации о результатах используйте:\n"
            "💬 Помощь → 📋 Часто задаваемые вопросы → 🕐 Когда будут результаты?"
        )
        await self.help_and_support_handler(message)

    async def show_info_menu(self, message: types.Message) -> None:
        text = (
            "🎉 О нашем розыгрыше\n\n"
            "ℹ️ Выберите раздел для подробной информации:"
        )
        await message.answer(text, reply_markup=get_info_menu_keyboard())

    async def handle_info_callback(self, callback: types.CallbackQuery) -> None:
        mapping = {
            "info_rules": (
                "📋 Правила участия в розыгрыше\n\n"
                "✅ Кто может участвовать: совершеннолетние владельцы карт лояльности (1 заявка на участника).\n\n"
                "📝 Для участия: укажите реальные данные и загрузите фото лифлета."
            ),
            "info_prizes": (
                "🏆 Призы розыгрыша\n\n"
                "Главный приз: сертификат на 50 000 ₽. Дополнительно — другие призы и промокоды."
            ),
            "info_schedule": (
                "📅 Сроки проведения\n\n"
                "Прием заявок, дата розыгрыша и публикация результатов объявляются в канале."
            ),
            "info_fairness": (
                "⚖️ Гарантии честности\n\n"
                "Используем проверяемый алгоритм выбора, ведем трансляции и публикуем статистику."
            ),
            "info_contacts": (
                "📞 Контакты организаторов\n\n"
                "Горячая линия и email доступны в админ-панели сайта."
            ),
        }
        await callback.message.edit_text(mapping.get(callback.data, "Информация недоступна."))
        await callback.answer()


def setup_common_handlers(dispatcher) -> CommonHandlers:
    handler = CommonHandlers()
    handler.setup(dispatcher)
    return handler

