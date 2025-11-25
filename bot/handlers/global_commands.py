"""Глобальные команды, которые работают в любом состоянии FSM."""

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import SkipHandler

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
        self.router.message.register(self.handle_menu, Command("menu"))
        
        # Обработчики соглашения на обработку персональных данных
        from bot.states import RegistrationStates
        self.router.message.register(self.handle_agreement_accept, RegistrationStates.accept_agreement, F.text == "✅ Согласен, принимаю")
        self.router.message.register(self.handle_agreement_decline, RegistrationStates.accept_agreement, F.text == "❌ Не согласен, не принимаю")
        
        # Блокировка всех действий для тех, кто отказался от соглашения
        self.router.message.register(self.block_declined_user, RegistrationStates.declined_agreement)
        
        # Экстренная навигация - работает везде
        self.router.message.register(self.emergency_menu, F.text == "🆘 МЕНЮ")
        self.router.message.register(self.emergency_cancel, F.text == "❌ ОТМЕНА")
        
        # Кнопка "Назад в меню" из любого состояния, НО НЕ в состояниях регистрации
        # В состояниях регистрации эти кнопки должны обрабатываться специальными обработчиками
        # Используем точное совпадение, чтобы не перехватывать кнопку "⬅️ Назад в меню" в состояниях регистрации
        from bot.states import RegistrationStates
        self.router.message.register(
            self.back_to_menu, 
            F.text == "⬅️ Назад в меню",
            ~StateFilter(RegistrationStates.enter_name),
            ~StateFilter(RegistrationStates.enter_phone),
            ~StateFilter(RegistrationStates.enter_loyalty_card),
            ~StateFilter(RegistrationStates.upload_photo),
            ~StateFilter(RegistrationStates.repeat_submission_guard),
        )
        
        # Кнопка "Главное меню" из любого состояния (включая поддержку), НО НЕ в состояниях регистрации
        self.router.message.register(
            self.back_to_menu, 
            F.text == "🏠 Главное меню",
            ~StateFilter(RegistrationStates.enter_name),
            ~StateFilter(RegistrationStates.enter_phone),
            ~StateFilter(RegistrationStates.enter_loyalty_card),
            ~StateFilter(RegistrationStates.upload_photo),
            ~StateFilter(RegistrationStates.repeat_submission_guard),
        )
    
    async def handle_start(self, message: types.Message, state: FSMContext) -> None:
        """Команда /start - сбрасывает состояние и показывает соглашение или меню"""
        from database.repositories import get_participant_status, check_user_agreement
        from bot.messages import smart_messages
        from bot.states import RegistrationStates
        
        # Проверяем текущее состояние
        current_state = await state.get_state()
        
        # Очищаем состояние
        await state.clear()
        
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
        
        # Проверяем, принял ли пользователь соглашение ранее
        agreement_accepted = await check_user_agreement(message.from_user.id)
        
        # DEBUG: Логируем для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"User {message.from_user.id}: is_registered={is_registered}, agreement_accepted={agreement_accepted}")
        
        # Если пользователь уже зарегистрирован ИЛИ ранее принял соглашение - показываем приветствие и меню
        if is_registered or agreement_accepted:
            # Показываем соответствующее приветствие
            welcome_msg = smart_messages.get_welcome_message(is_registered=is_registered)
            keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
            await message.answer(
                f"🔄 **Перезапуск бота**\n\n{welcome_msg['text']}", 
                reply_markup=keyboard, 
                parse_mode="Markdown"
            )
        else:
            # Новый пользователь или пользователь, который отказался ранее - показываем соглашение
            from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton
            
            agreement_text = (
                "✨ **Добро пожаловать в розыгрыш призов!**\n\n"
                "📋 **Соглашение на обработку персональных данных**\n\n"
                "Принимая участие в розыгрыше, ты подтверждаешь что:\n\n"
                "✅ Ты согласен на обработку твоих персональных данных\n"
                "✅ Ты принимаешь правила акции\n\n"
                "📄 Документ с полными условиями прикреплен ниже"
            )
            
            # Клавиатура с кнопками согласия
            agreement_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="✅ Согласен, принимаю")],
                    [KeyboardButton(text="❌ Не согласен, не принимаю")]
                ],
                resize_keyboard=True
            )
            
            # Отправляем PDF документ
            pdf_path = "1_6_согласие_на_обработку_персональных_данных.pdf"
            try:
                document = FSInputFile(pdf_path)
                await message.answer_document(
                    document=document,
                    caption=agreement_text,
                    parse_mode="Markdown",
                    reply_markup=agreement_keyboard
                )
            except Exception as e:
                # Если файл не найден, отправляем текст без документа
                await message.answer(
                    agreement_text,
                    parse_mode="Markdown",
                    reply_markup=agreement_keyboard
                )
            
            await state.set_state(RegistrationStates.accept_agreement)
    
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

    async def handle_menu(self, message: types.Message, state: FSMContext) -> None:
        """Команда /menu - показать главное меню и сбросить состояние"""
        await state.clear()
        keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
        await message.answer("🏠 Главное меню", reply_markup=keyboard)
    
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
    
    async def back_to_menu(self, message: types.Message, state: FSMContext) -> None:
        """Обработчик кнопки 'Назад в меню' из любого состояния"""
        # КРИТИЧЕСКИ ВАЖНО: Проверяем, не находимся ли мы в состоянии регистрации
        # Если да, то этот обработчик не должен срабатывать - есть специальный обработчик в registration.py
        from bot.states import RegistrationStates
        current_state = await state.get_state()
        
        # Если мы в состоянии регистрации, не обрабатываем здесь
        # Используем SkipHandler, чтобы явно пропустить этот обработчик и передать управление следующему
        if current_state in [
            RegistrationStates.enter_name,
            RegistrationStates.enter_phone,
            RegistrationStates.enter_loyalty_card,
            RegistrationStates.upload_photo,
            RegistrationStates.repeat_submission_guard
        ]:
            raise SkipHandler()
        
        # Очищаем FSM состояние
        await state.clear()
        
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.update_context(
                message.from_user.id,
                UserContext.NAVIGATION,
                UserAction.BUTTON_CLICK
            )
        
        # Возвращаем в главное меню
        keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
        await message.answer(
            "🏠 **Главное меню**\n\n"
            "Вы вернулись в главное меню. Все незавершенные действия отменены.",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    async def handle_agreement_accept(self, message: types.Message, state: FSMContext) -> None:
        """Обработчик согласия на обработку персональных данных"""
        await state.clear()
        
        from bot.messages import smart_messages
        from database.repositories import save_user_agreement
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"User {message.from_user.id} accepted agreement, saving to DB...")
        
        # Сохраняем согласие в БД
        await save_user_agreement(message.from_user.id)
        
        logger.info(f"User {message.from_user.id} agreement saved successfully")
        
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.update_context(
                message.from_user.id,
                UserContext.NAVIGATION,
                UserAction.BUTTON_CLICK
            )
        
        # Показываем приветственное сообщение и главное меню
        welcome_msg = smart_messages.get_welcome_message(is_registered=False)
        
        keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
        await message.answer(
            f"✅ **Благодарим за согласие!**\n\n{welcome_msg['text']}", 
            reply_markup=keyboard, 
            parse_mode="Markdown"
        )
    
    async def handle_agreement_decline(self, message: types.Message, state: FSMContext) -> None:
        """Обработчик отказа от соглашения"""
        from bot.states import RegistrationStates
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        
        # Устанавливаем состояние "отказался от соглашения"
        await state.set_state(RegistrationStates.declined_agreement)
        
        # Креативное сообщение об отказе
        creative_messages = [
            "🌟 **Мы всегда будем вас ждать!**\n\n"
            "Двери нашего розыгрыша открыты для вас в любое время.\n"
            "Как только будете готовы — мы с радостью вас встретим! 🎉\n\n"
            "Для участия в розыгрыше необходимо принять соглашение.\n"
            "Нажмите /start когда будете готовы.",
            
            "💫 **Без проблем!**\n\n"
            "Наше приглашение остается в силе.\n"
            "Когда захотите присоединиться — мы будем здесь! 🚪✨\n\n"
            "Для участия в розыгрыше необходимо принять соглашение.\n"
            "Нажмите /start когда будете готовы.",
            
            "🎭 **Решение за вами!**\n\n"
            "Байкал подождёт, а мы будем рады видеть вас снова.\n"
            "Приходите, когда будете готовы к приключениям! 🏔️\n\n"
            "Для участия в розыгрыше необходимо принять соглашение.\n"
            "Нажмите /start когда будете готовы."
        ]
        
        import random
        selected_message = random.choice(creative_messages)
        
        # Убираем клавиатуру - пользователь должен нажать /start
        from aiogram.types import ReplyKeyboardRemove
        await message.answer(
            selected_message,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
    
    async def block_declined_user(self, message: types.Message, state: FSMContext) -> None:
        """Блокировка всех действий для пользователя, отказавшегося от соглашения"""
        from aiogram.types import ReplyKeyboardRemove
        
        await message.answer(
            "⚠️ Для использования бота необходимо принять соглашение на обработку персональных данных.\n\n"
            "Нажмите /start чтобы ознакомиться с соглашением.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )


def setup_global_commands(dispatcher) -> GlobalCommandsHandler:
    """Настройка глобальных команд"""
    handler = GlobalCommandsHandler()
    handler.setup(dispatcher)
    return handler
