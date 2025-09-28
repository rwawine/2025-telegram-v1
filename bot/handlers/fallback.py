"""Универсальная система fallback-обработчиков для всех неочевидных действий пользователя."""

from __future__ import annotations

import random
from typing import Dict, Any

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.context_manager import get_context_manager, UserContext, UserAction
from bot.keyboards import (
    get_main_menu_keyboard_for_user,
    get_support_menu_keyboard,
    get_name_input_keyboard,
    get_phone_input_keyboard,
    get_loyalty_card_keyboard,
    get_photo_upload_keyboard
)


class SmartFallbackHandler:
    """Умный обработчик для всех неожиданных действий пользователя"""
    
    def __init__(self):
        self.router = Router()
        self._register_handlers()
    
    def setup(self, dispatcher) -> None:
        # В aiogram 3.x приоритеты не поддерживаются напрямую на include_router
        dispatcher.include_router(self.router)
    
    def _register_handlers(self):
        """Регистрация универсальных fallback обработчиков"""
        
        # Обработчик для всех неожиданных текстовых сообщений (самый низкий приоритет)
        self.router.message.register(
            self.handle_unexpected_text,
            F.text,
        )
        
        # Обработчики для разных типов контента в неожиданных местах
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
        )
        
        self.router.message.register(
            self.handle_unexpected_contact,
            F.contact,
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
        """Обработчик неожиданных текстовых сообщений"""
        
        from bot.context_manager import get_context_manager
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.update_context(
                message.from_user.id, 
                UserContext.CONFUSED, 
                UserAction.TEXT_INPUT
            )
        
        # Проверяем, запутался ли пользователь
        is_confused = False
        context_manager = get_context_manager()
        if context_manager:
            try:
                is_confused = await context_manager.detect_user_confusion(message.from_user.id, message, state)
            except Exception:
                is_confused = False
        
        if is_confused:
            await self._handle_confused_user(message, state)
        else:
            await self._provide_contextual_help(message, state)
    
    async def handle_unexpected_sticker(self, message: types.Message, state: FSMContext):
        """Обработка стикеров в неожиданных местах"""
        await context_manager.increment_error_count(message.from_user.id)
        
        witty_responses = context_manager.get_witty_responses()["sticker_in_registration"]
        response = random.choice(witty_responses)
        
        await message.answer(response)
        
        # Предлагаем контекстную помощь
        await self._provide_contextual_help(message, state, is_media_error=True)
    
    async def handle_unexpected_voice(self, message: types.Message, state: FSMContext):
        """Обработка голосовых сообщений"""
        await context_manager.increment_error_count(message.from_user.id)
        
        witty_responses = context_manager.get_witty_responses()["voice_unexpected"]
        response = random.choice(witty_responses)
        
        await message.answer(response)
        await self._provide_contextual_help(message, state, is_media_error=True)
    
    async def handle_unexpected_media(self, message: types.Message, state: FSMContext):
        """Обработка неожиданного медиа контента"""
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
        
        await self._provide_contextual_help(message, state, is_media_error=True)
    
    async def handle_unexpected_photo(self, message: types.Message, state: FSMContext):
        """Обработка фото в неожиданных местах"""
        current_state = await state.get_state()
        
        # Если мы НЕ в состоянии загрузки фото, то это неожиданно
        if not current_state or "upload_photo" not in current_state:
            await context_manager.increment_error_count(message.from_user.id)
            
            await message.answer(
                "📸 Красивое фото! Но сейчас оно не подходит для текущего шага.\n\n"
                "🔄 Давайте разберемся, что нужно сделать:"
            )
            
            await self._provide_contextual_help(message, state, is_media_error=True)
    
    async def handle_unexpected_contact(self, message: types.Message, state: FSMContext):
        """Обработка контакта в неожиданных местах"""
        current_state = await state.get_state()
        
        if not current_state or "enter_phone" not in current_state:
            await context_manager.increment_error_count(message.from_user.id)
            
            await message.answer(
                "📱 Спасибо за контакт! Но сейчас он пригодится на другом этапе.\n\n"
                "🧭 Позвольте направить вас:"
            )
            
            await self._provide_contextual_help(message, state, is_media_error=True)
    
    async def handle_unexpected_location(self, message: types.Message, state: FSMContext):
        """Обработка геолокации"""
        await message.answer(
            "🗺️ Интересное место! Но для нашего розыгрыша геолокация не нужна.\n\n"
            "🎯 Давайте вернемся к главному:"
        )
        
        keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
        await message.answer("Выберите нужный раздел:", reply_markup=keyboard)
    
    async def handle_unknown_callback(self, callback: types.CallbackQuery):
        """Обработка неизвестных callback запросов"""
        await callback.answer(
            "🤖 Эта кнопка больше не активна или произошла ошибка.\n"
            "Попробуйте вернуться в главное меню.",
            show_alert=True
        )
    
    async def _handle_confused_user(self, message: types.Message, state: FSMContext):
        """Помощь запутавшемуся пользователю"""
        
        confusion_responses = context_manager.get_witty_responses()["confusion_general"]
        response = random.choice(confusion_responses)
        
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
        
        # Регистрируем обработчики для быстрой навигации
        self._register_quick_nav_handlers()
    
    async def _provide_contextual_help(self, message: types.Message, state: FSMContext, is_media_error: bool = False):
        """Предоставление контекстной помощи"""
        
        suggestion = None
        context_manager = get_context_manager()
        if context_manager:
            try:
                suggestion = await context_manager.get_smart_suggestion(message.from_user.id, message, state)
            except (AttributeError, Exception):
                # Метод get_smart_suggestion недоступен или ошибка, используем fallback
                suggestion = None
        
        if suggestion:
            # Строим сообщение с подсказкой
            help_text = f"💡 **{suggestion['message']}**"
            
            if 'next_step_hint' in suggestion:
                help_text += f"\n\n🔮 **Что дальше:** {suggestion['next_step_hint']}"
            
            await message.answer(help_text)
            
            # Показываем клавиатуру в зависимости от контекста
            context = suggestion.get('context', '')
            keyboard = None
            
            if 'registration_name' in context:
                keyboard = get_name_input_keyboard()
            elif 'registration_phone' in context:
                keyboard = get_phone_input_keyboard() 
            elif 'registration_photo' in context:
                keyboard = get_photo_upload_keyboard()
            elif 'support' in context:
                keyboard = get_support_menu_keyboard()
            else:
                keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
            
            if keyboard:
                await message.answer("Выберите действие:", reply_markup=keyboard)
        else:
            # Общая помощь если нет специфических предложений
            keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
            await message.answer(
                "🤔 Не совсем понял, что вы хотели сделать.\n\n"
                "🏠 Давайте начнем с главного меню:",
                reply_markup=keyboard
            )
    
    def _register_quick_nav_handlers(self):
        """Регистрация обработчиков быстрой навигации"""
        
        @self.router.callback_query(F.data == "quick_nav_main")
        async def nav_to_main(callback: types.CallbackQuery, state: FSMContext):
            await state.clear()
            keyboard = await get_main_menu_keyboard_for_user(callback.from_user.id)
            await callback.message.edit_text(
                "🏠 **Главное меню**\n\nВыберите нужный раздел:",
                reply_markup=keyboard
            )
            await callback.answer()
        
        @self.router.callback_query(F.data == "quick_nav_register") 
        async def nav_to_register(callback: types.CallbackQuery, state: FSMContext):
            # Перенаправляем к регистрации
            from bot.states import RegistrationStates
            await state.set_state(RegistrationStates.enter_name)
            await callback.message.edit_text(
                "🚀 **Регистрация участника**\n\n"
                "Введите ваше полное имя (как в документе).\n"
                "Например: Иванов Иван Иванович"
            )
            await callback.message.answer(
                "👆 Напишите имя в следующем сообщении:",
                reply_markup=get_name_input_keyboard()
            )
            await callback.answer()
        
        @self.router.callback_query(F.data == "quick_nav_support")
        async def nav_to_support(callback: types.CallbackQuery, state: FSMContext):
            await state.clear()
            await callback.message.edit_text(
                "💬 **Центр поддержки**\n\n"
                "Выберите, что вас интересует:"
            )
            await callback.message.answer(
                "Чем можем помочь?",
                reply_markup=get_support_menu_keyboard()
            )
            await callback.answer()
        
        @self.router.callback_query(F.data == "quick_nav_help")
        async def nav_to_help(callback: types.CallbackQuery):
            help_text = (
                "❓ **Краткая справка**\n\n"
                "🚀 **Регистрация** - подать заявку на участие в розыгрыше\n"
                "📋 **Мой статус** - проверить статус вашей заявки\n" 
                "💬 **Техподдержка** - задать вопрос или сообщить о проблеме\n"
                "📊 **О розыгрыше** - правила, призы и сроки\n\n"
                "🎯 **Для участия нужно:**\n"
                "1️⃣ Полное имя\n"
                "2️⃣ Номер телефона\n"
                "3️⃣ Номер карты лояльности\n"
                "4️⃣ Фото лифлета"
            )
            
            await callback.message.edit_text(help_text)
            await callback.answer()


def setup_fallback_handlers(dispatcher) -> SmartFallbackHandler:
    """Настройка fallback обработчиков"""
    handler = SmartFallbackHandler()
    handler.setup(dispatcher)
    return handler
