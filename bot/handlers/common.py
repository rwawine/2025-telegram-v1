"""Common bot commands and informational handlers."""

from aiogram import F, Router, types

from bot.keyboards import get_info_menu_keyboard, get_support_menu_keyboard
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
        # REMOVED: Command("start") - теперь в global_commands.py
        self.router.message.register(self.help_and_support_handler, F.text.in_(["❓ Помощь", "💬 Помощь", "💬 Техподдержка", "💬 Поддержка"]))
        self.router.message.register(self.status_handler, F.text.in_(["📋 Мой статус", "✅ Мой статус", "⏳ Мой статус", "❌ Мой статус", "🔄 Обновить статус"]))
        # Обработчик для повторной подачи заявки
        self.router.message.register(self.restart_registration, F.text == "🔄 Подать заявку снова")
        # Обработчик для кнопки "О розыгрыше"
        self.router.message.register(self.show_info_menu, F.text == "📊 О розыгрыше")
        # Обработчик для старых результатов - перенаправляем на помощь
        self.router.message.register(self.handle_results_redirect, F.text == "🏆 Результаты")
        self.router.callback_query.register(self.handle_info_callback, F.data.startswith("info_"))

    # REMOVED: start method - теперь в global_commands.py

    async def help_and_support_handler(self, message: types.Message) -> None:
        """Объединенный обработчик помощи и техподдержки - перенаправляем в support handler"""
        from bot.messages import smart_messages
        
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.update_context(
                message.from_user.id,
                UserContext.SUPPORT,
                UserAction.BUTTON_CLICK
            )
        
        support_messages = smart_messages.get_support_messages()
        menu_msg = support_messages["menu"]
        
        keyboard = get_support_menu_keyboard()
        await message.answer(
            menu_msg["text"],
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
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

    async def restart_registration(self, message: types.Message) -> None:
        """Обработчик повторной подачи заявки"""
        from bot.handlers.registration import RegistrationHandler
        from pathlib import Path
        from services.cache import get_cache
        
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.update_context(
                message.from_user.id,
                UserContext.REGISTRATION,
                UserAction.BUTTON_CLICK
            )
        
        # Создаем экземпляр обработчика регистрации и запускаем процесс
        registration_handler = RegistrationHandler(
            upload_dir=Path("uploads"),
            cache=get_cache(),
            bot=None  # Не нужен для этого действия
        )
        
        await registration_handler.start_registration(message, None)

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
        # Если нажата кнопка "Назад к меню О розыгрыше"
        if callback.data == "info_back":
            text = (
                "🎉 О нашем розыгрыше\n\n"
                "ℹ️ Выберите раздел для подробной информации:"
            )
            await callback.message.edit_text(text, reply_markup=get_info_menu_keyboard())
            await callback.answer()
            return
        
        mapping = {
            "info_rules": (
                "🗒 *Правила участия в розыгрыше*\n\n"
                "→ Всего необходимо собрать *15 стикеров*\n"
                "→ Соберите все стикеры и приклейте на карту, сделайте фото и загрузите фото в чат-бот\n"
                "→ Получите шанс выиграть путешествие на Байкал или сертификат номиналом 200\\.000\n\n"
                "✅ *Как получить стикеры:*\n\n"
                "Совершайте покупки с картой лояльности Магнолии одним из способов:\n\n"
                "• Оплачивайте улыбкой со SberPay от 500 ₽\n"
                "• Или совершайте покупку от 1500 ₽ (обязательно с товаром бренда-партнёра)\n\n"
                "За каждую подходящую покупку вы получаете 3D-стикер с достопримечательностью Байкала\\.\n\n"
                "✏️ *Как участвовать в розыгрыше:*\n\n"
                "Соберите все стикеры и заполните ими лифлет полностью\\. Затем в этом боте укажите свои реальные данные и загрузите фото лифлета со всеми приклеенными стикерами\\.\n\n"
                "Победители определяются среди участников, собравших полную коллекцию\\!\n\n"
                "Важно, что для участия в розыгрыше главного приза необходимо оплатить покупки улыбкой со SberPay\\.\n"
                "Сертификат номиналом 200\\.000 рублей получают при покупке у партнерских брендов независимо от способа оплаты"
            ),
            "info_prizes": (
                "🏆 *Приз розыгрыша*\n\n"
                "Главный приз — *путешествие на Байкал* — выдается только при оплате покупок улыбкой со SberPay.\n\n"
                "При покупке товаров у брендов-партнеров участникам выдается другой приз — *сертификат номиналом 200.000 рублей*\\*\n\n"
                "\\*Важно, что для участия в розыгрыше главного приза необходимо оплатить покупки улыбкой со SberPay\\.\n"
                "Сертификат номиналом 200\\.000 рублей получают при покупке у партнерских брендов независимо от способа оплаты\\.\n\n"
                "🏔️ *Ваше приключение начинается здесь!*"
            ),
            "info_schedule": (
                "📅 *Сроки проведения акции*\n\n"
                "Акция «Путешествие по Москве» проходит с *15 октября по 15 декабря 2025 года*."
            ),
            "info_fairness": (
                "⚖️ *Гарантии честности*\n\n"
                "Используем проверяемый алгоритм выбора, ведем трансляции и публикуем статистику."
            ),
        }
        
        # Создаем кнопку "Назад" для возврата к меню "О розыгрыше"
        back_button = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Назад к меню", callback_data="info_back")]
        ])
        
        await callback.message.edit_text(
            mapping.get(callback.data, "Информация недоступна."),
            parse_mode="Markdown",
            reply_markup=back_button
        )
        await callback.answer()


def setup_common_handlers(dispatcher) -> CommonHandlers:
    handler = CommonHandlers()
    handler.setup(dispatcher)
    return handler

