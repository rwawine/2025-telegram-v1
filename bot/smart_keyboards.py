"""Умные клавиатуры с визуальными индикаторами и контекстными подсказками."""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from database.repositories import get_participant_status


class SmartKeyboardBuilder:
    """Конструктор умных клавиатур с адаптивным интерфейсом"""
    
    @staticmethod
    def create_progress_keyboard(
        step: int, 
        total_steps: int,
        main_buttons: List[List[str]],
        back_button: Optional[str] = None,
        help_button: Optional[str] = None,
        special_buttons: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> ReplyKeyboardMarkup:
        """Создает клавиатуру с индикатором прогресса"""
        
        # Создаем строку прогресса
        progress_bar = "🟢" * step + "⚪" * (total_steps - step)
        progress_text = f"📊 Шаг {step}/{total_steps}: {progress_bar}"
        
        keyboard = []
        
        # Добавляем основные кнопки
        for row in main_buttons:
            keyboard_row = []
            for btn in row:
                if special_buttons and btn in special_buttons:
                    # Создаем специальную кнопку с дополнительными параметрами
                    params = special_buttons[btn]
                    keyboard_row.append(KeyboardButton(text=btn, **params))
                else:
                    # Обычная кнопка
                    keyboard_row.append(KeyboardButton(text=btn))
            keyboard.append(keyboard_row)
        
        # Добавляем служебные кнопки
        service_row = []
        if back_button:
            service_row.append(KeyboardButton(text=back_button))
        if help_button:
            service_row.append(KeyboardButton(text=help_button))
        
        if service_row:
            keyboard.append(service_row)
        
        return ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
            input_field_placeholder=progress_text
        )
    
    @staticmethod
    def create_contextual_keyboard(
        context: str,
        buttons: List[List[str]],
        hints: Optional[Dict[str, str]] = None
    ) -> ReplyKeyboardMarkup:
        """Создает контекстную клавиатуру с подсказками"""
        
        context_emojis = {
            "registration": "🚀",
            "support": "💬",
            "info": "📊",
            "status": "📋"
        }
        
        context_hints = {
            "registration": "Заполните все поля для участия в розыгрыше",
            "support": "Опишите проблему максимально подробно",
            "info": "Изучите правила и условия розыгрыша",
            "status": "Проверьте актуальную информацию о заявке"
        }
        
        emoji = context_emojis.get(context, "🎯")
        hint = hints.get(context) if hints else context_hints.get(context, "Выберите действие")
        
        keyboard = []
        for row in buttons:
            keyboard.append([KeyboardButton(text=btn) for btn in row])
        
        return ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
            input_field_placeholder=f"{emoji} {hint}"
        )
    
    @staticmethod
    def create_smart_inline_keyboard(
        buttons: List[List[Dict[str, str]]],
        style: str = "default"
    ) -> InlineKeyboardMarkup:
        """Создает умную inline-клавиатуру со стилями"""
        
        style_emojis = {
            "navigation": "🧭",
            "action": "⚡",
            "selection": "🎯",
            "confirmation": "✅"
        }
        
        keyboard = []
        for row in buttons:
            keyboard_row = []
            for btn_data in row:
                text = btn_data["text"]
                callback_data = btn_data["callback_data"]
                
                # Добавляем эмодзи если не указан
                if style in style_emojis and not any(emoji in text for emoji in ["🎯", "📝", "⚡", "🧭", "✅", "❌", "🔙"]):
                    text = f"{style_emojis[style]} {text}"
                
                keyboard_row.append(
                    InlineKeyboardButton(text=text, callback_data=callback_data)
                )
            keyboard.append(keyboard_row)
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)


class AdaptiveKeyboards:
    """Адаптивные клавиатуры, изменяющиеся в зависимости от состояния пользователя"""
    
    @staticmethod
    async def get_main_menu_keyboard(telegram_id: int) -> ReplyKeyboardMarkup:
        """Главное меню с адаптацией под статус пользователя"""
        user_status = await get_participant_status(telegram_id)
        
        keyboard = []
        
        # Кнопки в зависимости от статуса регистрации
        if user_status is None:
            # Незарегистрированный пользователь
            keyboard.extend([
                [KeyboardButton(text="🚀 Начать регистрацию")],
                [KeyboardButton(text="📊 О розыгрыше"), KeyboardButton(text="💬 Поддержка")]
            ])
        elif user_status == "pending":
            # Заявка на модерации
            keyboard.extend([
                [KeyboardButton(text="⏳ Мой статус")],
                [KeyboardButton(text="📊 О розыгрыше"), KeyboardButton(text="💬 Поддержка")]
            ])
        elif user_status == "approved":
            # Одобренный участник
            keyboard.extend([
                [KeyboardButton(text="✅ Мой статус")],
                [KeyboardButton(text="📊 О розыгрыше"), KeyboardButton(text="💬 Поддержка")]
            ])
        elif user_status == "rejected":
            # Отклоненная заявка
            keyboard.extend([
                [KeyboardButton(text="🔄 Подать заявку снова")],
                [KeyboardButton(text="📊 О розыгрыше"), KeyboardButton(text="💬 Поддержка")]
            ])
        
        # Определяем подсказку
        hints = {
            None: "Начните с регистрации для участия в розыгрыше!",
            "pending": "Ваша заявка рассматривается. Проверяйте статус!",
            "approved": "Поздравляем! Вы участник розыгрыша!",
            "rejected": "Исправьте заявку и подайте повторно"
        }
        
        return ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
            input_field_placeholder=f"🎯 {hints.get(user_status, 'Выберите действие')}"
        )
    
    @staticmethod
    def get_registration_step_keyboard(step: int, step_name: str) -> ReplyKeyboardMarkup:
        """Клавиатуры для шагов регистрации с прогрессом"""
        
        step_configs = {
            1: {  # Имя
                "buttons": [],
                "back": "⬅️ Назад в меню",
                "help": "❓ Как правильно ввести имя?"
            },
            2: {  # Телефон
                "buttons": [["📞 Отправить мой номер"], ["✏️ Ввести вручную"]],
                "back": "⬅️ Назад к имени",
                "help": "❓ Проблемы с номером?",
                "special_buttons": {"📞 Отправить мой номер": {"request_contact": True}}
            },
            3: {  # Карта лояльности
                "buttons": [],
                "back": "⬅️ Назад к телефону",
                "help": "❓ Где найти номер карты?"
            },
            4: {  # Фото
                "buttons": [
                    ["📷 Сделать фото", "🖼️ Выбрать из галереи"]
                ],
                "back": "⬅️ Назад к карте лояльности",
                "help": None
            }
        }
        
        config = step_configs.get(step, {})
        
        return SmartKeyboardBuilder.create_progress_keyboard(
            step=step,
            total_steps=4,
            main_buttons=config.get("buttons", []),
            back_button=config.get("back"),
            help_button=config.get("help"),
            special_buttons=config.get("special_buttons")
        )
    
    @staticmethod
    def get_support_keyboard_with_quick_actions() -> ReplyKeyboardMarkup:
        """Клавиатура поддержки с быстрыми действиями"""
        keyboard = [
            [KeyboardButton(text="❓ Частые вопросы")],
            [KeyboardButton(text="📝 Написать сообщение")], 
            [KeyboardButton(text="📞 Мои обращения")],
            [KeyboardButton(text="🏠 Главное меню")]
        ]
        
        return ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
            input_field_placeholder="💬 Выберите тип обращения или опишите проблему"
        )
    
    @staticmethod
    def get_ticket_creation_keyboard() -> ReplyKeyboardMarkup:
        """Клавиатура для создания обращения"""
        keyboard = [
            [KeyboardButton(text="📷 Прикрепить фото"), KeyboardButton(text="📄 Прикрепить документ")],
            [KeyboardButton(text="✅ Отправить обращение"), KeyboardButton(text="⬅️ Назад")],
            [KeyboardButton(text="🏠 Главное меню")]
        ]
        
        return ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
            input_field_placeholder="✍️ Опишите проблему подробно, приложите фото при необходимости"
        )
    
    @staticmethod 
    def get_smart_categories_keyboard() -> InlineKeyboardMarkup:
        """Умная клавиатура категорий с индикаторами популярности"""
        
        categories = [
            {"text": "🔥 Проблема с фото (частая)", "callback_data": "cat_photo"},
            {"text": "💳 Вопрос по карте лояльности", "callback_data": "cat_card"}, 
            {"text": "📱 Технические проблемы", "callback_data": "cat_tech"},
            {"text": "📋 Статус заявки", "callback_data": "cat_status"},
            {"text": "🏆 Вопросы о розыгрыше", "callback_data": "cat_lottery"},
            {"text": "✏️ Другая проблема", "callback_data": "cat_other"}
        ]
        
        return SmartKeyboardBuilder.create_smart_inline_keyboard(
            [[cat] for cat in categories],
            style="selection"
        )
    
    @staticmethod
    def get_confusion_help_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура помощи для запутавшихся пользователей"""
        
        help_options = [
            [
                {"text": "🏠 В главное меню", "callback_data": "help_main"},
                {"text": "🚀 К регистрации", "callback_data": "help_register"}
            ],
            [
                {"text": "💬 В поддержку", "callback_data": "help_support"},
                {"text": "📋 Проверить статус", "callback_data": "help_status"}
            ],
            [
                {"text": "❓ Подробная справка", "callback_data": "help_detailed"}
            ]
        ]
        
        return SmartKeyboardBuilder.create_smart_inline_keyboard(
            help_options,
            style="navigation"
        )


# Глобальные экземпляры
smart_keyboards = SmartKeyboardBuilder()
adaptive_keyboards = AdaptiveKeyboards()
