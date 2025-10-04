# 🚀 Руководство по развертыванию Lottery Bot

## Содержание

- [Подготовка](#подготовка)
- [Локальное развертывание](#локальное-развертывание)
- [Production развертывание](#production-развертывание)
- [Мониторинг и обслуживание](#мониторинг-и-обслуживание)
- [Troubleshooting](#troubleshooting)

## Подготовка

### Требования к системе

**Минимальные:**
- OS: Linux (Ubuntu 20.04+), macOS, Windows 10+
- Python: 3.11+
- RAM: 512 MB
- Disk: 1 GB
- CPU: 1 core

**Рекомендуемые для production:**
- OS: Ubuntu 22.04 LTS
- Python: 3.11+
- RAM: 2 GB+
- Disk: 10 GB SSD
- CPU: 2+ cores

### Получение токенов

#### 1. Telegram Bot Token

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Сохраните полученный токен

**Настройте бота:**
```
/setdescription - Бот для проведения розыгрышей
/setabouttext - Честный и прозрачный розыгрыш призов
/setcommands:
start - Начать работу
help - Помощь
menu - Главное меню
status - Проверить статус заявки
support - Техническая поддержка
```

#### 2. Admin User IDs

Узнайте ваш Telegram ID:
1. Откройте [@userinfobot](https://t.me/userinfobot)
2. Скопируйте ваш ID

## Локальное развертывание

### Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone https://github.com/yourusername/lottery-bot.git
cd lottery-bot

# 2. Создать виртуальное окружение
python3.11 -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate

# 3. Установить зависимости
pip install --upgrade pip
pip install -r requirements.txt

# 4. Создать файл конфигурации
cat > .env << EOF
BOT_TOKEN=your_bot_token_here
ADMIN_USER_IDS=123456789
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
DATABASE_PATH=data/lottery_bot.sqlite
LOG_LEVEL=INFO
EOF

# 5. Создать необходимые директории
mkdir -p data logs uploads exports backups

# 6. Запустить бота
python main.py
```

### Проверка установки

```bash
# Health check
python scripts/health_check.py

# Smoke test
python scripts/smoke_test.py
```

Ожидаемый вывод:
```
✅ Database: OK
✅ Bot configuration: OK
✅ Web server: OK
✅ All systems operational
```

## Production развертывание

### Вариант 1: Render.com (Рекомендуется)

Render автоматически обнаружит `render.yaml` и настроит сервис.

**Шаги:**

1. **Подготовка репозитория**
```bash
git add .
git commit -m "Ready for deployment"
git push origin main
```

2. **Создание сервиса в Render**
   - Перейдите на [render.com](https://render.com)
   - Нажмите "New +" → "Web Service"
   - Подключите ваш GitHub репозиторий
   - Render автоматически обнаружит `render.yaml`

3. **Настройка переменных окружения**

В Render Dashboard → Environment:
```env
BOT_TOKEN=your_real_bot_token
ADMIN_USER_IDS=123456789,987654321
ADMIN_USERNAME=admin
ADMIN_PASSWORD=strong_password_here
SECRET_KEY=generate_with_secrets_module
DATABASE_PATH=/opt/render/project/data/lottery_bot.sqlite
LOG_LEVEL=WARNING
MAX_FILE_SIZE=10485760
RATE_LIMIT=30
```

4. **Настройка Persistent Disk (важно!)**
   - В настройках сервиса → Storage
   - Создайте Disk: Name=`lottery-data`, Mount Path=`/opt/render/project/data`
   - Размер: 1 GB (минимум)

5. **Deploy**
   - Render автоматически запустит деплой
   - Дождитесь успешного завершения
   - Проверьте логи

**render.yaml:**
```yaml
services:
  - type: web
    name: lottery-bot
    env: python
    plan: starter
    buildCommand: pip install -r requirements.txt
    startCommand: python main.py
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
```

### Вариант 2: VPS/Dedicated Server

#### С использованием systemd

**1. Установка зависимостей**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nginx

# CentOS/RHEL
sudo yum install -y python311 python311-pip nginx
```

**2. Создание пользователя**
```bash
sudo useradd -m -s /bin/bash lotterybot
sudo su - lotterybot
```

**3. Установка приложения**
```bash
cd /home/lotterybot
git clone https://github.com/yourusername/lottery-bot.git app
cd app

python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Создать .env
nano .env
# Добавьте все необходимые переменные

# Создать директории
mkdir -p data logs uploads exports backups
```

**4. Создание systemd service**
```bash
sudo nano /etc/systemd/system/lottery-bot.service
```

```ini
[Unit]
Description=Lottery Bot Service
After=network.target

[Service]
Type=simple
User=lotterybot
WorkingDirectory=/home/lotterybot/app
Environment="PATH=/home/lotterybot/app/venv/bin"
ExecStart=/home/lotterybot/app/venv/bin/python main.py
Restart=always
RestartSec=10

# Логирование
StandardOutput=journal
StandardError=journal
SyslogIdentifier=lottery-bot

# Безопасность
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/lotterybot/app/data /home/lotterybot/app/logs /home/lotterybot/app/uploads

[Install]
WantedBy=multi-user.target
```

**5. Запуск сервиса**
```bash
sudo systemctl daemon-reload
sudo systemctl enable lottery-bot
sudo systemctl start lottery-bot

# Проверка статуса
sudo systemctl status lottery-bot

# Просмотр логов
sudo journalctl -u lottery-bot -f
```

**6. Настройка Nginx (опционально для веб-панели)**
```bash
sudo nano /etc/nginx/sites-available/lottery-bot
```

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

    # Static files
    location /static/ {
        alias /home/lotterybot/app/web/static/;
        expires 30d;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/lottery-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**7. Настройка SSL (Let's Encrypt)**
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Вариант 3: Docker (Скоро)

```bash
# Build
docker build -t lottery-bot .

# Run
docker run -d \
  --name lottery-bot \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/uploads:/app/uploads \
  --env-file .env \
  lottery-bot
```

## Мониторинг и обслуживание

### Логирование

**Просмотр логов:**
```bash
# Systemd
sudo journalctl -u lottery-bot -f

# Файловые логи
tail -f logs/lottery_bot.log

# Фильтрация по уровню
grep ERROR logs/lottery_bot.log

# Последние 100 строк
tail -n 100 logs/lottery_bot.log
```

**Ротация логов:**
```bash
# /etc/logrotate.d/lottery-bot
/home/lotterybot/app/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 lotterybot lotterybot
    sharedscripts
    postrotate
        systemctl reload lottery-bot
    endscript
}
```

### Мониторинг здоровья

**Автоматический health check:**
```bash
# Создать cron job
crontab -e

# Добавить строку (проверка каждые 5 минут)
*/5 * * * * /home/lotterybot/app/venv/bin/python /home/lotterybot/app/scripts/health_check.py || systemctl restart lottery-bot
```

**Health check endpoints:**
- `http://your-domain.com/health` - Basic health
- `http://your-domain.com/health/db` - Database health
- `http://your-domain.com/health/detailed` - Detailed system info

### Резервное копирование

**Автоматический backup:**
```bash
# /home/lotterybot/backup.sh
#!/bin/bash
BACKUP_DIR="/home/lotterybot/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup database
cp /home/lotterybot/app/data/lottery_bot.sqlite "$BACKUP_DIR/db_$DATE.sqlite"

# Backup uploads
tar -czf "$BACKUP_DIR/uploads_$DATE.tar.gz" /home/lotterybot/app/uploads

# Keep only last 7 days
find "$BACKUP_DIR" -name "*.sqlite" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
```

```bash
# Добавить в crontab (ежедневно в 3:00)
0 3 * * * /home/lotterybot/backup.sh
```

### Обновление

**Безопасное обновление:**
```bash
cd /home/lotterybot/app

# 1. Backup
./backup.sh

# 2. Pull changes
git pull origin main

# 3. Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# 4. Run migrations (если есть)
python -c "from database.migrations import run_migrations; import asyncio; asyncio.run(run_migrations())"

# 5. Restart service
sudo systemctl restart lottery-bot

# 6. Check logs
sudo journalctl -u lottery-bot -n 50
```

### Мониторинг метрик

**С использованием Prometheus + Grafana (опционально):**

```python
# metrics.py
from prometheus_client import Counter, Histogram, start_http_server

registration_counter = Counter('bot_registrations_total', 'Total registrations')
response_time = Histogram('bot_response_seconds', 'Response time')

# В коде
registration_counter.inc()
with response_time.time():
    await handle_message()
```

## Troubleshooting

### Частые проблемы

#### 1. Бот не отвечает

**Проверка:**
```bash
# Проверить статус сервиса
sudo systemctl status lottery-bot

# Проверить логи
sudo journalctl -u lottery-bot -n 100

# Проверить токен
python -c "from config import load_config; print(load_config().bot_token)"
```

**Решение:**
- Проверьте токен бота
- Убедитесь, что бот не заблокирован
- Проверьте интернет-соединение
- Перезапустите сервис

#### 2. Database locked

**Симптомы:**
```
sqlite3.OperationalError: database is locked
```

**Решение:**
```bash
# Проверить процессы
lsof /home/lotterybot/app/data/lottery_bot.sqlite

# Увеличить busy_timeout в config.py
DATABASE_POOL_SIZE = 10
DATABASE_BUSY_TIMEOUT_MS = 30000  # 30 секунд
```

#### 3. Out of memory

**Симптомы:**
```
MemoryError
Killed
```

**Решение:**
```bash
# Проверить использование памяти
ps aux | grep python

# Добавить swap (если нужно)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Оптимизировать кэш в config.py
CACHE_HOT_TTL = 30      # Уменьшить TTL
CACHE_WARM_TTL = 180
CACHE_COLD_TTL = 1800
```

#### 4. High CPU usage

**Диагностика:**
```bash
# Top процессов
top -p $(pgrep -f "python main.py")

# Python profiling
pip install py-spy
py-spy top --pid $(pgrep -f "python main.py")
```

**Решение:**
- Проверить бесконечные циклы
- Оптимизировать запросы к БД
- Добавить индексы
- Уменьшить rate limit

#### 5. Web panel not accessible

**Проверка:**
```bash
# Проверить порт
netstat -tlnp | grep 5000

# Проверить Nginx
sudo nginx -t
sudo systemctl status nginx

# Проверить firewall
sudo ufw status
```

**Решение:**
```bash
# Открыть порты
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Проверить конфигурацию Flask
# В config.py:
WEB_HOST = "0.0.0.0"  # Слушать все интерфейсы
WEB_PORT = 5000
```

### Диагностические команды

```bash
# Системная информация
python scripts/health_check.py

# Проверка БД
sqlite3 data/lottery_bot.sqlite "PRAGMA integrity_check;"

# Размер БД
du -h data/lottery_bot.sqlite

# Количество участников
sqlite3 data/lottery_bot.sqlite "SELECT COUNT(*) FROM participants;"

# Последние ошибки
tail -n 100 logs/lottery_bot.log | grep ERROR

# Производительность БД
sqlite3 data/lottery_bot.sqlite "ANALYZE; SELECT * FROM sqlite_stat1;"
```

### Получение поддержки

1. **Проверьте логи** - большинство проблем видны в логах
2. **Поиск в Issues** - возможно, проблема уже решена
3. **Создайте Issue** с информацией:
   - Версия Python
   - Операционная система
   - Шаги для воспроизведения
   - Логи ошибок
   - Конфигурация (без секретов!)

## Performance Tuning

### Оптимизация базы данных

```sql
-- Анализ и оптимизация
ANALYZE;
VACUUM;

-- Настройка SQLite
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-64000;  -- 64MB
PRAGMA temp_store=MEMORY;
```

### Оптимизация Python

```python
# config.py
import multiprocessing

# Для production
WORKERS = multiprocessing.cpu_count() * 2 + 1
MAX_CONNECTIONS = 20
POOL_SIZE = 10
```

### Оптимизация сети

```bash
# /etc/sysctl.conf
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 8096
net.ipv4.tcp_tw_reuse = 1
```

---

## Checklist перед production

- [ ] Все секреты в переменных окружения
- [ ] DEBUG режим выключен
- [ ] LOG_LEVEL = WARNING или ERROR
- [ ] Настроено резервное копирование
- [ ] Настроен мониторинг
- [ ] Настроена ротация логов
- [ ] SSL сертификат установлен
- [ ] Firewall настроен
- [ ] Health checks работают
- [ ] Проведено нагрузочное тестирование
- [ ] Документация актуальна

---

<p align="center">Успешного развертывания! 🚀</p>

