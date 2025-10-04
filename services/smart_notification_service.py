"""Система умных персонализированных уведомлений."""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, time, timedelta
from dataclasses import dataclass
from enum import Enum
import random
from database.connection import get_db_pool


class NotificationPriority(Enum):
    """Приоритет уведомления."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class NotificationType(Enum):
    """Типы уведомлений."""
    STATUS_UPDATE = "status_update"
    LOTTERY_RESULT = "lottery_result"
    REMINDER = "reminder"
    SUPPORT_RESPONSE = "support_response"
    SYSTEM = "system"
    PROMOTIONAL = "promotional"


@dataclass
class NotificationTemplate:
    """Шаблон уведомления с вариантами."""
    type: NotificationType
    variants: List[str]
    priority: NotificationPriority
    best_time_start: time
    best_time_end: time


class SmartNotificationService:
    """Сервис умных персонализированных уведомлений."""
    
    # Шаблоны уведомлений с вариантами для A/B тестирования
    TEMPLATES = {
        NotificationType.STATUS_UPDATE: NotificationTemplate(
            type=NotificationType.STATUS_UPDATE,
            variants=[
                "🎉 Отличные новости, {name}! Ваша заявка одобрена!",
                "✅ {name}, поздравляем! Вы успешно прошли модерацию!",
                "🌟 {name}, ваша заявка принята! Теперь вы участник розыгрыша!",
            ],
            priority=NotificationPriority.HIGH,
            best_time_start=time(9, 0),
            best_time_end=time(21, 0)
        ),
        NotificationType.LOTTERY_RESULT: NotificationTemplate(
            type=NotificationType.LOTTERY_RESULT,
            variants=[
                "🎊 {name}, у нас потрясающие новости! Вы победитель!",
                "🏆 Поздравляем, {name}! Вы выиграли в розыгрыше!",
                "✨ {name}, это ваш счастливый день - вы выиграли!",
            ],
            priority=NotificationPriority.URGENT,
            best_time_start=time(10, 0),
            best_time_end=time(20, 0)
        ),
        NotificationType.REMINDER: NotificationTemplate(
            type=NotificationType.REMINDER,
            variants=[
                "⏰ {name}, напоминаем: {reminder_text}",
                "🔔 {name}, не забудьте: {reminder_text}",
                "💡 {name}, дружеское напоминание: {reminder_text}",
            ],
            priority=NotificationPriority.MEDIUM,
            best_time_start=time(10, 0),
            best_time_end=time(19, 0)
        ),
        NotificationType.SUPPORT_RESPONSE: NotificationTemplate(
            type=NotificationType.SUPPORT_RESPONSE,
            variants=[
                "💬 {name}, ваше обращение #{ticket_id} получило ответ!",
                "📨 {name}, поддержка ответила на ваш вопрос!",
                "✉️ {name}, новое сообщение в тикете #{ticket_id}!",
            ],
            priority=NotificationPriority.HIGH,
            best_time_start=time(8, 0),
            best_time_end=time(22, 0)
        ),
    }
    
    def __init__(self):
        """Инициализирует сервис уведомлений."""
        # История отправленных уведомлений: {user_id: [(type, timestamp), ...]}
        self.notification_history: Dict[int, List[Tuple[NotificationType, datetime]]] = {}
        
        # Предпочтения пользователей: {user_id: preferences}
        self.user_preferences: Dict[int, Dict] = {}
        
        # Результаты A/B тестов: {variant: {sent, opened, clicked}}
        self.ab_test_results: Dict[str, Dict] = {}
    
    async def send_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        params: Dict = None,
        priority: Optional[NotificationPriority] = None,
        force_send: bool = False
    ) -> bool:
        """
        Отправляет умное персонализированное уведомление.
        
        Args:
            user_id: ID пользователя
            notification_type: Тип уведомления
            params: Параметры для шаблона
            priority: Приоритет (если None - берется из шаблона)
            force_send: Игнорировать проверки времени и частоты
            
        Returns:
            True если уведомление отправлено
        """
        if params is None:
            params = {}
        
        # Получаем информацию о пользователе
        user_info = await self._get_user_info(user_id)
        if not user_info:
            return False
        
        params['name'] = user_info.get('name', 'Участник')
        
        # Проверяем, можно ли отправить уведомление
        if not force_send:
            if not await self._can_send_notification(user_id, notification_type):
                return False
            
            if not self._is_good_time_to_send(notification_type):
                # Отложим уведомление на лучшее время
                await self._schedule_notification(user_id, notification_type, params)
                return False
        
        # Получаем лучший вариант текста (A/B тестирование)
        template = self.TEMPLATES.get(notification_type)
        if not template:
            return False
        
        variant_text = self._select_best_variant(template.variants, user_id)
        
        # Персонализируем текст
        message = await self._personalize_message(variant_text, user_id, params)
        
        # Отправляем уведомление
        success = await self._send_telegram_message(user_id, message)
        
        if success:
            # Записываем в историю
            await self._record_notification(user_id, notification_type, variant_text)
        
        return success
    
    async def _get_user_info(self, user_id: int) -> Optional[Dict]:
        """Получает информацию о пользователе."""
        pool = get_db_pool()
        
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT telegram_id, full_name FROM participants WHERE telegram_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return {
                    'telegram_id': row[0],
                    'name': row[1].split()[0] if row[1] else 'Участник'  # Только имя
                }
            return None
    
    async def _can_send_notification(
        self,
        user_id: int,
        notification_type: NotificationType
    ) -> bool:
        """
        Проверяет, можно ли отправить уведомление пользователю.
        
        Учитывает:
        - Частоту уведомлений
        - Группировку похожих уведомлений
        - Предпочтения пользователя
        """
        # Проверяем предпочтения пользователя
        prefs = self.user_preferences.get(user_id, {})
        
        # Проверяем, не отключены ли уведомления этого типа
        if prefs.get(f'disable_{notification_type.value}', False):
            return False
        
        # Проверяем частоту (не более N уведомлений в час)
        max_per_hour = prefs.get('max_notifications_per_hour', 5)
        recent_count = await self._count_recent_notifications(user_id, hours=1)
        
        if recent_count >= max_per_hour:
            return False
        
        # Проверяем, не отправляли ли мы такое же уведомление недавно
        last_same_type = await self._get_last_notification_time(user_id, notification_type)
        if last_same_type:
            min_interval = timedelta(minutes=prefs.get('min_interval_minutes', 30))
            if datetime.now() - last_same_type < min_interval:
                return False
        
        return True
    
    def _is_good_time_to_send(self, notification_type: NotificationType) -> bool:
        """
        Проверяет, хорошее ли сейчас время для отправки уведомления.
        
        Избегает ночных часов и учитывает лучшее время для каждого типа.
        """
        current_time = datetime.now().time()
        
        # Никогда не отправляем ночью (00:00 - 07:00)
        if time(0, 0) <= current_time < time(7, 0):
            return False
        
        # Проверяем лучшее время для типа уведомления
        template = self.TEMPLATES.get(notification_type)
        if template:
            if not (template.best_time_start <= current_time <= template.best_time_end):
                return False
        
        return True
    
    def _select_best_variant(self, variants: List[str], user_id: int) -> str:
        """
        Выбирает лучший вариант текста на основе A/B тестирования.
        
        Использует epsilon-greedy алгоритм:
        - 80% времени выбирает лучший вариант
        - 20% времени выбирает случайный (для exploration)
        """
        if random.random() < 0.2:  # Exploration
            return random.choice(variants)
        
        # Exploitation - выбираем лучший вариант
        best_variant = variants[0]
        best_score = 0.0
        
        for variant in variants:
            results = self.ab_test_results.get(variant, {'sent': 0, 'opened': 0})
            if results['sent'] > 0:
                score = results['opened'] / results['sent']
                if score > best_score:
                    best_score = score
                    best_variant = variant
        
        return best_variant
    
    async def _personalize_message(
        self,
        template: str,
        user_id: int,
        params: Dict
    ) -> str:
        """
        Персонализирует сообщение на основе истории пользователя.
        
        Добавляет:
        - Обращение по имени
        - Контекстные данные (сколько раз участвовал и т.д.)
        - Эмоциональную окраску в зависимости от истории
        """
        # Базовая подстановка параметров
        message = template.format(**params)
        
        # Получаем историю пользователя
        user_history = await self._get_user_history(user_id)
        
        # Добавляем персонализацию
        if user_history.get('participation_count', 0) > 1:
            message += f"\n\n🌟 Вы с нами уже {user_history['participation_count']} раз!"
        
        if user_history.get('is_loyal'):
            message += "\n💎 Спасибо за вашу лояльность!"
        
        return message
    
    async def _get_user_history(self, user_id: int) -> Dict:
        """Получает историю участия пользователя."""
        pool = get_db_pool()
        
        async with pool.connection() as conn:
            # Количество участий
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM participants WHERE telegram_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            participation_count = row[0] if row else 0
            
            # Количество побед
            cursor = await conn.execute(
                """
                SELECT COUNT(*) FROM winners w
                JOIN participants p ON w.participant_id = p.id
                WHERE p.telegram_id = ?
                """,
                (user_id,)
            )
            row = await cursor.fetchone()
            wins_count = row[0] if row else 0
            
            return {
                'participation_count': participation_count,
                'wins_count': wins_count,
                'is_loyal': participation_count >= 3,
                'is_winner': wins_count > 0
            }
    
    async def _send_telegram_message(self, user_id: int, message: str) -> bool:
        """
        Отправляет сообщение через Telegram.
        
        TODO: Интегрировать с реальным bot instance
        """
        # Заглушка - нужно интегрировать с bot instance
        print(f"[NOTIFICATION] To user {user_id}: {message}")
        return True
    
    async def _record_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        variant_text: str
    ) -> None:
        """Записывает отправленное уведомление."""
        # Обновляем историю
        if user_id not in self.notification_history:
            self.notification_history[user_id] = []
        
        self.notification_history[user_id].append((notification_type, datetime.now()))
        
        # Обновляем статистику A/B теста
        if variant_text not in self.ab_test_results:
            self.ab_test_results[variant_text] = {'sent': 0, 'opened': 0, 'clicked': 0}
        
        self.ab_test_results[variant_text]['sent'] += 1
        
        # Сохраняем в БД
        pool = get_db_pool()
        async with pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO notification_log (user_id, type, variant, sent_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, notification_type.value, variant_text, datetime.now())
            )
            await conn.commit()
    
    async def _count_recent_notifications(self, user_id: int, hours: int = 1) -> int:
        """Подсчитывает количество уведомлений за последние N часов."""
        if user_id not in self.notification_history:
            return 0
        
        cutoff = datetime.now() - timedelta(hours=hours)
        return sum(1 for _, timestamp in self.notification_history[user_id] if timestamp > cutoff)
    
    async def _get_last_notification_time(
        self,
        user_id: int,
        notification_type: NotificationType
    ) -> Optional[datetime]:
        """Получает время последнего уведомления определенного типа."""
        if user_id not in self.notification_history:
            return None
        
        for ntype, timestamp in reversed(self.notification_history[user_id]):
            if ntype == notification_type:
                return timestamp
        
        return None
    
    async def _schedule_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        params: Dict
    ) -> None:
        """Откладывает уведомление на лучшее время."""
        # TODO: Реализовать очередь отложенных уведомлений
        pass
    
    async def set_user_preferences(
        self,
        user_id: int,
        preferences: Dict
    ) -> None:
        """
        Устанавливает предпочтения пользователя по уведомлениям.
        
        Args:
            user_id: ID пользователя
            preferences: Словарь с настройками:
                - max_notifications_per_hour: int
                - min_interval_minutes: int
                - disable_promotional: bool
                - quiet_hours_start: time
                - quiet_hours_end: time
        """
        self.user_preferences[user_id] = preferences
        
        # Сохраняем в БД
        pool = get_db_pool()
        async with pool.connection() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO notification_preferences (user_id, preferences)
                VALUES (?, ?)
                """,
                (user_id, str(preferences))
            )
            await conn.commit()
    
    async def group_similar_notifications(
        self,
        user_id: int,
        notifications: List[Dict]
    ) -> List[Dict]:
        """
        Группирует похожие уведомления для отправки одним сообщением.
        
        Например: "У вас 3 новых ответа в поддержке"
        вместо трех отдельных уведомлений.
        """
        grouped = {}
        
        for notif in notifications:
            ntype = notif['type']
            if ntype not in grouped:
                grouped[ntype] = []
            grouped[ntype].append(notif)
        
        result = []
        for ntype, group in grouped.items():
            if len(group) > 1:
                # Группируем
                result.append({
                    'type': ntype,
                    'count': len(group),
                    'grouped': True,
                    'items': group
                })
            else:
                result.extend(group)
        
        return result
    
    async def get_ab_test_results(self) -> Dict:
        """Получает результаты A/B тестирования."""
        return dict(self.ab_test_results)
    
    async def track_notification_opened(self, user_id: int, variant_text: str) -> None:
        """Отмечает, что пользователь открыл уведомление."""
        if variant_text in self.ab_test_results:
            self.ab_test_results[variant_text]['opened'] += 1
    
    async def track_notification_clicked(self, user_id: int, variant_text: str) -> None:
        """Отмечает, что пользователь кликнул по уведомлению."""
        if variant_text in self.ab_test_results:
            self.ab_test_results[variant_text]['clicked'] += 1


# Глобальный экземпляр
smart_notification_service = SmartNotificationService()

