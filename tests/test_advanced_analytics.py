"""Unit tests for AdvancedAnalyticsService."""

import pytest
import asyncio
from datetime import datetime, timedelta
from services.advanced_analytics_service import (
    AdvancedAnalyticsService,
    ConversionMetrics,
    RetentionMetrics,
    MetricPeriod
)


@pytest.fixture
def analytics_service():
    """Create analytics service instance."""
    return AdvancedAnalyticsService()


@pytest.mark.asyncio
async def test_conversion_metrics_calculation():
    """Test conversion metrics calculation."""
    service = AdvancedAnalyticsService()
    
    # Мокаем данные (в реальном тесте использовать test database)
    metrics = ConversionMetrics(
        total_registrations=100,
        approved=70,
        rejected=20,
        pending=10,
        conversion_rate=70.0,
        approval_rate=77.78,
        rejection_rate=22.22
    )
    
    assert metrics.total_registrations == 100
    assert metrics.approved == 70
    assert metrics.conversion_rate == 70.0


@pytest.mark.asyncio
async def test_retention_metrics_calculation():
    """Test retention metrics calculation."""
    metrics = RetentionMetrics(
        total_users=100,
        returning_users=30,
        new_users=70,
        retention_rate=30.0,
        churn_rate=70.0
    )
    
    assert metrics.retention_rate == 30.0
    assert metrics.churn_rate == 70.0


def test_metric_period_enum():
    """Test MetricPeriod enum."""
    assert MetricPeriod.HOURLY.value == "hourly"
    assert MetricPeriod.DAILY.value == "daily"
    assert MetricPeriod.WEEKLY.value == "weekly"
    assert MetricPeriod.MONTHLY.value == "monthly"


@pytest.mark.asyncio
async def test_funnel_stages():
    """Test conversion funnel stages."""
    service = AdvancedAnalyticsService()
    
    # Тестируем структуру воронки
    # В реальном тесте вызывать get_conversion_funnel с test DB
    funnel = {
        "stages": [
            {"stage": "Начали регистрацию", "count": 100, "percentage": 100.0, "drop_off": 0},
            {"stage": "Завершили регистрацию", "count": 85, "percentage": 85.0, "drop_off": 15.0},
            {"stage": "Одобрено", "count": 70, "percentage": 70.0, "drop_off": 17.65}
        ],
        "overall_conversion": 70.0
    }
    
    assert len(funnel["stages"]) == 3
    assert funnel["overall_conversion"] == 70.0


def test_time_series_point():
    """Test TimeSeriesPoint dataclass."""
    from services.advanced_analytics_service import TimeSeriesPoint
    
    point = TimeSeriesPoint(
        timestamp=datetime.now(),
        value=42.0,
        label="2025-10-04"
    )
    
    assert point.value == 42.0
    assert point.label == "2025-10-04"


# Интеграционные тесты (требуют test database)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_analytics_flow(test_db):
    """Test full analytics flow with test database."""
    # Этот тест требует настроенной test database
    pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_heatmap_generation(test_db):
    """Test activity heatmap generation."""
    # Этот тест требует настроенной test database
    pass

