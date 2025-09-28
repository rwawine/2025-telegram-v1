"""
Интеграция шардирования с существующим кодом.
"""

import os
import logging
import sys
from typing import Dict, List, Any, Optional

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Импортируем конфигурацию шардирования
from config import load_config

# Загружаем конфигурацию
config = load_config()
SHARDING_ENABLED = config.sharding_enabled
SHARDING_BASE_PATH = config.sharding_base_path
SHARDING_NUM_SHARDS = config.sharding_num_shards
from database.sharding import init_sharding, ShardRouter

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальный экземпляр маршрутизатора шардов
shard_router: Optional[ShardRouter] = None

def initialize_sharding():
    """Инициализация системы шардирования."""
    global shard_router
    
    if SHARDING_ENABLED:
        logger.info(f"Initializing sharding with {SHARDING_NUM_SHARDS} shards at {SHARDING_BASE_PATH}")
        shard_router = init_sharding(SHARDING_BASE_PATH, SHARDING_NUM_SHARDS)
        return shard_router
    else:
        logger.info("Sharding is disabled")
        return None

def get_shard_router() -> Optional[ShardRouter]:
    """
    Получение экземпляра маршрутизатора шардов.
    
    Returns:
        Маршрутизатор шардов или None, если шардирование отключено
    """
    global shard_router
    
    if shard_router is None and SHARDING_ENABLED:
        shard_router = initialize_sharding()
    
    return shard_router

# Функции-обертки для работы с участниками

def get_participant(telegram_id: int) -> Optional[Dict[str, Any]]:
    """
    Получение информации об участнике с учетом шардирования.
    
    Args:
        telegram_id: Telegram ID участника
        
    Returns:
        Информация об участнике или None, если участник не найден
    """
    router = get_shard_router()
    
    if router:
        return router.get_participant(telegram_id)
    else:
        # Используем стандартный метод без шардирования
        from database.repositories import get_participant as get_participant_standard
        return get_participant_standard(telegram_id)

def add_participant(participant_data: Dict[str, Any]) -> int:
    """
    Добавление нового участника с учетом шардирования.
    
    Args:
        participant_data: Данные участника
        
    Returns:
        ID добавленного участника
    """
    router = get_shard_router()
    
    if router:
        return router.add_participant(participant_data)
    else:
        # Используем стандартный метод без шардирования
        from database.repositories import add_participant as add_participant_standard
        return add_participant_standard(participant_data)

def update_participant(telegram_id: int, update_data: Dict[str, Any]) -> bool:
    """
    Обновление данных участника с учетом шардирования.
    
    Args:
        telegram_id: Telegram ID участника
        update_data: Данные для обновления
        
    Returns:
        True, если обновление выполнено успешно, иначе False
    """
    router = get_shard_router()
    
    if router:
        return router.update_participant(telegram_id, update_data)
    else:
        # Используем стандартный метод без шардирования
        from database.repositories import update_participant as update_participant_standard
        return update_participant_standard(telegram_id, update_data)

def get_participants_by_status(status: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Получение списка участников по статусу с учетом шардирования.
    
    Args:
        status: Статус участников
        limit: Ограничение количества результатов
        offset: Смещение
        
    Returns:
        Список участников
    """
    router = get_shard_router()
    
    if router:
        return router.get_participants_by_status(status, limit, offset)
    else:
        # Используем стандартный метод без шардирования
        from database.repositories import get_participants_by_status as get_participants_standard
        return get_participants_standard(status, limit, offset)

def count_participants_by_status() -> Dict[str, int]:
    """
    Подсчет количества участников по статусам с учетом шардирования.
    
    Returns:
        Словарь с количеством участников по статусам
    """
    router = get_shard_router()
    
    if router:
        return router.count_participants_by_status()
    else:
        # Используем стандартный метод без шардирования
        from database.repositories import count_participants_by_status as count_participants_standard
        return count_participants_standard()

def batch_insert_participants(participants: List[Dict[str, Any]]) -> Dict[int, List[int]]:
    """
    Пакетная вставка участников с учетом шардирования.
    
    Args:
        participants: Список данных участников
        
    Returns:
        Словарь с ID добавленных участников по шардам или список ID
    """
    router = get_shard_router()
    
    if router:
        return router.batch_insert_participants(participants)
    else:
        # Используем стандартный метод без шардирования
        from database.repositories import batch_insert_participants as batch_insert_standard
        result = batch_insert_standard(participants)
        # Преобразуем результат в формат, совместимый с шардированием
        return {0: result} if isinstance(result, list) else result