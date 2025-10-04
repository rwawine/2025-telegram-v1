# 🎰 Lottery Bot - Telegram Bot для Розыгрышей

> Современный высокопроизводительный Telegram бот для проведения розыгрышей призов с веб-панелью администратора.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-blue.svg)](https://docs.aiogram.dev/)
[![Flask](https://img.shields.io/badge/flask-3.x-green.svg)](https://flask.palletsprojects.com/)

## 📋 Содержание

- [Возможности](#-возможности)
- [Быстрый старт](#-быстрый-старт)
- [Структура проекта](#-структура-проекта)
- [Конфигурация](#-конфигурация)
- [Документация](#-документация)
- [Лицензия](#-лицензия)

## ✨ Возможности

### Для пользователей
- 📝 **Регистрация** с проверкой данных (имя, телефон, карта лояльности, фото)
- 💾 **Автосохранение прогресса** регистрации
- ✅ **Подтверждение данных** перед отправкой (inline клавиатура)
- 📊 **Проверка статуса** заявки в реальном времени
- 🎫 **Техподдержка** с системой тикетов
- 🔔 **Уведомления** о статусе заявки и результатах розыгрыша

### Для администраторов
- 🎲 **Провоцируемый честный розыгрыш** с криптографическими гарантиями
- 👥 **Модерация участников** (одобрение/отклонение заявок)
- 📊 **Детальная аналитика** и статистика
- 📢 **Массовые рассылки** с поддержкой медиа
- 🎯 **Управление победителями** (перерозыгрыш, уведомления)
- 💬 **Управление тикетами** техподдержки
- 📈 **Мониторинг системы** в реальном времени

### Технические особенности
- ⚡ **Высокая производительность** (500+ пользователей одновременно)
- 🛡️ **Защита от мошенничества** (FraudDetectionService)
- 💾 **Многоуровневое кэширование** (hot/warm/cold tiers)
- 📊 **Аналитика событий** (AnalyticsService)
- 🔄 **Retry механизм** для загрузки фото
- 🗄️ **Оптимизированный пул соединений** SQLite
- 🔐 **CSRF защита** для веб-панели
- 📱 **Адаптивный дизайн** админ-панели

## 🚀 Быстрый старт

### Требования

- Python 3.11+
- SQLite 3.35+
- Telegram Bot Token (от [@BotFather](https://t.me/BotFather))

### Установка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/yourusername/lottery-bot.git
cd lottery-bot

# 2. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Создать файл .env
cp .env.example .env
# Отредактировать .env и добавить токены
```

### Конфигурация (.env)

```env
# Telegram Bot
BOT_TOKEN=your_bot_token_here
ADMIN_USER_IDS=123456789,987654321

# Admin Panel
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure_password_here
SECRET_KEY=your-secret-key-here

# Database
DATABASE_PATH=data/lottery_bot.sqlite

# Optional
LOG_LEVEL=INFO
MAX_FILE_SIZE=10485760
RATE_LIMIT=30
```

### Запуск

```bash
# Запуск бота и веб-панели
python main.py

# Бот будет доступен в Telegram
# Веб-панель: http://localhost:5000
```

### Первый запуск

1. **Запустите бота** - он автоматически создаст все необходимые таблицы
2. **Войдите в админ-панель** (http://localhost:5000)
3. **Создайте тестовую заявку** через бота
4. **Одобрите заявку** в панели модерации
5. **Проведите розыгрыш** в разделе "Розыгрыши"

## 📁 Структура проекта

```
lottery-bot/
├── bot/                    # Telegram бот
│   ├── handlers/          # Обработчики команд и сообщений
│   ├── keyboards/         # Клавиатуры
│   ├── middleware/        # Middleware (rate limit, логирование)
│   └── states.py          # FSM состояния
├── web/                   # Веб-панель администратора
│   ├── routes/           # Маршруты Flask
│   ├── templates/        # HTML шаблоны
│   └── static/          # CSS, JS, изображения
├── services/             # Бизнес-логика
│   ├── lottery.py       # Сервис розыгрышей
│   ├── broadcast.py     # Сервис рассылок
│   ├── cache.py         # Кэширование
│   ├── analytics_service.py        # Аналитика
│   ├── fraud_detection_service.py  # Защита от мошенничества
│   ├── notification_service.py     # Уведомления
│   └── photo_upload_service.py     # Загрузка фото
├── database/             # Работа с БД
│   ├── repositories.py  # Репозитории данных
│   ├── migrations.py    # Миграции
│   └── connection.py    # Пул соединений
├── core/                 # Ядро приложения
│   ├── logger.py        # Логирование
│   ├── constants.py     # Константы
│   └── exceptions.py    # Исключения
├── utils/                # Утилиты
│   └── validators.py    # Валидаторы
├── scripts/              # Вспомогательные скрипты
│   ├── health_check.py  # Проверка здоровья
│   └── load_test.py     # Нагрузочное тестирование
├── docs/                 # Документация
├── main.py              # Точка входа
├── config.py            # Конфигурация
└── requirements.txt     # Зависимости
```

## ⚙️ Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|-----------|----------|--------------|
| `BOT_TOKEN` | Токен Telegram бота | - |
| `ADMIN_USER_IDS` | ID администраторов (через запятую) | - |
| `ADMIN_USERNAME` | Логин админ-панели | `admin` |
| `ADMIN_PASSWORD` | Пароль админ-панели | - |
| `SECRET_KEY` | Секретный ключ Flask | - |
| `DATABASE_PATH` | Путь к БД SQLite | `data/lottery_bot.sqlite` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |
| `MAX_FILE_SIZE` | Макс. размер фото (байты) | `10485760` (10 МБ) |
| `RATE_LIMIT` | Лимит запросов в минуту | `30` |

### Настройка лимитов

Редактируйте `core/constants.py` для изменения:
- Лимитов сообщений Telegram
- Размеров загружаемых файлов
- Параметров валидации данных
- Timeouts и retry логики

## 📚 Документация

- **[Архитектура](docs/ARCHITECTURE.md)** - Подробное описание архитектуры системы
- **[Развертывание](docs/DEPLOYMENT.md)** - Инструкции по развертыванию в production
- **[API Reference](docs/API_REFERENCE.md)** - Описание внутренних API и сервисов

## 🧪 Тестирование

```bash
# Smoke тест (быстрая проверка)
python scripts/smoke_test.py

# Нагрузочное тестирование (500+ пользователей)
python scripts/load_test.py

# Проверка здоровья системы
python scripts/health_check.py
```

## 🛠️ Разработка

### Требования для разработки

```bash
pip install -r requirements.txt
```

### Запуск в режиме разработки

```bash
# С автоперезагрузкой
export FLASK_ENV=development
python main.py
```

### Линтинг и форматирование

```bash
# Проверка типов
mypy .

# Форматирование
black .
isort .
```

## 📊 Производительность

По результатам нагрузочных тестов:

- ✅ **500 одновременных регистраций**: 100% успех
- ⚡ **~12 операций/сек** при полном цикле регистрации
- 💾 **Среднее время отклика**: ~1.8 секунды
- 🎯 **Максимальное время**: < 5 секунд

## 🔒 Безопасность

- 🛡️ **Fraud Detection** - автоматическое обнаружение мошенничества
- 🔐 **CSRF Protection** - защита веб-панели
- 🚦 **Rate Limiting** - ограничение частоты запросов
- 📝 **Валидация данных** - на всех уровнях
- 🔑 **Безопасное хранение** - хеширование паролей (bcrypt)

## 🚢 Развертывание

### Render.com (рекомендуется)

1. Создайте новый Web Service
2. Подключите репозиторий
3. Настройте переменные окружения
4. Render автоматически использует `render.yaml`

### Docker (скоро)

```bash
docker-compose up -d
```

### VPS/Dedicated Server

См. подробные инструкции в [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## 📝 Changelog

### v2.0.0 (Current)
- ✨ Добавлен FraudDetectionService
- ✨ Добавлен AnalyticsService
- ✨ Добавлен NotificationService
- ✨ Автосохранение прогресса регистрации
- ✨ Inline клавиатура подтверждения
- ✨ Retry механизм для загрузки фото
- ⚡ Оптимизирован пул соединений БД
- 🐛 Исправлены многочисленные баги

## 🤝 Вклад в проект

Contributions welcome! Пожалуйста:

1. Fork репозиторий
2. Создайте feature branch (`git checkout -b feature/amazing`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing`)
5. Создайте Pull Request

## 📄 Лицензия

MIT License - см. файл [LICENSE](LICENSE)

## 💬 Поддержка

- 📧 Email: support@example.com
- 💬 Telegram: [@yoursupport](https://t.me/yoursupport)
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/lottery-bot/issues)

## 🙏 Благодарности

- [aiogram](https://github.com/aiogram/aiogram) - Telegram Bot framework
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [SQLite](https://www.sqlite.org/) - Database engine

---

<p align="center">Сделано с ❤️ для проведения честных розыгрышей</p>
