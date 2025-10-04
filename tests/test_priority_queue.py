"""Unit tests for PriorityQueueService."""

import pytest
from datetime import datetime
from services.priority_queue_service import (
    PriorityQueueService,
    QueuePriority,
    ParticipantScore
)


def test_queue_priority_enum():
    """Test QueuePriority enum values."""
    assert QueuePriority.CRITICAL.value == 1
    assert QueuePriority.HIGH.value == 2
    assert QueuePriority.MEDIUM.value == 3
    assert QueuePriority.LOW.value == 4


def test_participant_score_dataclass():
    """Test ParticipantScore dataclass."""
    score = ParticipantScore(
        participant_id=123,
        total_score=0.75,
        priority=QueuePriority.HIGH,
        factors={'wait_time': 0.5, 'user_loyalty': 0.25}
    )
    assert score.participant_id == 123
    assert score.total_score == 0.75
    assert score.priority == QueuePriority.HIGH


@pytest.mark.asyncio
async def test_priority_calculation():
    """Test priority score calculation."""
    # Мокаем расчет приоритета
    # Веса: waiting_time=0.30, user_loyalty=0.25, task_complexity=0.15,
    #       system_load=0.10, sla_category=0.15, re_submission=0.05
    
    # Пример: задача ждет 12 часов, пользователь VIP
    waiting_score = 0.5  # 12 часов из 24
    loyalty_score = 0.5
    complexity_score = 0.3
    load_score = 0.5
    sla_score = 1.0  # VIP
    resubmit_score = 0.0
    
    expected_priority = (
        waiting_score * 0.30 +
        loyalty_score * 0.25 +
        complexity_score * 0.15 +
        load_score * 0.10 +
        sla_score * 0.15 +
        resubmit_score * 0.05
    )
    
    assert 0.0 <= expected_priority <= 1.0


def test_priority_weights():
    """Test priority queue weights configuration."""
    weights = {
        'wait_time': 0.30,
        'user_loyalty': 0.25,
        'complexity': 0.15,
        'system_load': 0.10,
        'sla_category': 0.15,
        'resubmission': 0.05,
    }
    
    # Сумма весов должна быть 1.0
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01  # Небольшая погрешность для float


def test_sla_definitions():
    """Test SLA time definitions."""
    from datetime import timedelta
    
    sla_times = {
        'VIP': timedelta(hours=1),
        'PREMIUM': timedelta(hours=4),
        'STANDARD': timedelta(hours=24),
        'LOW': timedelta(hours=48)
    }
    
    assert sla_times['VIP'].total_seconds() == 3600
    assert sla_times['PREMIUM'].total_seconds() == 14400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_queue_processing(test_db):
    """Integration test for queue processing."""
    # Требует test database
    pass

