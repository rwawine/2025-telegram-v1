"""
Модуль для шардирования данных при высоких нагрузках.
Реализует механизм горизонтального шардирования для таблицы participants.
"""

import os
import sqlite3
import hashlib
import logging
import threading
from typing import List, Dict, Any, Tuple, Optional
from functools import lru_cache

from database.connection import OptimizedSQLitePool
from services.cache import MultiLevelCache as Cache

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальный кэш для шардов
shard_cache = Cache(hot_ttl=300, warm_ttl=600, cold_ttl=900)

class ShardConfig:
    """Конфигурация шардирования."""
    
    def __init__(self, base_path: str, num_shards: int = 4):
        """
        Инициализация конфигурации шардирования.
        
        Args:
            base_path: Базовый путь для хранения шардов
            num_shards: Количество шардов
        """
        self.base_path = base_path
        self.num_shards = num_shards
        self.shard_pools: Dict[int, OptimizedSQLitePool] = {}
        self._lock = threading.RLock()
        
        # Создаем директорию для шардов, если она не существует
        os.makedirs(os.path.join(base_path, "shards"), exist_ok=True)
        
        # Инициализируем пулы соединений для каждого шарда
        self._init_shard_pools()
    
    def _init_shard_pools(self):
        """Инициализация пулов соединений для шардов."""
        with self._lock:
            for shard_id in range(self.num_shards):
                shard_path = self._get_shard_path(shard_id)
                self.shard_pools[shard_id] = OptimizedSQLitePool(
                    database_path=shard_path,
                    pool_size=10
                )
                
                # Инициализируем схему шарда, если это новый шард
                self._init_shard_schema(shard_id)
    
    def _get_shard_path(self, shard_id: int) -> str:
        """
        Получение пути к файлу шарда.
        
        Args:
            shard_id: Идентификатор шарда
            
        Returns:
            Путь к файлу шарда
        """
        return os.path.join(self.base_path, "shards", f"shard_{shard_id}.db")
    
    def _init_shard_schema(self, shard_id: int):
        """
        Инициализация схемы шарда.
        
        Args:
            shard_id: Идентификатор шарда
        """
        pool = self.shard_pools[shard_id]
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            
            # Создаем таблицу participants, если она не существует
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                email TEXT,
                registration_date TIMESTAMP,
                status TEXT DEFAULT 'pending',
                rejection_reason TEXT,
                shard_id INTEGER
            )
            ''')
            
            # Создаем индексы для оптимизации запросов
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_telegram_id ON participants(telegram_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON participants(status)')
            
            conn.commit()
        finally:
            pool.release_connection(conn)
    
    def get_shard_pool(self, shard_id: int) -> OptimizedSQLitePool:
        """
        Получение пула соединений для шарда.
        
        Args:
            shard_id: Идентификатор шарда
            
        Returns:
            Пул соединений для шарда
        """
        with self._lock:
            return self.shard_pools[shard_id]


class ShardRouter:
    """Маршрутизатор запросов к шардам."""
    
    def __init__(self, config: ShardConfig):
        """
        Инициализация маршрутизатора.
        
        Args:
            config: Конфигурация шардирования
        """
        self.config = config
    
    @lru_cache(maxsize=10000)
    def get_shard_id(self, telegram_id: int) -> int:
        """
        Определение идентификатора шарда для пользователя.
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            Идентификатор шарда
        """
        # Используем хеширование для равномерного распределения
        hash_value = int(hashlib.md5(str(telegram_id).encode()).hexdigest(), 16)
        return hash_value % self.config.num_shards
    
    def execute_on_shard(self, shard_id: int, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """
        Выполнение запроса на конкретном шарде.
        
        Args:
            shard_id: Идентификатор шарда
            query: SQL-запрос
            params: Параметры запроса
            
        Returns:
            Результат запроса
        """
        pool = self.config.get_shard_pool(shard_id)
        conn = pool.get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if query.strip().upper().startswith(('SELECT', 'PRAGMA')):
                result = [dict(row) for row in cursor.fetchall()]
                return result
            else:
                conn.commit()
                return [{"rowcount": cursor.rowcount, "lastrowid": cursor.lastrowid}]
        finally:
            pool.release_connection(conn)
    
    def execute_on_all_shards(self, query: str, params: Tuple = ()) -> Dict[int, List[Dict[str, Any]]]:
        """
        Выполнение запроса на всех шардах.
        
        Args:
            query: SQL-запрос
            params: Параметры запроса
            
        Returns:
            Словарь с результатами запросов по шардам
        """
        results = {}
        for shard_id in range(self.config.num_shards):
            results[shard_id] = self.execute_on_shard(shard_id, query, params)
        return results
    
    def get_participant(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение информации о пользователе.
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            Информация о пользователе или None, если пользователь не найден
        """
        # Проверяем кэш
        cache_key = f"participant:{telegram_id}"
        cached_result = shard_cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Определяем шард
        shard_id = self.get_shard_id(telegram_id)
        
        # Выполняем запрос
        result = self.execute_on_shard(
            shard_id,
            "SELECT * FROM participants WHERE telegram_id = ?",
            (telegram_id,)
        )
        
        # Сохраняем в кэш и возвращаем результат
        if result:
            shard_cache.set(cache_key, result[0])
            return result[0]
        return None
    
    def add_participant(self, participant_data: Dict[str, Any]) -> int:
        """
        Добавление нового участника.
        
        Args:
            participant_data: Данные участника
            
        Returns:
            ID добавленного участника
        """
        telegram_id = participant_data.get('telegram_id')
        if not telegram_id:
            raise ValueError("telegram_id is required")
        
        # Определяем шард
        shard_id = self.get_shard_id(telegram_id)
        
        # Добавляем информацию о шарде
        participant_data['shard_id'] = shard_id
        
        # Формируем запрос
        fields = ', '.join(participant_data.keys())
        placeholders = ', '.join(['?'] * len(participant_data))
        query = f"INSERT INTO participants ({fields}) VALUES ({placeholders})"
        
        # Выполняем запрос
        result = self.execute_on_shard(
            shard_id,
            query,
            tuple(participant_data.values())
        )
        
        # Инвалидируем кэш
        cache_key = f"participant:{telegram_id}"
        shard_cache.invalidate(cache_key)
        
        return result[0]['lastrowid']
    
    def update_participant(self, telegram_id: int, update_data: Dict[str, Any]) -> bool:
        """
        Обновление данных участника.
        
        Args:
            telegram_id: Telegram ID участника
            update_data: Данные для обновления
            
        Returns:
            True, если обновление выполнено успешно, иначе False
        """
        # Определяем шард
        shard_id = self.get_shard_id(telegram_id)
        
        # Формируем запрос
        set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
        query = f"UPDATE participants SET {set_clause} WHERE telegram_id = ?"
        
        # Выполняем запрос
        result = self.execute_on_shard(
            shard_id,
            query,
            tuple(update_data.values()) + (telegram_id,)
        )
        
        # Инвалидируем кэш
        cache_key = f"participant:{telegram_id}"
        shard_cache.invalidate(cache_key)
        
        return result[0]['rowcount'] > 0
    
    def get_participants_by_status(self, status: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Получение списка участников по статусу.
        
        Args:
            status: Статус участников
            limit: Ограничение количества результатов
            offset: Смещение
            
        Returns:
            Список участников
        """
        # Запрашиваем данные со всех шардов
        all_results = []
        for shard_id in range(self.config.num_shards):
            results = self.execute_on_shard(
                shard_id,
                "SELECT * FROM participants WHERE status = ? LIMIT ? OFFSET ?",
                (status, limit, offset)
            )
            all_results.extend(results)
        
        # Сортируем по registration_date и применяем limit/offset
        all_results.sort(key=lambda x: x.get('registration_date', ''), reverse=True)
        return all_results[:limit]
    
    def count_participants_by_status(self) -> Dict[str, int]:
        """
        Подсчет количества участников по статусам.
        
        Returns:
            Словарь с количеством участников по статусам
        """
        # Запрашиваем данные со всех шардов
        counts = {'total': 0, 'pending': 0, 'approved': 0, 'rejected': 0}
        
        for shard_id in range(self.config.num_shards):
            # Общее количество
            total_result = self.execute_on_shard(
                shard_id,
                "SELECT COUNT(*) as count FROM participants"
            )
            counts['total'] += total_result[0]['count'] if total_result else 0
            
            # По статусам
            for status in ['pending', 'approved', 'rejected']:
                status_result = self.execute_on_shard(
                    shard_id,
                    "SELECT COUNT(*) as count FROM participants WHERE status = ?",
                    (status,)
                )
                counts[status] += status_result[0]['count'] if status_result else 0
        
        return counts
    
    def batch_insert_participants(self, participants: List[Dict[str, Any]]) -> Dict[int, List[int]]:
        """
        Пакетная вставка участников.
        
        Args:
            participants: Список данных участников
            
        Returns:
            Словарь с ID добавленных участников по шардам
        """
        # Группируем участников по шардам
        participants_by_shard = {}
        for participant in participants:
            telegram_id = participant.get('telegram_id')
            if not telegram_id:
                raise ValueError("telegram_id is required for each participant")
            
            shard_id = self.get_shard_id(telegram_id)
            participant['shard_id'] = shard_id
            
            if shard_id not in participants_by_shard:
                participants_by_shard[shard_id] = []
            participants_by_shard[shard_id].append(participant)
        
        # Вставляем данные в каждый шард
        results = {}
        for shard_id, shard_participants in participants_by_shard.items():
            shard_results = []
            
            # Получаем соединение
            pool = self.config.get_shard_pool(shard_id)
            conn = pool.get_connection()
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Выполняем вставку для каждого участника
                for participant in shard_participants:
                    fields = ', '.join(participant.keys())
                    placeholders = ', '.join(['?'] * len(participant))
                    query = f"INSERT INTO participants ({fields}) VALUES ({placeholders})"
                    
                    cursor.execute(query, tuple(participant.values()))
                    shard_results.append(cursor.lastrowid)
                    
                    # Инвалидируем кэш
                    cache_key = f"participant:{participant['telegram_id']}"
                    shard_cache.invalidate(cache_key)
                
                conn.commit()
                results[shard_id] = shard_results
            finally:
                pool.release_connection(conn)
        
        return results


# Создаем глобальные экземпляры для использования в приложении
def init_sharding(base_path: str, num_shards: int = 4) -> ShardRouter:
    """
    Инициализация системы шардирования.
    
    Args:
        base_path: Базовый путь для хранения шардов
        num_shards: Количество шардов
        
    Returns:
        Маршрутизатор шардов
    """
    config = ShardConfig(base_path, num_shards)
    router = ShardRouter(config)
    return router