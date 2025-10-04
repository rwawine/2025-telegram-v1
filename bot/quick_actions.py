"""Система быстрых действий (Quick Actions) для бота."""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


@dataclass
class QuickAction:
    """Быстрое действие."""
    id: str
    title: str
    icon: str
    callback_data: str
    description: str
    is_frequent: bool = False


class QuickActionsManager:
    """Менеджер быстрых действий."""
    
    # Определяем все доступные быстрые действия
    ACTIONS = {
        "check_status": QuickAction(
            id="check_status",
            title="Проверить статус",
            icon="✅",
            callback_data="quick_check_status",
            description="Быстро узнайте статус заявки",
            is_frequent=True
        ),
        "create_ticket": QuickAction(
            id="create_ticket",
            title="Написать в поддержку",
            icon="💬",
            callback_data="quick_create_ticket",
            description="Создайте обращение в поддержку",
            is_frequent=True
        ),
        "view_history": QuickAction(
            id="view_history",
            title="История участия",
            icon="📜",
            callback_data="quick_view_history",
            description="Посмотрите историю ваших заявок",
            is_frequent=False
        ),
        "resume_registration": QuickAction(
            id="resume_registration",
            title="Продолжить регистрацию",
            icon="▶️",
            callback_data="quick_resume_registration",
            description="Завершите незаконченную регистрацию",
            is_frequent=True
        ),
        "view_prizes": QuickAction(
            id="view_prizes",
            title="Призы розыгрыша",
            icon="🏆",
            callback_data="quick_view_prizes",
            description="Узнайте, что можно выиграть",
            is_frequent=False
        ),
        "faq": QuickAction(
            id="faq",
            title="Частые вопросы",
            icon="❓",
            callback_data="quick_faq",
            description="Быстрые ответы на популярные вопросы",
            is_frequent=True
        ),
    }
    
    def __init__(self):
        """Инициализирует менеджер быстрых действий."""
        # История действий пользователей: {user_id: [(action_id, timestamp), ...]}
        self.user_action_history: Dict[int, List[Tuple[str, datetime]]] = {}
        # Контекстные предложения: {user_id: [action_ids]}
        self.contextual_suggestions: Dict[int, List[str]] = {}
    
    def record_action(self, user_id: int, action_id: str) -> None:
        """Записывает выполненное действие."""
        if user_id not in self.user_action_history:
            self.user_action_history[user_id] = []
        
        self.user_action_history[user_id].append((action_id, datetime.now()))
        
        # Ограничиваем историю последними 50 действиями
        if len(self.user_action_history[user_id]) > 50:
            self.user_action_history[user_id] = self.user_action_history[user_id][-50:]
    
    def get_frequent_actions(self, user_id: int, limit: int = 3) -> List[QuickAction]:
        """Возвращает самые частые действия пользователя."""
        if user_id not in self.user_action_history:
            # Возвращаем действия по умолчанию для новых пользователей
            return [
                self.ACTIONS["check_status"],
                self.ACTIONS["create_ticket"],
                self.ACTIONS["faq"]
            ]
        
        # Считаем частоту действий за последние 30 дней
        cutoff_date = datetime.now() - timedelta(days=30)
        recent_actions = [
            action_id for action_id, timestamp in self.user_action_history[user_id]
            if timestamp > cutoff_date
        ]
        
        # Подсчитываем частоту
        action_counts = {}
        for action_id in recent_actions:
            action_counts[action_id] = action_counts.get(action_id, 0) + 1
        
        # Сортируем по частоте
        sorted_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Возвращаем топ действий
        result = []
        for action_id, _ in sorted_actions[:limit]:
            if action_id in self.ACTIONS:
                result.append(self.ACTIONS[action_id])
        
        # Если недостаточно действий, добавляем популярные
        if len(result) < limit:
            default_actions = [
                self.ACTIONS["check_status"],
                self.ACTIONS["create_ticket"],
                self.ACTIONS["faq"]
            ]
            for action in default_actions:
                if action not in result and len(result) < limit:
                    result.append(action)
        
        return result
    
    def get_contextual_actions(
        self,
        user_id: int,
        user_status: Optional[str] = None,
        has_incomplete_registration: bool = False
    ) -> List[QuickAction]:
        """Возвращает контекстные действия на основе состояния пользователя."""
        suggestions = []
        
        # Если есть незавершенная регистрация
        if has_incomplete_registration:
            suggestions.append(self.ACTIONS["resume_registration"])
        
        # На основе статуса
        if user_status == "pending":
            suggestions.append(self.ACTIONS["check_status"])
        elif user_status == "rejected":
            suggestions.append(self.ACTIONS["create_ticket"])
        elif user_status == "approved":
            suggestions.append(self.ACTIONS["view_prizes"])
        
        # Добавляем FAQ если еще мало действий
        if len(suggestions) < 2:
            suggestions.append(self.ACTIONS["faq"])
        
        # Добавляем историю если пользователь активен
        if user_id in self.user_action_history and len(self.user_action_history[user_id]) > 5:
            if self.ACTIONS["view_history"] not in suggestions:
                suggestions.append(self.ACTIONS["view_history"])
        
        return suggestions[:3]  # Максимум 3 контекстных действия
    
    def get_quick_actions_keyboard(
        self,
        user_id: int,
        user_status: Optional[str] = None,
        has_incomplete_registration: bool = False,
        include_back: bool = True
    ) -> InlineKeyboardMarkup:
        """Создает inline клавиатуру с быстрыми действиями."""
        buttons = []
        
        # Получаем контекстные и частые действия
        contextual = self.get_contextual_actions(user_id, user_status, has_incomplete_registration)
        frequent = self.get_frequent_actions(user_id)
        
        # Объединяем, избегая дубликатов
        all_actions = contextual.copy()
        for action in frequent:
            if action not in all_actions:
                all_actions.append(action)
        
        # Ограничиваем до 6 действий
        all_actions = all_actions[:6]
        
        # Создаем кнопки (по 2 в ряд)
        for i in range(0, len(all_actions), 2):
            row = []
            for j in range(2):
                if i + j < len(all_actions):
                    action = all_actions[i + j]
                    row.append(InlineKeyboardButton(
                        text=f"{action.icon} {action.title}",
                        callback_data=action.callback_data
                    ))
            buttons.append(row)
        
        # Кнопка назад
        if include_back:
            buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_quick_actions_reply_keyboard(
        self,
        user_id: int,
        user_status: Optional[str] = None,
        has_incomplete_registration: bool = False
    ) -> ReplyKeyboardMarkup:
        """Создает reply клавиатуру с быстрыми действиями."""
        # Получаем топ-3 действия
        contextual = self.get_contextual_actions(user_id, user_status, has_incomplete_registration)
        
        buttons = []
        for action in contextual:
            buttons.append([KeyboardButton(text=f"{action.icon} {action.title}")])
        
        # Добавляем главное меню
        buttons.append([KeyboardButton(text="🏠 Главное меню")])
        
        return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    
    def get_action_description(self, action_id: str) -> str:
        """Возвращает описание действия."""
        if action_id in self.ACTIONS:
            action = self.ACTIONS[action_id]
            return f"{action.icon} *{action.title}*\n\n{action.description}"
        return "Неизвестное действие"
    
    def suggest_next_actions(self, user_id: int, current_action: str) -> List[QuickAction]:
        """Предлагает следующие действия после текущего."""
        # Логика предложения следующих действий
        next_actions_map = {
            "check_status": ["create_ticket", "view_history"],
            "create_ticket": ["check_status", "faq"],
            "view_history": ["check_status", "view_prizes"],
            "resume_registration": ["check_status", "faq"],
            "view_prizes": ["check_status", "faq"],
            "faq": ["create_ticket", "check_status"],
        }
        
        suggested_ids = next_actions_map.get(current_action, ["check_status", "faq"])
        return [self.ACTIONS[aid] for aid in suggested_ids if aid in self.ACTIONS]


# Глобальный экземпляр
quick_actions_manager = QuickActionsManager()

