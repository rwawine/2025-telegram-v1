# TODO: Пошаговая разработка системы розыгрыша призов

## 🎯 КРИТИЧЕСКИЕ ТРЕБОВАНИЯ
- ✅ **ОБЯЗАТЕЛЬНО**: Система должна выдерживать 500-1000 одновременных пользователей
- ✅ **ОБЯЗАТЕЛЬНО**: База данных должна поддерживать 10000+ участников без блокировок
- ❌ **ЗАПРЕЩЕНО**: Использовать PostgreSQL, MySQL, MongoDB
- ✅ **РАЗРЕШЕНО**: SQLite с WAL-режимом, DuckDB, встраиваемые БД
- ⚡ **ПРОИЗВОДИТЕЛЬНОСТЬ**: Время отклика < 1-2 секунды при пиковых нагрузках

---

## PHASE 1: Инициализация проекта и структура

### 1.1 Создание базовой структуры проекта
```
lottery-bot/
├── main.py                 # Точка входа
├── requirements.txt        # Зависимости
├── .env.example           # Шаблон конфигурации
├── config.py              # Конфигурация системы
├── database/
│   ├── __init__.py
│   ├── models.py          # Модели данных
│   ├── connection.py      # Пул соединений с БД
│   └── migrations.py      # Миграции схемы
├── bot/
│   ├── __init__.py
│   ├── handlers/          # Обработчики команд
│   ├── keyboards/         # Клавиатуры
│   └── states.py          # FSM состояния
├── web/
│   ├── __init__.py
│   ├── app.py            # Flask приложение
│   ├── auth.py           # Авторизация
│   ├── routes/           # Маршруты
│   ├── templates/        # HTML шаблоны
│   └── static/           # CSS/JS файлы
├── services/
│   ├── lottery.py        # Логика розыгрыша
│   ├── broadcast.py      # Рассылки
│   └── cache.py          # Кэширование
├── utils/
│   ├── performance.py    # Мониторинг производительности
│   └── validators.py     # Валидация данных
└── tests/
    └── stress_test.py    # Нагрузочное тестирование
```

### 1.2 Установка зависимостей
```python
# requirements.txt
aiogram==3.3.0          # Асинхронный Telegram бот
flask==3.0.0            # Веб-интерфейс
flask-login==0.6.3      # Авторизация
werkzeug==3.0.1         # Утилиты для Flask
python-dotenv==1.0.0    # Переменные окружения
aiosqlite==0.19.0       # Асинхронный SQLite
duckdb==0.9.2           # Альтернативная БД (опционально)
cachetools==5.3.2       # LRU кэш в памяти
pillow==10.1.0          # Обработка изображений
openpyxl==3.1.2         # Экспорт в Excel
cryptography==41.0.7    # Шифрование
ujson==5.9.0            # Быстрый JSON парсер
asyncio-throttle==1.0.2 # Rate limiting
prometheus-client==0.19.0 # Метрики производительности
```

---

## PHASE 2: Настройка базы данных для высоких нагрузок

### 2.1 Выбор и настройка БД

#### Вариант A: SQLite с WAL-режимом (рекомендуется для начала)
```python
# database/connection.py
import sqlite3
import aiosqlite
from contextlib import asynccontextmanager

class OptimizedSQLitePool:
    def __init__(self, database_path, pool_size=20):
        self.database_path = database_path
        self.pool_size = pool_size
        self.connections = []
        
    async def init_pool(self):
        """Инициализация пула соединений с оптимизациями"""
        for _ in range(self.pool_size):
            conn = await aiosqlite.connect(self.database_path)
            
            # КРИТИЧЕСКИ ВАЖНЫЕ настройки для 1000+ пользователей
            await conn.execute("PRAGMA journal_mode = WAL")  # Параллельные операции
            await conn.execute("PRAGMA synchronous = NORMAL")  # Баланс скорость/надежность
            await conn.execute("PRAGMA cache_size = -64000")  # 64MB кэш
            await conn.execute("PRAGMA temp_store = MEMORY")  # Temp в RAM
            await conn.execute("PRAGMA mmap_size = 268435456")  # 256MB mmap
            await conn.execute("PRAGMA locking_mode = NORMAL")  # Избегаем EXCLUSIVE
            await conn.execute("PRAGMA busy_timeout = 5000")  # 5 сек timeout
            
            self.connections.append(conn)
    
    @asynccontextmanager
    async def get_connection(self):
        """Получение соединения из пула"""
        # Реализовать логику получения свободного соединения
        pass
```

#### Вариант B: DuckDB для аналитики + SQLite для операций
```python
# database/hybrid_db.py
import duckdb
import aiosqlite

class HybridDatabase:
    """
    SQLite для записи/обновления (OLTP)
    DuckDB для чтения/аналитики (OLAP)
    """
    def __init__(self):
        self.sqlite_pool = OptimizedSQLitePool("data/main.db")
        self.duckdb_conn = duckdb.connect("data/analytics.duckdb")
        
    async def sync_to_duckdb(self):
        """Периодическая синхронизация SQLite -> DuckDB"""
        # Копировать данные для аналитики каждые 30 секунд
        pass
```

### 2.2 Создание оптимизированной схемы БД
```sql
-- Схема с индексами для 10000+ участников

-- Участники
CREATE TABLE participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    full_name TEXT NOT NULL,
    phone_number TEXT UNIQUE NOT NULL,
    loyalty_card TEXT UNIQUE NOT NULL,
    photo_path TEXT,
    status TEXT DEFAULT 'pending',
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- КРИТИЧЕСКИЕ индексы для производительности
CREATE INDEX idx_participants_status ON participants(status);
CREATE INDEX idx_participants_telegram_id ON participants(telegram_id);
CREATE INDEX idx_participants_phone ON participants(phone_number);
CREATE INDEX idx_participants_registration_date ON participants(registration_date);
CREATE INDEX idx_participants_composite ON participants(status, registration_date);

-- Победители (партиционированная по розыгрышам)
CREATE TABLE winners (
    id INTEGER PRIMARY KEY,
    participant_id INTEGER REFERENCES participants(id),
    lottery_date TIMESTAMP,
    position INTEGER,
    prize_description TEXT,
    claimed BOOLEAN DEFAULT FALSE
);
CREATE INDEX idx_winners_participant ON winners(participant_id);
CREATE INDEX idx_winners_lottery_date ON winners(lottery_date);

-- Оптимизация для массовых операций
CREATE TABLE broadcast_queue (
    id INTEGER PRIMARY KEY,
    participant_id INTEGER,
    message_text TEXT,
    status TEXT DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_broadcast_status ON broadcast_queue(status, created_at);
```

---

## PHASE 3: Разработка Telegram-бота с поддержкой высоких нагрузок

### 3.1 Асинхронный бот с оптимизациями
```python
# bot/__init__.py
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
from asyncio_throttle import Throttler

class OptimizedBot:
    def __init__(self, token):
        self.bot = Bot(token=token)
        
        # Настройки для 1000 одновременных пользователей
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        
        # Rate limiting
        self.throttler = Throttler(
            rate_limit=30,  # 30 сообщений в секунду
            period=1.0
        )
        
        # Пул воркеров
        self.worker_pool_size = 10
        self.message_queue = asyncio.Queue(maxsize=1000)
```

### 3.2 Кэширование для снижения нагрузки на БД
```python
# services/cache.py
from cachetools import TTLCache
import asyncio

class MultiLevelCache:
    def __init__(self):
        # L1: Горячий кэш (частые запросы)
        self.hot_cache = TTLCache(maxsize=1000, ttl=30)  # 30 сек
        
        # L2: Теплый кэш (статистика, настройки)
        self.warm_cache = TTLCache(maxsize=500, ttl=300)  # 5 мин
        
        # L3: Холодный кэш (редкие данные)
        self.cold_cache = TTLCache(maxsize=200, ttl=3600)  # 1 час
    
    async def get_participant_status(self, telegram_id):
        # Проверяем кэш перед БД
        if telegram_id in self.hot_cache:
            return self.hot_cache[telegram_id]
        
        # Если нет в кэше - запрос к БД
        status = await self.db_query(telegram_id)
        self.hot_cache[telegram_id] = status
        return status
```

### 3.3 Обработчики с батчингом
```python
# bot/handlers/registration.py
class RegistrationHandler:
    def __init__(self):
        self.batch_queue = []
        self.batch_size = 25
        self.batch_timeout = 0.5  # секунд
        
    async def batch_processor(self):
        """Обработка регистраций пакетами для оптимизации БД"""
        while True:
            if len(self.batch_queue) >= self.batch_size:
                await self.process_batch()
            await asyncio.sleep(self.batch_timeout)
    
    async def process_batch(self):
        if not self.batch_queue:
            return
        
        batch = self.batch_queue[:self.batch_size]
        self.batch_queue = self.batch_queue[self.batch_size:]
        
        # Одна транзакция для всех записей
        async with db_pool.get_connection() as conn:
            await conn.execute("BEGIN TRANSACTION")
            for item in batch:
                await conn.execute("INSERT INTO participants ...", item)
            await conn.execute("COMMIT")
```

---

## PHASE 4: Веб-интерфейс администратора

### 4.1 Flask приложение с оптимизациями
```python
# web/app.py
from flask import Flask
from flask_caching import Cache
import asyncio

app = Flask(__name__)
app.config['CACHE_TYPE'] = 'simple'
cache = Cache(app)

# Настройки для производительности
app.config.update(
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,  # 10MB максимум
    SEND_FILE_MAX_AGE_DEFAULT=3600,  # Кэш статики
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False,  # True если HTTPS
)
```

### 4.2 Страницы админки с пагинацией
```python
# web/routes/participants.py
@app.route('/participants')
@cache.cached(timeout=30)  # Кэш на 30 секунд
async def participants_list():
    page = request.args.get('page', 1, type=int)
    per_page = 50  # Не больше 50 записей на страницу
    
    # Используем LIMIT и OFFSET для пагинации
    offset = (page - 1) * per_page
    
    query = """
        SELECT * FROM participants 
        WHERE status = ?
        ORDER BY registration_date DESC
        LIMIT ? OFFSET ?
    """
    # Реализация пагинации
```

---

## PHASE 5: Система розыгрыша

### 5.1 Криптографически защищенный розыгрыш
```python
# services/lottery.py
import hashlib
import random
from datetime import datetime

class SecureLottery:
    def __init__(self):
        self.seed = None
        
    def generate_seed(self):
        """Генерация криптографического семени"""
        timestamp = datetime.now().isoformat()
        random_bytes = os.urandom(32)
        combined = f"{timestamp}{random_bytes.hex()}"
        self.seed = hashlib.sha256(combined.encode()).hexdigest()
        return self.seed
    
    async def select_winners(self, num_winners):
        # Получаем всех eligible участников
        participants = await self.get_approved_participants()
        
        # Детерминированная случайность
        random.seed(self.seed)
        winners = random.sample(participants, min(num_winners, len(participants)))
        
        return winners
```

---

## PHASE 6: Массовые рассылки

### 6.1 Оптимизированная система рассылок
```python
# services/broadcast.py
class BroadcastService:
    def __init__(self):
        self.rate_limit = 30  # сообщений в секунду
        self.retry_attempts = 3
        self.batch_size = 30
        
    async def send_broadcast(self, message, recipient_ids):
        """Рассылка на 10000+ получателей"""
        
        # Разбиваем на батчи
        for i in range(0, len(recipient_ids), self.batch_size):
            batch = recipient_ids[i:i+self.batch_size]
            
            # Параллельная отправка в батче
            tasks = [self.send_message(rid, message) for rid in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Rate limiting между батчами
            await asyncio.sleep(1.0)  # Пауза 1 секунда
```

---

## PHASE 7: Мониторинг производительности

### 7.1 Метрики и health checks
```python
# utils/performance.py
from prometheus_client import Counter, Histogram, Gauge

# Метрики для мониторинга
request_count = Counter('bot_requests_total', 'Total requests')
request_duration = Histogram('bot_request_duration_seconds', 'Request duration')
active_users = Gauge('bot_active_users', 'Active users count')
db_connections = Gauge('db_connection_pool_size', 'DB connection pool')
queue_size = Gauge('message_queue_size', 'Message queue size')

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
        
    async def check_system_health(self):
        """Проверка здоровья системы"""
        health = {
            'database': await self.check_db_health(),
            'bot': await self.check_bot_health(),
            'memory': self.check_memory_usage(),
            'queue_size': self.message_queue.qsize(),
            'active_connections': len(self.db_pool.connections)
        }
        return health
```

---

## PHASE 8: Нагрузочное тестирование

### 8.1 Создание stress test
```python
# tests/stress_test.py
import asyncio
import aiohttp
from faker import Faker

class StressTest:
    def __init__(self, num_users=1000):
        self.num_users = num_users
        self.fake = Faker()
        
    async def simulate_user(self, user_id):
        """Симуляция действий одного пользователя"""
        # 1. Старт бота
        await self.send_command('/start')
        
        # 2. Регистрация
        await self.register_user(user_id)
        
        # 3. Проверка статуса
        await self.check_status()
        
        # 4. Случайные действия
        await self.random_actions()
    
    async def run_test(self):
        """Запуск теста на 1000 пользователей"""
        print(f"Starting stress test with {self.num_users} users")
        
        tasks = []
        for i in range(self.num_users):
            task = self.simulate_user(i)
            tasks.append(task)
            
            # Постепенное увеличение нагрузки
            if i % 100 == 0:
                await asyncio.sleep(1)
        
        results = await asyncio.gather(*tasks)
        self.analyze_results(results)
```

### 8.2 Тестовые сценарии
```python
# tests/test_scenarios.py
"""
ОБЯЗАТЕЛЬНЫЕ ТЕСТЫ:
1. 1000 одновременных регистраций
2. 500 параллельных проверок статуса
3. Массовая рассылка на 10000 получателей
4. Розыгрыш с 10000 участниками
5. 100 одновременных загрузок фото
6. Работа при заполненной БД (10000+ записей)
"""
```

---

## PHASE 9: Оптимизация и тюнинг

### 9.1 Профилирование и оптимизация
```python
# utils/profiler.py
import cProfile
import pstats
import memory_profiler

class SystemProfiler:
    def profile_bottlenecks(self):
        """Поиск узких мест"""
        # 1. Анализ медленных SQL запросов
        # 2. Поиск N+1 проблем
        # 3. Проверка утечек памяти
        # 4. Оптимизация горячих путей кода
```

### 9.2 Настройки для продакшена
```python
# config.py
class ProductionConfig:
    # База данных
    DB_POOL_SIZE = 20
    DB_TIMEOUT = 5000  # ms
    
    # Бот
    BOT_WORKERS = 10
    MESSAGE_QUEUE_SIZE = 1000
    RATE_LIMIT = 30  # msg/sec
    
    # Кэш
    CACHE_TTL_HOT = 30  # seconds
    CACHE_TTL_WARM = 300
    CACHE_SIZE = 1000
    
    # Батчинг
    BATCH_SIZE = 25
    BATCH_TIMEOUT = 0.5
    
    # Мониторинг
    ALERT_RESPONSE_TIME = 3  # seconds
    ALERT_CPU_USAGE = 80  # percent
    ALERT_MEMORY_USAGE = 80  # percent
```

---

## PHASE 10: Развертывание и запуск

### 10.1 Подготовка сервера
```bash
# Требования к VPS
# - 4 CPU cores (минимум 2)
# - 4GB RAM (минимум 2GB)
# - 20GB SSD
# - Ubuntu 22.04 LTS

# Установка системных зависимостей
sudo apt update
sudo apt install python3.10 python3-pip python3-venv
sudo apt install sqlite3 nginx supervisor
```

### 10.2 Запуск системы
```python
# main.py
async def main():
    # 1. Инициализация БД с оптимизациями
    await init_optimized_database()
    
    # 2. Прогрев кэшей
    await warmup_caches()
    
    # 3. Запуск пула воркеров
    await start_worker_pool()
    
    # 4. Запуск бота
    bot_task = asyncio.create_task(start_bot())
    
    # 5. Запуск веб-сервера
    web_task = asyncio.create_task(start_web_server())
    
    # 6. Запуск мониторинга
    monitor_task = asyncio.create_task(start_monitoring())
    
    # 7. Ожидание завершения
    await asyncio.gather(bot_task, web_task, monitor_task)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📊 КОНТРОЛЬНЫЕ ТОЧКИ ПРОИЗВОДИТЕЛЬНОСТИ

### Минимальные требования для приемки:
- [ ] **Test 1**: 1000 одновременных `/start` команд обрабатываются < 2 сек
- [ ] **Test 2**: Регистрация 500 пользователей одновременно без "database is locked"
- [ ] **Test 3**: Проверка статуса для 1000 пользователей < 1 сек на запрос
- [ ] **Test 4**: Розыгрыш среди 10000 участников завершается < 5 сек
- [ ] **Test 5**: Массовая рассылка на 10000 получателей без потерь
- [ ] **Test 6**: Стабильная работа 24 часа с 500 активными пользователями
- [ ] **Test 7**: Потребление RAM < 2GB при 1000 онлайн
- [ ] **Test 8**: CPU < 70% при пиковых нагрузках
- [ ] **Test 9**: Веб-интерфейс отзывчив при 10000 записях в БД
- [ ] **Test 10**: Backup БД с 10000 записей < 30 секунд

### Критерии отказа (система НЕ принимается если):
- ❌ Появляется "database is locked" при нормальной работе
- ❌ Время ответа бота > 3 секунды
- ❌ Потеря сообщений при рассылке
- ❌ Падение системы при 1000 пользователях
- ❌ Использование PostgreSQL/MySQL/MongoDB

---

## 🚀 ПОРЯДОК ВЫПОЛНЕНИЯ

1. Phase 1-2 (Структура + БД)
2. Phase 3 (Telegram бот)
3. Phase 4-5 (Веб-интерфейс + Розыгрыш)
4. Phase 6-7 (Рассылки + Мониторинг)
5. Phase 8 (Тестирование производительности)
6. Phase 9 (Оптимизация)
7. Phase 10 (Развертывание)

## ⚠️ КРИТИЧЕСКИ ВАЖНО

**ПОМНИ**: Система ДОЛЖНА работать с 500-1000 одновременными пользователями и 10000+ участниками в базе используя ТОЛЬКО встраиваемые БД (SQLite/DuckDB). Это не рекомендация, а ОБЯЗАТЕЛЬНОЕ требование!

Каждый шаг должен быть протестирован на производительность перед переходом к следующему.