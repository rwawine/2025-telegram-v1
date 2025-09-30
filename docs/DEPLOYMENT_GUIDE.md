# 🚀 Руководство по развертыванию

## Быстрый старт для продакшена

### Шаг 1: Подготовка окружения

```bash
# Клонируем репозиторий
git clone <repository-url>
cd 2025-telegram-v1

# Создаем виртуальное окружение
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
.\venv\Scripts\activate  # Windows

# Устанавливаем зависимости
pip install -r requirements.txt
```

### Шаг 2: Настройка конфигурации

```bash
# Копируем example файл
cp .env.example .env

# Редактируем .env
nano .env
```

**Обязательные переменные для продакшена:**

```env
# Telegram Bot
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
ENABLE_BOT=True

# Security
SECRET_KEY=<генерируем_случайную_строку_64_символа>

# Admin Panel
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<надежный_пароль_минимум_12_символов>
ADMIN_IDS=123456789,987654321

# Database
DATABASE_PATH=data/lottery_bot.sqlite
DB_POOL_SIZE=20
DB_BUSY_TIMEOUT=10000

# Cache
CACHE_TTL_HOT=300
CACHE_TTL_WARM=1800
CACHE_TTL_COLD=7200

# Web Server
WEB_HOST=0.0.0.0
WEB_PORT=5000

# Performance
BOT_RATE_LIMIT=30
BOT_WORKER_THREADS=4
MESSAGE_QUEUE_SIZE=1000
```

**Генерация SECRET_KEY:**

```python
import secrets
print(secrets.token_urlsafe(48))
```

### Шаг 3: Инициализация системы

```bash
# Создаем необходимые папки
mkdir -p data logs uploads exports backups

# Запускаем инициализацию (автоматически при первом запуске)
python main.py
```

При первом запуске система автоматически:
- Создаст базу данных
- Выполнит миграции
- Создаст файл .env (если его нет)
- Настроит структуру папок

### Шаг 4: Проверка готовности

```bash
# Запускаем тесты
python tests/test_bot_comprehensive_context.py
python tests/test_bot_integration_scenarios.py

# Проверяем конфигурацию
python -c "from config import load_config; c = load_config(); print(f'Bot enabled: {c.enable_bot}')"

# Проверяем подключение к Telegram
python -c "import asyncio; from aiogram import Bot; asyncio.run(Bot(token='YOUR_TOKEN').get_me())"
```

---

## 🌐 Развертывание на Render.com

### Преимущества Render.com
- ✅ Бесплатный tier для небольших проектов
- ✅ Автоматический SSL
- ✅ Простое развертывание из Git
- ✅ Автоматические перезапуски

### Инструкция

1. **Создать аккаунт на Render.com**
   - Перейти на https://render.com
   - Зарегистрироваться через GitHub

2. **Создать новый Web Service**
   - Dashboard → New → Web Service
   - Подключить ваш репозиторий
   - Выбрать ветку `main`

3. **Настроить параметры**
   ```
   Name: lottery-bot
   Environment: Python 3.11
   Build Command: pip install -r requirements.txt
   Start Command: python main.py
   ```

4. **Добавить переменные окружения**
   - В разделе Environment добавить все переменные из .env
   - **Важно:** Добавить `PORT` (Render автоматически назначит)

5. **Deploy**
   - Нажать "Create Web Service"
   - Дождаться завершения деплоя (5-10 минут)

6. **Проверка**
   ```
   https://your-app.onrender.com/health
   ```

### Настройка автоматического деплоя

```bash
# Подключаем GitHub Actions
git add .github/workflows/deploy.yml
git commit -m "Add auto-deploy"
git push origin main
```

---

## 🐳 Развертывание через Docker

### Dockerfile (создать в корне проекта)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем приложение
COPY . .

# Создаем необходимые папки
RUN mkdir -p data logs uploads exports backups

# Открываем порт
EXPOSE 5000

# Запускаем приложение
CMD ["python", "main.py"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  lottery-bot:
    build: .
    container_name: lottery-bot
    restart: always
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - SECRET_KEY=${SECRET_KEY}
      - ADMIN_USERNAME=${ADMIN_USERNAME}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - PORT=5000
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./uploads:/app/uploads
      - ./backups:/app/backups
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Запуск через Docker

```bash
# Сборка образа
docker-compose build

# Запуск
docker-compose up -d

# Проверка логов
docker-compose logs -f

# Остановка
docker-compose down
```

---

## 🖥️ Развертывание на VPS (Ubuntu 22.04)

### Полная инструкция

```bash
# 1. Подключаемся к серверу
ssh user@your-server-ip

# 2. Обновляем систему
sudo apt update && sudo apt upgrade -y

# 3. Устанавливаем Python 3.11
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev -y

# 4. Устанавливаем дополнительные зависимости
sudo apt install git nginx sqlite3 -y

# 5. Создаем пользователя для приложения
sudo useradd -m -s /bin/bash lottery
sudo su - lottery

# 6. Клонируем репозиторий
git clone <repository-url> lottery-bot
cd lottery-bot

# 7. Настраиваем виртуальное окружение
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 8. Настраиваем .env
nano .env
# (вставляем конфигурацию)

# 9. Выходим из пользователя lottery
exit

# 10. Создаем systemd service
sudo nano /etc/systemd/system/lottery-bot.service
```

**Содержимое lottery-bot.service:**

```ini
[Unit]
Description=Telegram Lottery Bot
After=network.target

[Service]
Type=simple
User=lottery
WorkingDirectory=/home/lottery/lottery-bot
ExecStart=/home/lottery/lottery-bot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=append:/home/lottery/lottery-bot/logs/service.log
StandardError=append:/home/lottery/lottery-bot/logs/service-error.log

[Install]
WantedBy=multi-user.target
```

```bash
# 11. Активируем и запускаем сервис
sudo systemctl daemon-reload
sudo systemctl enable lottery-bot
sudo systemctl start lottery-bot
sudo systemctl status lottery-bot

# 12. Настраиваем Nginx
sudo nano /etc/nginx/sites-available/lottery-bot
```

**Содержимое Nginx конфига:**

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /home/lottery/lottery-bot/web/static;
        expires 30d;
    }
}
```

```bash
# 13. Активируем конфиг Nginx
sudo ln -s /etc/nginx/sites-available/lottery-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 14. Настраиваем SSL (Let's Encrypt)
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com

# 15. Настраиваем автоматическое обновление сертификата
sudo systemctl enable certbot.timer
```

---

## 🔄 Обновление приложения

### Render.com

```bash
# Просто делаем push в main
git add .
git commit -m "Update"
git push origin main
# Render автоматически задеплоит
```

### Docker

```bash
# Останавливаем контейнер
docker-compose down

# Обновляем код
git pull origin main

# Пересобираем и запускаем
docker-compose build
docker-compose up -d
```

### VPS

```bash
# Подключаемся к серверу
ssh user@your-server-ip

# Переходим в папку приложения
sudo su - lottery
cd lottery-bot

# Обновляем код
git pull origin main

# Обновляем зависимости (если изменились)
source venv/bin/activate
pip install -r requirements.txt

# Перезапускаем сервис
exit
sudo systemctl restart lottery-bot
sudo systemctl status lottery-bot
```

---

## 📊 Мониторинг и логи

### Просмотр логов

```bash
# Render.com
# Логи доступны в Dashboard → Logs

# Docker
docker-compose logs -f

# VPS
sudo journalctl -u lottery-bot -f
# или
tail -f /home/lottery/lottery-bot/logs/lottery_bot.log
```

### Мониторинг производительности

```bash
# Проверка использования ресурсов (VPS)
htop
# или
docker stats  # для Docker
```

### Health Check

```bash
# Проверка работоспособности
curl http://your-domain.com/health

# Ожидаемый ответ:
# {"status": "healthy", "database": "connected", "bot": "running"}
```

---

## 🔐 Безопасность

### Обязательные меры

1. **Изменить дефолтные пароли**
   ```bash
   # В .env
   ADMIN_PASSWORD=<сложный_пароль>
   ```

2. **Настроить firewall (VPS)**
   ```bash
   sudo ufw allow 22/tcp   # SSH
   sudo ufw allow 80/tcp   # HTTP
   sudo ufw allow 443/tcp  # HTTPS
   sudo ufw enable
   ```

3. **Ограничить доступ к админ-панели**
   - Использовать whitelist IP
   - Настроить 2FA
   - Регулярно менять пароли

4. **Регулярные обновления**
   ```bash
   # Обновлять зависимости
   pip list --outdated
   pip install -U <package>
   ```

---

## 🆘 Решение проблем

### Бот не отвечает

```bash
# 1. Проверить логи
tail -100 logs/lottery_bot.log

# 2. Проверить токен бота
python -c "from config import load_config; print(load_config().bot_token)"

# 3. Проверить подключение к Telegram
curl https://api.telegram.org/bot<TOKEN>/getMe
```

### База данных заблокирована

```bash
# 1. Проверить процессы
lsof data/lottery_bot.sqlite

# 2. Увеличить таймаут
# В .env:
DB_BUSY_TIMEOUT=20000
```

### Проблемы с памятью

```bash
# 1. Проверить использование памяти
free -h

# 2. Уменьшить размер кэша
# В .env:
CACHE_TTL_HOT=60
CACHE_TTL_WARM=300
```

---

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи
2. Изучите документацию в `/docs`
3. Создайте issue в GitHub
4. Свяжитесь с технической поддержкой

---

*Версия: 1.0*  
*Последнее обновление: 2025-09-30*
