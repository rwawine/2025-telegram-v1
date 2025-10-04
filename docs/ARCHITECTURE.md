# 🏗️ Архитектура Lottery Bot

## Содержание

- [Обзор](#обзор)
- [Архитектурные принципы](#архитектурные-принципы)
- [Компоненты системы](#компоненты-системы)
- [Потоки данных](#потоки-данных)
- [База данных](#база-данных)
- [Масштабирование](#масштабирование)

## Обзор

Lottery Bot построен на модульной архитектуре с четким разделением ответственности между компонентами.

```
┌─────────────────────────────────────────────────────────┐
│                     Users / Admins                       │
└────────────┬──────────────────────────┬──────────────────┘
             │                          │
    ┌────────▼────────┐        ┌────────▼────────┐
    │  Telegram Bot   │        │   Web Panel     │
    │   (aiogram)     │        │    (Flask)      │
    └────────┬────────┘        └────────┬────────┘
             │                          │
    ┌────────▼──────────────────────────▼────────┐
    │           Services Layer                   │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐  │
    │  │ Lottery  │ │Analytics │ │  Fraud   │  │
    │  │ Broadcast│ │  Photo   │ │  Notify  │  │
    │  └──────────┘ └──────────┘ └──────────┘  │
    └────────┬──────────────────────────────────┘
             │
    ┌────────▼────────┐
    │  Data Layer     │
    │  ┌──────────┐   │
    │  │ SQLite   │   │
    │  │+ Cache   │   │
    │  └──────────┘   │
    └─────────────────┘
```

## Архитектурные принципы

### 1. Слоистая архитектура

**Presentation Layer (Слой представления)**
- `bot/handlers/` - обработчики Telegram сообщений
- `web/routes/` - маршруты веб-панели
- `bot/keyboards/` - клавиатуры бота

**Business Logic Layer (Бизнес-логика)**
- `services/` - сервисы бизнес-логики
- Изолированы от деталей представления
- Переиспользуемые между bot и web

**Data Access Layer (Доступ к данным)**
- `database/repositories.py` - репозитории
- `database/connection.py` - управление соединениями
- Абстракция над SQLite

### 2. Разделение ответственности

Каждый модуль отвечает за одну задачу:

```python
# ❌ Плохо: все в одном месте
async def handle_registration(message):
    # Валидация
    # Сохранение в БД
    # Отправка уведомления
    # Аналитика
    pass

# ✅ Хорошо: разделенная ответственность
async def handle_registration(message):
    data = await validator.validate(message)
    await repository.save(data)
    await notification_service.notify(user_id)
    await analytics.track_event("registration", user_id)
```

### 3. Dependency Injection

Сервисы получают зависимости через конструктор:

```python
class RegistrationHandler:
    def __init__(self, upload_dir: Path, cache, bot):
        self.upload_dir = upload_dir
        self.cache = cache
        self.bot = bot
```

### 4. Singleton Pattern для сервисов

```python
# Глобальный singleton для доступа из любой точки
_notification_service: Optional[NotificationService] = None

def get_notification_service() -> NotificationService:
    if _notification_service is None:
        raise RuntimeError("Service not initialized")
    return _notification_service
```

## Компоненты системы

### 1. Bot Layer (bot/)

#### Handlers (bot/handlers/)

**registration.py** - Регистрация пользователей
- FSM-based регистрация (4 шага)
- Валидация на каждом шаге
- Автосохранение прогресса
- Inline подтверждение

**support.py** - Система поддержки
- Создание тикетов
- Просмотр истории
- FAQ

**common.py** - Общие обработчики
- Проверка статуса
- Главное меню

**global_commands.py** - Глобальные команды
- /start, /help, /menu
- Доступны из любого состояния

#### Middleware (bot/middleware/)

**rate_limit.py** - Rate Limiting
```python
class RateLimitMiddleware:
    """Ограничивает частоту запросов пользователя."""
    def __init__(self, rate_limit: int = 30):
        self.rate_limit = rate_limit  # requests per minute
```

**fsm_logger.py** - Логирование FSM переходов
- Отслеживание состояний
- Отладка потока пользователя

#### Keyboards (bot/keyboards/)

**main_menu.py** - Главное меню
- Динамическая генерация на основе статуса
- Адаптивные кнопки

**smart_keyboards.py** - Умные клавиатуры
- Contact sharing
- Location sharing
- Inline кнопки

### 2. Services Layer (services/)

#### LotteryService (lottery.py)

**Функции:**
- Криптографически честный розыгрыш
- Генерация seed на основе блокчейн хеша
- Детерминированный выбор победителей

**Алгоритм:**
```python
def draw_winners(participants, seed):
    random.seed(seed)
    return random.sample(participants, k=num_winners)
```

#### BroadcastService (broadcast.py)

**Функции:**
- Массовая рассылка сообщений
- Поддержка медиа (фото, видео)
- Retry логика при ошибках
- Tracking статуса доставки

**Queue-based подход:**
```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Job      │────▶│ Queue    │────▶│ Sent     │
│ Created  │     │ Pending  │     │ Success  │
└──────────┘     └──────────┘     └──────────┘
                       │
                       ▼
                 ┌──────────┐
                 │ Failed   │
                 │+ Retry   │
                 └──────────┘
```

#### CacheService (cache.py)

**Многоуровневое кэширование:**

```python
class MultiLevelCache:
    hot_tier   # Fast, short TTL (60s)
    warm_tier  # Medium TTL (5min)
    cold_tier  # Long TTL (1h)
```

**Стратегия:**
- Hot tier: Часто запрашиваемые данные (статус пользователя)
- Warm tier: Периодически обновляемые (список участников)
- Cold tier: Редко меняющиеся (FAQ)

#### AnalyticsService (analytics_service.py)

**События:**
- `REGISTRATION_STARTED` - Начало регистрации
- `REGISTRATION_STEP_COMPLETED` - Завершение шага
- `REGISTRATION_COMPLETED` - Успешная регистрация
- `BUTTON_CLICKED` - Клик по кнопке
- `ERROR_OCCURRED` - Возникновение ошибки

**Использование:**
```python
await AnalyticsService.track_event(
    AnalyticsEvent.REGISTRATION_STARTED,
    user_id=user_id,
    properties={"source": "referral"}
)
```

#### FraudDetectionService (fraud_detection_service.py)

**Проверки:**
1. Скорость регистрации (< 15 сек = подозрительно)
2. Дубликаты телефонов/карт
3. Множественные попытки
4. Подозрительные паттерны в данных
5. Высокая активность

**Scoring:**
```
0.0 - 0.4: Safe
0.5 - 0.7: Suspicious (warning)
0.8 - 1.0: High risk (block)
```

#### NotificationService (notification_service.py)

**Типы уведомлений:**
- Изменение статуса заявки
- Ответ на тикет поддержки
- Победа в розыгрыше
- Системные уведомления

#### PhotoUploadService (photo_upload_service.py)

**Функции:**
- Retry механизм (3 попытки)
- Exponential backoff
- Валидация размера
- Автоочистка старых файлов

### 3. Database Layer (database/)

#### Connection Pool (connection.py)

```python
class OptimizedSQLitePool:
    """Оптимизированный пул соединений."""
    def __init__(self, pool_size: int = 10):
        self.pool_size = pool_size
        self.connections = []
```

**Особенности:**
- WAL mode для concurrent reads
- Connection pooling
- Automatic retry при busy

#### Repositories (repositories.py)

**Pattern: Repository**
```python
async def get_participant_status(telegram_id: int):
    """Получить статус участника."""
    # Изоляция SQL-логики
```

**Batch Operations:**
```python
async def insert_participants_batch(records: List[Dict]):
    """Массовая вставка для производительности."""
    # 25 записей за раз
```

#### Migrations (migrations.py)

**Версионирование схемы:**
```python
SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS participants ...",
    "CREATE INDEX IF NOT EXISTS idx_participants_status ...",
    # ...
)
```

### 4. Web Layer (web/)

#### Flask Application (app.py)

**Компоненты:**
- Flask app с blueprint-based routing
- CSRF protection
- Session management
- Error handlers (404, 500)

#### Routes (web/routes/)

**admin.py** - Основные маршруты
- Dashboard
- Participants management
- Lottery management
- Broadcasts
- Support tickets
- System logs

**health.py** - Health checks
- `/health` - Базовая проверка
- `/health/db` - Проверка БД
- `/health/detailed` - Детальная проверка

#### Templates (web/templates/)

**Использование:**
- Jinja2 templating
- Bootstrap 5 для UI
- Font Awesome иконки
- Custom CSS для брендинга

## Потоки данных

### Поток регистрации

```
User                   Bot Handler              Services              Database
  │                         │                       │                     │
  │─────"Начать"───────────▶│                       │                     │
  │                         │                       │                     │
  │                         │──track_event()───────▶│                     │
  │                         │                       │──INSERT analytics──▶│
  │                         │                       │                     │
  │◀────"Введите имя"───────│                       │                     │
  │                         │                       │                     │
  │─────"Иван Иванов"──────▶│                       │                     │
  │                         │──validate_name()─────▶│                     │
  │                         │                       │                     │
  │                         │──save_state()────────▶│                     │
  │                         │                       │──INSERT state──────▶│
  │                         │                       │                     │
  │◀────"Введите телефон"───│                       │                     │
  │         ...             │          ...          │        ...          │
  │                         │                       │                     │
  │─────Подтвердить────────▶│                       │                     │
  │                         │──check_fraud()───────▶│                     │
  │                         │                       │──SELECT duplicates─▶│
  │                         │                       │◀────results─────────│
  │                         │◀─────fraud_score──────│                     │
  │                         │                       │                     │
  │                         │──insert_participant()─▶                     │
  │                         │                       │──INSERT participant▶│
  │                         │                       │                     │
  │◀────"Успех!"───────────│                       │                     │
```

### Поток розыгрыша

```
Admin Panel            Lottery Service         Database
     │                       │                     │
     │──"Run Lottery"───────▶│                     │
     │   (10 winners)        │                     │
     │                       │──get_approved()────▶│
     │                       │◀───participants─────│
     │                       │                     │
     │                       │──generate_seed()    │
     │                       │  (blockchain hash)  │
     │                       │                     │
     │                       │──draw_winners()     │
     │                       │  (deterministic)    │
     │                       │                     │
     │                       │──save_winners()────▶│
     │                       │                     │──INSERT winners
     │                       │                     │──INSERT lottery_run
     │                       │                     │
     │◀──winners_list────────│                     │
     │                       │                     │
     │──"Notify winners"────▶│                     │
     │                       │──notify_service()   │
     │                       │    (async)          │
```

## База данных

### Схема

```sql
-- Participants (Участники)
CREATE TABLE participants (
    id INTEGER PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    phone_number TEXT UNIQUE NOT NULL,
    loyalty_card TEXT UNIQUE NOT NULL,
    photo_path TEXT,
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected
    registration_date TIMESTAMP,
    admin_notes TEXT
);

-- Winners (Победители)
CREATE TABLE winners (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL,
    participant_id INTEGER NOT NULL,
    position INTEGER,
    prize_description TEXT,
    lottery_date TIMESTAMP,
    FOREIGN KEY(run_id) REFERENCES lottery_runs(id),
    FOREIGN KEY(participant_id) REFERENCES participants(id)
);

-- Lottery Runs (Розыгрыши)
CREATE TABLE lottery_runs (
    id INTEGER PRIMARY KEY,
    seed TEXT NOT NULL,
    executed_at TIMESTAMP,
    winners_count INTEGER NOT NULL
);

-- Analytics Events (Аналитика)
CREATE TABLE analytics_events (
    id INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id INTEGER,
    properties TEXT,  -- JSON
    timestamp TEXT NOT NULL
);

-- Fraud Log (Журнал мошенничества)
CREATE TABLE fraud_log (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    activity_type TEXT NOT NULL,
    details TEXT,  -- JSON
    detected_at TIMESTAMP
);

-- Registration States (Состояния регистрации)
CREATE TABLE registration_states (
    user_id INTEGER PRIMARY KEY,
    state_data TEXT NOT NULL,  -- JSON
    updated_at TEXT NOT NULL
);
```

### Индексы

```sql
-- Performance indexes
CREATE INDEX idx_participants_status ON participants(status);
CREATE INDEX idx_participants_telegram_id ON participants(telegram_id);
CREATE INDEX idx_analytics_events_user_id ON analytics_events(user_id);
CREATE INDEX idx_fraud_log_user ON fraud_log(user_id, detected_at);
```

### Оптимизации

1. **WAL Mode** - Concurrent reads без блокировки
2. **Connection Pooling** - Переиспользование соединений
3. **Batch Inserts** - До 25 записей за раз
4. **Prepared Statements** - Защита от SQL injection

## Масштабирование

### Горизонтальное масштабирование

**Telegram Bot:**
- Stateless design позволяет запускать несколько инстансов
- Long polling с разными offsets
- Webhook mode для production

**Web Panel:**
- Stateless Flask app
- Session в Redis (опционально)
- Load balancer (Nginx/HAProxy)

### Вертикальное масштабирование

**Database:**
- SQLite → PostgreSQL при > 1M записей
- Read replicas для аналитики
- Sharding по telegram_id

**Cache:**
- In-memory → Redis cluster
- Distributed cache

### Bottlenecks

1. **SQLite write lock** - Ограничение ~1000 writes/sec
   - Solution: PostgreSQL или batch writes
   
2. **Telegram API rate limits** - 30 msg/sec
   - Solution: Queue с throttling
   
3. **File storage** - Локальное хранилище фото
   - Solution: S3-compatible storage

### Мониторинг

**Метрики:**
- Request rate (bot commands/sec)
- Response time (percentiles: p50, p95, p99)
- Error rate (%)
- Queue length (broadcast queue)
- Cache hit rate (%)
- DB connection pool utilization

**Alerts:**
- Error rate > 5%
- Response time p95 > 5s
- Queue length > 1000
- DB connections exhausted

### Disaster Recovery

**Backup Strategy:**
1. Daily automated SQLite backups
2. Incremental backups каждый час
3. Off-site backup storage
4. Point-in-time recovery до 7 дней

**Recovery Plan:**
1. Restore database from backup
2. Verify data integrity
3. Restart services
4. Test critical paths
5. Monitor for issues

---

## Дальнейшее развитие

### Планируемые улучшения

1. **WebSocket для real-time updates**
2. **GraphQL API** для mobile apps
3. **Микросервисная архитектура** для крупных инсталляций
4. **Event-driven architecture** с message broker
5. **AI-powered fraud detection** с ML моделями

### Технический долг

- [ ] Рефакторинг длинных функций в registration.py
- [ ] Добавить integration tests
- [ ] Документировать все API endpoints
- [ ] Мигрировать на async SQLAlchemy
- [ ] Добавить OpenAPI спецификацию

---

<p align="center">Документация актуальна для версии 2.0.0</p>
