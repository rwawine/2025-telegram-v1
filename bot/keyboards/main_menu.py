"""Keyboard layouts for the Telegram bot"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.repositories import get_participant_status

# Main menu keyboard
def get_main_menu_keyboard(user_status: str = None) -> ReplyKeyboardMarkup:
    """Get main menu keyboard based on user registration status"""
    keyboard = []
    
    # Показываем кнопку регистрации только если пользователь не зарегистрирован
    if user_status is None or user_status == "not_registered":
        keyboard.append([KeyboardButton(text="🚀 Начать регистрацию")])
    
    keyboard.extend([
        [KeyboardButton(text="✅ Мой статус"), KeyboardButton(text="💬 Помощь")],
        [KeyboardButton(text="📊 О розыгрыше")]
    ])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


async def get_main_menu_keyboard_for_user(telegram_id: int) -> ReplyKeyboardMarkup:
    """Get main menu keyboard with automatic status detection"""
    # Импортируем здесь для избежания циклических импортов
    from bot.smart_keyboards import adaptive_keyboards
    return await adaptive_keyboards.get_main_menu_keyboard(telegram_id)

# Registration process keyboards
def get_name_input_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard for name input step with smart progress"""
    from bot.smart_keyboards import adaptive_keyboards
    return adaptive_keyboards.get_registration_step_keyboard(1, "name")

def get_phone_input_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard for phone input step with smart progress"""
    from bot.smart_keyboards import adaptive_keyboards
    return adaptive_keyboards.get_registration_step_keyboard(2, "phone")

def get_loyalty_card_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard for loyalty card input with smart progress"""
    from bot.smart_keyboards import adaptive_keyboards
    return adaptive_keyboards.get_registration_step_keyboard(3, "loyalty_card")

def get_photo_upload_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard for photo upload step with smart progress"""
    from bot.smart_keyboards import adaptive_keyboards
    return adaptive_keyboards.get_registration_step_keyboard(4, "photo")

def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for data confirmation"""
    keyboard = [
        [
            InlineKeyboardButton(text="✏️ Изменить имя", callback_data="edit_name"),
            InlineKeyboardButton(text="✏️ Изменить телефон", callback_data="edit_phone")
        ],
        [
            InlineKeyboardButton(text="✏️ Изменить карту", callback_data="edit_card"),
            InlineKeyboardButton(text="✏️ Изменить фото", callback_data="edit_photo")
        ],
        [
            InlineKeyboardButton(text="✅ Все верно, зарегистрировать", callback_data="confirm_registration")
        ],
        [
            InlineKeyboardButton(text="❌ Отменить регистрацию", callback_data="cancel_registration")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Status check keyboards
def get_status_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard for status checking"""
    keyboard = [
        [KeyboardButton(text="🔄 Обновить статус")],
        [KeyboardButton(text="💬 Поддержка")],
        [KeyboardButton(text="🏠 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# Support system keyboards
def get_support_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main support menu keyboard with quick actions"""
    from bot.smart_keyboards import adaptive_keyboards
    return adaptive_keyboards.get_support_keyboard_with_quick_actions()

def get_faq_keyboard() -> InlineKeyboardMarkup:
    """FAQ categories keyboard"""
    keyboard = [
        [InlineKeyboardButton(text="📋 Как подать заявку?", callback_data="faq_registration")],
        [InlineKeyboardButton(text="🕐 Когда будут результаты?", callback_data="faq_results")],
        [InlineKeyboardButton(text="🏆 Что можно выиграть?", callback_data="faq_prizes")],
        [InlineKeyboardButton(text="📱 Проблемы с фото", callback_data="faq_photo")],
        [InlineKeyboardButton(text="💳 Вопросы по картам", callback_data="faq_cards")],
        [InlineKeyboardButton(text="📞 Другой вопрос", callback_data="create_ticket")],
        [InlineKeyboardButton(text="⬅️ Назад к меню поддержки", callback_data="support_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_support_categories_keyboard() -> InlineKeyboardMarkup:
    """Support ticket categories keyboard with smart indicators"""
    from bot.smart_keyboards import adaptive_keyboards
    return adaptive_keyboards.get_smart_categories_keyboard()

def get_ticket_actions_keyboard() -> ReplyKeyboardMarkup:
    """Actions for ticket creation with smart hints"""
    from bot.smart_keyboards import adaptive_keyboards
    return adaptive_keyboards.get_ticket_creation_keyboard()

# Information keyboards
def get_info_menu_keyboard() -> InlineKeyboardMarkup:
    """Information menu keyboard"""
    keyboard = [
        [InlineKeyboardButton(text="📋 Правила участия", callback_data="info_rules")],
        [InlineKeyboardButton(text="🏆 Призы розыгрыша", callback_data="info_prizes")],
        [InlineKeyboardButton(text="📅 Сроки проведения", callback_data="info_schedule")],
        [InlineKeyboardButton(text="⚖️ Гарантии честности", callback_data="info_fairness")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Admin keyboards (for quick actions)
def get_admin_quick_keyboard() -> ReplyKeyboardMarkup:
    """Quick admin actions keyboard"""
    keyboard = [
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📤 Быстрый экспорт")],
        [KeyboardButton(text="🎲 Провести розыгрыш"), KeyboardButton(text="📢 Создать рассылку")],
        [KeyboardButton(text="🌐 Открыть админку")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# Universal action keyboards
def get_back_to_menu_keyboard() -> ReplyKeyboardMarkup:
    """Simple back to menu keyboard"""
    keyboard = [
        [KeyboardButton(text="🏠 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
