# 📡 API Reference - Lottery Bot

## Содержание

- [Services API](#services-api)
- [Database Repositories](#database-repositories)
- [Bot Handlers](#bot-handlers)
- [Web API Endpoints](#web-api-endpoints)
- [Utilities](#utilities)

## Services API

### LotteryService

Сервис для проведения честных розыгрышей.

#### `SecureLottery`

```python
from services import SecureLottery

lottery = SecureLottery()
```

**Methods:**

##### `async draw_winners(num_winners: int, seed: Optional[str] = None) -> List[Winner]`

Провести розыгрыш и выбрать победителей.

**Parameters:**
- `num_winners` (int): Количество победителей
- `seed` (str, optional): Seed для генератора. Если None, генерируется автоматически

**Returns:**
- `List[Winner]`: Список победителей с их данными

**Example:**
```python
winners = await lottery.draw_winners(num_winners=10)
for winner in winners:
    print(f"{winner.full_name} - {winner.telegram_id}")
```

**Raises:**
- `ValueError`: Если недостаточно одобренных участников

---

### CacheService

Многоуровневое кэширование.

#### `MultiLevelCache`

```python
from services import MultiLevelCache

cache = MultiLevelCache(
    hot_ttl=60,      # 1 minute
    warm_ttl=300,    # 5 minutes
    cold_ttl=3600    # 1 hour
)
```

**Methods:**

##### `async get_or_set(key: str, loader: Callable, level: str = "hot") -> Any`

Получить значение из кэша или загрузить с помощью loader.

**Parameters:**
- `key` (str): Ключ кэша
- `loader` (Callable): Async функция для загрузки данных
- `level` (str): Уровень кэша ("hot", "warm", "cold")

**Returns:**
- `Any`: Кэшированное или загруженное значение

**Example:**
```python
async def load_user_status(user_id):
    return await get_participant_status(user_id)

status = await cache.get_or_set(
    key=f"status:{user_id}",
    loader=lambda: load_user_status(user_id),
    level="hot"
)
```

##### `def invalidate(key: str) -> None`

Удалить значение из кэша.

**Example:**
```python
cache.invalidate(f"status:{user_id}")
```

---

### AnalyticsService

Сервис аналитики и трекинга событий.

#### `AnalyticsService`

```python
from services import AnalyticsService, AnalyticsEvent
```

**Methods:**

##### `async track_event(event_type: AnalyticsEvent, user_id: Optional[int] = None, properties: Optional[Dict[str, Any]] = None) -> bool`

Отследить событие.

**Parameters:**
- `event_type` (AnalyticsEvent): Тип события
- `user_id` (int, optional): ID пользователя
- `properties` (dict, optional): Дополнительные свойства события

**Returns:**
- `bool`: True если успешно отслежено

**Example:**
```python
await AnalyticsService.track_event(
    AnalyticsEvent.REGISTRATION_STARTED,
    user_id=123456789,
    properties={"source": "referral", "device": "mobile"}
)
```

##### `async track_registration_step(user_id: int, step: str, success: bool, error: Optional[str] = None) -> bool`

Отследить шаг регистрации.

**Parameters:**
- `user_id` (int): ID пользователя
- `step` (str): Название шага ("name", "phone", "loyalty_card", "photo")
- `success` (bool): Успешность шага
- `error` (str, optional): Сообщение об ошибке если неуспешно

**Example:**
```python
await AnalyticsService.track_registration_step(
    user_id=123456789,
    step="name",
    success=False,
    error="Invalid name format"
)
```

##### `async get_event_count(event_type: AnalyticsEvent, hours: int = 24) -> int`

Получить количество событий за последние N часов.

**Example:**
```python
count = await AnalyticsService.get_event_count(
    AnalyticsEvent.REGISTRATION_COMPLETED,
    hours=24
)
print(f"Registrations in last 24h: {count}")
```

**Event Types:**

```python
class AnalyticsEvent(str, Enum):
    REGISTRATION_STARTED = "registration_started"
    REGISTRATION_STEP_COMPLETED = "registration_step_completed"
    REGISTRATION_COMPLETED = "registration_completed"
    REGISTRATION_ABANDONED = "registration_abandoned"
    SUPPORT_TICKET_CREATED = "support_ticket_created"
    MENU_OPENED = "menu_opened"
    BUTTON_CLICKED = "button_clicked"
    ERROR_OCCURRED = "error_occurred"
```

---

### FraudDetectionService

Сервис обнаружения мошенничества.

#### `FraudDetectionService`

```python
from services import get_fraud_detection_service

fraud_service = get_fraud_detection_service()
```

**Methods:**

##### `async check_registration(user_id: int, full_name: str, phone_number: str, loyalty_card: str, registration_time: float) -> FraudScore`

Проверить регистрацию на признаки мошенничества.

**Parameters:**
- `user_id` (int): Telegram ID пользователя
- `full_name` (str): Полное имя
- `phone_number` (str): Номер телефона
- `loyalty_card` (str): Номер карты лояльности
- `registration_time` (float): Время регистрации в секундах

**Returns:**
- `FraudScore`: Объект с результатами проверки

**Example:**
```python
fraud_score = await fraud_service.check_registration(
    user_id=123456789,
    full_name="John Doe",
    phone_number="+1234567890",
    loyalty_card="ABC123",
    registration_time=45.5
)

if fraud_score.should_block:
    print(f"BLOCKED: Score {fraud_score.score}")
    print(f"Reasons: {fraud_score.reasons}")
elif fraud_score.is_suspicious:
    print(f"SUSPICIOUS: Score {fraud_score.score}")
```

**FraudScore:**
```python
@dataclass
class FraudScore:
    score: float              # 0.0-1.0 (0=safe, 1=fraud)
    reasons: list[str]        # Причины подозрения
    is_suspicious: bool       # True если score >= 0.5
    should_block: bool        # True если score >= 0.8
```

##### `async log_suspicious_activity(user_id: int, activity_type: str, details: Dict[str, Any]) -> None`

Залогировать подозрительную активность.

**Example:**
```python
await fraud_service.log_suspicious_activity(
    user_id=123456789,
    activity_type="multiple_attempts",
    details={"attempts": 5, "time_window": "10min"}
)
```

---

### NotificationService

Сервис уведомлений пользователей.

#### `NotificationService`

```python
from services import get_notification_service

notification_service = get_notification_service()
```

**Methods:**

##### `async notify_registration_status(user_id: int, status: str, reason: Optional[str] = None) -> bool`

Уведомить пользователя о статусе регистрации.

**Parameters:**
- `user_id` (int): Telegram ID
- `status` (str): Статус ("approved", "rejected", "pending")
- `reason` (str, optional): Причина отклонения

**Example:**
```python
await notification_service.notify_registration_status(
    user_id=123456789,
    status="approved"
)
```

##### `async notify_lottery_winner(user_id: int, prize_description: str) -> bool`

Уведомить победителя розыгрыша.

**Example:**
```python
await notification_service.notify_lottery_winner(
    user_id=123456789,
    prize_description="iPhone 15 Pro"
)
```

##### `async notify_ticket_status_change(user_id: int, ticket_id: int, old_status: str, new_status: str, admin_comment: Optional[str] = None) -> bool`

Уведомить об изменении статуса тикета.

**Example:**
```python
await notification_service.notify_ticket_status_change(
    user_id=123456789,
    ticket_id=42,
    old_status="open",
    new_status="closed",
    admin_comment="Проблема решена"
)
```

---

### PhotoUploadService

Сервис загрузки фото с retry механизмом.

#### `PhotoUploadService`

```python
from services import get_photo_upload_service

photo_service = get_photo_upload_service()
```

**Methods:**

##### `async download_photo_with_retry(file_id: str, retry_delay: float = 1.0) -> Optional[str]`

Скачать фото с автоматическими повторными попытками.

**Parameters:**
- `file_id` (str): Telegram file ID
- `retry_delay` (float): Задержка между попытками в секундах

**Returns:**
- `str`: Путь к сохраненному файлу
- `None`: Если загрузка не удалась

**Example:**
```python
file_path = await photo_service.download_photo_with_retry(
    file_id="AgACAgIAAxkBAAIC...",
    retry_delay=1.0
)

if file_path:
    print(f"Photo saved to: {file_path}")
else:
    print("Failed to download photo")
```

##### `async validate_photo_size(file_size: Optional[int], max_size: int = 10485760) -> tuple[bool, Optional[str]]`

Валидировать размер фото.

**Returns:**
- `tuple[bool, Optional[str]]`: (is_valid, error_message)

**Example:**
```python
is_valid, error_msg = await photo_service.validate_photo_size(
    file_size=5242880  # 5 MB
)
```

---

### RegistrationStateManager

Менеджер состояния регистрации с автосохранением.

#### `RegistrationStateManager`

```python
from services import RegistrationStateManager
```

**Methods:**

##### `async save_state(user_id: int, state_data: Dict[str, Any]) -> bool`

Сохранить состояние регистрации.

**Example:**
```python
await RegistrationStateManager.save_state(
    user_id=123456789,
    state_data={
        "full_name": "John Doe",
        "phone_number": "+1234567890",
        "loyalty_card": "ABC123"
    }
)
```

##### `async load_state(user_id: int) -> Optional[Dict[str, Any]]`

Загрузить сохраненное состояние.

**Returns:**
- `dict`: Данные состояния
- `None`: Если нет сохраненного состояния или истек срок

**Example:**
```python
state = await RegistrationStateManager.load_state(user_id=123456789)
if state:
    print(f"Saved name: {state.get('full_name')}")
```

##### `async clear_state(user_id: int) -> bool`

Очистить сохраненное состояние.

##### `async create_confirmation_message(state_data: Dict[str, Any]) -> str`

Создать сообщение подтверждения из данных состояния.

**Example:**
```python
message = await RegistrationStateManager.create_confirmation_message(state_data)
await bot.send_message(user_id, message)
```

---

## Database Repositories

### Participant Repository

```python
from database.repositories import (
    get_participant_status,
    insert_participants_batch,
    get_approved_participants,
    update_participant_status
)
```

#### `async get_participant_status(telegram_id: int) -> Optional[str]`

Получить статус участника.

**Returns:**
- `str`: "pending", "approved", "rejected"
- `None`: Пользователь не найден

**Example:**
```python
status = await get_participant_status(123456789)
if status == "approved":
    print("User approved!")
```

#### `async insert_participants_batch(records: List[Dict[str, Any]]) -> None`

Массовая вставка участников (батчинг для производительности).

**Example:**
```python
records = [
    {
        "telegram_id": 123456789,
        "username": "john_doe",
        "full_name": "John Doe",
        "phone_number": "+1234567890",
        "loyalty_card": "ABC123",
        "photo_path": "uploads/photo.jpg"
    },
    # ... more records
]
await insert_participants_batch(records)
```

#### `async get_approved_participants() -> List[Tuple[int, str]]`

Получить список одобренных участников для розыгрыша.

**Returns:**
- `List[Tuple[int, str]]`: [(participant_id, full_name), ...]

**Example:**
```python
approved = await get_approved_participants()
print(f"Ready for lottery: {len(approved)} participants")
```

---

## Bot Handlers

### Registration Handler

```python
from bot.handlers.registration import setup_registration_handlers

handler = setup_registration_handlers(
    dispatcher,
    upload_dir=Path("uploads"),
    cache=cache,
    bot=bot
)
```

**States:**
```python
from bot.states import RegistrationStates

class RegistrationStates(StatesGroup):
    enter_name = State()
    enter_phone = State()
    enter_loyalty_card = State()
    upload_photo = State()
```

---

## Web API Endpoints

### Admin Panel Routes

**Authentication Required:** Все endpoints требуют авторизации через login.

#### Dashboard
- `GET /admin/` - Главная панель с статистикой

#### Participants
- `GET /admin/participants` - Список участников
- `GET /admin/participants/<id>` - Детали участника
- `POST /admin/participants/<id>/status` - Обновить статус
- `POST /admin/participants/bulk-action` - Массовое действие
- `GET /admin/participants/export` - Экспорт в CSV

#### Lottery
- `GET /admin/lottery` - Управление розыгрышами
- `POST /admin/lottery/run` - Провести розыгрыш
- `GET /admin/lottery/history` - История розыгрышей
- `POST /admin/lottery/notify_winners` - Уведомить всех победителей
- `POST /admin/lottery/notify_winner/<id>` - Уведомить одного победителя

#### Broadcasts
- `GET /admin/broadcasts` - Список рассылок
- `POST /admin/broadcasts/create` - Создать рассылку
- `POST /admin/broadcasts/<id>/send` - Отправить рассылку

#### Support
- `GET /admin/support` - Список тикетов
- `GET /admin/support/<id>` - Детали тикета
- `POST /admin/support/<id>/reply` - Ответить на тикет
- `POST /admin/support/<id>/close` - Закрыть тикет

### Health Check Endpoints

#### `GET /health`

Базовая проверка здоровья.

**Response:**
```json
{
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

#### `GET /health/db`

Проверка подключения к базе данных.

**Response:**
```json
{
    "status": "healthy",
    "database": "connected",
    "participants_count": 1523
}
```

#### `GET /health/detailed`

Детальная проверка всех компонентов.

**Response:**
```json
{
    "status": "healthy",
    "components": {
        "database": "ok",
        "cache": "ok",
        "disk_space": "ok"
    },
    "metrics": {
        "participants": 1523,
        "approved": 1250,
        "pending": 200,
        "rejected": 73
    }
}
```

---

## Utilities

### Validators

```python
from utils.validators import (
    validate_full_name,
    validate_phone,
    validate_loyalty_card,
    normalize_phone
)
```

#### `validate_full_name(name: str) -> bool`

Валидирует полное имя (минимум 2 слова, только буквы, дефисы и пробелы).

**Example:**
```python
if validate_full_name("John Doe"):
    print("Valid name")
```

#### `validate_phone(phone: str) -> bool`

Валидирует номер телефона (7-15 цифр, опциональный +).

**Example:**
```python
if validate_phone("+1234567890"):
    print("Valid phone")
```

#### `validate_loyalty_card(card: str) -> bool`

Валидирует номер карты лояльности (6-20 символов, буквы и цифры).

#### `normalize_phone(phone: str) -> str`

Нормализует номер телефона к единому формату.

**Example:**
```python
normalized = normalize_phone("8 (900) 123-45-67")
# Returns: "+79001234567"
```

---

## Error Handling

### Custom Exceptions

```python
from core.exceptions import (
    DatabaseError,
    ValidationError,
    NotFoundException,
    RateLimitError
)
```

**Example:**
```python
try:
    await some_operation()
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
    await message.answer("Invalid data format")
except DatabaseError as e:
    logger.error(f"Database error: {e}")
    await message.answer("System error, please try again")
```

---

## Constants

```python
from core.constants import (
    TelegramLimits,
    FileUploadLimits,
    ValidationRules
)
```

### TelegramLimits
```python
TelegramLimits.MESSAGE_LENGTH = 4096
TelegramLimits.CAPTION_LENGTH = 1024
TelegramLimits.RATE_LIMIT = 30  # messages per second
```

### FileUploadLimits
```python
FileUploadLimits.MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10 MB
FileUploadLimits.ALLOWED_FORMATS = ["jpg", "jpeg", "png"]
```

### ValidationRules
```python
ValidationRules.MIN_NAME_LENGTH = 2
ValidationRules.MAX_NAME_LENGTH = 100
ValidationRules.PHONE_LENGTH_MIN = 7
ValidationRules.PHONE_LENGTH_MAX = 15
```

---

## Logging

```python
from core import get_logger

logger = get_logger(__name__)
```

**Usage:**
```python
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)
```

**Structured logging:**
```python
logger.info(
    "User registered",
    extra={
        "user_id": 123456789,
        "status": "approved",
        "registration_time": 45.5
    }
)
```

---

<p align="center">API Reference для версии 2.0.0</p>

