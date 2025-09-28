"""Центральный менеджер контекста для умной обработки всех состояний пользователя."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List
from enum import Enum
from dataclasses import dataclass

from aiogram import types
from aiogram.fsm.context import FSMContext

from database.repositories import get_participant_status
from services.cache import get_cache


class UserContext(Enum):
    """Контексты взаимодействия пользователя"""
    REGISTRATION = "registration"
    SUPPORT = "support"
    NAVIGATION = "navigation"
    INFO_BROWSING = "info_browsing"
    IDLE = "idle"
    CONFUSED = "confused"


class UserAction(Enum):
    """Типы действий пользователя"""
    TEXT_INPUT = "text_input"
    PHOTO_UPLOAD = "photo_upload"
    CONTACT_SHARE = "contact_share"
    DOCUMENT_UPLOAD = "document_upload"
    BUTTON_CLICK = "button_click"
    CALLBACK_QUERY = "callback_query"
    STICKER_SEND = "sticker_send"
    VOICE_SEND = "voice_send"
    UNEXPECTED = "unexpected"


@dataclass
class UserSession:
    """Информация о сессии пользователя"""
    telegram_id: int
    current_context: UserContext
    last_action: Optional[UserAction]
    last_message_time: datetime
    consecutive_errors: int
    registration_status: Optional[str]
    breadcrumbs: List[str]  # История навигации
    hints_shown: List[str]  # Показанные подсказки
    preferred_style: str = "friendly"  # friendly, professional, witty


class ContextManager:
    """Центральный менеджер контекста пользователей"""
    
    def __init__(self):
        self.sessions: Dict[int, UserSession] = {}
        self.cache = get_cache()
        
    async def get_or_create_session(self, telegram_id: int) -> UserSession:
        """Получить или создать сессию пользователя"""
        if telegram_id not in self.sessions:
            # Создаем новую сессию
            registration_status = await get_participant_status(telegram_id)
            
            self.sessions[telegram_id] = UserSession(
                telegram_id=telegram_id,
                current_context=UserContext.IDLE,
                last_action=None,
                last_message_time=datetime.now(),
                consecutive_errors=0,
                registration_status=registration_status,
                breadcrumbs=[],
                hints_shown=[]
            )
        
        return self.sessions[telegram_id]
    
    async def update_context(self, telegram_id: int, context: UserContext, action: UserAction = None):
        """Обновить контекст пользователя"""
        session = await self.get_or_create_session(telegram_id)
        
        # Добавляем в breadcrumbs если контекст изменился
        if session.current_context != context:
            session.breadcrumbs.append(f"{session.current_context.value}→{context.value}")
            # Ограничиваем историю
            if len(session.breadcrumbs) > 10:
                session.breadcrumbs = session.breadcrumbs[-10:]
        
        session.current_context = context
        session.last_action = action
        session.last_message_time = datetime.now()
        
        # Сбрасываем счетчик ошибок при успешном действии
        if action and action != UserAction.UNEXPECTED:
            session.consecutive_errors = 0
    
    async def detect_user_confusion(self, telegram_id: int, message: types.Message, state: FSMContext) -> bool:
        """Определить, запутался ли пользователь"""
        session = await self.get_or_create_session(telegram_id)
        current_state = await state.get_state()
        
        confusion_indicators = 0
        
        # 1. Много ошибок подряд
        if session.consecutive_errors >= 2:
            confusion_indicators += 2
            
        # 2. Отправляет неподходящий тип контента
        text = message.text or ""
        if current_state:
            if "enter_name" in current_state and (message.photo or message.contact):
                confusion_indicators += 1
            elif "upload_photo" in current_state and message.text and not any(word in text.lower() for word in ["фото", "галер", "камер"]):
                confusion_indicators += 1
        
        # 3. Повторяет одно и то же действие
        if len(session.breadcrumbs) >= 3:
            recent_actions = session.breadcrumbs[-3:]
            if len(set(recent_actions)) == 1:  # Все действия одинаковые
                confusion_indicators += 1
        
        # 4. Отправляет общие фразы в специфическом контексте
        generic_phrases = ["что", "как", "помоги", "не понимаю", "не работает", "???", "хелп", "help"]
        if any(phrase in text.lower() for phrase in generic_phrases):
            confusion_indicators += 1
        
        return confusion_indicators >= 2
    
    async def get_smart_suggestion(self, telegram_id: int, message: types.Message, state: FSMContext) -> Optional[Dict[str, Any]]:
        """Получить умную подсказку для пользователя"""
        session = await self.get_or_create_session(telegram_id)
        current_state = await state.get_state()
        
        # Анализируем контекст и предлагаем следующие шаги
        if current_state:
            if "enter_name" in current_state:
                return {
                    "context": "registration_name",
                    "message": "🤔 Кажется, вы застряли на вводе имени!\n\n✨ Подсказка: введите ваше полное имя как в паспорте, например: **Иванов Иван Иванович**",
                    "quick_actions": ["⬅️ Вернуться в меню", "❓ Что такое полное имя?"],
                    "next_step_hint": "После имени мы попросим ваш номер телефона 📱"
                }
            elif "enter_phone" in current_state:
                return {
                    "context": "registration_phone", 
                    "message": "📱 Давайте разберемся с номером телефона!\n\n🎯 Два простых способа:\n• Нажать **📞 Отправить мой номер**\n• Или написать в формате **+79001234567**",
                    "quick_actions": ["📞 Отправить контакт", "⬅️ К имени", "🏠 В меню"],
                    "next_step_hint": "Далее понадобится номер карты лояльности 💳"
                }
            elif "upload_photo" in current_state:
                return {
                    "context": "registration_photo",
                    "message": "📸 Последний шаг - фото лифлета!\n\n🎨 **Лифлет** - это рекламная листовка или баннер мероприятия\n\n✅ Попробуйте:\n• **📷 Сделать фото** прямо сейчас\n• **🖼️ Выбрать из галереи**",
                    "quick_actions": ["📷 Камера", "🖼️ Галерея", "❓ Что такое лифлет?"],
                    "next_step_hint": "После фото заявка отправится на модерацию! 🎉"
                }
            elif "entering_message" in current_state:
                return {
                    "context": "support_message",
                    "message": "💬 Создаем обращение в поддержку!\n\n📝 **Опишите проблему** - чем подробнее, тем быстрее поможем\n\n📎 Можете приложить фото или документ для наглядности",
                    "quick_actions": ["📷 Добавить фото", "📄 Добавить файл", "✅ Отправить"],
                    "next_step_hint": "Наша команда ответит в течение 24 часов ⏰"
                }
        
        # Контекстные подсказки для разных ситуаций
        if session.registration_status is None:
            return {
                "context": "new_user",
                "message": "👋 Добро пожаловать!\n\n🎯 Начните с **🚀 Начать регистрацию** для участия в розыгрыше\n\n🔍 Или изучите **📊 О розыгрыше** чтобы узнать больше",
                "quick_actions": ["🚀 Регистрация", "📊 О розыгрыше", "💬 Поддержка"],
                "next_step_hint": "Регистрация займет всего 2-3 минуты! ⚡"
            }
        
        return None
    
    async def increment_error_count(self, telegram_id: int):
        """Увеличить счетчик ошибок"""
        session = await self.get_or_create_session(telegram_id)
        session.consecutive_errors += 1
    
    async def add_hint_shown(self, telegram_id: int, hint_id: str):
        """Отметить показанную подсказку"""
        session = await self.get_or_create_session(telegram_id)
        if hint_id not in session.hints_shown:
            session.hints_shown.append(hint_id)
    
    async def should_show_hint(self, telegram_id: int, hint_id: str) -> bool:
        """Проверить, нужно ли показать подсказку"""
        session = await self.get_or_create_session(telegram_id)
        return hint_id not in session.hints_shown
    
    def get_witty_responses(self) -> Dict[str, List[str]]:
        """Остроумные ответы для разных ситуаций"""
        return {
            "sticker_in_registration": [
                "😄 Отличный стикер! Но сейчас мне нужно ваше имя текстом - стикеры я пока не умею читать 🤖",
                "🎨 Красиво! А теперь давайте познакомимся через имя в текстовом формате",
                "😊 Стикер принят с благодарностью! Но для регистрации нужно старомодное текстовое имя"
            ],
            "voice_unexpected": [
                "🎙️ Голос отличный! Но я лучше читаю, чем слушаю - напишите, пожалуйста, текстом",
                "🔊 Интересно звучит! К сожалению, мои уши пока в разработке - текст предпочтительнее",
                "🎵 Музыка для моих схем! Но давайте переключимся на письменное общение"
            ],
            "confusion_general": [
                "🤔 Кажется, мы немного запутались! Ничего страшного - такое бывает с каждым",
                "🧭 Похоже, мы свернули не туда. Давайте я покажу правильную дорогу!",
                "🔄 Небольшая навигационная заминка? Это нормально! Сейчас все исправим"
            ],
            "wrong_content_type": [
                "📎 Вижу, что вы отправили {content_type}! Но сейчас лучше подойдет {expected_type}",
                "🎯 {content_type} получен, но для этого шага нужен {expected_type}. Попробуем еще раз?",
                "🔄 {content_type} - хорошая попытка! Но давайте попробуем {expected_type}"
            ]
        }


# Глобальный экземпляр менеджера - инициализируется позже
context_manager = None

def init_context_manager():
    """Инициализация менеджера контекста после инициализации кеша"""
    global context_manager
    context_manager = ContextManager()
    return context_manager
