"""Интеллектуальная система приоритетной очереди обработки заявок."""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio
from database.connection import get_db_pool


class QueuePriority(Enum):
    """Уровни приоритета в очереди."""
    CRITICAL = 1  # Срочные (VIP, проблемы)
    HIGH = 2      # Высокий (давно ждут)
    MEDIUM = 3    # Средний (обычные)
    LOW = 4       # Низкий (новые)


@dataclass
class ParticipantScore:
    """Оценка приоритета участника."""
    participant_id: int
    total_score: float
    priority: QueuePriority
    factors: Dict[str, float]  # Факторы, влияющие на приоритет


class PriorityQueueService:
    """
    Интеллектуальная очередь обработки заявок.
    
    Вместо простого FIFO учитывает множество факторов:
    - Время ожидания (старые заявки выше)
    - История пользователя (лояльные пользователи приоритетнее)
    - Сложность проверки (простые заявки быстрее)
    - Текущая загрузка системы (балансировка)
    - SLA для разных категорий пользователей
    """
    
    # Веса для факторов (можно настраивать)
    WEIGHTS = {
        'wait_time': 0.30,           # Время ожидания
        'user_loyalty': 0.25,        # Лояльность пользователя
        'complexity': 0.15,          # Сложность проверки
        'system_load': 0.10,         # Загрузка системы
        'sla_category': 0.15,        # SLA категория
        'resubmission': 0.05,        # Повторная подача
    }
    
    # SLA категории (время обработки в часах)
    SLA = {
        'vip': 1,        # VIP - 1 час
        'premium': 4,    # Premium - 4 часа
        'standard': 24,  # Standard - 24 часа
        'low': 48,       # Low - 48 часов
    }
    
    def __init__(self):
        """Инициализирует сервис очереди."""
        self.queue_cache: Dict[int, ParticipantScore] = {}
        self.last_queue_update = datetime.now()
    
    async def get_next_participant(self, moderator_workload: int = 0) -> Optional[Dict]:
        """
        Возвращает следующего участника из очереди с учетом всех факторов.
        
        Args:
            moderator_workload: Текущая загрузка модератора (0-100)
            
        Returns:
            Словарь с данными участника или None
        """
        # Обновляем очередь если нужно
        if datetime.now() - self.last_queue_update > timedelta(minutes=5):
            await self._rebuild_queue()
        
        # Получаем всех участников в очереди с приоритетами
        scored_participants = await self._score_all_participants(moderator_workload)
        
        if not scored_participants:
            return None
        
        # Сортируем по приоритету
        sorted_participants = sorted(
            scored_participants,
            key=lambda x: (x.priority.value, -x.total_score)
        )
        
        # Возвращаем участника с наивысшим приоритетом
        top_participant = sorted_participants[0]
        
        return await self._get_participant_details(top_participant.participant_id)
    
    async def get_queue_stats(self) -> Dict:
        """
        Получает статистику очереди.
        
        Returns:
            Статистика: общее количество, по приоритетам, средние времена
        """
        pool = get_db_pool()
        
        async with pool.connection() as conn:
            # Общее количество в очереди
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM participants WHERE status = 'pending'"
            )
            total = (await cursor.fetchone())[0]
            
            # Средн время ожидания
            cursor = await conn.execute(
                """
                SELECT AVG(julianday('now') - julianday(registration_date)) * 24 as avg_wait_hours
                FROM participants 
                WHERE status = 'pending'
                """
            )
            row = await cursor.fetchone()
            avg_wait_hours = row[0] if row and row[0] else 0
            
            # Распределение по возрасту заявок
            cursor = await conn.execute(
                """
                SELECT 
                    CASE 
                        WHEN julianday('now') - julianday(registration_date) < 1 THEN 'new'
                        WHEN julianday('now') - julianday(registration_date) < 3 THEN 'pending'
                        ELSE 'old'
                    END as age_category,
                    COUNT(*) as count
                FROM participants
                WHERE status = 'pending'
                GROUP BY age_category
                """
            )
            age_distribution = {row[0]: row[1] for row in await cursor.fetchall()}
        
        return {
            'total_pending': total,
            'avg_wait_hours': round(avg_wait_hours, 2),
            'age_distribution': age_distribution,
            'queue_health': self._calculate_queue_health(total, avg_wait_hours)
        }
    
    async def _score_all_participants(self, moderator_workload: int) -> List[ParticipantScore]:
        """Оценивает всех участников в очереди."""
        pool = get_db_pool()
        scores = []
        
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, telegram_id, registration_date, full_name, phone_number
                FROM participants
                WHERE status = 'pending'
                ORDER BY registration_date
                """
            )
            participants = await cursor.fetchall()
            
            for participant in participants:
                score = await self._calculate_priority_score(
                    dict(participant),
                    moderator_workload
                )
                scores.append(score)
        
        return scores
    
    async def _calculate_priority_score(
        self,
        participant: Dict,
        moderator_workload: int
    ) -> ParticipantScore:
        """
        Вычисляет приоритетную оценку для участника.
        
        Учитывает множество факторов с настраиваемыми весами.
        """
        factors = {}
        
        # 1. Фактор времени ожидания (0-100)
        wait_time_hours = (datetime.now() - participant['registration_date']).total_seconds() / 3600
        factors['wait_time'] = min(wait_time_hours / 48 * 100, 100)  # Нормализуем к 48 часам
        
        # 2. Фактор лояльности пользователя (0-100)
        user_loyalty = await self._calculate_user_loyalty(participant['telegram_id'])
        factors['user_loyalty'] = user_loyalty
        
        # 3. Фактор сложности проверки (0-100)
        complexity = await self._estimate_verification_complexity(participant)
        factors['complexity'] = 100 - complexity  # Инвертируем: простые = выше
        
        # 4. Фактор загрузки системы (0-100)
        system_load = await self._get_system_load()
        # При высокой загрузке приоритизируем простые заявки
        factors['system_load'] = (100 - system_load) if complexity < 50 else system_load
        
        # 5. Фактор SLA категории (0-100)
        sla_category = await self._get_user_sla_category(participant['telegram_id'])
        sla_hours = self.SLA.get(sla_category, 24)
        sla_urgency = min(wait_time_hours / sla_hours * 100, 100)
        factors['sla_category'] = sla_urgency
        
        # 6. Фактор повторной подачи (0-100)
        is_resubmission = await self._is_resubmission(participant['telegram_id'])
        factors['resubmission'] = 80 if is_resubmission else 20
        
        # Вычисляем взвешенную сумму
        total_score = sum(
            factors[key] * self.WEIGHTS[key]
            for key in factors
        )
        
        # Определяем категорию приоритета
        if total_score >= 80:
            priority = QueuePriority.CRITICAL
        elif total_score >= 60:
            priority = QueuePriority.HIGH
        elif total_score >= 40:
            priority = QueuePriority.MEDIUM
        else:
            priority = QueuePriority.LOW
        
        return ParticipantScore(
            participant_id=participant['id'],
            total_score=total_score,
            priority=priority,
            factors=factors
        )
    
    async def _calculate_user_loyalty(self, telegram_id: int) -> float:
        """
        Вычисляет лояльность пользователя (0-100).
        
        Учитывает:
        - Количество предыдущих участий
        - Количество побед
        - Наличие одобренных заявок
        """
        pool = get_db_pool()
        
        async with pool.connection() as conn:
            # Количество предыдущих участий
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM participants WHERE telegram_id = ? AND status = 'approved'",
                (telegram_id,)
            )
            approved_count = (await cursor.fetchone())[0]
            
            # Количество побед
            cursor = await conn.execute(
                """
                SELECT COUNT(*) FROM winners w
                JOIN participants p ON w.participant_id = p.id
                WHERE p.telegram_id = ?
                """,
                (telegram_id,)
            )
            wins_count = (await cursor.fetchone())[0]
            
            # Вычисляем оценку лояльности
            loyalty_score = min(
                (approved_count * 10) + (wins_count * 30),
                100
            )
            
            return float(loyalty_score)
    
    async def _estimate_verification_complexity(self, participant: Dict) -> float:
        """
        Оценивает сложность проверки заявки (0-100).
        
        Факторы сложности:
        - Наличие всех данных
        - Качество фото
        - История отклонений
        """
        complexity = 30  # Базовая сложность
        
        # Проверяем наличие всех данных
        if not participant.get('full_name'):
            complexity += 20
        if not participant.get('phone_number'):
            complexity += 20
        
        # TODO: Добавить проверку качества фото через ML
        
        # Проверяем историю отклонений
        pool = get_db_pool()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM participants WHERE telegram_id = ? AND status = 'rejected'",
                (participant['telegram_id'],)
            )
            rejected_count = (await cursor.fetchone())[0]
            complexity += min(rejected_count * 10, 30)
        
        return min(complexity, 100)
    
    async def _get_system_load(self) -> float:
        """
        Получает текущую загрузку системы (0-100).
        
        Учитывает:
        - Количество заявок в очереди
        - Количество активных модераторов
        - Среднее время обработки
        """
        pool = get_db_pool()
        
        async with pool.connection() as conn:
            # Количество в очереди
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM participants WHERE status = 'pending'"
            )
            pending_count = (await cursor.fetchone())[0]
            
            # Нормализуем к 100
            load_score = min(pending_count / 100 * 100, 100)
            
            return float(load_score)
    
    async def _get_user_sla_category(self, telegram_id: int) -> str:
        """
        Определяет SLA категорию пользователя.
        
        Категории:
        - vip: VIP пользователи, победители
        - premium: Лояльные пользователи (3+ участия)
        - standard: Обычные пользователи
        - low: Новые пользователи
        """
        pool = get_db_pool()
        
        async with pool.connection() as conn:
            # Проверяем, является ли пользователь победителем
            cursor = await conn.execute(
                """
                SELECT COUNT(*) FROM winners w
                JOIN participants p ON w.participant_id = p.id
                WHERE p.telegram_id = ?
                """,
                (telegram_id,)
            )
            is_winner = (await cursor.fetchone())[0] > 0
            
            if is_winner:
                return 'vip'
            
            # Проверяем количество участий
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM participants WHERE telegram_id = ?",
                (telegram_id,)
            )
            participation_count = (await cursor.fetchone())[0]
            
            if participation_count >= 3:
                return 'premium'
            elif participation_count >= 1:
                return 'standard'
            else:
                return 'low'
    
    async def _is_resubmission(self, telegram_id: int) -> bool:
        """Проверяет, является ли заявка повторной подачей."""
        pool = get_db_pool()
        
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM participants WHERE telegram_id = ? AND status = 'rejected'",
                (telegram_id,)
            )
            rejected_count = (await cursor.fetchone())[0]
            
            return rejected_count > 0
    
    async def _get_participant_details(self, participant_id: int) -> Optional[Dict]:
        """Получает полные данные участника."""
        pool = get_db_pool()
        
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM participants WHERE id = ?",
                (participant_id,)
            )
            row = await cursor.fetchone()
            
            return {key: row[key] for key in row.keys()} if row else None
    
    async def _rebuild_queue(self) -> None:
        """Перестраивает кэш очереди."""
        self.queue_cache.clear()
        self.last_queue_update = datetime.now()
    
    def _calculate_queue_health(self, total_pending: int, avg_wait_hours: float) -> str:
        """
        Оценивает здоровье очереди.
        
        Returns:
            'healthy', 'warning', 'critical'
        """
        if total_pending < 10 and avg_wait_hours < 12:
            return 'healthy'
        elif total_pending < 50 and avg_wait_hours < 24:
            return 'warning'
        else:
            return 'critical'
    
    async def get_queue_visualization(self) -> Dict:
        """
        Создает данные для визуализации очереди.
        
        Returns:
            Данные для графиков и диаграмм
        """
        scored_participants = await self._score_all_participants(0)
        
        # Распределение по приоритетам
        priority_distribution = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }
        
        for score in scored_participants:
            priority_distribution[score.priority.name.lower()] += 1
        
        # Топ-10 факторов влияния
        factor_importance = {}
        for score in scored_participants:
            for factor, value in score.factors.items():
                if factor not in factor_importance:
                    factor_importance[factor] = []
                factor_importance[factor].append(value)
        
        avg_factors = {
            factor: sum(values) / len(values)
            for factor, values in factor_importance.items()
        }
        
        return {
            'priority_distribution': priority_distribution,
            'total_queue': len(scored_participants),
            'avg_factors': avg_factors,
            'top_priority_ids': [s.participant_id for s in scored_participants[:10]]
        }


# Глобальный экземпляр
priority_queue_service = PriorityQueueService()

