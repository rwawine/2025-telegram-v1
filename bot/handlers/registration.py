"""Registration handlers with batching for database writes."""

from __future__ import annotations

import asyncio
import uuid
import logging
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict, List

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

from bot.states import RegistrationStates
from database.repositories import get_participant_status, insert_participants_batch
from utils.validators import validate_full_name, validate_phone, validate_loyalty_card, normalize_phone
from bot.keyboards import (
    get_main_menu_keyboard_for_user,
    get_name_input_keyboard,
    get_phone_input_keyboard,
    get_loyalty_card_keyboard,
    get_photo_upload_keyboard,
    get_status_keyboard,
)
from bot.context_manager import UserContext, UserAction
from bot.messages import smart_messages

BATCH_SIZE = 25
BATCH_TIMEOUT = 0.5


class RegistrationHandler:
    def __init__(self, upload_dir: Path, cache, bot) -> None:
        self.router = Router()
        self.batch: List[Dict[str, Any]] = []
        self.lock = asyncio.Lock()
        self.flush_task = asyncio.create_task(self._periodic_flush())
        self.upload_dir = upload_dir
        self.cache = cache
        self.bot = bot
        self._register_handlers()

    def setup(self, dispatcher) -> None:
        # КРИТИЧЕСКИ ВАЖНО: Регистрация роутера с ВЫСШИМ приоритетом
        # В aiogram последний зарегистрированный роутер имеет ПРИОРИТЕТ
        # Этот роутер должен регистрироваться ПОСЛЕ fallback handlers
        # для гарантированного приоритета обработки сообщений в состояниях регистрации
        dispatcher.include_router(self.router)
        dispatcher.shutdown.register(self.shutdown)

    def _register_handlers(self) -> None:
        # Entry points and main actions
        self.router.message.register(self.start_registration, F.text.contains("регистрац"))
        self.router.message.register(self.start_registration, F.text == "🚀 Начать регистрацию")
        
        # Agreement handlers REMOVED - теперь в global_commands.py
        # REMOVED: handle_status (теперь в common.py)
        # REMOVED: back_to_menu с "Главное меню" (теперь в global_commands.py)

        # Navigation within flow (should run before field validation handlers)
        # REMOVED: back_to_menu с "Назад в меню" (теперь в global_commands.py)
        self.router.message.register(self.back_to_name, F.text.contains("Назад к имени"))
        self.router.message.register(self.back_to_phone, F.text.contains("Назад к телефону"))
        self.router.message.register(self.back_to_card, F.text.contains("Назад к карте"))
        self.router.message.register(self.ask_take_photo, RegistrationStates.upload_photo, F.text.contains("Сделать фото"))
        self.router.message.register(self.ask_choose_gallery, RegistrationStates.upload_photo, F.text.contains("галере"))
        # Убрали обработчик reply-кнопки "лифлет" - теперь используем инлайн-кнопку

        # Content-type aware guards (must be before main state handlers)
        # Name step: help button handler BEFORE validation
        self.router.message.register(self.help_enter_name, RegistrationStates.enter_name, F.text.contains("❓ Как правильно ввести имя"))
        
        # Name step: block non-text and premature phone/contact
        self.router.message.register(self.name_unexpected_contact, RegistrationStates.enter_name, F.contact)
        self.router.message.register(self.name_unexpected_photo, RegistrationStates.enter_name, F.photo)
        self.router.message.register(self.name_unexpected_document, RegistrationStates.enter_name, F.document)
        self.router.message.register(self.name_unexpected_sticker, RegistrationStates.enter_name, F.sticker)
        self.router.message.register(self.name_unexpected_media, RegistrationStates.enter_name, F.video)
        self.router.message.register(self.name_unexpected_media, RegistrationStates.enter_name, F.voice)
        self.router.message.register(self.name_unexpected_media, RegistrationStates.enter_name, F.audio)
        self.router.message.register(self.name_unexpected_media, RegistrationStates.enter_name, F.location)

        # Phone step: help button handler BEFORE validation
        self.router.message.register(self.help_enter_phone, RegistrationStates.enter_phone, F.text.contains("❓ Проблемы с номером"))
        
        # Phone step: block irrelevant content (contact is handled separately below)
        self.router.message.register(self.phone_unexpected_photo, RegistrationStates.enter_phone, F.photo)
        self.router.message.register(self.phone_unexpected_document, RegistrationStates.enter_phone, F.document)
        self.router.message.register(self.phone_unexpected_sticker, RegistrationStates.enter_phone, F.sticker)
        self.router.message.register(self.phone_unexpected_media, RegistrationStates.enter_phone, F.video)
        self.router.message.register(self.phone_unexpected_media, RegistrationStates.enter_phone, F.voice)
        self.router.message.register(self.phone_unexpected_media, RegistrationStates.enter_phone, F.audio)
        self.router.message.register(self.phone_unexpected_media, RegistrationStates.enter_phone, F.location)

        # Loyalty card step: help button handler BEFORE validation
        self.router.message.register(self.help_find_card_number, RegistrationStates.enter_loyalty_card, F.text.contains("❓ Где найти номер карты"))
        
        # Loyalty card step: block non-text
        self.router.message.register(self.card_unexpected_photo, RegistrationStates.enter_loyalty_card, F.photo)
        self.router.message.register(self.card_unexpected_document, RegistrationStates.enter_loyalty_card, F.document)
        self.router.message.register(self.card_unexpected_sticker, RegistrationStates.enter_loyalty_card, F.sticker)
        self.router.message.register(self.card_unexpected_media, RegistrationStates.enter_loyalty_card, F.video)
        self.router.message.register(self.card_unexpected_media, RegistrationStates.enter_loyalty_card, F.voice)
        self.router.message.register(self.card_unexpected_media, RegistrationStates.enter_loyalty_card, F.audio)
        self.router.message.register(self.card_unexpected_media, RegistrationStates.enter_loyalty_card, F.location)

        # Photo step: block text and non-photo content
        self.router.message.register(self.photo_unexpected_text, RegistrationStates.upload_photo, F.text)
        self.router.message.register(self.photo_unexpected_document, RegistrationStates.upload_photo, F.document)
        self.router.message.register(self.photo_unexpected_sticker, RegistrationStates.upload_photo, F.sticker)
        self.router.message.register(self.photo_unexpected_media, RegistrationStates.upload_photo, F.video)
        self.router.message.register(self.photo_unexpected_media, RegistrationStates.upload_photo, F.voice)
        self.router.message.register(self.photo_unexpected_media, RegistrationStates.upload_photo, F.audio)
        self.router.message.register(self.photo_unexpected_media, RegistrationStates.upload_photo, F.location)

        # CRITICAL FIX: Missing callback handlers for confirmation keyboard
        self.router.callback_query.register(self.handle_edit_name, F.data == "edit_name")
        self.router.callback_query.register(self.handle_edit_phone, F.data == "edit_phone")
        self.router.callback_query.register(self.handle_edit_card, F.data == "edit_card")
        self.router.callback_query.register(self.handle_edit_photo, F.data == "edit_photo")
        self.router.callback_query.register(self.handle_confirm_registration, F.data == "confirm_registration")
        self.router.callback_query.register(self.handle_cancel_registration, F.data == "cancel_registration")
        
        # Добавляем обработчик инлайн-кнопки "Что такое лифлет?"
        self.router.callback_query.register(self.handle_explain_leaflet_callback, F.data == "explain_leaflet")

        # Registration flow
        self.router.message.register(self.enter_name, RegistrationStates.enter_name, F.text)
        # IMPORTANT: limit phone step handler to text only so contacts go to handle_contact
        self.router.message.register(self.enter_phone, RegistrationStates.enter_phone, F.text)
        # IMPORTANT: limit loyalty card handler to text only to prevent processing other content types
        self.router.message.register(self.enter_loyalty_card, RegistrationStates.enter_loyalty_card, F.text)
        self.router.message.register(self.upload_photo, RegistrationStates.upload_photo, F.photo)

        # Special inputs
        self.router.message.register(self.handle_contact, RegistrationStates.enter_phone, F.contact)
        
        # Repeat submission guard - обрабатывает любые сообщения при повторной попытке регистрации
        self.router.message.register(self.handle_repeat_submission, RegistrationStates.repeat_submission_guard)

    async def start_registration(self, message: types.Message, state: FSMContext) -> None:
        # Обновляем контекст пользователя
        from bot.context_manager import get_context_manager
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.update_context(
                message.from_user.id,
                UserContext.REGISTRATION,
                UserAction.BUTTON_CLICK
            )
        
        # Проверяем статус пользователя - блокируем повторную регистрацию
        from database.repositories import get_participant_status
        from bot.keyboards.main_menu import get_status_keyboard
        
        user_status = await get_participant_status(message.from_user.id)
        
        if user_status == "pending":
            await state.update_data(repeat_reason="pending")
            await state.set_state(RegistrationStates.repeat_submission_guard)
            await message.answer(
                "⏳ **Ваша заявка уже на модерации**\n\n"
                "📋 Статус: На рассмотрении\n"
                "⏰ Результат придет в течение 24 часов\n"
                "🔔 Мы обязательно уведомим вас о решении\n\n"
                "💡 Пока можете изучить подробности розыгрыша",
                reply_markup=get_status_keyboard(),
                parse_mode="Markdown"
            )
            return
        
        if user_status == "approved":
            await state.update_data(repeat_reason="approved")
            await state.set_state(RegistrationStates.repeat_submission_guard)
            await message.answer(
                "✅ **Вы уже зарегистрированы!**\n\n"
                "🎉 Поздравляем! Вы участвуете в розыгрыше!\n"
                "📋 Статус: Одобрена\n\n"
                "💡 Следите за обновлениями в чате",
                reply_markup=get_status_keyboard(),
                parse_mode="Markdown"
            )
            return
        
        # Начинаем регистрацию с ввода имени
        await message.answer(
            "🎯 Шаг 1 из 4: Ваше имя\n\n"
            "📝 Введите только ваше имя как в документе\n\n"
            "✅ Примеры:\n"
            "• Алексей\n"
            "• Анна-Мария\n"
            "• Жан-Поль\n"
            "• О'Коннор\n\n"
            "❌ Избегайте: фамилий, отчеств, цифр, пробелов\n\n"
            "💡 Это важно для корректного оформления приза\n\n"
            "📊 Прогресс: 🟢⚪⚪⚪ (1/4)",
            reply_markup=get_name_input_keyboard(),
            parse_mode="Markdown"
        )
        await state.set_state(RegistrationStates.enter_name)

    async def enter_name(self, message: types.Message, state: FSMContext) -> None:
        """Обработчик ввода имени - должен иметь приоритет над fallback"""
        # Логируем для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"enter_name handler called for user {message.from_user.id} with text: {message.text}")
        
        full_name = message.text or ""
        
        from bot.context_manager import get_context_manager
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.update_context(
                message.from_user.id,
                UserContext.REGISTRATION,
                UserAction.TEXT_INPUT
            )
        
        # If user sends a phone number as name, guide them
        if validate_phone(full_name):
            if context_manager:
                await context_manager.increment_error_count(message.from_user.id)
            await message.answer(
                "📱 **Это похоже на номер телефона!**\n\n"
                "🎯 Сейчас нам нужно ваше **имя**\n"
                "Телефон вы укажете на следующем шаге\n\n"
                "✅ **Примеры:**\n"
                "• Алексей\n"
                "• Анна-Мария\n"
                "• Жан-Поль\n"
                "• О'Коннор",
                reply_markup=get_name_input_keyboard(),
                parse_mode="Markdown"
            )
            return
            
        if not validate_full_name(full_name):
            if context_manager:
                await context_manager.increment_error_count(message.from_user.id)
            error_messages = smart_messages.get_error_messages()
            error_msg = error_messages["name_invalid"]
            
            await message.answer(
                error_msg["text"],
                reply_markup=get_name_input_keyboard(),
                parse_mode="Markdown"
            )
            return
            
        # Успешный ввод имени
        await state.update_data(full_name=full_name)
        
        # Показываем успешное сообщение с именем
        reg_messages = smart_messages.get_registration_messages()
        success_msg = reg_messages["name_success"]["text"].format(name=full_name.split()[0])
        
        await message.answer(success_msg, parse_mode="Markdown")
        
        # Переходим к следующему шагу
        await state.set_state(RegistrationStates.enter_phone)
        phone_msg = reg_messages["start_phone"]
        
        await message.answer(
            smart_messages.format_message_with_progress(phone_msg["text"], 2),
            reply_markup=get_phone_input_keyboard(),
            parse_mode="Markdown"
        )

    async def enter_phone(self, message: types.Message, state: FSMContext) -> None:
        phone_number = message.text or ""
        if message.text == "✏️ Ввести вручную":
            await message.answer(
                "🎯 Шаг 2 из 4: Номер телефона\n\n"
                "📱 Два способа на выбор:\n"
                "• Нажать 📞 Отправить мой номер (быстро и безопасно)\n"
                "• Написать вручную в формате +79001234567\n\n"
                "🔒 Номер нужен только для связи с победителями\n\n"
                "📊 Прогресс: 🟢🟢⚪⚪ (2/4)",
                reply_markup=get_phone_input_keyboard(),
                parse_mode="Markdown"
            )
            return
        if not validate_phone(phone_number):
            # Попробуем нормализовать и валидировать еще раз
            normalized_phone = normalize_phone(phone_number)
            if not validate_phone(normalized_phone):
                await message.answer(
                    "❌ **Некорректный номер телефона**\n\n"
                    "✅ Правильно: +79001234567, +1234567890, 123-456-7890\n"
                    "❌ Неправильно: слишком короткий номер, только буквы\n\n"
                    "💡 **Поддерживаемые форматы:**\n"
                    "• Любые международные номера\n"
                    "• С кодом страны или без\n" 
                    "• От 7 до 15 цифр\n\n"
                    "📊 Прогресс: 🟢🟢⚪⚪ (2/4)",
                    reply_markup=get_phone_input_keyboard(),
                    parse_mode="Markdown"
                )
                return
            else:
                # Нормализация помогла, используем нормализованный номер
                phone_number = normalized_phone

        # Нормализуем номер телефона к единому формату
        normalized_phone = normalize_phone(phone_number)
        await state.update_data(phone_number=normalized_phone)
        await state.set_state(RegistrationStates.enter_loyalty_card)
        await message.answer(
            "🎯 Шаг 3 из 4: Карта лояльности\n\n"
            "💳 Введите номер вашей карты лояльности\n\n"
            "✅ Правильно: 1234567890123 (13 цифр) или 1234567890123456 (16 цифр)\n"
            "❌ Неправильно: 123-456, карта123, ABC12345\n\n"
            "💡 Найдите номер на **лицевой стороне** карты лояльности\n"
            "📐 Формат: 13 или 16 цифр (без пробелов и дефисов)\n\n"
            "📊 Прогресс: 🟢🟢🟢⚪ (3/4)",
            reply_markup=get_loyalty_card_keyboard(),
            parse_mode="Markdown"
        )

    async def enter_loyalty_card(self, message: types.Message, state: FSMContext) -> None:
        loyalty_card = message.text or ""
        if not validate_loyalty_card(loyalty_card):
            await message.answer(
                "❌ **Неверный номер карты**\n\n"
                "✅ Правильно: 1234567890123 (13 цифр) или 1234567890123456 (16 цифр)\n"
                "❌ Неправильно: 123-456, карта123, ABC12345\n\n"
                "💡 Найдите номер на **лицевой стороне** карты лояльности\n"
                "📐 Формат: 13 или 16 цифр (без пробелов и дефисов)\n\n"
                "📊 Прогресс: 🟢🟢🟢⚪ (3/4)",
                reply_markup=get_loyalty_card_keyboard(),
                parse_mode="Markdown"
            )
            return
        await state.update_data(loyalty_card=loyalty_card)
        await state.set_state(RegistrationStates.upload_photo)
        
        # Создаем комбинированную клавиатуру: reply-кнопки сверху + инлайн-кнопка снизу
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❓ Что такое лифлет?", callback_data="explain_leaflet")]
        ])
        
        await message.answer(
            "🎯 Шаг 4 из 4: Фото лифлета\n\n"
            "📸 Загрузите фото лифлета со всеми приклеенными стикерами\n\n"
            "✅ Способы загрузки:\n"
            "• Просто отправить фото сообщением\n"
            "• Нажать «📷 Сделать фото»\n"
            "• Нажать «🖼️ Выбрать из галереи»\n\n"
            "📐 Требования: четкое качество, размер до 10МБ\n\n"
            "📊 Прогресс: 🟢🟢🟢🟢 (4/4) - последний шаг!",
            reply_markup=get_photo_upload_keyboard(),
            parse_mode="Markdown"
        )
        
        # Добавляем инлайн-кнопку сразу следующим сообщением
        await message.answer(
            "👇 Есть вопросы?",
            reply_markup=inline_keyboard
        )

    async def upload_photo(self, message: types.Message, state: FSMContext) -> None:
        data = await state.get_data()
        file_id = message.photo[-1].file_id if message.photo else None

        # Validate photo size against config limit (Stage 7: media limits)
        try:
            from config import load_config
            max_size = load_config().max_file_size
        except Exception:
            max_size = 10 * 1024 * 1024  # Fallback 10MB

        photo_size = getattr(message.photo[-1], "file_size", None)
        if photo_size and photo_size > max_size:
            await message.answer(
                "❌ **Фото слишком большое**\n\n"
                f"📊 Размер вашего фото: {photo_size // (1024*1024)} МБ\n"
                f"📐 Максимальный размер: {max_size // (1024*1024)} МБ\n\n"
                "💡 Попробуйте:\n"
                "• Сжать фото в приложении камеры\n"
                "• Уменьшить разрешение\n"
                "• Выбрать другое фото\n\n"
                "📊 Прогресс: 🟢🟢🟢🟢 (4/4) - последний шаг!",
                reply_markup=get_photo_upload_keyboard(),
                parse_mode="Markdown"
            )
            return

        # Download photo and ensure it was saved
        photo_path = await self._download_photo(file_id) if file_id else None
        if not photo_path:
            await message.answer(
                "❌ **Не удалось сохранить фото**\n\n"
                "🔧 Попробуйте:\n"
                "• Отправить фото еще раз\n"
                "• Выбрать другое изображение\n"
                "• Проверить качество интернета\n\n"
                "💡 Фото должно быть четким и читаемым\n\n"
                "📊 Прогресс: 🟢🟢🟢🟢 (4/4) - последний шаг!",
                reply_markup=get_photo_upload_keyboard(),
                parse_mode="Markdown"
            )
            return

        await state.clear()

        record = {
            "telegram_id": message.from_user.id,
            "username": message.from_user.username,
            "full_name": data.get("full_name"),
            "phone_number": data.get("phone_number"),
            "loyalty_card": data.get("loyalty_card"),
            "photo_path": photo_path,
        }

        await self._enqueue_record(record)
        # КРИТИЧЕСКИ ВАЖНО: Принудительно записываем в БД сразу, чтобы статус был доступен
        await self._flush()
        
        await message.answer(
            "🎉 **Регистрация завершена!**\n\n"
            "✅ Ваша заявка успешно отправлена на модерацию\n"
            "⏰ Результат рассмотрения придет в течение 24 часов\n"
            "🔔 Мы обязательно уведомим вас о решении\n\n"
            "💡 А пока можете изучить подробности розыгрыша\n\n"
            "📊 Прогресс: 🟢🟢🟢🟢 (4/4) - **ЗАВЕРШЕНО!**",
            reply_markup=get_status_keyboard(),
            parse_mode="Markdown"
        )

    async def handle_status(self, message: types.Message) -> None:
        from bot.context_manager import get_context_manager, UserContext, UserAction
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.update_context(
                message.from_user.id,
                UserContext.NAVIGATION,
                UserAction.BUTTON_CLICK
            )
        
        async def loader():
            return await get_participant_status(message.from_user.id)

        status = await self.cache.get_or_set(
            key=f"status:{message.from_user.id}",
            loader=loader,
            level="hot",
        )
        
        # Получаем умное сообщение о статусе
        if status is None:
            # Пользователь не зарегистрирован
            await message.answer(
                "📝 **Вы еще не зарегистрированы**\n\n"
                "🚀 Нажмите **Начать регистрацию** чтобы принять участие в розыгрыше!\n\n"
                "⚡ Это займет всего 2-3 минуты",
                reply_markup=get_status_keyboard(),
                parse_mode="Markdown"
            )
        else:
            # Получаем умное сообщение для конкретного статуса
            username = message.from_user.first_name or "Участник"
            status_msg = smart_messages.get_status_message(status, username)
            
            await message.answer(
                status_msg["text"],
                reply_markup=get_status_keyboard(),
                parse_mode="Markdown"
            )

    # Auxiliary handlers
    async def handle_contact(self, message: types.Message, state: FSMContext) -> None:
        """Обработчик контактов (отправленного номера телефона)"""
        print(f"📞 DEBUG REGISTRATION: handle_contact called!")
        from bot.context_manager import get_context_manager
        context_manager = get_context_manager()
        
        try:
            # Проверяем, что контакт содержит номер телефона
            if not message.contact or not message.contact.phone_number:
                if context_manager:
                    await context_manager.increment_error_count(message.from_user.id)
                await message.answer(
                    "Не удалось получить номер телефона из контакта.\n"
                    "Попробуйте еще раз или введите номер вручную.",
                    reply_markup=get_phone_input_keyboard()
                )
                return
            
            phone = message.contact.phone_number
            
            # DEBUG: Логируем полученный номер
            print(f"📞 DEBUG: Received contact phone: '{phone}' (type: {type(phone)})")
            logger.info(f"📞 Received contact phone: '{phone}' (type: {type(phone)})")
            
            # Нормализуем номер телефона к единому формату
            normalized_phone = normalize_phone(phone)
            print(f"📞 DEBUG: Normalized phone: '{normalized_phone}'")
            logger.info(f"📞 Normalized phone: '{normalized_phone}'")
            
            # Валидируем нормализованный номер
            if not validate_phone(normalized_phone):
                print(f"📞 DEBUG: Phone validation failed for: '{normalized_phone}'")
                logger.warning(f"📞 Phone validation failed for: '{normalized_phone}'")
                await message.answer(
                    "❌ **Получен некорректный номер телефона**\n\n"
                    "Попробуйте ввести номер вручную.\n"
                    "Принимаются любые международные форматы.",
                    reply_markup=get_phone_input_keyboard(),
                    parse_mode="Markdown"
                )
                return
                
            # Обновляем контекст
            if context_manager:
                await context_manager.update_context(
                    message.from_user.id,
                    UserContext.REGISTRATION,
                    UserAction.CONTACT_SHARE
                )
            
            # Сохраняем нормализованный номер
            await state.update_data(phone_number=normalized_phone)
            
            # Переходим к следующему шагу
            await state.set_state(RegistrationStates.enter_loyalty_card)
            
            # Получаем умные сообщения
            reg_messages = smart_messages.get_registration_messages()
            phone_success_msg = reg_messages.get("phone_success", {
                "text": "📱 **Номер принят!**\n\n🎯 Переходим к карте лояльности...",
                "style": "encouraging"
            })
            loyalty_msg = reg_messages.get("start_loyalty_card", {
                "text": (
                    "🎯 **Шаг 3 из 4: Карта лояльности**\n\n"
                    "💳 Введите номер карты лояльности\n"
                    "📝 **Формат:** 13 или 16 цифр с лицевой стороны карты\n"
                    "✅ **Примеры:** 1234567890123 или 1234567890123456\n\n"
                    "❓ *Карту можно найти в приложении или на физической карте*"
                )
            })
            
            # Отправляем подтверждение
            await message.answer(
                phone_success_msg["text"],
                parse_mode="Markdown"
            )
            
            # Переходим к карте лояльности
            await message.answer(
                smart_messages.format_message_with_progress(loyalty_msg["text"], 3),
                reply_markup=get_loyalty_card_keyboard(),
                parse_mode="Markdown"
            )
            
        except Exception as e:
            if context_manager:
                await context_manager.increment_error_count(message.from_user.id)
            await message.answer(
                "Произошла ошибка при обработке контакта.\n"
                "Попробуйте ввести номер телефона вручную в формате +79001234567",
                reply_markup=get_phone_input_keyboard()
            )

    async def back_to_menu(self, message: types.Message, state: FSMContext) -> None:
        await state.clear()
        keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
        await message.answer("Главное меню", reply_markup=keyboard)

    async def back_to_name(self, message: types.Message, state: FSMContext) -> None:
        await state.set_state(RegistrationStates.enter_name)
        await message.answer(
            "🎯 Шаг 1 из 4: Ваше имя\n\n"
            "📝 Введите полное имя точно как в документе\n\n"
            "✅ Правильно: Иванов Иван Иванович\n"
            "❌ Неправильно: Ваня, Иван, i.ivanov\n\n"
            "💡 Это важно для корректного оформления приза\n\n"
            "📊 Прогресс: 🟢⚪⚪⚪ (1/4)",
            reply_markup=get_name_input_keyboard(),
            parse_mode="Markdown"
        )

    async def back_to_phone(self, message: types.Message, state: FSMContext) -> None:
        await state.set_state(RegistrationStates.enter_phone)
        await message.answer(
            "🎯 Шаг 2 из 4: Номер телефона\n\n"
            "📱 Два способа на выбор:\n"
            "• Нажать 📞 Отправить мой номер (быстро и безопасно)\n"
            "• Написать вручную в формате +79001234567\n\n"
            "🔒 Номер нужен только для связи с победителями\n\n"
            "📊 Прогресс: 🟢🟢⚪⚪ (2/4)",
            reply_markup=get_phone_input_keyboard(),
            parse_mode="Markdown"
        )

    async def back_to_card(self, message: types.Message, state: FSMContext) -> None:
        await state.set_state(RegistrationStates.enter_loyalty_card)
        await message.answer(
            "🎯 Шаг 3 из 4: Карта лояльности\n\n"
            "💳 Введите номер вашей карты лояльности\n\n"
            "✅ Правильно: 1234567890123456 (16 цифр)\n"
            "❌ Неправильно: 123-456, карта123, ABC12345\n\n"
            "💡 Найдите 16 цифр на **лицевой стороне** карты лояльности\n"
            "📐 Формат: ровно 16 цифр (без пробелов и дефисов)\n\n"
            "📊 Прогресс: 🟢🟢🟢⚪ (3/4)",
            reply_markup=get_loyalty_card_keyboard(),
            parse_mode="Markdown"
        )

    # ========== Content-type guards implementations ==========
    # Name step guards
    async def name_unexpected_contact(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "📞 **Телефон получен!**\n\n"
            "Но сейчас нужно **имя текстом** ✍️\n"
            "Телефон вы отправите на следующем шаге\n\n"
            "📊 Прогресс: 🟢⚪⚪⚪ (1/4) - **имя**",
            reply_markup=get_name_input_keyboard(),
            parse_mode="Markdown"
        )

    async def name_unexpected_photo(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "📸 **Красивое фото!**\n\n"
            "Но сейчас нужно **имя текстом** ✍️\n"
            "Фото понадобится на последнем шаге\n\n"
            "💡 Напишите полное имя как в паспорте\n\n"
            "📊 Прогресс: 🟢⚪⚪⚪ (1/4) - **имя**",
            reply_markup=get_name_input_keyboard(),
            parse_mode="Markdown"
        )

    async def name_unexpected_document(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "📄 **Документ получен!**\n\n"
            "Но сейчас нужно **имя текстом** ✍️\n"
            "Просто напишите полное имя следующим сообщением\n\n"
            "📊 Прогресс: 🟢⚪⚪⚪ (1/4) - **имя**",
            reply_markup=get_name_input_keyboard(),
            parse_mode="Markdown"
        )

    async def name_unexpected_sticker(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "😊 **Милый стикер!**\n\n"
            "Но сейчас нужно **имя текстом** ✍️\n"
            "Стикеры я пока не умею читать 🤖\n\n"
            "💡 Напишите имя как в документе\n\n"
            "📊 Прогресс: 🟢⚪⚪⚪ (1/4) - **имя**",
            reply_markup=get_name_input_keyboard(),
            parse_mode="Markdown"
        )

    async def name_unexpected_media(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Пожалуйста, введите полное имя текстом.\n"
            "Например: Иванов Иван Иванович",
            reply_markup=get_name_input_keyboard(),
        )

    # Phone step guards (contact handled separately)
    async def phone_unexpected_photo(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "📸 **Фото получено!**\n\n"
            "Но сейчас нужно **номер телефона** 📱\n"
            "Фото понадобится на последнем шаге\n\n"
            "💡 Нажмите «📞 Отправить мой номер» или напишите +79001234567\n\n"
            "📊 Прогресс: 🟢🟢⚪⚪ (2/4) - **телефон**",
            reply_markup=get_phone_input_keyboard(),
            parse_mode="Markdown"
        )

    async def phone_unexpected_document(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "📄 **Документ получен!**\n\n"
            "Но сейчас нужно **номер телефона** 📱\n\n"
            "💡 **Два способа:**\n"
            "• Нажать «📞 Отправить мой номер»\n"
            "• Написать в формате +79001234567\n\n"
            "📊 Прогресс: 🟢🟢⚪⚪ (2/4) - **телефон**",
            reply_markup=get_phone_input_keyboard(),
            parse_mode="Markdown"
        )

    async def phone_unexpected_sticker(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "😊 **Стикер принят!**\n\n"
            "Но сейчас нужно **номер телефона** 📱\n"
            "Стикеры я читать пока не умею 🤖\n\n"
            "💡 Нажмите «📞 Отправить мой номер» - это быстро и безопасно\n\n"
            "📊 Прогресс: 🟢🟢⚪⚪ (2/4) - **телефон**",
            reply_markup=get_phone_input_keyboard(),
            parse_mode="Markdown"
        )

    async def phone_unexpected_media(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "🎥 **Медиа получено!**\n\n"
            "Но сейчас нужно **номер телефона текстом** 📱\n\n"
            "✅ Правильно: +79001234567, +79123456789\n"
            "💡 Или просто нажмите «📞 Отправить мой номер»\n\n"
            "📊 Прогресс: 🟢🟢⚪⚪ (2/4) - **телефон**",
            reply_markup=get_phone_input_keyboard(),
            parse_mode="Markdown"
        )

    # Loyalty card step guards
    async def card_unexpected_photo(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "📸 **Фото получено!**\n\n"
            "Но сейчас нужно **номер карты лояльности текстом** 💳\n"
            "Фото понадобится на следующем шаге\n\n"
            "✅ Правильно: 1234567890123 (13 цифр) или 1234567890123456 (16 цифр)\n\n"
            "📊 Прогресс: 🟢🟢🟢⚪ (3/4) - **карта**",
            reply_markup=get_loyalty_card_keyboard(),
            parse_mode="Markdown"
        )

    async def card_unexpected_document(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "📄 **Документ получен!**\n\n"
            "Но сейчас нужно **номер карты лояльности текстом** 💳\n\n"
            "✅ Правильно: 1234567890123 (13 цифр) или 1234567890123456 (16 цифр)\n"
            "📐 Формат: 13 или 16 цифр с лицевой стороны карты\n\n"
            "📊 Прогресс: 🟢🟢🟢⚪ (3/4) - **карта**",
            reply_markup=get_loyalty_card_keyboard(),
            parse_mode="Markdown"
        )

    async def card_unexpected_sticker(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "😊 **Классный стикер!**\n\n"
            "Но сейчас нужно **номер карты лояльности** 💳\n"
            "Стикеры я пока не читаю 🤖\n\n"
            "💡 Найдите карту в приложении магазина или кошельке\n\n"
            "📊 Прогресс: 🟢🟢🟢⚪ (3/4) - **карта**",
            reply_markup=get_loyalty_card_keyboard(),
            parse_mode="Markdown"
        )

    async def card_unexpected_media(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "🎥 **Медиа получено!**\n\n"
            "Но нужно **номер карты лояльности текстом** 💳\n\n"
            "✅ Правильно: 1234567890123 (13 цифр) или 1234567890123456 (16 цифр)\n"
            "❌ Неправильно: abc-123, карта123, 12/34\n\n"
            "📊 Прогресс: 🟢🟢🟢⚪ (3/4) - **карта**",
            reply_markup=get_loyalty_card_keyboard(),
            parse_mode="Markdown"
        )

    # Photo step guards
    async def photo_unexpected_text(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "📝 **Текст получен!**\n\n"
            "Но сейчас нужно **фото лифлета** 📸\n\n"
            "💡 **Способы отправки:**\n"
            "• Нажать «📷 Сделать фото»\n"
            "• Нажать «🖼️ Выбрать из галереи»\n"
            "• Просто прислать фото сообщением\n\n"
            "📊 Прогресс: 🟢🟢🟢🟢 (4/4) - последний шаг!",
            reply_markup=get_photo_upload_keyboard(),
            parse_mode="Markdown"
        )

    async def photo_unexpected_document(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "📄 **Документ получен!**\n\n"
            "Но нужно именно **фото** (не файл) 📸\n\n"
            "💡 Лифлет должен быть сфотографирован как изображение\n"
            "📱 Используйте камеру телефона или галерею\n\n"
            "📊 Прогресс: 🟢🟢🟢🟢 (4/4) - последний шаг!",
            reply_markup=get_photo_upload_keyboard(),
            parse_mode="Markdown"
        )

    async def photo_unexpected_sticker(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "😊 **Забавный стикер!**\n\n"
            "Но нужно **фото лифлета** 📸\n"
            "Стикеры не подойдут для модерации\n\n"
            "💡 Сфотографируйте настоящий лифлет события\n\n"
            "📊 Прогресс: 🟢🟢🟢🟢 (4/4) - последний шаг!",
            reply_markup=get_photo_upload_keyboard(),
            parse_mode="Markdown"
        )

    async def photo_unexpected_media(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "🎥 **Медиа получено!**\n\n"
            "Но нужно именно **фото** лифлета 📸\n"
            "Видео и аудио не подходят\n\n"
            "💡 Отправьте обычное фото одним сообщением\n\n"
            "📊 Прогресс: 🟢🟢🟢🟢 (4/4) - последний шаг!",
            reply_markup=get_photo_upload_keyboard(),
            parse_mode="Markdown"
        )

    async def ask_take_photo(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "📷 **Делаем фото!**\n\n"
            "🎯 Откройте камеру на телефоне и сфотографируйте лифлет\n\n"
            "💡 **Советы для хорошего фото:**\n"
            "• Хорошее освещение\n"
            "• Весь лифлет в кадре\n"
            "• Четкое изображение\n"
            "• Без бликов и теней\n\n"
            "📤 Затем отправьте фото в этот чат\n\n"
            "📊 Прогресс: 🟢🟢🟢🟢 (4/4) - последний шаг!",
            reply_markup=get_photo_upload_keyboard(),
            parse_mode="Markdown"
        )

    async def ask_choose_gallery(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "🖼️ **Выбираем из галереи!**\n\n"
            "📱 Откройте галерею и найдите фото лифлета\n\n"
            "✅ **Убедитесь что фото:**\n"
            "• Четкое и читаемое\n"
            "• Содержит весь лифлет\n"
            "• Хорошего качества\n\n"
            "📤 Выберите фото и отправьте в этот чат\n\n"
            "📊 Прогресс: 🟢🟢🟢🟢 (4/4) - последний шаг!",
            reply_markup=get_photo_upload_keyboard(),
            parse_mode="Markdown"
        )

    async def explain_leaflet(self, message: types.Message) -> None:
        await message.answer(
            "🎨 **Что такое лифлет?**\n\n"
            "📄 Лифлет - это специальная листовка для сбора стикеров\n\n"
            "✅ **Как его получить:**\n"
            "• Приобрести в любом магазине сети Магнолия за 29,90 рублей\n"
            "• Скачать с официального сайта Акции https://play.mgnl.ru/\n\n"
            "🏆 Победитель определяется среди тех, кто собрал полную коллекцию!",
            parse_mode="Markdown"
        )

    async def help_enter_name(self, message: types.Message, state: FSMContext) -> None:
        """Обработчик кнопки помощи '❓ Как правильно ввести имя?' - показывает подсказку без изменения состояния"""
        await message.answer(
            "✍️ **Как правильно ввести имя?**\n\n"
            "📝 **Правильные примеры:**\n"
            "• Алексей\n"
            "• Анна-Мария\n"
            "• Жан-Поль\n"
            "• О'Коннор\n"
            "• Мария\n\n"
            "❌ **Неправильные примеры:**\n"
            "• Иванов Иван (фамилия + имя)\n"
            "• Иван Иванович (имя + отчество)\n"
            "• Ваня123 (цифры)\n"
            "• i.ivanov (латиница)\n\n"
            "💡 **Правила:**\n"
            "• Только имя (без фамилии и отчества)\n"
            "• Допускаются дефисы и апострофы\n"
            "• Минимум 2 символа\n\n"
            "📊 Прогресс: 🟢⚪⚪⚪ (1/4)",
            reply_markup=get_name_input_keyboard(),
            parse_mode="Markdown"
        )

    async def help_enter_phone(self, message: types.Message, state: FSMContext) -> None:
        """Обработчик кнопки помощи '❓ Проблемы с номером?' - показывает подсказку без изменения состояния"""
        await message.answer(
            "📱 **Как ввести номер телефона?**\n\n"
            "✅ **Правильные форматы:**\n"
            "• +79001234567\n"
            "• +1234567890\n"
            "• 89001234567\n"
            "• 123-456-7890\n\n"
            "❌ **Неправильные примеры:**\n"
            "• 123 (слишком короткий)\n"
            "• abc123 (содержит буквы)\n"
            "• 12 (менее 7 цифр)\n\n"
            "💡 **Два способа ввода:**\n"
            "1️⃣ **Быстро:** Нажмите кнопку «📞 Отправить мой номер»\n"
            "   • Безопасно и быстро\n"
            "   • Гарантирует правильность\n\n"
            "2️⃣ **Вручную:** Напишите номер текстом\n"
            "   • Любой международный формат\n"
            "   • От 7 до 15 цифр\n"
            "   • С кодом страны или без\n\n"
            "📊 Прогресс: 🟢🟢⚪⚪ (2/4)",
            reply_markup=get_phone_input_keyboard(),
            parse_mode="Markdown"
        )

    async def help_find_card_number(self, message: types.Message, state: FSMContext) -> None:
        """Обработчик кнопки помощи '❓ Где найти номер карты?' - показывает подсказку без изменения состояния"""
        await message.answer(
            "💳 **Где найти номер карты лояльности?**\n\n"
            "📍 **Физическая карта:**\n"
            "• На лицевой стороне карты\n"
            "• Обычно это 13 или 16 цифр крупным шрифтом\n"
            "• Может быть разбит на группы по 4 цифры\n\n"
            "📱 **Мобильное приложение:**\n"
            "• Откройте приложение Магнолия\n"
            "• Перейдите в раздел «Моя карта» или «Профиль»\n"
            "• Номер отображается на экране карты\n\n"
            "✅ **Пример:** 1234567890123456\n\n"
            "💡 **Введите только цифры, без пробелов и дефисов**\n\n"
            "📊 Прогресс: 🟢🟢🟢⚪ (3/4)",
            reply_markup=get_loyalty_card_keyboard(),
            parse_mode="Markdown"
        )

    async def handle_explain_leaflet_callback(self, callback: types.CallbackQuery) -> None:
        """Обработчик инлайн-кнопки 'Что такое лифлет?' - показывает информацию без изменения состояния"""
        await callback.answer()  # Убираем индикатор загрузки
        
        await callback.message.answer(
            "🎨 **Что такое лифлет?**\n\n"
            "📄 Лифлет - это специальная листовка для сбора стикеров\n\n"
            "✅ **Как его получить:**\n"
            "• Приобрести в любом магазине сети Магнолия за 29,90 рублей\n"
            "• Скачать с официального сайта Акции https://play.mgnl.ru/\n\n"
            "🏆 Победитель определяется среди тех, кто собрал полную коллекцию!",
            parse_mode="Markdown"
        )

    async def _enqueue_record(self, record: Dict[str, Any]) -> None:
        async with self.lock:
            self.batch.append(record)
            if len(self.batch) >= BATCH_SIZE:
                await self._flush()

    async def _flush(self) -> None:
        if not self.batch:
            return
        async with self.lock:
            batch = self.batch[:]
            self.batch.clear()

        await insert_participants_batch(batch)
        for record in batch:
            self.cache.invalidate(f"status:{record['telegram_id']}")

    async def _download_photo(self, file_id: str) -> str | None:
        try:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{uuid.uuid4().hex}.jpg"
            destination = self.upload_dir / filename
            await self.bot.download(file_id, destination=str(destination))
            return destination.as_posix()
        except Exception:
            return None

    async def _periodic_flush(self) -> None:
        while True:
            await asyncio.sleep(BATCH_TIMEOUT)
            await self._flush()

    async def shutdown(self) -> None:
        self.flush_task.cancel()
        with suppress(asyncio.CancelledError):
            await self.flush_task
        await self._flush()

    # CRITICAL FIX: Missing callback handlers implementation
    async def handle_edit_name(self, callback: types.CallbackQuery, state: FSMContext) -> None:
        """Handle edit name button in confirmation"""
        await callback.answer()
        await state.set_state(RegistrationStates.enter_name)
        await callback.message.edit_text(
            "🎯 Шаг 1 из 4: Ваше имя\n\n"
            "📝 Введите полное имя точно как в документе\n\n"
            "✅ Правильно: Иванов Иван Иванович\n"
            "❌ Неправильно: Ваня, Иван, i.ivanov\n\n"
            "💡 Это важно для корректного оформления приза\n\n"
            "📊 Прогресс: 🟢⚪⚪⚪ (1/4)",
            parse_mode="Markdown"
        )
        await callback.message.answer(
            "👆 Напишите новое имя:",
            reply_markup=get_name_input_keyboard()
        )

    async def handle_edit_phone(self, callback: types.CallbackQuery, state: FSMContext) -> None:
        """Handle edit phone button in confirmation"""
        await callback.answer()
        await state.set_state(RegistrationStates.enter_phone)
        await callback.message.edit_text(
            "🎯 Шаг 2 из 4: Номер телефона\n\n"
            "📱 Два способа на выбор:\n"
            "• Нажать 📞 Отправить мой номер (быстро и безопасно)\n"
            "• Написать вручную в формате +79001234567\n\n"
            "🔒 Номер нужен только для связи с победителями\n\n"
            "📊 Прогресс: 🟢🟢⚪⚪ (2/4)",
            parse_mode="Markdown"
        )
        await callback.message.answer(
            "📱 Отправьте новый номер телефона:",
            reply_markup=get_phone_input_keyboard()
        )

    async def handle_edit_card(self, callback: types.CallbackQuery, state: FSMContext) -> None:
        """Handle edit loyalty card button in confirmation"""
        await callback.answer()
        await state.set_state(RegistrationStates.enter_loyalty_card)
        await callback.message.edit_text(
            "🎯 Шаг 3 из 4: Карта лояльности\n\n"
            "💳 Введите номер вашей карты лояльности\n\n"
            "✅ Правильно: 1234567890123 (13 цифр) или 1234567890123456 (16 цифр)\n"
            "❌ Неправильно: 123-456, карта123, ABC12345\n\n"
            "💡 Найдите номер на **лицевой стороне** карты лояльности\n"
            "📐 Формат: 13 или 16 цифр (без пробелов и дефисов)\n\n"
            "📊 Прогресс: 🟢🟢🟢⚪ (3/4)",
            parse_mode="Markdown"
        )
        await callback.message.answer(
            "💳 Введите новый номер карты:",
            reply_markup=get_loyalty_card_keyboard()
        )

    async def handle_edit_photo(self, callback: types.CallbackQuery, state: FSMContext) -> None:
        """Handle edit photo button in confirmation"""
        await callback.answer()
        await state.set_state(RegistrationStates.upload_photo)
        await callback.message.edit_text(
            "🎯 Шаг 4 из 4: Фото лифлета\n\n"
            "📸 Загрузите фото рекламного лифлета мероприятия\n\n"
            "✅ Способы загрузки:\n"
            "• Просто отправить фото сообщением\n"
            "• Нажать «📷 Сделать фото»\n"
            "• Нажать «🖼️ Выбрать из галереи»\n\n"
            "💡 **Что такое лифлет?** Рекламная листовка или баннер события\n"
            "📐 Требования: четкое качество, размер до 10МБ\n\n"
            "📊 Прогресс: 🟢🟢🟢🟢 (4/4) - последний шаг!",
            parse_mode="Markdown"
        )
        await callback.message.answer(
            "📸 Отправьте новое фото:",
            reply_markup=get_photo_upload_keyboard()
        )

    async def handle_confirm_registration(self, callback: types.CallbackQuery, state: FSMContext) -> None:
        """Handle final registration confirmation"""
        await callback.answer("✅ Обрабатываем регистрацию...")
        
        data = await state.get_data()
        await state.clear()

        record = {
            "telegram_id": callback.from_user.id,
            "username": callback.from_user.username,
            "full_name": data.get("full_name"),
            "phone_number": data.get("phone_number"),
            "loyalty_card": data.get("loyalty_card"),
            "photo_path": data.get("photo_path"),
        }

        await self._enqueue_record(record)
        # КРИТИЧЕСКИ ВАЖНО: Принудительно записываем в БД сразу, чтобы статус был доступен
        await self._flush()
        
        await callback.message.edit_text(
            "🎉 **Поздравляем! Регистрация завершена!**\n\n"
            "✅ Ваша заявка успешно отправлена на модерацию\n"
            "⏰ Результат рассмотрения придет в течение 24 часов\n"
            "🔔 Мы обязательно уведомим вас о решении\n\n"
            "💡 А пока можете изучить подробности розыгрыша\n\n"
            "📊 **СТАТУС:** 🟢🟢🟢🟢 ЗАВЕРШЕНО!\n"
            "🎯 Вы в игре! Удачи в розыгрыше! 🍀",
            parse_mode="Markdown"
        )
        
        keyboard = await get_main_menu_keyboard_for_user(callback.from_user.id)
        await callback.message.answer("Что дальше?", reply_markup=keyboard)

    async def handle_cancel_registration(self, callback: types.CallbackQuery, state: FSMContext) -> None:
        """Handle registration cancellation"""
        await callback.answer()
        await state.clear()
        
        await callback.message.edit_text(
            "❌ **Регистрация отменена**\n\n"
            "🗑️ Все введенные данные удалены\n"
            "🔄 Вы можете начать заново в любое время\n\n"
            "💡 Для участия в розыгрыше регистрация обязательна\n\n"
            "📊 Прогресс сброшен: ⚪⚪⚪⚪ (0/4)",
            parse_mode="Markdown"
        )
        
        keyboard = await get_main_menu_keyboard_for_user(callback.from_user.id)
        await callback.message.answer("Главное меню:", reply_markup=keyboard)

    async def handle_repeat_submission(self, message: types.Message, state: FSMContext) -> None:
        """Обработчик повторных попыток регистрации - показывает актуальный статус и очищает состояние"""
        data = await state.get_data()
        reason = data.get("repeat_reason", "unknown")
        
        # Обновляем контекст
        from bot.context_manager import get_context_manager, UserContext, UserAction
        context_manager = get_context_manager()
        if context_manager:
            await context_manager.update_context(
                message.from_user.id,
                UserContext.NAVIGATION,
                UserAction.TEXT_INPUT
            )
        
        # Получаем актуальный статус
        user_status = await get_participant_status(message.from_user.id)
        
        if user_status == "pending":
            await message.answer(
                "⏳ **Ваша заявка уже на модерации**\n\n"
                "📋 Статус: На рассмотрении\n"
                "⏰ Результат придет в течение 24 часов\n"
                "🔔 Мы обязательно уведомим вас о решении\n\n"
                "💡 Пока можете изучить подробности розыгрыша",
                reply_markup=get_status_keyboard(),
                parse_mode="Markdown"
            )
        elif user_status == "approved":
            await message.answer(
                "✅ **Вы уже зарегистрированы!**\n\n"
                "🎉 Поздравляем! Вы участвуете в розыгрыше!\n"
                "📋 Статус: Одобрена\n\n"
                "💡 Следите за обновлениями в чате",
                reply_markup=get_status_keyboard(),
                parse_mode="Markdown"
            )
        else:
            # Если статус изменился или не найден, очищаем состояние и предлагаем начать заново
            await message.answer(
                "📝 **Вы еще не зарегистрированы**\n\n"
                "🚀 Нажмите **Начать регистрацию** чтобы принять участие в розыгрыше!\n\n"
                "⚡ Это займет всего 2-3 минуты",
                reply_markup=get_status_keyboard(),
                parse_mode="Markdown"
            )
        
        # Очищаем состояние после показа статуса
        await state.clear()
        
        # Предлагаем главное меню
        keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
        await message.answer("Главное меню:", reply_markup=keyboard)


def setup_registration_handlers(dispatcher, *, upload_dir: Path, cache, bot) -> RegistrationHandler:
    handler = RegistrationHandler(upload_dir=upload_dir, cache=cache, bot=bot)
    handler.setup(dispatcher)
    return handler

