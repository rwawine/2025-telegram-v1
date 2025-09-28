"""Registration handlers with batching for database writes."""

from __future__ import annotations

import asyncio
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict, List

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from bot.states import RegistrationStates
from database.repositories import get_participant_status, insert_participants_batch
from utils.validators import validate_full_name, validate_phone, validate_loyalty_card
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
        dispatcher.include_router(self.router)
        dispatcher.shutdown.register(self.shutdown)

    def _register_handlers(self) -> None:
        # Entry points and main actions
        self.router.message.register(self.start_registration, F.text.contains("регистрац"))
        self.router.message.register(self.start_registration, F.text == "🚀 Начать регистрацию")
        self.router.message.register(self.start_registration, F.text == "🔄 Подать заявку снова")
        self.router.message.register(self.handle_status, F.text.contains("статус"))
        self.router.message.register(self.back_to_menu, F.text.contains("Главное меню"))

        # Navigation within flow (should run before field validation handlers)
        self.router.message.register(self.back_to_menu, F.text.contains("Назад в меню"))
        self.router.message.register(self.back_to_name, F.text.contains("Назад к имени"))
        self.router.message.register(self.back_to_phone, F.text.contains("Назад к телефону"))
        self.router.message.register(self.back_to_card, F.text.contains("Назад к карте"))
        self.router.message.register(self.ask_take_photo, RegistrationStates.upload_photo, F.text.contains("Сделать фото"))
        self.router.message.register(self.ask_choose_gallery, RegistrationStates.upload_photo, F.text.contains("галере"))
        self.router.message.register(self.explain_leaflet, F.text.contains("лифлет"))

        # Content-type aware guards (must be before main state handlers)
        # Name step: block non-text and premature phone/contact
        self.router.message.register(self.name_unexpected_contact, RegistrationStates.enter_name, F.contact)
        self.router.message.register(self.name_unexpected_photo, RegistrationStates.enter_name, F.photo)
        self.router.message.register(self.name_unexpected_document, RegistrationStates.enter_name, F.document)
        self.router.message.register(self.name_unexpected_sticker, RegistrationStates.enter_name, F.sticker)
        self.router.message.register(self.name_unexpected_media, RegistrationStates.enter_name, F.video)
        self.router.message.register(self.name_unexpected_media, RegistrationStates.enter_name, F.voice)
        self.router.message.register(self.name_unexpected_media, RegistrationStates.enter_name, F.audio)
        self.router.message.register(self.name_unexpected_media, RegistrationStates.enter_name, F.location)

        # Phone step: block irrelevant content (contact is handled separately below)
        self.router.message.register(self.phone_unexpected_photo, RegistrationStates.enter_phone, F.photo)
        self.router.message.register(self.phone_unexpected_document, RegistrationStates.enter_phone, F.document)
        self.router.message.register(self.phone_unexpected_sticker, RegistrationStates.enter_phone, F.sticker)
        self.router.message.register(self.phone_unexpected_media, RegistrationStates.enter_phone, F.video)
        self.router.message.register(self.phone_unexpected_media, RegistrationStates.enter_phone, F.voice)
        self.router.message.register(self.phone_unexpected_media, RegistrationStates.enter_phone, F.audio)
        self.router.message.register(self.phone_unexpected_media, RegistrationStates.enter_phone, F.location)

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

        # Registration flow
        self.router.message.register(self.enter_name, RegistrationStates.enter_name)
        self.router.message.register(self.enter_phone, RegistrationStates.enter_phone)
        self.router.message.register(self.enter_loyalty_card, RegistrationStates.enter_loyalty_card)
        self.router.message.register(self.upload_photo, RegistrationStates.upload_photo, F.photo)

        # Special inputs
        self.router.message.register(self.handle_contact, RegistrationStates.enter_phone, F.contact)

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
        
        # Получаем умное сообщение для ввода имени
        reg_messages = smart_messages.get_registration_messages()
        name_msg = reg_messages["start_name"]
        
        await message.answer(
            smart_messages.format_message_with_progress(name_msg["text"], 1),
            reply_markup=get_name_input_keyboard(),
            parse_mode="Markdown"
        )
        await state.set_state(RegistrationStates.enter_name)

    async def enter_name(self, message: types.Message, state: FSMContext) -> None:
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
                "🎯 Сейчас нам нужно ваше **полное имя**\n"
                "Телефон вы укажете на следующем шаге\n\n"
                "✅ **Например:** Иванов Иван Иванович",
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
                "Введите номер телефона в формате +7XXXXXXXXXX",
                reply_markup=get_phone_input_keyboard(),
            )
            return
        if not validate_phone(phone_number):
            await message.answer(
                "Некорректный номер телефона. Пример: +79001234567.\n"
                "Или нажмите «📞 Отправить мой номер».",
                reply_markup=get_phone_input_keyboard(),
            )
            return
        await state.update_data(phone_number=phone_number)
        await state.set_state(RegistrationStates.enter_loyalty_card)
        await message.answer(
            "Введите номер карты лояльности (латинские буквы и цифры, 6–20 символов).\n"
            "Например: ABC12345",
            reply_markup=get_loyalty_card_keyboard(),
        )

    async def enter_loyalty_card(self, message: types.Message, state: FSMContext) -> None:
        loyalty_card = message.text or ""
        if not validate_loyalty_card(loyalty_card):
            await message.answer(
                "Неверный номер карты. Используйте латинские буквы и цифры (6–20 символов).\n"
                "Пример: ABC12345",
                reply_markup=get_loyalty_card_keyboard(),
            )
            return
        await state.update_data(loyalty_card=loyalty_card)
        await state.set_state(RegistrationStates.upload_photo)
        await message.answer(
            "Загрузите фото лифлета: отправьте одно фото сообщением.\n"
            "Если не получается — нажмите «📷 Сделать фото» или «🖼️ Выбрать из галереи».",
            reply_markup=get_photo_upload_keyboard(),
        )

    async def upload_photo(self, message: types.Message, state: FSMContext) -> None:
        data = await state.get_data()
        file_id = message.photo[-1].file_id if message.photo else None
        await state.clear()

        record = {
            "telegram_id": message.from_user.id,
            "username": message.from_user.username,
            "full_name": data.get("full_name"),
            "phone_number": data.get("phone_number"),
            "loyalty_card": data.get("loyalty_card"),
            "photo_path": await self._download_photo(file_id) if file_id else None,
        }

        await self._enqueue_record(record)
        await message.answer(
            "Спасибо! Ваша заявка отправлена на модерацию.\n"
            "Мы уведомим вас, когда модератор примет решение.",
            reply_markup=get_status_keyboard(),
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
        try:
            phone = message.contact.phone_number
        except Exception:
            await message.answer("Не удалось получить номер. Введите вручную", reply_markup=get_phone_input_keyboard())
            return
        await state.update_data(phone_number=phone)
        await state.set_state(RegistrationStates.enter_loyalty_card)
        await message.answer("Введите номер карты лояльности", reply_markup=get_loyalty_card_keyboard())

    async def back_to_menu(self, message: types.Message, state: FSMContext) -> None:
        await state.clear()
        keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
        await message.answer("Главное меню", reply_markup=keyboard)

    async def back_to_name(self, message: types.Message, state: FSMContext) -> None:
        await state.set_state(RegistrationStates.enter_name)
        await message.answer(
            "Введите ваше полное имя (как в документе). Например: Иванов Иван Иванович",
            reply_markup=get_name_input_keyboard(),
        )

    async def back_to_phone(self, message: types.Message, state: FSMContext) -> None:
        await state.set_state(RegistrationStates.enter_phone)
        await message.answer(
            "Введите номер телефона в формате +7XXXXXXXXXX или нажмите «📞 Отправить мой номер»",
            reply_markup=get_phone_input_keyboard(),
        )

    async def back_to_card(self, message: types.Message, state: FSMContext) -> None:
        await state.set_state(RegistrationStates.enter_loyalty_card)
        await message.answer(
            "Введите номер карты лояльности (латинские буквы и цифры, 6–20 символов).\n"
            "Например: ABC12345",
            reply_markup=get_loyalty_card_keyboard(),
        )

    # ========== Content-type guards implementations ==========
    # Name step guards
    async def name_unexpected_contact(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "На этом шаге нужно ввести полное имя текстом. Телефон вы отправите на следующем шаге.",
            reply_markup=get_name_input_keyboard(),
        )

    async def name_unexpected_photo(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Фото получено, но сейчас нужно ввести полное имя текстом.\n"
            "Например: Иванов Иван Иванович",
            reply_markup=get_name_input_keyboard(),
        )

    async def name_unexpected_document(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Пожалуйста, отправьте полное имя текстом, без файлов.\n"
            "Например: Иванов Иван Иванович",
            reply_markup=get_name_input_keyboard(),
        )

    async def name_unexpected_sticker(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Стикер — это мило 😊 Но сейчас нужно ввести полное имя текстом.",
            reply_markup=get_name_input_keyboard(),
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
            "Сейчас нужно отправить номер телефона текстом или нажать «📞 Отправить мой номер».",
            reply_markup=get_phone_input_keyboard(),
        )

    async def phone_unexpected_document(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Пожалуйста, отправьте номер телефона текстом или нажмите «📞 Отправить мой номер».",
            reply_markup=get_phone_input_keyboard(),
        )

    async def phone_unexpected_sticker(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Стикер принят 😊 Но нужен номер телефона. Пример: +79001234567",
            reply_markup=get_phone_input_keyboard(),
        )

    async def phone_unexpected_media(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Пожалуйста, отправьте номер телефона текстом. Пример: +79001234567",
            reply_markup=get_phone_input_keyboard(),
        )

    # Loyalty card step guards
    async def card_unexpected_photo(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Сейчас нужно ввести номер карты лояльности текстом. Пример: ABC12345",
            reply_markup=get_loyalty_card_keyboard(),
        )

    async def card_unexpected_document(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Пожалуйста, отправьте номер карты текстом. Пример: ABC12345",
            reply_markup=get_loyalty_card_keyboard(),
        )

    async def card_unexpected_sticker(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Стикер — это классно 😊 Но нужен номер карты. Пример: ABC12345",
            reply_markup=get_loyalty_card_keyboard(),
        )

    async def card_unexpected_media(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Пожалуйста, отправьте номер карты текстом. Пример: ABC12345",
            reply_markup=get_loyalty_card_keyboard(),
        )

    # Photo step guards
    async def photo_unexpected_text(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "На этом шаге нужно отправить фото лифлета.\n"
            "Нажмите «📷 Сделать фото» или «🖼️ Выбрать из галереи», либо просто пришлите фото сообщением.",
            reply_markup=get_photo_upload_keyboard(),
        )

    async def photo_unexpected_document(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Пожалуйста, отправьте именно фото (не файл/документ).",
            reply_markup=get_photo_upload_keyboard(),
        )

    async def photo_unexpected_sticker(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Стикер не подойдёт 😊 Пришлите фото лифлета.",
            reply_markup=get_photo_upload_keyboard(),
        )

    async def photo_unexpected_media(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Пришлите фото лифлета одним сообщением.",
            reply_markup=get_photo_upload_keyboard(),
        )

    async def ask_take_photo(self, message: types.Message, state: FSMContext) -> None:
        await message.answer("Сделайте фото и отправьте его в чат", reply_markup=get_photo_upload_keyboard())

    async def ask_choose_gallery(self, message: types.Message, state: FSMContext) -> None:
        await message.answer("Выберите фото в галерее и отправьте его сюда", reply_markup=get_photo_upload_keyboard())

    async def explain_leaflet(self, message: types.Message) -> None:
        await message.answer("Лифлет — промо-материал. Можно использовать фото листовки/баннера мероприятия.")

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


def setup_registration_handlers(dispatcher, *, upload_dir: Path, cache, bot) -> RegistrationHandler:
    handler = RegistrationHandler(upload_dir=upload_dir, cache=cache, bot=bot)
    handler.setup(dispatcher)
    return handler

