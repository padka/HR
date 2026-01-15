# Server Stability & Monitoring Guide

## 📋 Содержание
- [Механизмы защиты от падений](#механизмы-защиты-от-падений)
- [Мониторинг здоровья сервера](#мониторинг-здоровья-сервера)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

---

## 🛡️ Механизмы защиты от падений

### 1. Global Exception Handler
Все необработанные исключения в asyncio event loop автоматически логируются:

```python
# Автоматически устанавливается при старте приложения
setup_global_exception_handler()
```

**Что это даёт:**
- Ни одно исключение не упадёт молча
- Полные stacktrace в логах
- Контекст исключения для debugging

### 2. Resilient Background Tasks
Все фоновые задачи защищены декоратором `@resilient_task`:

```python
@resilient_task(
    task_name="periodic_stalled_candidate_checker",
    retry_on_error=True,
    retry_delay=300.0,  # 5 минут
    log_errors=True,
)
async def periodic_stalled_candidate_checker():
    # Задача будет автоматически перезапущена при ошибке
    pass
```

**Защищённые задачи:**
- `cache_health_watcher` - мониторинг Redis кеша
- `periodic_stalled_candidate_checker` - проверка зависших кандидатов
- `bot_polling` - опрос Telegram API

**Параметры:**
- `retry_on_error=True` - автоматический перезапуск при ошибке
- `retry_delay` - задержка перед перезапуском (с экспоненциальным backoff)
- `max_retries` - максимум попыток (None = бесконечно)
- `log_errors=True` - логирование всех ошибок

### 3. Graceful Shutdown
При остановке сервера все задачи завершаются корректно:

```python
# Timeout 15 секунд для завершения всех задач
shutdown_manager = GracefulShutdown(timeout=15.0)
```

**Что происходит при shutdown:**
1. Отправляется сигнал cancel всем задачам
2. Ожидание завершения в течение timeout
3. Принудительное завершение если timeout истёк
4. Закрытие всех соединений (DB, Redis, Bot)

### 4. Database Connection Pooling
Автоматическое управление пулом соединений:

```env
# .env конфигурация
DB_POOL_SIZE=20           # Размер пула
DB_MAX_OVERFLOW=10        # Дополнительные соединения
DB_POOL_TIMEOUT=30        # Таймаут ожидания соединения
DB_POOL_RECYCLE=3600      # Переподключение через 1 час
```

### 5. Redis Auto-Reconnect
Автоматическое переподключение к Redis при сбоях:

```python
# Параметры retry
CACHE_RETRY_ATTEMPTS = 5
CACHE_RETRY_BASE_DELAY = 1.0
CACHE_RETRY_MAX_DELAY = 30.0
CACHE_HEALTH_INTERVAL = 15.0  # Проверка каждые 15 секунд
```

---

## 📊 Мониторинг здоровья сервера

### Health Check Endpoints

#### 1. `/health` - Общее состояние
```bash
curl http://localhost:8000/health
```

**Ответ:**
```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "state_manager": "ok",
    "cache": "ok",
    "background_tasks": {
      "cache_watcher": "running",
      "stalled_candidate_checker": "running"
    },
    "bot_client": "ready",
    "bot_integration": "enabled",
    "bot": "configured"
  }
}
```

**Возможные статусы:**
- `ok` - всё работает нормально
- `error` - критическая ошибка (HTTP 503)
- `disabled` - сервис отключён
- `degraded` - работает с ограничениями
- `missing` - сервис не настроен

#### 2. `/health/bot` - Telegram Bot
```bash
curl http://localhost:8000/health/bot
```

Детальная информация о состоянии Telegram бота:
- Конфигурация
- Статус соединения
- Метрики state store
- Очереди напоминаний

#### 3. `/health/notifications` - Notification System
```bash
curl http://localhost:8000/health/notifications
```

Состояние системы уведомлений:
- Статус брокера (Redis)
- Polling состояние
- Метрики отправки
- Rate limiting

#### 4. `/metrics/notifications` - Prometheus Metrics
```bash
curl http://localhost:8000/metrics/notifications
```

Метрики в формате Prometheus для Grafana:
```
# HELP notification_broker_up Broker ping status (1=up)
# TYPE notification_broker_up gauge
notification_broker_up 1

# HELP notification_outbox_queue_depth Number of pending notifications
# TYPE notification_outbox_queue_depth gauge
notification_outbox_queue_depth 5

# HELP notification_sent_total Notifications successfully sent
# TYPE notification_sent_total counter
notification_sent_total{type="booking_proposed"} 142
```

---

## 🔧 Troubleshooting

### Проблема: Сервер "падает" каждые 5 минут

**Диагностика:**
```bash
# Проверить логи
tail -f logs/app.log

# Проверить процессы
ps aux | grep uvicorn

# Проверить health
curl http://localhost:8000/health
```

**Возможные причины:**
1. **Dev server auto-restart** - это нормально для разработки
   - `scripts/dev_server.py` автоматически перезапускает при изменении файлов
   - Для production используйте `uvicorn` напрямую

2. **Background task crash** - проверить логи:
   ```bash
   grep "ERROR" logs/app.log | grep "background"
   ```

3. **Database connection timeout** - увеличить timeout:
   ```env
   DB_POOL_TIMEOUT=60
   ```

4. **Out of memory** - проверить использование памяти:
   ```bash
   ps aux | grep python | awk '{print $6/1024" MB  "$11}'
   ```

### Проблема: Background tasks не работают

**Проверка:**
```bash
curl http://localhost:8000/health | jq '.checks.background_tasks'
```

**Решение:**
```bash
# Перезапустить сервер
pkill -f uvicorn
make dev

# Проверить логи startup
grep "Started periodic" logs/app.log
```

### Проблема: Redis connection errors

**Диагностика:**
```bash
# Проверить Redis
redis-cli ping

# Проверить соединение из Python
python -c "import redis; r=redis.Redis(); print(r.ping())"
```

**Решение:**
```bash
# Запустить Redis
make docker-up

# Проверить конфигурацию
grep REDIS_URL .env
```

### Проблема: Database errors

**Диагностика:**
```bash
# Проверить миграции
ls backend/migrations/versions/

# Запустить миграции
make migrate

# Проверить соединение
sqlite3 data/bot.db "SELECT 1;"
```

---

## 📈 Best Practices

### 1. Мониторинг в Production

#### Prometheus + Grafana
```yaml
# docker-compose.prometheus.yml
version: "3.9"
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

#### Prometheus config
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'recruitsmart_admin'
    static_configs:
      - targets: ['host.docker.internal:8000']
    metrics_path: '/metrics/notifications'
    scrape_interval: 15s
```

### 2. Логирование

```python
# backend/core/logging.py настроен на:
# - Structured logging (JSON in production)
# - Log rotation
# - Уровни: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**Рекомендуемые уровни:**
- Development: `LOG_LEVEL=DEBUG`
- Staging: `LOG_LEVEL=INFO`
- Production: `LOG_LEVEL=WARNING`

### 3. Alerting

Настройте алерты в Prometheus/Grafana:

```yaml
# alerts.yml
groups:
  - name: recruitsmart_admin
    rules:
      # Сервер недоступен
      - alert: ServerDown
        expr: up{job="recruitsmart_admin"} == 0
        for: 1m
        annotations:
          summary: "Admin server is down"

      # Background tasks остановлены
      - alert: BackgroundTasksStopped
        expr: |
          (notification_seconds_since_poll > 300)
        for: 5m
        annotations:
          summary: "Background tasks not running"

      # Высокая нагрузка на очередь
      - alert: HighQueueDepth
        expr: notification_outbox_queue_depth > 100
        for: 10m
        annotations:
          summary: "High notification queue depth"

      # Много ошибок отправки
      - alert: HighFailureRate
        expr: |
          rate(notification_failed_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High notification failure rate"
```

### 4. Production Deployment

```bash
# 1. Установить зависимости
pip install -e ".[dev]"

# 2. Запустить миграции
ENVIRONMENT=production make migrate

# 3. Запустить с Gunicorn/Uvicorn workers
gunicorn backend.apps.admin_ui.app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --graceful-timeout 30 \
  --access-logfile - \
  --error-logfile - \
  --log-level warning

# Или просто:
uvicorn backend.apps.admin_ui.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level warning
```

### 5. Environment Variables для Production

```env
# Обязательно изменить:
ENVIRONMENT=production
SESSION_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
ADMIN_PASSWORD=<strong-password>

# Redis обязателен в production:
REDIS_URL=redis://redis:6379/0
NOTIFICATION_BROKER=redis

# Логирование:
LOG_LEVEL=WARNING
LOG_JSON=true
LOG_FILE=/var/log/recruitsmart/app.log

# Database:
DATABASE_URL=sqlite:////data/bot.db
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
```

### 6. Systemd Service (Linux)

```ini
# /etc/systemd/system/recruitsmart-admin.service
[Unit]
Description=Recruitsmart Admin Server
After=network.target redis.service

[Service]
Type=notify
User=recruitsmart
WorkingDirectory=/opt/recruitsmart_admin
Environment="PATH=/opt/recruitsmart_admin/.venv/bin"
EnvironmentFile=/opt/recruitsmart_admin/.env
ExecStart=/opt/recruitsmart_admin/.venv/bin/uvicorn \
  backend.apps.admin_ui.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4
Restart=always
RestartSec=10
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

```bash
# Управление сервисом
sudo systemctl enable recruitsmart-admin
sudo systemctl start recruitsmart-admin
sudo systemctl status recruitsmart-admin

# Логи
sudo journalctl -u recruitsmart-admin -f
```

---

## 🎯 Ключевые метрики для мониторинга

1. **Uptime** - `up{job="recruitsmart_admin"}`
2. **Queue Depth** - `notification_outbox_queue_depth`
3. **Error Rate** - `rate(notification_failed_total[5m])`
4. **Response Time** - HTTP response duration
5. **Memory Usage** - процесс Python
6. **CPU Usage** - нагрузка на процессор
7. **Database Connections** - активные соединения
8. **Background Tasks** - статус всех задач

---

## 📞 Поддержка

Если сервер продолжает падать после применения всех улучшений:

1. Включить DEBUG logging: `LOG_LEVEL=DEBUG`
2. Собрать логи за 5-10 минут работы
3. Проверить health endpoints перед падением
4. Собрать метрики памяти и CPU
5. Проверить дисковое пространство

Файл с логами отправить для анализа.
