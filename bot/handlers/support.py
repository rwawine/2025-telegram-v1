"""Support ticket handlers."""

from __future__ import annotations

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.connection import get_db_pool
from services.cache import get_cache
from bot.states import SupportStates
from bot.keyboards import (
    get_support_menu_keyboard,
    get_faq_keyboard,
    get_support_categories_keyboard,
    get_ticket_actions_keyboard,
    get_back_to_menu_keyboard,
    get_main_menu_keyboard_for_user,
)
from bot.context_manager import context_manager, UserContext, UserAction
from bot.messages import smart_messages


class SupportHandler:
    def __init__(self) -> None:
        self.router = Router()
        self._register()

    def setup(self, dispatcher) -> None:
        dispatcher.include_router(self.router)

    def _register(self) -> None:
        # Entry
        self.router.message.register(self.open_support_menu, Command("support"))
        self.router.message.register(self.open_support_menu, F.text.contains("поддержк"))

        # FAQ and categories
        self.router.message.register(self.show_faq, F.text.contains("Частые вопросы"))
        self.router.message.register(self.ask_new_ticket, F.text.contains("Написать сообщение"))
        self.router.message.register(self.list_my_tickets, F.text.contains("Мои обращения"))
        # 'Главное меню' handled in registration/common; avoid duplicate replies here

        # Inline callbacks
        self.router.callback_query.register(self.handle_faq_callback, F.data.startswith("faq_"))
        self.router.callback_query.register(self.start_ticket_from_callback, F.data == "create_ticket")
        self.router.callback_query.register(self.pick_category, F.data.startswith("cat_"))
        self.router.callback_query.register(self.view_ticket_detail, F.data.startswith("view_ticket_"))
        self.router.callback_query.register(self.back_to_tickets_list, F.data == "back_to_tickets")

        # Compose ticket
        # Draft message and actions within composing state
        self.router.message.register(self.handle_send_ticket, SupportStates.entering_message, F.text == "✅ Отправить обращение")
        self.router.message.register(self.handle_change_category, SupportStates.entering_message, F.text == "⬅️ Изменить категорию")
        self.router.message.register(self.back_to_menu, F.text == "🏠 Главное меню")
        self.router.message.register(self.handle_attach_photo, SupportStates.entering_message, F.text == "📷 Прикрепить фото")
        self.router.message.register(self.handle_attach_document, SupportStates.entering_message, F.text == "📄 Прикрепить документ")
        # Any other text becomes the draft body
        self.router.message.register(self.receive_ticket_message, SupportStates.entering_message)

    async def open_support_menu(self, message: types.Message) -> None:
        await context_manager.update_context(
            message.from_user.id,
            UserContext.SUPPORT,
            UserAction.BUTTON_CLICK
        )
        
        support_messages = smart_messages.get_support_messages()
        menu_msg = support_messages["menu"]
        
        await message.answer(
            menu_msg["text"],
            reply_markup=get_support_menu_keyboard(),
            parse_mode="Markdown"
        )

    async def show_faq(self, message: types.Message) -> None:
        await message.answer("Частые вопросы:", reply_markup=get_faq_keyboard())

    async def ask_new_ticket(self, message: types.Message, state: FSMContext) -> None:
        await context_manager.update_context(
            message.from_user.id,
            UserContext.SUPPORT,
            UserAction.BUTTON_CLICK
        )
        
        # Let user pick a category first (optional), then type a message
        await state.set_state(SupportStates.entering_message)
        
        support_messages = smart_messages.get_support_messages()
        create_msg = support_messages["create_ticket"]
        
        await message.answer(create_msg["text"], parse_mode="Markdown")
        await message.answer("🏷️ **Выберите категорию проблемы:**", reply_markup=get_support_categories_keyboard(), parse_mode="Markdown")
        await message.answer("✍️ Теперь опишите проблему подробно:", reply_markup=get_ticket_actions_keyboard())

    async def start_ticket_from_callback(self, callback: types.CallbackQuery, state: FSMContext) -> None:
        await state.set_state(SupportStates.entering_message)
        await callback.message.answer("📝 Создание обращения в техподдержку\n\nВыберите категорию вашего вопроса:")
        await callback.message.answer("Категории проблем:", reply_markup=get_support_categories_keyboard())
        await callback.message.answer("Опишите вашу проблему.", reply_markup=get_ticket_actions_keyboard())
        await callback.answer()

    async def pick_category(self, callback: types.CallbackQuery, state: FSMContext) -> None:
        # Save category code like "cat_photo", "cat_card", etc.
        await state.update_data(category=callback.data)
        await state.set_state(SupportStates.entering_message)
        await callback.message.answer("Опишите проблему подробнее.")
        await callback.answer()

    async def handle_faq_callback(self, callback: types.CallbackQuery) -> None:
        mapping = {
            "faq_registration": "Чтобы подать заявку, нажмите 'Начать регистрацию' в главном меню.",
            "faq_results": "Результаты публикуются после завершения розыгрыша в админ-панели.",
            "faq_prizes": "Призы указаны в разделе информации.",
            "faq_photo": "Если не отправляется фото — попробуйте сжать изображение или отправить как файл.",
            "faq_cards": "Проверьте правильность номера карты и повторите ввод.",
        }
        await callback.message.answer(mapping.get(callback.data, "Задайте вопрос оператору."))
        await callback.answer()

    async def list_my_tickets(self, message: types.Message) -> None:
        pool = get_db_pool()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT t.id, t.subject, t.status, t.created_at
                FROM support_tickets t
                JOIN participants p ON p.id = t.participant_id
                WHERE p.telegram_id=?
                ORDER BY t.created_at DESC
                LIMIT 10
                """,
                (message.from_user.id,),
            )
            rows = await cursor.fetchall()

        if not rows:
            await message.answer(
                "📭 У вас пока нет обращений в техподдержку.\n\n"
                "Вы можете создать обращение, нажав '📝 Написать сообщение'.",
                reply_markup=get_support_menu_keyboard(),
            )
            return

        status_emoji = {
            "open": "🟡",
            "in_progress": "🔵",
            "closed": "🟢",
        }
        status_text = {
            "open": "Открыто",
            "in_progress": "В работе",
            "closed": "Закрыто",
        }

        lines: list[str] = ["📞 Ваши обращения:\n"]
        inline_keyboard = []
        
        for ticket_id, subject, status, created_at in rows:
            emoji = status_emoji.get(status, "⚪️")
            text = status_text.get(status, status)
            lines.append(f"{emoji} {subject}\n📅 {created_at} — {text}\n")
            
            # Добавляем inline-кнопку для просмотра детального содержимого
            inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"📄 Просмотреть: {subject[:20]}...",
                    callback_data=f"view_ticket_{ticket_id}"
                )
            ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
        await message.answer("\n".join(lines), reply_markup=keyboard)

    async def handle_attach_photo(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Пришлите фото одним сообщением, чтобы прикрепить его к обращению.",
            reply_markup=get_ticket_actions_keyboard(),
        )

    async def handle_attach_document(self, message: types.Message, state: FSMContext) -> None:
        await message.answer(
            "Пришлите документ одним сообщением, чтобы прикрепить его к обращению.",
            reply_markup=get_ticket_actions_keyboard(),
        )

    async def back_to_menu(self, message: types.Message) -> None:
        keyboard = await get_main_menu_keyboard_for_user(message.from_user.id)
        await message.answer("🏠 Главное меню", reply_markup=keyboard)

    async def receive_ticket_message(self, message: types.Message, state: FSMContext) -> None:
        # Save draft text or attachments
        data = await state.get_data()
        draft_subject = (data.get("draft_subject") or "").strip()
        draft_message = (data.get("draft_message") or "").strip()

        if message.photo:
            file_id = message.photo[-1].file_id
            photos = list(data.get("attachments_photos") or [])
            photos.append(file_id)
            await state.update_data(attachments_photos=photos)
            await message.answer("📎 Фото добавлено к обращению.", reply_markup=get_ticket_actions_keyboard())
            return

        if message.document:
            file_id = message.document.file_id
            docs = list(data.get("attachments_docs") or [])
            docs.append(file_id)
            await state.update_data(attachments_docs=docs)
            await message.answer("📎 Документ добавлен к обращению.", reply_markup=get_ticket_actions_keyboard())
            return

        text = (message.text or "").strip()
        if not text:
            await message.answer("Опишите вашу проблему текстом или пришлите вложение.", reply_markup=get_ticket_actions_keyboard())
            return
        await state.update_data(draft_subject=(text[:80] or draft_subject) or "Обращение", draft_message=(draft_message + ("\n" if draft_message else "") + text))
        await message.answer(
            "✅ Описание сохранено. Нажмите '✅ Отправить обращение' для отправки, либо измените категорию.",
            reply_markup=get_ticket_actions_keyboard(),
        )

    async def handle_send_ticket(self, message: types.Message, state: FSMContext) -> None:
        data = await state.get_data()
        subject = (data.get("draft_subject") or "Support request").strip()[:80]
        body = data.get("draft_message") or ""
        photos = list(data.get("attachments_photos") or [])
        docs = list(data.get("attachments_docs") or [])

        pool = get_db_pool()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO support_tickets (participant_id, subject, message)
                VALUES ((SELECT id FROM participants WHERE telegram_id=?), ?, ?)
                RETURNING id
                """,
                (message.from_user.id, subject, body),
            )
            row = await cursor.fetchone()
            ticket_id = row[0]

            # Persist attachments as messages records (create messages table if necessary later)
            for file_id in photos:
                await conn.execute(
                    "INSERT INTO support_ticket_messages (ticket_id, sender_type, message_text, attachment_file_id) VALUES (?, 'user', '', ?)",
                    (ticket_id, file_id),
                )
            for file_id in docs:
                await conn.execute(
                    "INSERT INTO support_ticket_messages (ticket_id, sender_type, message_text, attachment_file_id) VALUES (?, 'user', '', ?)",
                    (ticket_id, file_id),
                )

            await conn.commit()

        await state.clear()
        
        # Показываем умное сообщение об успешной отправке
        support_messages = smart_messages.get_support_messages()
        sent_msg = support_messages["ticket_sent"]
        
        await message.answer(sent_msg["text"], parse_mode="Markdown")
        
        cache = get_cache()
        cache.invalidate(f"status:{message.from_user.id}")

    async def handle_change_category(self, message: types.Message, state: FSMContext) -> None:
        await message.answer("Выберите категорию:")
        await message.answer("Категории проблем:", reply_markup=get_support_categories_keyboard())

    async def view_ticket_detail(self, callback: types.CallbackQuery) -> None:
        """Детальный просмотр обращения с всеми сообщениями и вложениями"""
        # Извлекаем ID тикета из callback_data
        ticket_id = int(callback.data.split("_")[-1])
        
        pool = get_db_pool()
        async with pool.connection() as conn:
            # Получаем основную информацию о тикете
            cursor = await conn.execute(
                """
                SELECT t.id, t.subject, t.message, t.status, t.created_at,
                       p.full_name, p.telegram_id
                FROM support_tickets t
                JOIN participants p ON p.id = t.participant_id
                WHERE t.id = ? AND p.telegram_id = ?
                """,
                (ticket_id, callback.from_user.id),
            )
            ticket_row = await cursor.fetchone()
            
            if not ticket_row:
                await callback.answer("Обращение не найдено или нет доступа", show_alert=True)
                return
                
            ticket_id, subject, message, status, created_at, full_name, _ = ticket_row

            # Получаем все дополнительные сообщения и вложения
            cursor = await conn.execute(
                """
                SELECT sender_type, message_text, attachment_file_id, sent_at
                FROM support_ticket_messages
                WHERE ticket_id = ?
                ORDER BY sent_at ASC
                """,
                (ticket_id,),
            )
            messages = await cursor.fetchall()

        status_emoji = {
            "open": "🟡",
            "in_progress": "🔵", 
            "closed": "🟢",
        }
        status_text = {
            "open": "Открыто",
            "in_progress": "В работе",
            "closed": "Закрыто",
        }

        # Формируем детальное сообщение
        emoji = status_emoji.get(status, "⚪️")
        status_display = status_text.get(status, status)
        
        lines = [
            f"📋 Обращение #{ticket_id}",
            f"📌 Тема: {subject}",
            f"👤 От: {full_name}", 
            f"📅 Создано: {created_at}",
            f"{emoji} Статус: {status_display}",
            "",
            "💬 Ваше сообщение:",
            message,
        ]

        # Добавляем дополнительные сообщения и вложения
        if messages:
            lines.append("")
            lines.append("📎 Дополнительная информация:")
            
            for sender_type, msg_text, attachment_file_id, sent_at in messages:
                if sender_type == "user":
                    lines.append(f"👤 Вы ({sent_at}):")
                    if msg_text and msg_text.strip():
                        lines.append(f"  💬 {msg_text}")
                    if attachment_file_id:
                        lines.append(f"  📎 Приложено медиа")
                elif sender_type == "admin":
                    lines.append(f"👨‍💼 Администратор ({sent_at}):")
                    if msg_text and msg_text.strip():
                        lines.append(f"  💬 {msg_text}")
                    if attachment_file_id:
                        lines.append(f"  📎 Приложено медиа")
                lines.append("")

        # Создаем кнопку для возврата к списку
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Вернуться к списку обращений", callback_data="back_to_tickets")]
        ])

        full_text = "\n".join(lines)
        
        # Если текст слишком длинный, разбиваем на части
        if len(full_text) > 4096:
            parts = []
            current_part = ""
            for line in lines:
                if len(current_part + line + "\n") > 4000:
                    parts.append(current_part)
                    current_part = line + "\n"
                else:
                    current_part += line + "\n"
            if current_part:
                parts.append(current_part)
                
            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # Последняя часть с кнопками
                    await callback.message.answer(part, reply_markup=back_keyboard)
                else:
                    await callback.message.answer(part)
        else:
            await callback.message.answer(full_text, reply_markup=back_keyboard)
            
        await callback.answer()

    async def back_to_tickets_list(self, callback: types.CallbackQuery) -> None:
        """Возврат к списку обращений"""
        # Создаем фиктивное сообщение для переиспользования логики list_my_tickets
        fake_message = types.Message(
            message_id=callback.message.message_id,
            date=callback.message.date,
            chat=callback.message.chat,
            from_user=callback.from_user,
            content_type="text"
        )
        await self.list_my_tickets(fake_message)
        await callback.answer()


def setup_support_handlers(dispatcher) -> SupportHandler:
    handler = SupportHandler()
    handler.setup(dispatcher)
    return handler

