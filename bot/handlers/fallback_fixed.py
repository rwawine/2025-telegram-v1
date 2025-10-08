"""ИСПРАВЛЕННАЯ система fallback-обработчиков с правильной логикой FSM."""

from __future__ import annotations

import random
from typing import Dict, Any

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.context_manager import get_context_manager, UserContext, UserAction
from bot.states import RegistrationStates
from bot.keyboards import (
    get_main_menu_keyboard_for_user,
    get_support_menu_keyboard,
    get_name_input_keyboard,
    get_phone_input_keyboard,
    get_loyalty_card_keyboard,
    get_photo_upload_keyboard
)


class FixedSmartFallbackHandler:
    """ИСПРАВЛЕННЫЙ умный обработчик с правильной логикой FSM"""
    
    def __init__(self):
        self.router = Router()
        self.router.name = "smart_fallback"
        self._register_handlers()
        self._register_quick_nav_handlers()  # Регистрируем сразу
    
    def setup(self, dispatcher) -> None:
        # Fallback handlers должны быть последними (самый низкий приоритет)
        dispatcher.include_router(self.router)
    
    def _register_handlers(self):
        """Регистрация умных fallback обработчиков"""
        
        # ИСПРАВЛЕНИЕ: Убираем раннее возвращение при наличии состояния!
        # Теперь fallback handlers работают и в FSM состояниях
        
        # Обработчик для всех неожиданных текстовых сообщений (самый низкий приоритет)
        # ИСКЛЮЧАЕМ ВСЕ FSM состояния регистрации - они должны обрабатываться специальными обработчиками
        self.router.message.register(
            self.handle_unexpected_text,
            F.text,
            ~StateFilter(RegistrationStates.enter_name),
            ~StateFilter(RegistrationStates.enter_phone),
            ~StateFilter(RegistrationStates.enter_loyalty_card),
            ~StateFilter(RegistrationStates.upload_photo),
        )
        
        # Обработчики для разных типов контента
        self.router.message.register(
            self.handle_unexpected_sticker,
            F.sticker,
        )
        
        self.router.message.register(
            self.handle_unexpected_voice,
            F.voice | F.video_note,
        )
        
        self.router.message.register(
            self.handle_unexpected_media,
            F.video | F.audio | F.animation | F.document,
        )
        
        self.router.message.register(
            self.handle_unexpected_photo,
            F.photo,
            ~StateFilter(RegistrationStates.upload_photo),  # НЕ обрабатывать в состоянии upload_photo
        )
        
        self.router.message.register(
            self.handle_unexpected_contact,
            F.contact,
            ~StateFilter(RegistrationStates.enter_phone),  # НЕ обрабатывать в состоянии enter_phone
        )
        
        self.router.message.register(
            self.handle_unexpected_location,
            F.location | F.venue,
        )
        
        # Обработчик для неизвестных callback queries
        self.router.callback_query.register(
            self.handle_unknown_callback,
        )
    
    async def handle_unexpected_text(self, message: types.Message, state: FSMContext):
        """ИСПРАВЛЕННЫЙ обработчик неожиданных текстовых сообщений"""
        
        current_state = await state.get_state()
        context_manager = get_context_manager()
        
        # ВАЖНО: Не возвращаемся раньше времени!
        # Проверяем, обработал ли кто-то это сообщение в своем состоянии
        
        if context_manager:
            await context_manager.update_context(
                message.from_user.id, 
                UserContext.CONFUSED if current_state else UserContext.NAVIGATION,
                UserAction.TEXT_INPUT
            )
        
        # Если пользователь в FSM состоянии, помогаем контекстуально
        if current_state:
            await self._provide_fsm_help(message, state, current_state)
        else:
            # Если нет состояния, проверяем на запутанность
            is_confused = False
            if context_manager:
                try:
                    is_confused = await context_manager.detect_user_confusion(message.from_user.id, message, state)
                except Exception:
                    is_confused = False
            
            if is_confused:
                await self._handle_confused_user(message, state)
            else:
                # Простое нейтральное сообщение для неизвестного текста
                await message.answer(
                    "🤔 **Не совсем понял ваш запрос.**\n\n"
                    "💡 **Попробуйте:**\n"
                    "📋 Проверить свой статус\n"
                    "📊 Узнать о розыгрыше\n"
                    "💬 Связаться с поддержкой\n\n"
                    "👇 Используйте кнопки меню ниже:",
                    parse_mode="Markdown"
                )
                keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
                await message.answer("Выберите действие:", reply_markup=keyboard)
    
    async def _provide_fsm_help(self, message: types.Message, state: FSMContext, current_state: str):
        """Контекстная помощь для пользователей в FSM состояниях"""
        
        state_help_map = {
            "RegistrationStates:enter_name": {
                "message": "📝 **Сейчас нужно ввести имя**\n\n"
                          "✅ **Примеры:**\n"
                          "• Алексей\n"
                          "• Анна-Мария\n"
                          "• Жан-Поль\n"
                          "• О'Коннор\n\n"
                          "❌ **Избегайте:** фамилий, отчеств, цифр, пробелов\n\n"
                          "💡 *Введите только ваше имя*",
                "keyboard": get_name_input_keyboard(),
                "wrong_content_hints": {
                    "phone": "📱 Телефон вы укажете на следующем шаге!",
                    "photo": "📸 Фото понадобится в конце регистрации!",
                    "contact": "📞 Контакт пригодится для телефона!"
                }
            },
            "RegistrationStates:enter_phone": {
                "message": "📱 **Сейчас нужен номер телефона**\n\n"
                          "✅ **Два способа:**\n"
                          "• Нажать **📞 Отправить мой номер**\n"
                          "• Написать в формате **+79001234567**\n\n"
                          "💡 *Используйте действующий номер*",
                "keyboard": get_phone_input_keyboard(),
                "wrong_content_hints": {
                    "name": "✅ Имя уже сохранено! Теперь телефон.",
                    "photo": "📸 Фото будет последним шагом!"
                }
            },
            "RegistrationStates:enter_loyalty_card": {
                "message": "💳 **Сейчас нужен номер карты лояльности**\n\n"
                          "✅ **Формат:** ровно 16 цифр\n"
                          "✅ **Где найти:** на лицевой стороне карты\n"
                          "✅ **Пример:** 1234567890123456\n\n"
                          "💡 *Найдите карту в приложении или кошельке*",
                "keyboard": get_loyalty_card_keyboard()
            },
            "RegistrationStates:upload_photo": {
                "message": "📸 **Последний шаг - фото лифлета!**\n\n"
                          "🎨 **Лифлет** = рекламная листовка/баннер\n\n"
                          "✅ **Как отправить:**\n"
                          "• Нажать **📷 Сделать фото**\n"
                          "• Нажать **🖼️ Выбрать из галереи**\n"
                          "• Просто прислать фото сообщением\n\n"
                          "💡 *Фото должно быть четким и читаемым*",
                "keyboard": get_photo_upload_keyboard()
            },
            "SupportStates:entering_message": {
                "message": "💬 **Создание обращения в поддержку**\n\n"
                          "✅ **Опишите проблему подробно:**\n"
                          "• Что произошло?\n"
                          "• На каком этапе?\n"
                          "• Какие ошибки видите?\n\n"
                          "📎 *Можете приложить фото или документ*",
                "keyboard": None  # Используется клавиатура из support handler
            }
        }
        
        help_info = state_help_map.get(current_state)
        if not help_info:
            # Fallback для неизвестных состояний
            await message.answer(
                f"🤔 **Не уверен, что сейчас нужно делать**\n\n"
                f"📍 Текущее состояние: `{current_state}`\n\n"
                f"💡 Попробуйте:\n"
                f"• `/cancel` - отменить текущее действие\n"
                f"• `/start` - начать заново\n"
                f"• `/help` - получить помощь",
                parse_mode="Markdown"
            )
            return
        
        # Проверяем тип контента и даем специфическую подсказку
        content_hint = ""
        if message.photo:
            content_hint = help_info.get("wrong_content_hints", {}).get("photo", "")
        elif message.contact:
            content_hint = help_info.get("wrong_content_hints", {}).get("contact", "")
        elif self._looks_like_phone(message.text):
            content_hint = help_info.get("wrong_content_hints", {}).get("phone", "")
        elif self._looks_like_name(message.text) and "phone" in current_state:
            content_hint = help_info.get("wrong_content_hints", {}).get("name", "")
        
        response = help_info["message"]
        if content_hint:
            response = f"{content_hint}\n\n{response}"
        
        await message.answer(
            response,
            reply_markup=help_info["keyboard"],
            parse_mode="Markdown"
        )
    
    def _looks_like_phone(self, text: str) -> bool:
        """Проверяет, похож ли текст на номер телефона"""
        if not text:
            return False
        clean_text = ''.join(c for c in text if c.isdigit() or c == '+')
        return len(clean_text) >= 10 and (clean_text.startswith('+') or clean_text.startswith('7') or clean_text.startswith('8'))
    
    def _looks_like_name(self, text: str) -> bool:
        """Проверяет, похож ли текст на имя"""
        if not text:
            return False
        words = text.split()
        return len(words) >= 2 and all(word.isalpha() or word.replace('-', '').isalpha() for word in words)
    
    async def handle_unexpected_sticker(self, message: types.Message, state: FSMContext):
        """Обработка стикеров с учетом FSM состояния"""
        current_state = await state.get_state()
        
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.increment_error_count(message.from_user.id)
            witty_responses = context_manager.get_witty_responses()["sticker_in_registration"]
            response = random.choice(witty_responses)
        else:
            response = "😊 Стикер принят! Но сейчас нужно что-то другое."
        
        await message.answer(response)
        
        # Предлагаем контекстную помощь с учетом FSM состояния
        if current_state:
            await self._provide_fsm_help(message, state, current_state)
        else:
            # Простое сообщение без проверки статуса
            await message.answer(
                "😊 **Спасибо за стикер!**\n\n"
                "🤔 Но сейчас стикеры не требуются.\n\n"
                "👇 Используйте кнопки меню ниже:",
                parse_mode="Markdown"
            )
            keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
            await message.answer("Выберите действие:", reply_markup=keyboard)
    
    async def handle_unexpected_voice(self, message: types.Message, state: FSMContext):
        """Обработка голосовых сообщений с учетом FSM состояния"""
        current_state = await state.get_state()
        
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.increment_error_count(message.from_user.id)
            witty_responses = context_manager.get_witty_responses()["voice_unexpected"]
            response = random.choice(witty_responses)
        else:
            response = "🎤 Голосовое сообщение получено! Но сейчас нужен текст."
        
        await message.answer(response)
        
        if current_state:
            await self._provide_fsm_help(message, state, current_state)
        else:
            # Простое сообщение без проверки статуса
            await message.answer(
                "🎤 **Спасибо за голосовое сообщение!**\n\n"
                "🤔 Но сейчас голосовые сообщения не обрабатываются.\n\n"
                "👇 Используйте кнопки меню ниже:",
                parse_mode="Markdown"
            )
            keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
            await message.answer("Выберите действие:", reply_markup=keyboard)
    
    async def handle_unexpected_media(self, message: types.Message, state: FSMContext):
        """Обработка неожиданного медиа контента с учетом FSM состояния"""
        current_state = await state.get_state()
        
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.increment_error_count(message.from_user.id)
        
        content_type_map = {
            'video': 'видео 🎥',
            'audio': 'аудио 🎵', 
            'animation': 'GIF 🎬',
            'document': 'документ 📄'
        }
        
        content_type = None
        for msg_type, display_name in content_type_map.items():
            if hasattr(message, msg_type) and getattr(message, msg_type):
                content_type = display_name
                break
        
        if not content_type:
            content_type = "медиа 📎"
        
        await message.answer(
            f"📎 {content_type} получен! Но в данный момент мне нужно что-то другое.\n\n"
            f"🎯 Давайте я подскажу, что сейчас лучше отправить:"
        )
        
        if current_state:
            await self._provide_fsm_help(message, state, current_state)
        else:
            # Простое сообщение без проверки статуса
            await message.answer(
                f"📎 **{content_type} получен!**\n\n"
                f"🤔 Но сейчас такие файлы не требуются.\n\n"
                "👇 Используйте кнопки меню ниже:",
                parse_mode="Markdown"
            )
            keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
            await message.answer("Выберите действие:", reply_markup=keyboard)
    
    async def handle_unexpected_photo(self, message: types.Message, state: FSMContext):
        """Обработка фото в неожиданных местах"""
        current_state = await state.get_state()
        
        # Если пользователь в каком-то FSM состоянии (но не upload_photo)
        if current_state:
            context_manager = get_context_manager()
            if context_manager:
                await context_manager.increment_error_count(message.from_user.id)
            
            await message.answer(
                "📸 Красивое фото! Но сейчас оно не подходит для текущего шага.\n\n"
                "🔄 Давайте разберемся, что нужно сделать:"
            )
            
            await self._provide_fsm_help(message, state, current_state)
        else:
            # Для фото вне FSM состояния - простое сообщение без проверки статуса
            await message.answer(
                "📸 **Спасибо за фото!**\n\n"
                "🤔 Но сейчас фотографии не требуются.\n\n"
                "💡 **Что вы можете сделать:**\n"
                "📋 Проверить свой статус участия\n"
                "📊 Узнать о розыгрыше\n"
                "💬 Связаться с поддержкой\n\n"
                "👇 Используйте кнопки меню ниже:",
                parse_mode="Markdown"
            )
            keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
            await message.answer("Выберите действие:", reply_markup=keyboard)
    
    async def handle_unexpected_contact(self, message: types.Message, state: FSMContext):
        """Обработка контакта в неожиданных местах"""
        current_state = await state.get_state()
        
        # Если пользователь в каком-то FSM состоянии (но не enter_phone - фильтр исключает)
        
        if current_state:
            context_manager = get_context_manager()
            if context_manager:
                await context_manager.increment_error_count(message.from_user.id)
            
            await message.answer(
                "📱 Спасибо за контакт! Но сейчас он пригодится на другом этапе.\n\n"
                "🧭 Позвольте направить вас:"
            )
            
            await self._provide_fsm_help(message, state, current_state)
        else:
            # Простое сообщение без проверки статуса
            await message.answer(
                "📱 **Спасибо за контакт!**\n\n"
                "🤔 Но сейчас контакты не требуются.\n\n"
                "👇 Используйте кнопки меню ниже:",
                parse_mode="Markdown"
            )
            keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
            await message.answer("Выберите действие:", reply_markup=keyboard)
    
    async def handle_unexpected_location(self, message: types.Message, state: FSMContext):
        """Обработка геолокации"""
        current_state = await state.get_state()
        
        if current_state:
            await message.answer(
                "🗺️ Интересное место! Но для нашего розыгрыша геолокация не нужна.\n\n"
                "🎯 Давайте вернемся к главному:"
            )
            await self._provide_fsm_help(message, state, current_state)
        else:
            # Простое сообщение без проверки статуса
            await message.answer(
                "🗺️ **Спасибо за геолокацию!**\n\n"
                "🤔 Но сейчас геолокация не требуется.\n\n"
                "👇 Используйте кнопки меню ниже:",
                parse_mode="Markdown"
            )
            keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
            await message.answer("Выберите действие:", reply_markup=keyboard)
    
    async def _handle_confused_user(self, message: types.Message, state: FSMContext):
        """Помощь запутавшемуся пользователю"""
        
        context_manager = get_context_manager()
        if context_manager:
            confusion_responses = context_manager.get_witty_responses()["confusion_general"]
            response = random.choice(confusion_responses)
        else:
            response = "🤔 Кажется, что-то пошло не так. Давайте начнем сначала!"
        
        await message.answer(f"{response}\n\n🚀 **Быстрый перезапуск:**")
        
        # Создаем кнопки для быстрой навигации
        quick_nav = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="quick_nav_main"),
                InlineKeyboardButton(text="🚀 К регистрации", callback_data="quick_nav_register")
            ],
            [
                InlineKeyboardButton(text="💬 В поддержку", callback_data="quick_nav_support"),
                InlineKeyboardButton(text="❓ Помощь", callback_data="quick_nav_help")
            ]
        ])
        
        await message.answer(
            "🎯 **Куда направимся?**\n\n"
            "Выберите, что вы хотели сделать:",
            reply_markup=quick_nav
        )
    
    def _register_quick_nav_handlers(self) -> None:
        """Регистрация обработчиков для быстрых inline-действий навигации."""

        @self.router.callback_query(F.data == "quick_nav_main")
        async def quick_nav_main(callback: types.CallbackQuery, state: FSMContext):
            await state.clear()
            keyboard = await get_main_menu_keyboard_for_user(callback.from_user.id)
            await callback.message.edit_text(
                "🏠 **Главное меню**\n\nВыберите нужный раздел:",
                reply_markup=keyboard
            )
            await callback.answer()

        @self.router.callback_query(F.data == "quick_nav_register")
        async def quick_nav_register(callback: types.CallbackQuery, state: FSMContext):
            from bot.states import RegistrationStates
            await state.set_state(RegistrationStates.enter_name)
            await callback.message.edit_text(
                "🚀 **Регистрация участника**\n\nВведите ваше полное имя (как в документе).\nНапример: Иванов Иван Иванович"
            )
            await callback.message.answer(
                "👆 Напишите имя в следующем сообщении:",
                reply_markup=get_name_input_keyboard()
            )
            await callback.answer()

        @self.router.callback_query(F.data == "quick_nav_support")
        async def quick_nav_support(callback: types.CallbackQuery, state: FSMContext):
            await state.clear()
            await callback.message.edit_text(
                "💬 **Центр поддержки**\n\nВыберите, что вас интересует:"
            )
            await callback.message.answer(
                "Чем можем помочь?",
                reply_markup=get_support_menu_keyboard()
            )
            await callback.answer()

        @self.router.callback_query(F.data == "quick_nav_cancel")
        async def quick_nav_cancel(callback: types.CallbackQuery, state: FSMContext):
            # Эквивалент /cancel: очищаем состояние и возвращаемся в меню
            await state.clear()
            keyboard = await get_main_menu_keyboard_for_user(callback.from_user.id)
            await callback.message.edit_text(
                "❌ **Действие отменено**\n\n🏠 Возвращаемся в главное меню",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            await callback.answer()

        @self.router.callback_query(F.data == "quick_nav_help")  # noqa: F841
        async def quick_nav_help(callback: types.CallbackQuery):
            """Handle quick help navigation"""
            help_text = (
                "❓ **БЫСТРАЯ СПРАВКА**\n\n"
                "🚀 **Регистрация** - подать заявку на участие в розыгрыше\n"
                "📋 **Мой статус** - проверить статус вашей заявки\n" 
                "💬 **Поддержка** - задать вопрос или сообщить о проблеме\n"
                "📊 **О розыгрыше** - правила, призы и сроки\n\n"
                "🎯 **Для участия нужно:**\n"
                "1️⃣ Полное имя (как в документе)\n"
                "2️⃣ Номер телефона\n"
                "3️⃣ Номер карты лояльности\n"
                "4️⃣ Фото лифлета\n\n"
                "⚡ **Экстренные команды:**\n"
                "• `/start` - перезапуск бота\n"
                "• `/cancel` - отменить текущее действие\n"
                "• `/help` - получить помощь"
            )
            
            await callback.message.edit_text(help_text, parse_mode="Markdown")
            await callback.answer()
    
    async def handle_unknown_callback(self, callback: types.CallbackQuery):
        """Обработка неизвестных callback запросов"""
        await callback.answer(
            "🤖 Эта кнопка больше не активна или произошла ошибка.\n"
            "Попробуйте вернуться в главное меню.",
            show_alert=True
        )


def setup_fixed_fallback_handlers(dispatcher) -> FixedSmartFallbackHandler:
    """Настройка ИСПРАВЛЕННЫХ fallback обработчиков"""
    handler = FixedSmartFallbackHandler()
    handler.setup(dispatcher)
    return handler
