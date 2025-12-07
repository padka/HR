# Полное руководство по развертыванию веб-приложений на сервер

## Содержание
1. [Подготовка к развертыванию](#1-подготовка-к-развертыванию)
2. [Выбор инфраструктуры](#2-выбор-инфраструктуры)
3. [Процесс развертывания](#3-процесс-развертывания)
4. [Стратегия обновлений](#4-стратегия-обновлений)
5. [CI/CD Автоматизация](#5-cicd-автоматизация)
6. [Мониторинг и поддержка](#6-мониторинг-и-поддержка)

---

## 1. ПОДГОТОВКА К РАЗВЕРТЫВАНИЮ

### 1.1 Проверка готовности проекта

#### Чеклист готовности к деплою

**Для всех типов проектов:**
- [ ] Все зависимости четко определены в файлах конфигурации
- [ ] Конфиденциальные данные выведены в переменные окружения
- [ ] Логирование настроено и работает корректно
- [ ] Тесты проходят успешно (unit, integration)
- [ ] Документация актуальна
- [ ] `.gitignore` настроен корректно (исключены секреты, временные файлы)

**Python (Django/Flask/FastAPI):**
- [ ] `requirements.txt` или `pyproject.toml` актуален
- [ ] Миграции БД созданы и протестированы
- [ ] Static files собираются корректно
- [ ] WSGI/ASGI сервер настроен

**Node.js:**
- [ ] `package.json` и `package-lock.json` актуальны
- [ ] Build процесс работает (`npm run build`)
- [ ] Production зависимости отделены от dev
- [ ] Node версия зафиксирована в `.nvmrc` или `package.json`

**PHP:**
- [ ] `composer.json` и `composer.lock` актуальны
- [ ] `.env.example` создан
- [ ] Autoloading настроен
- [ ] PHP версия совместима с хостингом

**Статические сайты:**
- [ ] Build процесс настроен
- [ ] Assets оптимизированы (минификация, сжатие)
- [ ] SEO мета-теги настроены

#### Команды для проверки

```bash
# Python/FastAPI (пример из текущего проекта)
python -m pytest                          # Запуск тестов
python scripts/run_migrations.py         # Проверка миграций
python -c "from backend.core.settings import get_settings; get_settings()"  # Валидация конфигурации

# Node.js
npm test
npm run build
npm audit --production                    # Проверка уязвимостей

# PHP
composer install --no-dev
composer validate
./vendor/bin/phpunit

# Статические сайты
npm run build
npm run lint
```

### 1.2 Необходимые файлы конфигурации

#### Python/FastAPI проект

**requirements.txt / pyproject.toml**
```txt
# Production зависимости
fastapi==0.112.0
uvicorn[standard]==0.38.0
sqlalchemy==2.0.32
alembic==1.13.2
redis==5.0.7
python-dotenv==1.2.1
asyncpg==0.29.0  # для PostgreSQL
```

**Dockerfile**
```dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Установка системных зависимостей
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY . .

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Запуск приложения
CMD ["uvicorn", "backend.apps.admin_ui.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml** (для локальной разработки и staging)
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/dbname
      - REDIS_URL=redis://redis:6379/0
      - SESSION_SECRET=${SESSION_SECRET}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: dbname
      POSTGRES_USER: user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d dbname"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

#### Node.js/Express проект

**package.json**
```json
{
  "name": "myapp",
  "version": "1.0.0",
  "engines": {
    "node": ">=18.0.0",
    "npm": ">=9.0.0"
  },
  "scripts": {
    "start": "node dist/index.js",
    "build": "tsc",
    "dev": "nodemon src/index.ts",
    "test": "jest",
    "migrate": "knex migrate:latest"
  },
  "dependencies": {
    "express": "^4.18.0",
    "pg": "^8.11.0",
    "redis": "^4.6.0",
    "dotenv": "^16.0.0"
  }
}
```

**Dockerfile**
```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
```

#### PHP/Laravel проект

**composer.json**
```json
{
    "name": "myapp/laravel",
    "require": {
        "php": "^8.2",
        "laravel/framework": "^10.0"
    },
    "scripts": {
        "post-install-cmd": [
            "@php artisan optimize"
        ]
    }
}
```

**Dockerfile**
```dockerfile
FROM php:8.2-fpm-alpine

RUN docker-php-ext-install pdo pdo_mysql

WORKDIR /var/www

COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

COPY composer*.json ./
RUN composer install --no-dev --optimize-autoloader

COPY . .

RUN php artisan config:cache \
    && php artisan route:cache \
    && php artisan view:cache

CMD ["php-fpm"]
```

### 1.3 Переменные окружения

#### Критические переменные безопасности

**Python/FastAPI (пример из проекта)**

Создайте `.env.production` (НЕ коммитить в git!):
```bash
# === КРИТИЧНО ДЛЯ БЕЗОПАСНОСТИ ===
# Генерация: python -c "import secrets; print(secrets.token_hex(32))"
SESSION_SECRET=a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2

# === ОКРУЖЕНИЕ ===
ENVIRONMENT=production

# === БАЗА ДАННЫХ ===
DATABASE_URL=postgresql+asyncpg://recruitsmart:STRONG_PASSWORD@localhost:5432/recruitsmart
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600

# === REDIS ===
REDIS_URL=redis://localhost:6379/0
NOTIFICATION_BROKER=redis

# === АУТЕНТИФИКАЦИЯ АДМИНКИ ===
ADMIN_USER=admin
ADMIN_PASSWORD=VERY_STRONG_PASSWORD_16_CHARS_MINIMUM

# === TELEGRAM BOT ===
BOT_ENABLED=true
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
BOT_AUTOSTART=false  # В production запускается отдельным процессом

# === БЕЗОПАСНОСТЬ COOKIES ===
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=strict

# === ЛОГИРОВАНИЕ ===
LOG_LEVEL=INFO
LOG_JSON=true
LOG_FILE=/var/log/recruitsmart/app.log

# === ДАННЫЕ ПРИЛОЖЕНИЯ ===
DATA_DIR=/var/lib/recruitsmart_admin
TZ=Europe/Moscow
```

**Node.js**
```bash
NODE_ENV=production
PORT=3000
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379
JWT_SECRET=your-256-bit-secret
SESSION_SECRET=your-session-secret
```

**PHP/Laravel**
```bash
APP_ENV=production
APP_KEY=base64:your-generated-key
APP_DEBUG=false
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_DATABASE=laravel
DB_USERNAME=root
DB_PASSWORD=password
CACHE_DRIVER=redis
QUEUE_CONNECTION=redis
```

#### ⚠️ ВАЖНО: Управление секретами

**Что НЕ делать:**
- ❌ Не храните `.env` в Git
- ❌ Не используйте слабые пароли типа "admin" или "password"
- ❌ Не используйте одинаковые секреты на разных окружениях
- ❌ Не логируйте значения переменных окружения

**Что делать:**
- ✅ Используйте `.env.example` как шаблон (без реальных секретов)
- ✅ Генерируйте случайные секреты минимум 32 символа
- ✅ Храните production секреты в защищенном хранилище (Vault, AWS Secrets Manager)
- ✅ Используйте разные секреты для dev/staging/production
- ✅ Регулярно ротируйте секреты

**Генерация безопасных секретов:**
```bash
# Python
python -c "import secrets; print(secrets.token_hex(32))"

# Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# OpenSSL
openssl rand -hex 32

# Linux /dev/urandom
head -c 32 /dev/urandom | base64
```

### 1.4 Зависимости и требования

#### Системные требования

**Минимальные требования для типичного веб-приложения:**
- CPU: 2 vCPU (рекомендуется 4 для production)
- RAM: 2 GB (рекомендуется 4-8 GB)
- Storage: 20 GB SSD (быстрее HDD для БД)
- Bandwidth: 100 Mbps

**Python/FastAPI:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip
sudo apt install -y postgresql postgresql-contrib
sudo apt install -y redis-server
sudo apt install -y nginx
sudo apt install -y supervisor  # Для управления процессами

# Проверка версий
python3 --version  # >= 3.11
psql --version     # >= 14
redis-cli --version
nginx -v
```

**Node.js:**
```bash
# Установка через nvm (рекомендуется)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 18
nvm use 18

# Или через NodeSource
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Установка PM2 для управления процессами
npm install -g pm2
```

**PHP:**
```bash
# Ubuntu/Debian
sudo apt install -y php8.2-fpm php8.2-cli php8.2-mysql php8.2-redis
sudo apt install -y php8.2-mbstring php8.2-xml php8.2-curl
sudo apt install -y composer
```

---

## 2. ВЫБОР ИНФРАСТРУКТУРЫ

### 2.1 Сравнение вариантов хостинга

#### Таблица сравнения

| Критерий | VPS (DigitalOcean, Hetzner) | PaaS (Heroku, Railway) | Облако (AWS, GCP, Azure) | Shared Hosting |
|----------|------------------------------|------------------------|--------------------------|----------------|
| **Контроль** | Полный | Ограниченный | Полный | Минимальный |
| **Сложность настройки** | Средняя/Высокая | Низкая | Высокая | Низкая |
| **Стоимость (мал. проект)** | $5-20/мес | $7-25/мес | $10-50/мес | $3-10/мес |
| **Стоимость (средний проект)** | $20-100/мес | $50-200/мес | $100-500/мес | Не подходит |
| **Масштабируемость** | Ручная | Автоматическая | Автоматическая | Нет |
| **SSL сертификат** | Ручная настройка | Автоматически | Управляемо | Зависит |
| **База данных** | Самостоятельно | Управляемая | Управляемая | Ограниченная |
| **Резервное копирование** | Настроить вручную | Автоматически | Настраивается | Базовое |
| **Время развертывания** | 2-4 часа | 10-30 минут | 1-8 часов | 5-15 минут |
| **Подходит для** | Средние проекты | MVP, стартапы | Enterprise | Простые сайты |

#### Детальное сравнение по типам хостинга

### 2.1.1 VPS (Virtual Private Server)

**Провайдеры:**
- DigitalOcean (США, Европа) - от $6/мес
- Hetzner (Германия, Финляндия) - от €4.5/мес (лучшая цена/производительность)
- Linode (США, Европа, Азия) - от $5/мес
- Vultr (глобальная сеть) - от $6/мес
- Timeweb (Россия) - от 199₽/мес
- Beget VPS (Россия) - от 350₽/мес

**Преимущества:**
- ✅ Полный root доступ
- ✅ Возможность тонкой настройки
- ✅ Предсказуемая цена
- ✅ Можно разместить несколько проектов

**Недостатки:**
- ❌ Требуется опыт администрирования
- ❌ Ручное масштабирование
- ❌ Вы отвечаете за безопасность и обновления

**Когда использовать:**
- Вам нужен полный контроль
- У вас есть опыт работы с Linux
- Бюджет ограничен, но нужны гарантированные ресурсы
- Несколько проектов на одном сервере

**Пример конфигурации (Hetzner CX21):**
```
CPU: 2 vCPU AMD
RAM: 4 GB
Storage: 40 GB SSD
Traffic: 20 TB
Цена: ~€5/мес
Идеально для: FastAPI + PostgreSQL + Redis
```

### 2.1.2 PaaS (Platform as a Service)

**Провайдеры:**
- **Heroku** - классика, простота, дорого на scale
- **Railway** - современный, Git-based деплой, от $5/мес
- **Render** - аналог Heroku, бесплатный tier
- **Fly.io** - edge computing, контейнеры
- **Vercel** - идеально для Next.js/статики, бесплатный hobby tier
- **Netlify** - статика + serverless functions
- **PythonAnywhere** - специализация на Python

**Преимущества:**
- ✅ Деплой за минуты (git push)
- ✅ Автоматическое масштабирование
- ✅ Управляемые БД, Redis, логи
- ✅ SSL из коробки
- ✅ Не нужно настраивать инфраструктуру

**Недостатки:**
- ❌ Дороже при росте
- ❌ Vendor lock-in
- ❌ Ограничения на конфигурацию
- ❌ "Cold start" на бесплатных tier

**Когда использовать:**
- MVP, быстрый прототип
- Команда без DevOps специалиста
- Фокус на разработке, не на инфраструктуре
- Нужно быстро масштабироваться

**Пример стоимости Railway (Python app):**
```
Hobby tier: $5/мес + usage
- 512 MB RAM
- 1 GB Storage
- Shared CPU

Production: ~$20-50/мес
- 2 GB RAM
- PostgreSQL managed DB
- Redis
- Unlimited deployments
```

### 2.1.3 Облачные платформы (AWS, GCP, Azure)

**Основные сервисы:**

**AWS:**
- EC2 (виртуальные машины)
- RDS (управляемые БД)
- ElastiCache (Redis/Memcached)
- ECS/EKS (контейнеры/Kubernetes)
- Lambda (serverless)
- S3 (хранилище файлов)

**GCP:**
- Compute Engine (VM)
- Cloud SQL (БД)
- Cloud Run (контейнеры)
- Cloud Functions (serverless)
- Cloud Storage

**Azure:**
- Virtual Machines
- Azure Database
- Azure Container Instances
- Azure Functions
- Azure Blob Storage

**Преимущества:**
- ✅ Безграничное масштабирование
- ✅ Множество готовых сервисов
- ✅ Высокая надежность (99.95%+ SLA)
- ✅ Глобальная инфраструктура

**Недостатки:**
- ❌ Сложность (крутая кривая обучения)
- ❌ Непредсказуемая стоимость
- ❌ Overkill для малых проектов
- ❌ Требуется DevOps экспертиза

**Когда использовать:**
- Enterprise приложения
- Высокие требования к доступности
- Большие нагрузки
- Сложная инфраструктура (микросервисы)
- Нужна глобальная CDN

**Пример архитектуры AWS (средний проект):**
```
- EC2 t3.small (2 vCPU, 2GB RAM): ~$15/мес
- RDS PostgreSQL db.t3.micro: ~$15/мес
- ElastiCache Redis cache.t3.micro: ~$12/мес
- Application Load Balancer: ~$16/мес
- S3 + CloudFront (CDN): ~$5/мес
---------------------------------------------
ИТОГО: ~$63/мес (без учета трафика)
```

### 2.2 Рекомендации по выбору на основе типа проекта

#### Сценарий 1: Landing Page / Портфолио (статический сайт)

**Рекомендация: Netlify или Vercel (бесплатно)**

```bash
# Пример деплоя на Netlify
npm run build
netlify deploy --prod --dir=dist

# Или через Git (рекомендуется)
git push origin main  # Автодеплой при пуше
```

**Альтернативы:**
- GitHub Pages (бесплатно)
- Cloudflare Pages (бесплатно)
- AWS S3 + CloudFront (~$1/мес)

#### Сценарий 2: MVP / Стартап (Python FastAPI)

**Рекомендация: Railway или Render ($10-30/мес)**

**railway.toml:**
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn backend.apps.admin_ui.app:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "on_failure"

[[services]]
name = "web"

[[services]]
name = "postgres"
image = "postgres:16-alpine"

[[services]]
name = "redis"
image = "redis:7-alpine"
```

**Почему:**
- Управляемая БД и Redis из коробки
- Git-based деплой
- Автоматический SSL
- Легко добавить workers/cron

#### Сценарий 3: Средний проект с трафиком (Python + БД + Redis)

**Рекомендация: VPS Hetzner CPX21 (~€8/мес)**

**Преимущества для данного сценария:**
- Полный контроль
- Отличная цена/производительность
- 3 vCPU, 4 GB RAM - достаточно для 1000+ concurrent users
- Можно запустить несколько сервисов

**Архитектура:**
```
[Nginx] ─→ [Uvicorn Workers] ─→ [PostgreSQL]
           ↓
      [Redis]
```

#### Сценарий 4: Node.js API с микросервисами

**Рекомендация: AWS ECS с Fargate или Fly.io**

**docker-compose для локальной разработки:**
```yaml
services:
  api-gateway:
    build: ./api-gateway
    ports:
      - "3000:3000"

  user-service:
    build: ./services/users

  order-service:
    build: ./services/orders
```

**Fly.io depl конфигурация (fly.toml):**
```toml
app = "myapp-api"

[build]
  dockerfile = "Dockerfile"

[[services]]
  internal_port = 3000
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [services.concurrency]
    hard_limit = 25
    soft_limit = 20

[env]
  NODE_ENV = "production"
```

#### Сценарий 5: PHP Laravel E-commerce

**Рекомендация: Laravel Forge + DigitalOcean VPS**

**Laravel Forge:**
- Автоматизирует настройку VPS
- Управление SSL, деплоем, очередями
- $12/мес + стоимость VPS ($6/мес)
- Итого: ~$18/мес

**Альтернатива (дешевле, но вручную):**
- VPS Hetzner CPX11 (€4.5/мес)
- Ручная настройка Nginx + PHP-FPM
- Certbot для SSL
- Supervisor для queue workers

### 2.3 Оценка стоимости

#### Калькулятор стоимости по масштабу

**Малый проект (до 10,000 пользователей/месяц):**

| Вариант | Стоимость/мес | Сложность | Примечания |
|---------|---------------|-----------|------------|
| Shared Hosting | $5-10 | Низкая | Только для простых сайтов |
| VPS начальный (1GB RAM) | $5-10 | Средняя | Хорошо для старта |
| Railway/Render Hobby | $5-15 | Низкая | Рекомендуется для MVP |
| Netlify/Vercel (статика) | $0-10 | Низкая | Идеально для фронтенда |

**Средний проект (10,000-100,000 пользователей/месяц):**

| Вариант | Стоимость/мес | Компоненты |
|---------|---------------|-----------|
| **VPS (рекомендуется)** | **$20-50** | Hetzner CPX21 (€8) + Managed PostgreSQL (€10) + CDN (€5) |
| PaaS | $50-150 | Railway Pro + БД + Redis + Workers |
| AWS начальный | $50-100 | t3.small EC2 + RDS + ElastiCache + ALB |

**Крупный проект (100,000+ пользователей/месяц):**

| Вариант | Стоимость/мес | Компоненты |
|---------|---------------|-----------|
| **Множество VPS** | $100-300 | 3-5 серверов за балансировщиком |
| **AWS/GCP (рекомендуется)** | $300-1000+ | Auto-scaling, managed services, CDN |
| Dedicated Servers | $200-500 | Hetzner Dedicated, полный контроль |

#### Скрытые расходы (не забудьте учесть!)

```
Базовая стоимость VPS:           $20/мес
+ Резервные копии:               $5/мес
+ Мониторинг (Datadog/NewRelic): $10-50/мес
+ CDN (Cloudflare Pro):          $20/мес
+ Email сервис (SendGrid):       $15/мес
+ SSL сертификат:                $0 (Let's Encrypt бесплатно)
+ Domain:                        $10-15/год
+ Объектное хранилище (S3):     $5-20/мес
-------------------------------------------------
ИТОГО:                           $75-130/мес
```

#### Пример расчета для текущего проекта (FastAPI + PostgreSQL + Redis + Bot)

**Вариант 1: VPS самостоятельно (дешевле, сложнее)**
```
Hetzner CPX21:                   €7.59/мес ($8)
PostgreSQL (на том же VPS):      $0
Redis (на том же VPS):           $0
Nginx (на том же VPS):           $0
Backup volumes:                  €3/мес ($3)
Cloudflare (бесплатный tier):    $0
-------------------------------------------------
ИТОГО:                           ~$11/мес
```

**Вариант 2: Managed Database (проще, надежнее)**
```
Hetzner CPX11 (app):             €4.5/мес ($5)
Hetzner Managed PostgreSQL:      €9/мес ($10)
Redis на VPS:                    $0
Automated backups (встроено):    $0
-------------------------------------------------
ИТОГО:                           ~$15/мес
```

**Вариант 3: Railway (PaaS, максимально просто)**
```
Railway Pro plan:                $20/мес (включает credits)
Дополнительные ресурсы:          ~$10-30/мес
-------------------------------------------------
ИТОГО:                           ~$30-50/мес
```

**Рекомендация для данного проекта:**
- **Staging/тестирование**: Railway ($20/мес) - быстрый деплой
- **Production малая нагрузка**: Hetzner VPS CPX11 + Managed DB (~$15/мес)
- **Production средняя нагрузка**: Hetzner VPS CPX21 (~$8/мес, все на одном сервере)
- **Production высокая нагрузка**: AWS/GCP с auto-scaling ($100+/мес)

---

## 3. ПРОЦЕСС РАЗВЕРТЫВАНИЯ

### 3.1 Пошаговая инструкция для первичного деплоя

Рассмотрим детальные инструкции для основных вариантов развертывания.

### 3.1.1 Вариант А: VPS с нуля (Ubuntu 22.04)

#### Шаг 1: Подключение к серверу и начальная настройка

```bash
# 1. Подключение к серверу
ssh root@your-server-ip

# 2. Обновление системы
apt update && apt upgrade -y

# 3. Создание пользователя для приложения (не используйте root!)
adduser deploy
usermod -aG sudo deploy

# 4. Настройка SSH для нового пользователя
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys

# 5. Отключение root login (безопасность)
nano /etc/ssh/sshd_config
# Изменить: PermitRootLogin no
# Изменить: PasswordAuthentication no
systemctl restart sshd

# 6. Настройка firewall
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

#### Шаг 2: Установка необходимого ПО

**Для Python/FastAPI:**
```bash
# Переключиться на пользователя deploy
su - deploy

# Установка Python и зависимостей
sudo apt install -y python3.11 python3.11-venv python3-pip
sudo apt install -y build-essential libpq-dev

# Установка PostgreSQL
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Создание БД и пользователя
sudo -u postgres psql
```

```sql
CREATE DATABASE recruitsmart;
CREATE USER recruitsmart WITH PASSWORD 'YOUR_STRONG_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON DATABASE recruitsmart TO recruitsmart;
\q
```

```bash
# Установка Redis
sudo apt install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Установка Nginx
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx

# Установка Supervisor (для управления процессами Python)
sudo apt install -y supervisor
sudo systemctl enable supervisor
```

#### Шаг 3: Клонирование и настройка приложения

```bash
# Создание директорий
sudo mkdir -p /var/www/recruitsmart
sudo chown deploy:deploy /var/www/recruitsmart
cd /var/www/recruitsmart

# Клонирование репозитория
git clone https://github.com/yourusername/recruitsmart_admin.git .

# Создание виртуального окружения
python3.11 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install --upgrade pip
pip install -r requirements.txt

# Создание директории для данных
sudo mkdir -p /var/lib/recruitsmart_admin
sudo chown deploy:deploy /var/lib/recruitsmart_admin
```

#### Шаг 4: Конфигурация переменных окружения

```bash
# Создание production .env файла
nano /var/www/recruitsmart/.env
```

```bash
# /var/www/recruitsmart/.env
ENVIRONMENT=production

# Database
DATABASE_URL=postgresql+asyncpg://recruitsmart:YOUR_STRONG_PASSWORD_HERE@localhost:5432/recruitsmart
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://localhost:6379/0
NOTIFICATION_BROKER=redis

# Security (ГЕНЕРИРУЙТЕ НОВЫЕ ЗНАЧЕНИЯ!)
SESSION_SECRET=ВАШ_СГЕНЕРИРОВАННЫЙ_64_СИМВОЛЬНЫЙ_СЕКРЕТ
ADMIN_USER=admin
ADMIN_PASSWORD=СИЛЬНЫЙ_ПАРОЛЬ_МИНИМУМ_16_СИМВОЛОВ

# Bot
BOT_ENABLED=true
BOT_TOKEN=ВАШ_ТЕЛЕГРАМ_БОТ_ТОКЕН
BOT_AUTOSTART=false

# Cookies
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=strict

# Data and logs
DATA_DIR=/var/lib/recruitsmart_admin
LOG_LEVEL=INFO
LOG_JSON=true
LOG_FILE=/var/log/recruitsmart/app.log

TZ=Europe/Moscow
```

```bash
# Установка правильных прав доступа
chmod 600 /var/www/recruitsmart/.env
chown deploy:deploy /var/www/recruitsmart/.env

# Создание директории для логов
sudo mkdir -p /var/log/recruitsmart
sudo chown deploy:deploy /var/log/recruitsmart
```

#### Шаг 5: Применение миграций БД

```bash
cd /var/www/recruitsmart
source venv/bin/activate

# Применение миграций
python scripts/run_migrations.py

# Проверка, что миграции прошли успешно
python -c "from backend.core.db import check_db_connection; import asyncio; asyncio.run(check_db_connection())"
```

#### Шаг 6: Настройка Supervisor для управления процессами

```bash
# Создание конфигурации для Admin UI
sudo nano /etc/supervisor/conf.d/recruitsmart-admin-ui.conf
```

```ini
[program:recruitsmart-admin-ui]
directory=/var/www/recruitsmart
command=/var/www/recruitsmart/venv/bin/uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000 --workers 4
user=deploy
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/recruitsmart/admin-ui.err.log
stdout_logfile=/var/log/recruitsmart/admin-ui.out.log
environment=HOME="/home/deploy",USER="deploy",PATH="/var/www/recruitsmart/venv/bin"
```

```bash
# Создание конфигурации для Telegram Bot
sudo nano /etc/supervisor/conf.d/recruitsmart-bot.conf
```

```ini
[program:recruitsmart-bot]
directory=/var/www/recruitsmart
command=/var/www/recruitsmart/venv/bin/python bot.py
user=deploy
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/recruitsmart/bot.err.log
stdout_logfile=/var/log/recruitsmart/bot.out.log
environment=HOME="/home/deploy",USER="deploy",PATH="/var/www/recruitsmart/venv/bin"
```

```bash
# Перезагрузка Supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status

# Проверка логов
sudo supervisorctl tail -f recruitsmart-admin-ui stdout
sudo supervisorctl tail -f recruitsmart-bot stdout
```

#### Шаг 7: Настройка Nginx

```bash
sudo nano /etc/nginx/sites-available/recruitsmart
```

```nginx
# /etc/nginx/sites-available/recruitsmart

upstream recruitsmart_backend {
    server 127.0.0.1:8000;
}

# HTTP -> HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com www.yourdomain.com;

    # Let's Encrypt validation
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates (будут созданы на следующем шаге)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL настройки (современные, безопасные)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/recruitsmart.access.log;
    error_log /var/log/nginx/recruitsmart.error.log;

    # Max upload size
    client_max_body_size 10M;

    # Proxy settings
    location / {
        proxy_pass http://recruitsmart_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Buffering
        proxy_buffering off;
    }

    # Static files (если есть)
    location /static/ {
        alias /var/www/recruitsmart/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint
    location /health {
        proxy_pass http://recruitsmart_backend/health;
        access_log off;
    }
}
```

```bash
# Включение конфигурации
sudo ln -s /etc/nginx/sites-available/recruitsmart /etc/nginx/sites-enabled/

# Удаление дефолтного конфига
sudo rm /etc/nginx/sites-enabled/default

# Проверка конфигурации
sudo nginx -t

# Пока не перезагружаем Nginx, сначала получим SSL сертификат
```

### 3.2 Настройка домена и SSL

#### Шаг 1: Настройка DNS

Добавьте A-записи у вашего регистратора доменов:

```
Тип    Имя              Значение           TTL
A      yourdomain.com   YOUR_SERVER_IP     3600
A      www              YOUR_SERVER_IP     3600
```

Проверка DNS:
```bash
dig yourdomain.com +short
# Должен вернуть IP вашего сервера

# Или используйте nslookup
nslookup yourdomain.com
```

#### Шаг 2: Установка Let's Encrypt SSL (бесплатно)

```bash
# Установка Certbot
sudo apt install -y certbot python3-certbot-nginx

# Получение сертификата
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Следуйте инструкциям:
# 1. Введите email для уведомлений
# 2. Согласитесь с ToS
# 3. Выберите redirect HTTP -> HTTPS

# Проверка автообновления сертификатов
sudo certbot renew --dry-run

# Автообновление настроено через systemd timer
sudo systemctl status certbot.timer
```

#### Шаг 3: Перезагрузка Nginx

```bash
sudo nginx -t  # Проверка конфигурации
sudo systemctl reload nginx

# Проверка статуса
sudo systemctl status nginx
```

### 3.3 Проверка работоспособности

```bash
# 1. Проверка работы приложения
curl -I http://localhost:8000/health
# Должен вернуть HTTP 200

# 2. Проверка через доменное имя
curl -I https://yourdomain.com/health
# Должен вернуть HTTP 200 с SSL

# 3. Проверка логов приложения
sudo supervisorctl tail -f recruitsmart-admin-ui stdout
sudo supervisorctl tail -f recruitsmart-bot stdout

# 4. Проверка логов Nginx
sudo tail -f /var/log/nginx/recruitsmart.access.log
sudo tail -f /var/log/nginx/recruitsmart.error.log

# 5. Проверка подключения к БД
sudo -u postgres psql recruitsmart -c "SELECT version();"

# 6. Проверка Redis
redis-cli ping
# Должен вернуть PONG

# 7. SSL сертификат
echo | openssl s_client -servername yourdomain.com -connect yourdomain.com:443 2>/dev/null | openssl x509 -noout -dates
```

#### Типичные проблемы и решения

**Проблема 1: 502 Bad Gateway**
```bash
# Проверка, что приложение запущено
sudo supervisorctl status recruitsmart-admin-ui

# Если stopped - смотрим логи
sudo supervisorctl tail recruitsmart-admin-ui stderr

# Проверка, что приложение слушает порт 8000
sudo netstat -tlnp | grep 8000
```

**Проблема 2: Permission denied при доступе к БД**
```bash
# Проверка подключения
sudo -u deploy psql -h localhost -U recruitsmart -d recruitsmart

# Если ошибка аутентификации - проверьте pg_hba.conf
sudo nano /etc/postgresql/14/main/pg_hba.conf
# Должна быть строка:
# local   all             all                                     md5
sudo systemctl restart postgresql
```

**Проблема 3: SSL сертификат не применяется**
```bash
# Проверка наличия сертификатов
sudo ls -la /etc/letsencrypt/live/yourdomain.com/

# Повторное получение сертификата
sudo certbot certonly --nginx -d yourdomain.com -d www.yourdomain.com

# Проверка конфигурации Nginx
sudo nginx -t
sudo systemctl reload nginx
```

**Проблема 4: Приложение запускается, но падает через несколько минут**
```bash
# Проверка ресурсов сервера
free -h  # RAM
df -h    # Disk
top      # CPU

# Проверка логов на Out Of Memory
sudo dmesg | grep -i "killed process"

# Если не хватает памяти - добавьте swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

### 3.1.2 Вариант Б: Развертывание через Docker Compose

Этот вариант проще и быстрее для staging/testing окружений.

#### Шаг 1: Подготовка сервера

```bash
# Подключение к серверу
ssh deploy@your-server-ip

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Установка Docker Compose
sudo apt install -y docker-compose-plugin

# Проверка установки
docker --version
docker compose version
```

#### Шаг 2: Клонирование проекта и настройка

```bash
# Клонирование
git clone https://github.com/yourusername/recruitsmart_admin.git
cd recruitsmart_admin

# Создание production .env
cp .env.example .env
nano .env
```

```bash
# Замените следующие значения в .env:
ENVIRONMENT=production
POSTGRES_PASSWORD=СИЛЬНЫЙ_ПАРОЛЬ
ADMIN_PASSWORD=СИЛЬНЫЙ_ПАРОЛЬ
SESSION_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
BOT_TOKEN=ВАШ_ТЕЛЕГРАМ_БОТ_ТОКЕН
```

#### Шаг 3: Запуск stack

```bash
# Сборка образов
docker compose build

# Применение миграций
docker compose run --rm admin_ui python scripts/run_migrations.py

# Запуск всех сервисов
docker compose up -d

# Проверка статуса
docker compose ps
docker compose logs -f admin_ui
docker compose logs -f bot
```

#### Шаг 4: Настройка Nginx как reverse proxy

```bash
# Устанавливаем Nginx на хост-машину
sudo apt install -y nginx

sudo nano /etc/nginx/sites-available/recruitsmart
```

```nginx
upstream docker_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://docker_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/recruitsmart /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Получение SSL через Certbot (как в предыдущем разделе)
sudo certbot --nginx -d yourdomain.com
```

#### Шаг 5: Настройка автозапуска

```bash
# Docker Compose автоматически перезапустит контейнеры при перезагрузке сервера
# благодаря `restart: unless-stopped` в docker-compose.yml

# Проверка
sudo reboot
# После перезагрузки
docker compose ps  # Все сервисы должны быть UP
```

### 3.1.3 Вариант В: Railway (PaaS) - самый простой

#### Шаг 1: Подготовка проекта

```bash
# 1. Убедитесь, что в корне проекта есть:
# - Dockerfile
# - requirements.txt (или package.json для Node.js)

# 2. Создайте railway.toml для конфигурации
nano railway.toml
```

```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "uvicorn backend.apps.admin_ui.app:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "on_failure"
```

#### Шаг 2: Деплой через Railway CLI

```bash
# Установка Railway CLI
npm install -g @railway/cli

# Логин
railway login

# Инициализация проекта
railway init

# Создание PostgreSQL
railway add --database postgres

# Создание Redis
railway add --database redis

# Установка переменных окружения
railway variables set ENVIRONMENT=production
railway variables set SESSION_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
railway variables set ADMIN_PASSWORD=YOUR_PASSWORD
railway variables set BOT_TOKEN=YOUR_BOT_TOKEN

# Деплой
railway up

# Получение URL приложения
railway domain
```

#### Шаг 3: Настройка автодеплоя через GitHub

```bash
# 1. Подключите репозиторий GitHub в Railway Dashboard
# 2. Railway автоматически создаст webhook
# 3. Каждый push в main будет триггерить деплой

# Настройка production ветки
railway environment create production
railway environment switch production
railway link
```

#### Шаг 4: Применение миграций

```bash
# Разовая команда для миграций
railway run python scripts/run_migrations.py

# Или настройте Deploy Hook в Railway Dashboard:
# Settings -> Deploy Triggers -> Run Command
# Command: python scripts/run_migrations.py
```

---

### 3.1.4 Вариант Г: AWS (полный контроль, масштабируемость)

Для более крупных проектов с высокими требованиями.

#### Архитектура AWS

```
[Route 53] → [CloudFront CDN] → [Application Load Balancer]
                                       ↓
                        [ECS Fargate / EC2 Auto Scaling Group]
                                       ↓
                    [RDS PostgreSQL]  [ElastiCache Redis]
                                       ↓
                                  [S3 Storage]
```

#### Шаг 1: Настройка инфраструктуры (Terraform рекомендуется)

**Создайте `terraform/main.tf`:**

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-central-1"
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "recruitsmart-vpc"
  }
}

# Subnets
resource "aws_subnet" "public_1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "eu-central-1a"

  tags = {
    Name = "recruitsmart-public-1"
  }
}

resource "aws_subnet" "public_2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "eu-central-1b"

  tags = {
    Name = "recruitsmart-public-2"
  }
}

# RDS PostgreSQL
resource "aws_db_instance" "postgres" {
  identifier           = "recruitsmart-db"
  engine               = "postgres"
  engine_version       = "16.1"
  instance_class       = "db.t3.micro"
  allocated_storage    = 20
  storage_encrypted    = true
  db_name              = "recruitsmart"
  username             = "recruitsmart"
  password             = var.db_password
  publicly_accessible  = false
  skip_final_snapshot  = false
  backup_retention_period = 7

  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  tags = {
    Name = "recruitsmart-postgres"
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "recruitsmart-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  security_group_ids   = [aws_security_group.redis.id]
  subnet_group_name    = aws_elasticache_subnet_group.main.name

  tags = {
    Name = "recruitsmart-redis"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "recruitsmart-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "recruitsmart-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.public_1.id, aws_subnet.public_2.id]

  tags = {
    Name = "recruitsmart-alb"
  }
}

# ... (дополнительные ресурсы: security groups, target groups, ECS task definitions)
```

#### Шаг 2: Деплой через ECS

```bash
# Установка AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Конфигурация AWS
aws configure
# Введите Access Key, Secret Key, Region

# Логин в ECR (Docker registry AWS)
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.eu-central-1.amazonaws.com

# Создание ECR репозитория
aws ecr create-repository --repository-name recruitsmart/admin-ui

# Сборка и push образа
docker build -t recruitsmart/admin-ui:latest .
docker tag recruitsmart/admin-ui:latest YOUR_ACCOUNT_ID.dkr.ecr.eu-central-1.amazonaws.com/recruitsmart/admin-ui:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.eu-central-1.amazonaws.com/recruitsmart/admin-ui:latest

# Деплой Terraform инфраструктуры
cd terraform
terraform init
terraform plan
terraform apply

# Обновление ECS сервиса
aws ecs update-service --cluster recruitsmart-cluster --service admin-ui --force-new-deployment
```

---

## 4. СТРАТЕГИЯ ОБНОВЛЕНИЙ

### 4.1 Git Workflow для Production

#### Рекомендуемая структура веток

```
main (production)
  ↑
staging (pre-production)
  ↑
develop (integration)
  ↑
feature/* (новые функции)
hotfix/* (срочные исправления)
```

#### Процесс релиза

**1. Разработка новой функции:**
```bash
# Создание feature ветки от develop
git checkout develop
git pull origin develop
git checkout -b feature/user-notifications

# Разработка...
git add .
git commit -m "feat: add user notification system"

# Push и создание Pull Request
git push -u origin feature/user-notifications
# Создайте PR: feature/user-notifications → develop
```

**2. Тестирование на staging:**
```bash
# После merge в develop - деплой на staging
git checkout staging
git pull origin develop
git push origin staging

# Staging автоматически деплоится (через CI/CD)
```

**3. Release на production:**
```bash
# Создание release ветки
git checkout -b release/v1.2.0 staging

# Обновление версии
echo "1.2.0" > VERSION
git add VERSION
git commit -m "chore: bump version to 1.2.0"

# Создание тега
git tag -a v1.2.0 -m "Release version 1.2.0"

# Merge в main
git checkout main
git merge --no-ff release/v1.2.0
git push origin main
git push origin v1.2.0

# Merge обратно в develop
git checkout develop
git merge --no-ff release/v1.2.0
git push origin develop

# Удаление release ветки
git branch -d release/v1.2.0
```

**4. Hotfix (срочное исправление на production):**
```bash
# Создание hotfix ветки от main
git checkout main
git checkout -b hotfix/critical-security-fix

# Исправление...
git commit -am "fix: patch XSS vulnerability in user input"

# Bump patch version
echo "1.2.1" > VERSION
git commit -am "chore: bump version to 1.2.1"

# Tag
git tag -a v1.2.1 -m "Hotfix: Security patch"

# Merge в main
git checkout main
git merge --no-ff hotfix/critical-security-fix
git push origin main
git push origin v1.2.1

# Merge в develop и staging
git checkout develop
git merge --no-ff hotfix/critical-security-fix
git checkout staging
git merge --no-ff hotfix/critical-security-fix
git push origin develop staging

# Удаление hotfix ветки
git branch -d hotfix/critical-security-fix
```

### 4.2 Процесс внесения изменений в Production

#### Чеклист перед деплоем

```markdown
## Pre-Deploy Checklist

- [ ] Все тесты проходят (unit, integration, e2e)
- [ ] Code review выполнен и одобрен
- [ ] Миграции БД созданы и протестированы на staging
- [ ] Rollback план подготовлен
- [ ] Changelog обновлен
- [ ] Мониторинг и алерты настроены
- [ ] Резервная копия БД создана
- [ ] Уведомлены stakeholders о деплое
- [ ] Load testing выполнен (для больших изменений)
- [ ] Секреты и переменные окружения обновлены
```

#### Пошаговый процесс деплоя на VPS

**1. Создание резервной копии:**
```bash
# SSH на сервер
ssh deploy@your-server

# Бэкап БД
sudo -u postgres pg_dump recruitsmart > /tmp/recruitsmart_backup_$(date +%Y%m%d_%H%M%S).sql
# Скопируйте бэкап в безопасное место
scp deploy@your-server:/tmp/recruitsmart_backup_*.sql ./backups/

# Бэкап кода (опционально)
cd /var/www/recruitsmart
git branch backup-$(date +%Y%m%d-%H%M%S)
```

**2. Применение обновлений:**
```bash
cd /var/www/recruitsmart

# Pull последних изменений
git fetch origin
git checkout main
git pull origin main

# Активация venv
source venv/bin/activate

# Обновление зависимостей
pip install -r requirements.txt

# Применение миграций БД
python scripts/run_migrations.py

# Сбор статических файлов (если есть)
# python manage.py collectstatic --noinput  # Для Django
```

**3. Проверка перед перезапуском:**
```bash
# Smoke test конфигурации
python -c "from backend.core.settings import get_settings; s = get_settings(); print(f'Environment: {s.environment}')"

# Проверка подключения к БД
python -c "from backend.core.db import check_db_connection; import asyncio; asyncio.run(check_db_connection())"
```

**4. Перезапуск приложения:**
```bash
# Рестарт через Supervisor
sudo supervisorctl restart recruitsmart-admin-ui
sudo supervisorctl restart recruitsmart-bot

# Или graceful reload (zero downtime)
sudo supervisorctl signal HUP recruitsmart-admin-ui

# Проверка статуса
sudo supervisorctl status
```

**5. Проверка работоспособности:**
```bash
# Проверка health endpoint
curl -f https://yourdomain.com/health || echo "FAILED"

# Проверка логов на ошибки
sudo supervisorctl tail -f recruitsmart-admin-ui stderr | head -n 50

# Проверка метрик (если настроены)
curl https://yourdomain.com/metrics/notifications
```

**6. Мониторинг после деплоя:**
```bash
# Следите за логами в течение 5-10 минут
sudo supervisorctl tail -f recruitsmart-admin-ui stdout

# Проверьте error rate в логах
sudo tail -n 1000 /var/log/recruitsmart/admin-ui.err.log | grep -i error | wc -l

# Проверьте response time
curl -w "@curl-format.txt" -o /dev/null -s https://yourdomain.com/
# curl-format.txt:
# time_namelookup:  %{time_namelookup}\n
# time_connect:  %{time_connect}\n
# time_total:  %{time_total}\n
```

### 4.3 Zero-Downtime Deployment

#### Стратегия Blue-Green Deployment

**Архитектура:**
```
[Nginx Load Balancer]
    ├─→ [Blue Environment] (текущая версия)
    └─→ [Green Environment] (новая версия)
```

**Конфигурация Nginx:**
```nginx
upstream blue_backend {
    server 127.0.0.1:8000;
}

upstream green_backend {
    server 127.0.0.1:8001;
}

# Переменная для переключения
geo $deployment {
    default blue;
}

map $deployment $backend {
    blue    blue_backend;
    green   green_backend;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    location / {
        proxy_pass http://$backend;
        # ... остальные proxy настройки
    }
}
```

**Процесс деплоя:**
```bash
# 1. Текущая версия работает на порту 8000 (blue)
# 2. Деплой новой версии на порт 8001 (green)

# Supervisor конфиг для green
sudo nano /etc/supervisor/conf.d/recruitsmart-green.conf
```

```ini
[program:recruitsmart-green]
directory=/var/www/recruitsmart
command=/var/www/recruitsmart/venv/bin/uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8001 --workers 4
user=deploy
autostart=false
autorestart=true
```

```bash
# Запуск green environment
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start recruitsmart-green

# Проверка green работает
curl -f http://localhost:8001/health

# Smoke tests на green
./scripts/smoke_tests.sh http://localhost:8001

# Переключение трафика на green
sudo sed -i 's/default blue/default green/' /etc/nginx/sites-available/recruitsmart
sudo nginx -t && sudo systemctl reload nginx

# Мониторинг метрик и ошибок
# Если все ОК - останавливаем blue, иначе rollback

# Rollback (если что-то пошло не так)
sudo sed -i 's/default green/default blue/' /etc/nginx/sites-available/recruitsmart
sudo nginx -t && sudo systemctl reload nginx
```

#### Rolling Updates с Supervisor (более простой вариант)

**Конфигурация Supervisor для нескольких воркеров:**
```ini
[program:recruitsmart-worker]
directory=/var/www/recruitsmart
command=/var/www/recruitsmart/venv/bin/uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 80%(process_num)02d --workers 1
process_name=%(program_name)s-%(process_num)d
numprocs=4
numprocs_start=0
user=deploy
autostart=true
autorestart=true
```

**Nginx upstream с несколькими воркерами:**
```nginx
upstream recruitsmart_backend {
    least_conn;
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}
```

**Graceful restart (по одному воркеру):**
```bash
#!/bin/bash
# rolling_restart.sh

WORKERS=("recruitsmart-worker-0" "recruitsmart-worker-1" "recruitsmart-worker-2" "recruitsmart-worker-3")

for worker in "${WORKERS[@]}"; do
    echo "Restarting $worker..."
    sudo supervisorctl restart "$worker"

    # Ждем, пока воркер полностью запустится
    sleep 10

    # Проверяем health
    if ! curl -f http://localhost:8000/health; then
        echo "ERROR: $worker failed health check!"
        exit 1
    fi

    echo "$worker restarted successfully"
done

echo "Rolling restart completed!"
```

### 4.4 Rollback Стратегия

#### Автоматический Rollback через Git

```bash
#!/bin/bash
# rollback.sh - Автоматический откат к предыдущей версии

set -e

DEPLOY_DIR="/var/www/recruitsmart"
BACKUP_DIR="/var/backups/recruitsmart"

cd $DEPLOY_DIR

# Получаем текущий commit
CURRENT_COMMIT=$(git rev-parse HEAD)
echo "Current commit: $CURRENT_COMMIT"

# Получаем предыдущий commit
PREVIOUS_COMMIT=$(git rev-parse HEAD~1)
echo "Rolling back to: $PREVIOUS_COMMIT"

# Создаем backup текущего состояния
mkdir -p $BACKUP_DIR
cp -r $DEPLOY_DIR $BACKUP_DIR/backup-$(date +%Y%m%d-%H%M%S)

# Откат кода
git reset --hard $PREVIOUS_COMMIT

# Активация venv
source venv/bin/activate

# Откат зависимостей (если они изменились)
pip install -r requirements.txt

# ВАЖНО: Откат миграций БД (если были)
# Для Alembic:
# alembic downgrade -1

# Для Django:
# python manage.py migrate APP_NAME MIGRATION_BEFORE

# Рестарт приложения
sudo supervisorctl restart recruitsmart-admin-ui
sudo supervisorctl restart recruitsmart-bot

# Проверка health
sleep 5
if curl -f http://localhost:8000/health; then
    echo "✅ Rollback successful!"
    # Уведомление в Slack/Telegram
    curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
      -H 'Content-Type: application/json' \
      -d "{\"text\":\"🔄 Production rolled back to $PREVIOUS_COMMIT\"}"
else
    echo "❌ Rollback failed! Manual intervention required!"
    exit 1
fi
```

#### Rollback миграций БД

**Для Alembic (Python/SQLAlchemy):**
```bash
# Список примененных миграций
alembic history

# Откат на одну миграцию назад
alembic downgrade -1

# Откат на конкретную миграцию
alembic downgrade abc123def456

# Откат всех миграций
alembic downgrade base
```

**Для Django:**
```bash
# Просмотр миграций
python manage.py showmigrations

# Откат приложения myapp к миграции 0003
python manage.py migrate myapp 0003

# Откат всех миграций приложения
python manage.py migrate myapp zero
```

**ВАЖНО:**
- ⚠️ Некоторые миграции необратимы (например, DROP COLUMN)
- Всегда тестируйте rollback на staging
- Создавайте бэкап БД перед миграциями
- Держите откатываемые миграции минимум 2 релиза

---

## 5. CI/CD АВТОМАТИЗАЦИЯ

### 5.1 GitHub Actions

#### Полный CI/CD Pipeline для Python/FastAPI

**`.github/workflows/deploy.yml`:**

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, staging, develop]
  pull_request:
    branches: [main, staging]

env:
  PYTHON_VERSION: '3.11'
  NODE_VERSION: '18'

jobs:
  # ===== JOB 1: Linting & Code Quality =====
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install black isort mypy flake8
          pip install -r requirements-dev.txt

      - name: Run Black
        run: black --check backend tests

      - name: Run isort
        run: isort --check-only backend tests

      - name: Run Flake8
        run: flake8 backend tests --max-line-length=120

      - name: Run MyPy
        run: mypy backend --ignore-missing-imports

  # ===== JOB 2: Testing =====
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt

      - name: Run tests with coverage
        env:
          ENVIRONMENT: test
          DATABASE_URL: postgresql+asyncpg://test_user:test_password@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/0
          SESSION_SECRET: test-secret-key-32-characters-long
        run: |
          pytest --cov=backend --cov-report=xml --cov-report=term tests/

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          fail_ci_if_error: true

  # ===== JOB 3: Security Scan =====
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'

      - name: Upload Trivy results to GitHub Security
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-results.sarif'

      - name: Check for Python vulnerabilities (Safety)
        run: |
          pip install safety
          safety check --json

  # ===== JOB 4: Build Docker Image =====
  build:
    runs-on: ubuntu-latest
    needs: [lint, test]
    if: github.event_name == 'push'

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha,prefix={{branch}}-

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ===== JOB 5: Deploy to Staging =====
  deploy-staging:
    runs-on: ubuntu-latest
    needs: [build]
    if: github.ref == 'refs/heads/staging'
    environment:
      name: staging
      url: https://staging.yourdomain.com

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to staging server
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.STAGING_HOST }}
          username: ${{ secrets.STAGING_USER }}
          key: ${{ secrets.STAGING_SSH_KEY }}
          script: |
            cd /var/www/recruitsmart-staging
            git pull origin staging
            source venv/bin/activate
            pip install -r requirements.txt
            python scripts/run_migrations.py
            sudo supervisorctl restart recruitsmart-staging

            # Health check
            sleep 5
            curl -f http://localhost:8000/health || exit 1

      - name: Notify Slack
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Staging deployment completed'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}

  # ===== JOB 6: Deploy to Production =====
  deploy-production:
    runs-on: ubuntu-latest
    needs: [build]
    if: github.ref == 'refs/heads/main'
    environment:
      name: production
      url: https://yourdomain.com

    steps:
      - uses: actions/checkout@v4

      - name: Create deployment
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.repos.createDeployment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              ref: context.ref,
              environment: 'production',
              required_contexts: [],
              auto_merge: false
            })

      - name: Backup production database
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.PROD_HOST }}
          username: ${{ secrets.PROD_USER }}
          key: ${{ secrets.PROD_SSH_KEY }}
          script: |
            BACKUP_FILE="/var/backups/recruitsmart/db-$(date +%Y%m%d-%H%M%S).sql"
            sudo -u postgres pg_dump recruitsmart > $BACKUP_FILE
            gzip $BACKUP_FILE
            echo "Backup created: $BACKUP_FILE.gz"

      - name: Deploy to production
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.PROD_HOST }}
          username: ${{ secrets.PROD_USER }}
          key: ${{ secrets.PROD_SSH_KEY }}
          script: |
            cd /var/www/recruitsmart

            # Store current commit for potential rollback
            CURRENT_COMMIT=$(git rev-parse HEAD)
            echo $CURRENT_COMMIT > /tmp/recruitsmart-previous-commit

            # Pull latest code
            git fetch origin
            git checkout main
            git pull origin main

            # Update dependencies
            source venv/bin/activate
            pip install -r requirements.txt

            # Run migrations
            python scripts/run_migrations.py

            # Graceful restart (zero downtime)
            ./scripts/rolling_restart.sh

            # Health check
            sleep 5
            if ! curl -f https://yourdomain.com/health; then
              echo "Health check failed! Rolling back..."
              git reset --hard $CURRENT_COMMIT
              sudo supervisorctl restart recruitsmart-admin-ui
              exit 1
            fi

            echo "✅ Deployment successful!"

      - name: Run smoke tests
        run: |
          curl -f https://yourdomain.com/health
          curl -f https://yourdomain.com/health/bot
          curl -f https://yourdomain.com/health/notifications

      - name: Notify on success
        if: success()
        uses: 8398a7/action-slack@v3
        with:
          status: custom
          custom_payload: |
            {
              text: `:rocket: Production deployment successful!\nCommit: ${{ github.sha }}\nAuthor: ${{ github.actor }}`,
              color: 'good'
            }
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}

      - name: Notify on failure
        if: failure()
        uses: 8398a7/action-slack@v3
        with:
          status: custom
          custom_payload: |
            {
              text: `:x: Production deployment FAILED!\nCommit: ${{ github.sha }}\nAuthor: ${{ github.actor }}\n@channel`,
              color: 'danger'
            }
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

#### Настройка GitHub Secrets

В Settings → Secrets and variables → Actions добавьте:

```
# Staging
STAGING_HOST=staging.yourdomain.com
STAGING_USER=deploy
STAGING_SSH_KEY=<private SSH key>

# Production
PROD_HOST=yourdomain.com
PROD_USER=deploy
PROD_SSH_KEY=<private SSH key>

# Notifications
SLACK_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Optional: Docker registry
DOCKERHUB_USERNAME=your-username
DOCKERHUB_TOKEN=your-token
```

### 5.2 GitLab CI/CD

**`.gitlab-ci.yml`:**

```yaml
stages:
  - lint
  - test
  - build
  - deploy

variables:
  PYTHON_VERSION: "3.11"
  DOCKER_DRIVER: overlay2
  DOCKER_TLS_CERTDIR: "/certs"

# ===== Templates =====
.python_template: &python_template
  image: python:${PYTHON_VERSION}-slim
  before_script:
    - pip install --upgrade pip
    - pip install -r requirements-dev.txt
  cache:
    paths:
      - .cache/pip

# ===== Linting =====
lint:black:
  <<: *python_template
  stage: lint
  script:
    - black --check backend tests

lint:mypy:
  <<: *python_template
  stage: lint
  script:
    - mypy backend --ignore-missing-imports
  allow_failure: true

# ===== Testing =====
test:unit:
  <<: *python_template
  stage: test
  services:
    - postgres:16-alpine
    - redis:7-alpine
  variables:
    POSTGRES_DB: test_db
    POSTGRES_USER: test_user
    POSTGRES_PASSWORD: test_password
    DATABASE_URL: postgresql+asyncpg://test_user:test_password@postgres:5432/test_db
    REDIS_URL: redis://redis:6379/0
    ENVIRONMENT: test
    SESSION_SECRET: test-secret-32-chars-minimum-length
  script:
    - pytest --cov=backend --cov-report=term --cov-report=html:coverage tests/
  coverage: '/TOTAL.*\s+(\d+%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
    paths:
      - coverage/
    expire_in: 1 week

# ===== Build Docker Image =====
build:docker:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA .
    - docker tag $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA $CI_REGISTRY_IMAGE:latest
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA
    - docker push $CI_REGISTRY_IMAGE:latest
  only:
    - main
    - staging

# ===== Deploy to Staging =====
deploy:staging:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache openssh-client
    - eval $(ssh-agent -s)
    - echo "$STAGING_SSH_KEY" | tr -d '\r' | ssh-add -
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
    - ssh-keyscan $STAGING_HOST >> ~/.ssh/known_hosts
  script:
    - |
      ssh $STAGING_USER@$STAGING_HOST << 'EOF'
        cd /var/www/recruitsmart-staging
        git pull origin staging
        source venv/bin/activate
        pip install -r requirements.txt
        python scripts/run_migrations.py
        sudo supervisorctl restart recruitsmart-staging
        sleep 5
        curl -f http://localhost:8000/health || exit 1
      EOF
  environment:
    name: staging
    url: https://staging.yourdomain.com
  only:
    - staging

# ===== Deploy to Production =====
deploy:production:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache openssh-client curl
    - eval $(ssh-agent -s)
    - echo "$PROD_SSH_KEY" | tr -d '\r' | ssh-add -
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
    - ssh-keyscan $PROD_HOST >> ~/.ssh/known_hosts
  script:
    - |
      ssh $PROD_USER@$PROD_HOST << 'EOF'
        cd /var/www/recruitsmart

        # Backup
        sudo -u postgres pg_dump recruitsmart > /var/backups/recruitsmart/db-$(date +%Y%m%d-%H%M%S).sql

        # Deploy
        git pull origin main
        source venv/bin/activate
        pip install -r requirements.txt
        python scripts/run_migrations.py

        # Rolling restart
        ./scripts/rolling_restart.sh

        # Health check
        sleep 5
        curl -f https://yourdomain.com/health || exit 1
      EOF
  environment:
    name: production
    url: https://yourdomain.com
  when: manual  # Требует ручного подтверждения
  only:
    - main
```

### 5.3 Альтернативы: Jenkins, CircleCI

#### Jenkins Pipeline

**`Jenkinsfile`:**

```groovy
pipeline {
    agent any

    environment {
        PYTHON_VERSION = '3.11'
        VENV_PATH = "${WORKSPACE}/venv"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup') {
            steps {
                sh '''
                    python${PYTHON_VERSION} -m venv ${VENV_PATH}
                    . ${VENV_PATH}/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements-dev.txt
                '''
            }
        }

        stage('Lint') {
            parallel {
                stage('Black') {
                    steps {
                        sh '''
                            . ${VENV_PATH}/bin/activate
                            black --check backend tests
                        '''
                    }
                }
                stage('Flake8') {
                    steps {
                        sh '''
                            . ${VENV_PATH}/bin/activate
                            flake8 backend tests
                        '''
                    }
                }
            }
        }

        stage('Test') {
            steps {
                sh '''
                    . ${VENV_PATH}/bin/activate
                    pytest --cov=backend --cov-report=xml tests/
                '''
            }
            post {
                always {
                    junit '**/test-results/*.xml'
                    cobertura coberturaReportFile: 'coverage.xml'
                }
            }
        }

        stage('Build') {
            when {
                branch 'main'
            }
            steps {
                sh 'docker build -t recruitsmart:${BUILD_NUMBER} .'
            }
        }

        stage('Deploy to Production') {
            when {
                branch 'main'
            }
            input {
                message "Deploy to production?"
                ok "Deploy"
            }
            steps {
                sshagent(['prod-ssh-key']) {
                    sh '''
                        ssh deploy@prod.yourdomain.com "cd /var/www/recruitsmart && \
                        git pull origin main && \
                        source venv/bin/activate && \
                        pip install -r requirements.txt && \
                        python scripts/run_migrations.py && \
                        sudo supervisorctl restart recruitsmart-admin-ui"
                    '''
                }
            }
        }
    }

    post {
        success {
            slackSend(
                color: 'good',
                message: "Build #${BUILD_NUMBER} succeeded - ${JOB_NAME}"
            )
        }
        failure {
            slackSend(
                color: 'danger',
                message: "Build #${BUILD_NUMBER} FAILED - ${JOB_NAME}"
            )
        }
    }
}
```

---

## 6. МОНИТОРИНГ И ПОДДЕРЖКА

### 6.1 Логирование

#### Настройка структурированного логирования

**Python/FastAPI:**

```python
# backend/core/logging_config.py
import logging
import sys
from pathlib import Path
from pythonjsonlogger import jsonlogger

from backend.core.settings import get_settings

settings = get_settings()


def setup_logging():
    """Настройка логирования для production."""

    # Базовая конфигурация
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Очистка существующих handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if settings.log_json:
        # JSON формат для production (легко парсится в Elasticsearch/Datadog)
        json_formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d',
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
        console_handler.setFormatter(json_formatter)
    else:
        # Human-readable для development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)

    # File handler (если указан LOG_FILE)
    if settings.log_file:
        log_file_path = Path(settings.log_file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=settings.log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)

        if settings.log_json:
            file_handler.setFormatter(json_formatter)
        else:
            file_handler.setFormatter(formatter)

        root_logger.addHandler(file_handler)

    # Отключаем verbose логи от библиотек
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.INFO)

    logging.info("Logging configured", extra={
        "log_level": settings.log_level,
        "log_json": settings.log_json,
        "log_file": settings.log_file,
        "environment": settings.environment
    })
```

**Использование в коде:**

```python
import logging

logger = logging.getLogger(__name__)

# Структурированные логи с дополнительным контекстом
logger.info(
    "User registered successfully",
    extra={
        "user_id": user.id,
        "email": user.email,
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent")
    }
)

# Error логирование с traceback
try:
    result = perform_operation()
except Exception as e:
    logger.exception(
        "Operation failed",
        extra={
            "operation": "perform_operation",
            "user_id": user.id
        }
    )
    raise
```

#### Централизованное логирование

**Вариант 1: ELK Stack (Elasticsearch + Logstash + Kibana)**

```bash
# docker-compose для ELK stack
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    volumes:
      - es_data:/usr/share/elasticsearch/data

  logstash:
    image: docker.elastic.co/logstash/logstash:8.11.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    ports:
      - "5044:5044"
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch

volumes:
  es_data:
```

**logstash.conf:**

```
input {
  file {
    path => "/var/log/recruitsmart/*.log"
    codec => json
    type => "recruitsmart"
  }
}

filter {
  if [type] == "recruitsmart" {
    date {
      match => [ "asctime", "ISO8601" ]
      target => "@timestamp"
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "recruitsmart-%{+YYYY.MM.dd}"
  }

  # Debug output
  stdout { codec => rubydebug }
}
```

**Вариант 2: Grafana Loki (легковесная альтернатива)**

```yaml
# docker-compose.yml для Loki
services:
  loki:
    image: grafana/loki:2.9.0
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yaml
    volumes:
      - loki_data:/loki

  promtail:
    image: grafana/promtail:2.9.0
    volumes:
      - /var/log:/var/log
      - ./promtail-config.yaml:/etc/promtail/config.yaml
    command: -config.file=/etc/promtail/config.yaml

  grafana:
    image: grafana/grafana:10.2.0
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  loki_data:
  grafana_data:
```

**promtail-config.yaml:**

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: recruitsmart
    static_configs:
      - targets:
          - localhost
        labels:
          job: recruitsmart
          __path__: /var/log/recruitsmart/*.log
    pipeline_stages:
      - json:
          expressions:
            level: levelname
            message: message
            logger: name
      - labels:
          level:
          logger:
```

### 6.2 Мониторинг производительности

#### Prometheus + Grafana

**1. Добавление метрик в FastAPI приложение:**

```python
# backend/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
import time

# Метрики
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

active_users = Gauge(
    'active_users_total',
    'Number of active users'
)

db_connections = Gauge(
    'database_connections_active',
    'Active database connections'
)

class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time

        # Записываем метрики
        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

        return response


# В main.py приложения:
from fastapi import FastAPI, Response
from backend.core.metrics import PrometheusMiddleware, generate_latest

app = FastAPI()
app.add_middleware(PrometheusMiddleware)

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )
```

**2. Конфигурация Prometheus:**

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'recruitsmart'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'

  - job_name: 'node_exporter'
    static_configs:
      - targets: ['localhost:9100']

  - job_name: 'postgres_exporter'
    static_configs:
      - targets: ['localhost:9187']
```

**3. Docker Compose с мониторингом:**

```yaml
services:
  # ... ваше приложение ...

  prometheus:
    image: prom/prometheus:v2.47.0
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    ports:
      - "9090:9090"
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.2.0
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_INSTALL_PLUGINS=redis-datasource
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
    restart: unless-stopped

  node_exporter:
    image: prom/node-exporter:v1.6.1
    command:
      - '--path.rootfs=/host'
    pid: host
    restart: unless-stopped
    volumes:
      - '/:/host:ro,rslave'

  postgres_exporter:
    image: prometheuscommunity/postgres-exporter:v0.15.0
    environment:
      DATA_SOURCE_NAME: "postgresql://recruitsmart:${POSTGRES_PASSWORD}@postgres:5432/recruitsmart?sslmode=disable"
    ports:
      - "9187:9187"
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
```

**4. Grafana Dashboard JSON (пример):**

```json
{
  "dashboard": {
    "title": "RecruitSmart Monitoring",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Response Time (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m])",
            "legendFormat": "5xx errors"
          }
        ],
        "type": "graph"
      }
    ]
  }
}
```

### 6.3 Алерты и уведомления

#### Alertmanager конфигурация

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m
  slack_api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'

route:
  group_by: ['alertname', 'cluster']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'slack-notifications'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
    - match:
        severity: warning
      receiver: 'slack-notifications'

receivers:
  - name: 'slack-notifications'
    slack_configs:
      - channel: '#alerts'
        title: 'RecruitSmart Alert'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'
```

#### Prometheus Alert Rules

```yaml
# alert_rules.yml
groups:
  - name: application_alerts
    interval: 30s
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors/sec"

      # Slow responses
      - alert: SlowResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Slow response time"
          description: "95th percentile response time is {{ $value }}s"

      # Database connections exhausted
      - alert: DatabaseConnectionsHigh
        expr: database_connections_active > 18
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Database connections running high"
          description: "Active connections: {{ $value }}/20"

      # Disk space low
      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100 < 10
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Disk space critically low"
          description: "Only {{ $value }}% disk space remaining"

      # High CPU usage
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ $value }}%"

      # Application down
      - alert: ApplicationDown
        expr: up{job="recruitsmart"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Application is down"
          description: "RecruitSmart application is not responding"
```

### 6.4 Резервное копирование

#### Автоматический бэкап PostgreSQL

```bash
#!/bin/bash
# /usr/local/bin/backup_postgres.sh

set -e

BACKUP_DIR="/var/backups/recruitsmart/postgres"
RETENTION_DAYS=7
DB_NAME="recruitsmart"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

# Создание директории
mkdir -p "$BACKUP_DIR"

# Бэкап
echo "Starting backup of $DB_NAME..."
sudo -u postgres pg_dump "$DB_NAME" | gzip > "$BACKUP_FILE"

# Проверка успешности
if [ $? -eq 0 ]; then
    echo "✅ Backup successful: $BACKUP_FILE"
    echo "Size: $(du -h $BACKUP_FILE | cut -f1)"
else
    echo "❌ Backup failed!"
    exit 1
fi

# Удаление старых бэкапов
echo "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Опционально: загрузка на S3/облако
# aws s3 cp "$BACKUP_FILE" s3://my-backups/postgres/

echo "Backup completed!"
```

**Настройка через cron:**

```bash
# Редактирование crontab
sudo crontab -e

# Ежедневный бэкап в 2:00 ночи
0 2 * * * /usr/local/bin/backup_postgres.sh >> /var/log/recruitsmart/backup.log 2>&1

# Недельный бэкап с отправкой на S3 (воскресенье, 3:00)
0 3 * * 0 /usr/local/bin/backup_postgres.sh && aws s3 sync /var/backups/recruitsmart s3://my-backups/recruitsmart/
```

#### Восстановление из бэкапа

```bash
#!/bin/bash
# restore_postgres.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

DB_NAME="recruitsmart"

echo "⚠️  WARNING: This will REPLACE the current database!"
read -p "Are you sure? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo "Creating backup of current database..."
sudo -u postgres pg_dump "$DB_NAME" | gzip > "/tmp/${DB_NAME}_before_restore_$(date +%Y%m%d_%H%M%S).sql.gz"

echo "Dropping existing database..."
sudo -u postgres psql -c "DROP DATABASE IF EXISTS $DB_NAME;"

echo "Creating new database..."
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;"

echo "Restoring from backup..."
gunzip < "$BACKUP_FILE" | sudo -u postgres psql "$DB_NAME"

if [ $? -eq 0 ]; then
    echo "✅ Restore successful!"
else
    echo "❌ Restore failed!"
    exit 1
fi
```

### 6.5 Uptime Monitoring

#### UptimeRobot (бесплатный tier)

```bash
# Настройка через API
curl -X POST https://api.uptimerobot.com/v2/newMonitor \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "api_key=YOUR_API_KEY" \
  -d "friendly_name=RecruitSmart Production" \
  -d "url=https://yourdomain.com/health" \
  -d "type=1" \
  -d "interval=300" \
  -d "alert_contacts=CONTACT_ID"
```

#### Простой health check скрипт

```bash
#!/bin/bash
# /usr/local/bin/health_check.sh

HEALTH_URL="https://yourdomain.com/health"
SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK"

response=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL")

if [ "$response" != "200" ]; then
    message="🚨 ALERT: RecruitSmart health check failed! HTTP $response"

    curl -X POST "$SLACK_WEBHOOK" \
      -H 'Content-Type: application/json' \
      -d "{\"text\":\"$message\"}"

    echo "$message"
    exit 1
else
    echo "✅ Health check passed"
fi
```

**Cron (каждые 5 минут):**
```bash
*/5 * * * * /usr/local/bin/health_check.sh >> /var/log/recruitsmart/healthcheck.log 2>&1
```

---

## 7. ЗАКЛЮЧЕНИЕ И BEST PRACTICES

### Чеклист production-ready приложения

```markdown
## Infrastructure
- [ ] Используется production-grade база данных (PostgreSQL, не SQLite)
- [ ] Настроено автоматическое резервное копирование (ежедневно + недельно)
- [ ] Настроен мониторинг (Prometheus/Grafana или аналог)
- [ ] Логи централизованы (ELK/Loki или cloud logging)
- [ ] SSL сертификаты настроены и автообновляются
- [ ] Firewall настроен (только 80, 443, SSH)
- [ ] SSH доступ только по ключам, root login отключен

## Application
- [ ] Все секреты в переменных окружения, не в коде
- [ ] Production конфигурация валидирована (см. backend/core/settings.py)
- [ ] Миграции БД протестированы и имеют rollback план
- [ ] Rate limiting настроен для API
- [ ] CORS настроен корректно
- [ ] Helmet/security headers включены
- [ ] Graceful shutdown реализован

## Deployment
- [ ] CI/CD pipeline настроен
- [ ] Staging окружение существует и используется
- [ ] Deployment требует code review + approval
- [ ] Rollback процедура документирована и протестирована
- [ ] Zero-downtime deployment настроен

## Monitoring & Alerts
- [ ] Uptime monitoring настроен (UptimeRobot/Pingdom)
- [ ] Error tracking настроен (Sentry/Rollbar)
- [ ] Performance monitoring настроен (New Relic/Datadog)
- [ ] Alerts настроены для критичных метрик
- [ ] On-call rotation определена (PagerDuty)

## Documentation
- [ ] README актуален
- [ ] Deployment guide существует
- [ ] Runbook для инцидентов создан
- [ ] Architecture diagram актуален
- [ ] API документация доступна
```

### Распространенные ошибки

1. **Использование SQLite в production** ❌
   - SQLite не подходит для concurrent writes
   - Используйте PostgreSQL или MySQL

2. **Игнорирование миграций БД** ❌
   - Всегда применяйте миграции через automation
   - Тестируйте rollback

3. **Хранение секретов в коде** ❌
   - Используйте переменные окружения
   - Ротируйте секреты регулярно

4. **Отсутствие мониторинга** ❌
   - "Если вы не мониторите - вы не знаете, что сломалось"
   - Минимум: uptime check + error logging

5. **Деплой напрямую в production** ❌
   - Всегда тестируйте на staging
   - Используйте Git tags для релизов

6. **Отсутствие резервных копий** ❌
   - Автоматизируйте бэкапы
   - Тестируйте восстановление

7. **Игнорирование безопасности** ❌
   - Держите зависимости актуальными
   - Сканируйте уязвимости (Snyk, Dependabot)

### Полезные ресурсы

**Документация:**
- [The Twelve-Factor App](https://12factor.net/) - best practices для SaaS
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [PostgreSQL Backup Best Practices](https://www.postgresql.org/docs/current/backup.html)

**Инструменты:**
- [Ansible](https://www.ansible.com/) - автоматизация конфигурации
- [Terraform](https://www.terraform.io/) - infrastructure as code
- [Docker Compose](https://docs.docker.com/compose/) - локальная и staging среда

**Мониторинг:**
- [Sentry](https://sentry.io/) - error tracking (бесплатный tier)
- [UptimeRobot](https://uptimerobot.com/) - uptime monitoring (бесплатно)
- [Grafana Cloud](https://grafana.com/products/cloud/) - metrics + logs (бесплатный tier)

---

**Этот отчет подготовлен на основе реального проекта RecruitSmart Admin и применим для большинства веб-приложений на Python, Node.js, PHP и статических сайтов.**
