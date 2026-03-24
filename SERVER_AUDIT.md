# Server Audit — RecruitSmart Production
## Дата: 2026-03-15

Аудит выполнен по `root@185.104.115.19`, hostname `4410671-mt35494`.
Изменений на сервере не вносилось. Значения секретов намеренно не выводились.

## 1. Железо и ОС
| Параметр | Значение |
|----------|----------|
| ОС | Ubuntu 22.04.5 LTS (Jammy Jellyfish) |
| Kernel | `Linux 5.15.0-1032-realtime #35-Ubuntu SMP PREEMPT_RT Tue Jan 24 11:45:03 UTC 2023` |
| Hostname | `4410671-mt35494` |
| CPU (ядра) | 2 vCPU, `AMD EPYC Processor`, `Thread(s) per core = 1`, `Socket(s) = 2` |
| RAM | `1.93 GiB total / 1.22 GiB used / 21.87 MiB free / 711.58 MiB buff-cache / 567.36 MiB available` |
| Swap | `2.00 GiB total / 534.43 MiB used / 1.48 GiB free` |
| Диск (всего / использовано / свободно) | `39.28 GiB / 31.77 GiB / 7.50 GiB` (`81%` root FS) |
| Тип диска | `lsblk` reports `ROTA=1` on `/dev/vda`; это выглядит как rotational/HDD с точки зрения гипервизора |
| Uptime | `131 days, 21:41` |
| Load average | `0.52 / 0.61 / 0.63` |

### Наблюдения
- **Свободной RAM почти нет: `21.87 MiB free`, swap уже используется на `534.43 MiB`.**
- На момент аудита CPU не перегружен: load ниже количества vCPU.
- Сервер явно multi-tenant: кроме RecruitSmart здесь живут `n8n`, `vpn-control`, `wg-admin`, `xray`, `zabbix-agent`.

## 2. Диск — что занимает место
### Топ директорий от `/`
| Путь | Размер |
|------|--------|
| `/var` | `21.98 GiB` |
| `/usr` | `4.07 GiB` |
| `/opt` | `3.66 GiB` |
| `/snap` | `3.32 GiB` |
| `/root` | `1.11 GiB` |
| `/boot` | `247.29 MiB` |
| `/tmp` | `49.72 MiB` |
| `/srv` | `28.59 MiB` |
| `/etc` | `8.79 MiB` |
| `/home` | `368.00 KiB` |

### Ключевые тяжёлые поддиректории
| Путь | Размер |
|------|--------|
| `/var/lib` | `20.55 GiB` |
| `/var/lib/docker` | **`15.62 GiB`** |
| `/var/lib/n8n.ZOMBIE.2025-09-18_205154` | **`2.70 GiB`** |
| `/var/lib/snapd` | `1.66 GiB` |
| `/var/lib/postgresql` | `201.25 MiB` |
| `/var/log` | `424.07 MiB` |
| `/var/backups` | `368.12 MiB` |
| `/opt/recruitsmart_admin_prev_20260315_124124` | **`1.03 GiB`** |
| `/opt/recruitsmart_admin_hh_preview` | **`892.09 MiB`** |
| `/opt/vpn-service` | `593.66 MiB` |
| `/opt/recruitsmart_admin_prev_incoming_styles_20260315_135818` | `244.86 MiB` |
| `/opt/recruitsmart_admin` | `244.78 MiB` |
| `/root/backups` | `752.39 MiB` |
| `/root/backups/n8n` | `500.17 MiB` |
| `/root/backups/recruitsmart_admin` | `123.07 MiB` |

### Что выглядит особенно тяжёлым
- **Docker занимает `15.62 GiB` в `/var/lib/docker`.**
- **Старый каталог `n8n.ZOMBIE.2025-09-18_205154` занимает `2.70 GiB`.**
- **Только RecruitSmart snapshot-каталоги в `/opt` занимают `2.37 GiB`**:
  `recruitsmart_admin_prev_20260315_124124`, `recruitsmart_admin_hh_preview`,
  `recruitsmart_admin_prev_incoming_styles_20260315_135818`,
  `recruitsmart_admin_prev_hotfix_20260315_130706`,
  `recruitsmart_admin_prev_messenger_scroll_20260315_133131`,
  `recruitsmart_admin_prev_deploy_20260315_134648`.

### Docker images/volumes
| Категория | Состояние |
|----------|-----------|
| Images | `54 total`, `5.273GB`, reclaimable `2.873GB (54%)` |
| Containers | `8 total`, `1 active`, `56.35MB` |
| Local Volumes | `11 total`, `2.985GB`, reclaimable `2.869GB (96%)` |
| Build Cache | **`6.668GB`** |

Крупнейшие Docker volume:

| Volume | Размер | Ссылки |
|--------|--------|--------|
| `n8n_data` | **`2.821GB`** | `0` |
| `infra_pgdata` | `67.11MB` | `1` |
| `recruitment_system_postgres_data` | `48.33MB` | `0` |
| `recruitsmart_admin_postgres_data` | `48.05MB` | `1` |
| `7561dcdfff551fad055c135fefd9ee50810ba2708b56155c0014512720e1800d` | `683.3kB` | `1` |

Крупнейшие Docker images:

| Image | Размер | Контейнеров |
|-------|--------|-------------|
| `docker.n8n.io/n8nio/n8n:2.7.3` | `1.01GB` | `1` |
| `n8nio/n8n:1.110.1` | `974MB` | `0` |
| `infra-bot:latest` | `481MB` | `1` |
| `postgres:16` | `451MB` | `1` |
| `recruitsmart-frontend-build:20260216-165326` | `376MB` | `0` |

Дополнительно:
- Есть 7 stopped/created Docker containers от старого `infra-*` и `recruitsmart_admin-postgres-1`.
- Много dangling images (`<none>`), суммарно они забирают заметное место.

### Логи
| Путь | Размер |
|------|--------|
| `/var/log/journal` | `246.05 MiB` |
| `/var/log/nginx` | `92.64 MiB` |
| `/var/log/wgmon` | `9.44 MiB` |
| `/var/log/redis` | `476.00 KiB` |
| `/var/log/postgresql` | `304.00 KiB` |

`journalctl --disk-usage`: `238.0M`.

### Большие файлы (>100MB)
| Файл | Комментарий |
|------|-------------|
| `/swapfile` | `2.00 GiB` |
| `/opt/recruitsmart_admin_prev_20260315_124124/.git/objects/pack/...pack` | большой git pack старого deploy |
| `/opt/recruitsmart_admin_hh_preview/.git/objects/pack/...pack` | большой git pack preview deploy |
| `/var/lib/docker/volumes/n8n_data/_data/database.sqlite` | большой n8n SQLite DB |
| `/var/lib/n8n.ZOMBIE.2025-09-18_205154/database.sqlite.bak.2025-09-18_204457` | zombie backup |
| `/boot/initrd.img-5.15.0-1032-realtime` | системный образ initrd |
| `/boot/initrd.img-5.15.0-134-generic` | системный образ initrd |
| `/var/lib/snapd/snaps/core_17272.snap` | крупный snap |
| `/var/lib/snapd/snaps/core_17247.snap` | крупный snap |

### node_modules / .venv на сервере
- `node_modules`: в `/opt` и `/root` на глубине до 6 уровней **не найдено**.
- Активный RecruitSmart `.venv` в текущем deploy не локальный каталог, а symlink:
  `/opt/recruitsmart_admin/.venv -> /opt/recruitsmart_admin_prev_20260315_124124/.venv`
- Крупные virtualenv:

| Путь | Размер |
|------|--------|
| `/opt/recruitsmart_admin_prev_20260315_124124/.venv` | `273.74 MiB` |
| `/opt/recruitsmart_admin_hh_preview/.venv` | `273.73 MiB` |
| `/opt/wg-admin/.venv` | `19.02 MiB` |

### Git repos
| Путь | Размер |
|------|--------|
| `/opt/recruitsmart_admin_prev_20260315_124124/.git` | `114.53 MiB` |
| `/opt/recruitsmart_admin_hh_preview/.git` | `114.53 MiB` |

## 3. Процессы и ресурсы
### Топ по CPU
| Процесс | User | CPU | MEM | RSS | Комментарий |
|---------|------|-----|-----|-----|-------------|
| `python` (`recruitsmart-admin`, port `8010`) | `root` | `13.2%` | `14.5%` | `287.82 MiB` | основной FastAPI/uvicorn |
| `python` (`recruitsmart-bot`) | `root` | `0.8%` | `8.1%` | `161.95 MiB` | Telegram bot |
| `postgres` client backend | `postgres` | `0.7%` | `4.0%` | `80.79 MiB` | idle connection backend |
| `uvicorn` (`vpn-control`, port `8000`) | `root` | `0.3%` | `1.4%` | `27.98 MiB` | сторонний сервис |
| `fail2ban-server` | `root` | `0.2%` | `1.0%` | `21.73 MiB` | security |

Примечание: `sshd` в топе CPU относится к самой audit SSH-сессии и не учитывается как рабочая нагрузка.

### Топ по RAM
| Процесс | User | MEM | RSS | Комментарий |
|---------|------|-----|-----|-------------|
| `recruitsmart-admin` (`uvicorn 8010`) | `root` | `14.5%` | `287.82 MiB` | основной UI/API |
| `recruitsmart-bot` | `root` | `8.1%` | `161.95 MiB` | bot |
| `postgres checkpointer` | `postgres` | `5.7%` | `114.19 MiB` | background |
| `n8n` | `admin` | `4.8%` | `95.93 MiB` | Docker container |
| `postgres` idle backends | `postgres` | `2.7-4.0%` each | `55-82 MiB` each | много idle connections |

### Запущенные сервисы
Ключевые production/ops сервисы:

- `recruitsmart-admin.service`
- `recruitsmart-bot.service`
- `postgresql@14-main.service`
- `redis-server.service`
- `nginx.service`
- `docker.service`
- `fail2ban.service`
- `zabbix-agent.service`
- `vpn-control.service`
- `wg-admin.service`
- `xray.service`

Отдельное наблюдение:
- Вне `systemd` живёт preview-процесс `recruitsmart_admin_hh_preview` на `127.0.0.1:8011`.

### Docker контейнеры (с потреблением)
| Container | Image | Status | Ports | CPU | RAM |
|-----------|-------|--------|-------|-----|-----|
| `n8n_core` | `docker.n8n.io/n8nio/n8n:2.7.3` | `Up 8 days` | `127.0.0.1:5678->5678/tcp` | `0.21%` | `120.5MiB / 1.931GiB` |

Дополнительно:
- Есть `7` stopped/created контейнеров старого `infra-*` стека.

## 4. Сеть
### Открытые порты
| Адрес/порт | Видимость | Процесс |
|------------|-----------|---------|
| `0.0.0.0:80` | public | `nginx` |
| `0.0.0.0:443` | public | `nginx` |
| `0.0.0.0:22` | public | `sshd` |
| `*:4433` | public | `xray` |
| `0.0.0.0:10050` | public | `zabbix_agentd` |
| `10.8.0.1:8080` | VPN/internal | `nginx` (`wg-admin.local`) |
| `127.0.0.1:8010` | local only | `recruitsmart-admin` |
| `127.0.0.1:8011` | local only | `recruitsmart_admin_hh_preview` |
| `127.0.0.1:8000` | local only | `vpn-control` |
| `127.0.0.1:8001` | local only | `wg-admin` |
| `127.0.0.1:5678` | local only | `n8n_core` |
| `127.0.0.1:5432` | local only | PostgreSQL |
| `127.0.0.1:6379` | local only | Redis |

### Firewall
`ufw` активен.

Разрешённые входящие:
- `22/tcp`
- `80,443/tcp`
- `51821/udp`
- `4433/tcp`
- профили `OpenSSH` и `Nginx Full`

Есть forward rule `eth0 -> wg0`.

### Nginx конфигурация
Активные домены и upstream:

| Domain | Поведение |
|--------|-----------|
| `admin.recruitsmart.ru` | reverse proxy на `127.0.0.1:8010` |
| `bot.recruitsmart.ru` | `/webhook/` -> `127.0.0.1:5678`, остальное `403` |
| `n8n.recruitsmart.ru` | reverse proxy на `127.0.0.1:5678` |
| `botsmartservice.recruitsmart.ru` | `/webhook` -> `127.0.0.1:8081`, `/` -> `127.0.0.1:3000` |
| `vpn.recruitsmart.ru` | reverse proxy на `127.0.0.1:8000` |
| `wg-admin.local` | listen `10.8.0.1:8080`, proxy на `127.0.0.1:8001` |

Наблюдения:
- **В `nginx` есть upstream на `127.0.0.1:8081` и `127.0.0.1:3000`, но в `ss -tlnp` таких listeners нет.**
- Для `admin.recruitsmart.ru` nginx проксирует весь трафик в backend; inference: frontend раздаётся FastAPI из `frontend/dist`, а не напрямую nginx.

### SSL сертификаты (срок действия)
| Сертификат | notAfter |
|------------|----------|
| `admin.recruitsmart.ru` | `May 4 20:16:53 2026 GMT` |
| `bot.recruitsmart.ru` | `Jun 9 07:48:06 2026 GMT` |
| `botsmartservice.recruitsmart.ru` | `May 9 07:11:49 2026 GMT` |
| `mysmartservice.duckdns.org` | `May 16 22:15:07 2026 GMT` |
| `n8n.recruitsmart.ru` | `Jun 8 11:30:51 2026 GMT` |
| `vpn.recruitsmart.ru` | `Apr 16 11:35:24 2026 GMT` |

### DNS / hosts
| Запись | Значение |
|--------|----------|
| `127.0.1.1` | `4410671-mt35494` |
| `127.0.0.1` | `localhost` |
| `::1` | `localhost` |

## 5. PostgreSQL
| Параметр | Значение |
|----------|----------|
| Версия | `PostgreSQL 14.22` |
| Основная БД | `recruitsmart_db` |
| Размер БД | `115 MB` |
| Доп. БД | `rs = 12 MB`, `postgres = 8579 kB` |
| Активные соединения | `32 idle / 1 active / 5 background` |
| shared_buffers | `128.00 MiB` |
| effective_cache_size | **`4.00 GiB`** |
| work_mem | `4.00 MiB` |
| maintenance_work_mem | `64.00 MiB` |
| wal_buffers | `4.00 MiB` |
| max_connections | `100` |
| max_worker_processes | `8` |
| max_parallel_workers | `8` |
| effective_io_concurrency | `1` |
| random_page_cost | `4` |
| log_min_duration_statement | `-1` (slow query logging off) |
| autovacuum | `on`, `autovacuum_max_workers = 3` |

### Топ таблиц по размеру
| Таблица | Total | Data | Index | Columns |
|---------|-------|------|-------|---------|
| `public.ai_outputs` | `38 MB` | `9600 kB` | `2664 kB` | `8` |
| `public.hh_negotiations` | `18 MB` | `6024 kB` | `656 kB` | `16` |
| `public.candidate_external_identities` | `13 MB` | `808 kB` | `704 kB` | `15` |
| `public.chat_messages` | `9960 kB` | `8000 kB` | `1904 kB` | `13` |
| `public.hh_webhook_deliveries` | `9088 kB` | `7096 kB` | `1952 kB` | `11` |
| `public.question_answers` | `3944 kB` | `2848 kB` | `1040 kB` | `10` |
| `public.users` | `3312 kB` | `1208 kB` | `2064 kB` | `49` |
| `public.analytics_events` | `1456 kB` | `720 kB` | `696 kB` | `9` |
| `public.slots` | `944 kB` | `80 kB` | `824 kB` | `21` |
| `public.outbox_notifications` | `840 kB` | `360 kB` | `440 kB` | `14` |
| `public.notification_logs` | `552 kB` | `224 kB` | `288 kB` | `12` |
| `public.audit_log` | `552 kB` | `352 kB` | `168 kB` | `9` |
| `public.hh_resume_snapshots` | `280 kB` | `24 kB` | `80 kB` | `7` |
| `public.candidate_journey_events` | `272 kB` | `136 kB` | `104 kB` | `10` |
| `public.external_vacancy_bindings` | `248 kB` | `144 kB` | `64 kB` | `13` |
| `public.message_logs` | `248 kB` | `160 kB` | `48 kB` | `9` |
| `public.hh_connections` | `192 kB` | `80 kB` | `80 kB` | `18` |
| `public.test_results` | `192 kB` | `88 kB` | `80 kB` | `8` |
| `public.manual_slot_audit_logs` | `168 kB` | `64 kB` | `64 kB` | `15` |
| `public.hh_sync_jobs` | `152 kB` | `48 kB` | `64 kB` | `15` |

### Топ таблиц по количеству записей
| Таблица | Rows |
|---------|------|
| `question_answers` | `10787` |
| `ai_outputs` | `10102` |
| `hh_webhook_deliveries` | `7485` |
| `analytics_events` | `6388` |
| `users` | `3400` |
| `hh_negotiations` | `2221` |
| `candidate_external_identities` | `2173` |
| `test_results` | `986` |
| `candidate_journey_events` | `852` |
| `audit_log` | `839` |
| `chat_messages` | `617` |
| `telegram_callback_logs` | `539` |
| `action_tokens` | `322` |
| `message_logs` | `159` |
| `outbox_notifications` | `158` |
| `notification_logs` | `132` |
| `slots` | `65` |
| `ai_request_logs` | `59` |
| `message_templates` | `56` |
| `slot_assignments` | `46` |

### Медленные запросы
- `pg_stat_statements` **не включён / недоступен**.

### Неиспользуемые индексы
| Таблица | Индекс | Размер | Scans |
|---------|--------|--------|-------|
| `public.hh_webhook_deliveries` | `ix_hh_webhook_deliveries_action` | `888 kB` | `0` |
| `public.hh_negotiations` | `ix_hh_negotiations_resume_vacancy` | `280 kB` | `0` |
| `public.users` | `ix_users_hh_resume_id` | `208 kB` | `0` |
| `public.candidate_external_identities` | `ix_candidate_external_identity_resume` | `200 kB` | `0` |
| `public.hh_webhook_deliveries` | `hh_webhook_deliveries_pkey` | `184 kB` | `0` |
| `public.users` | `ix_users_username` | `168 kB` | `0` |
| `public.analytics_events` | `idx_analytics_events_created_at` | `160 kB` | `0` |
| `public.analytics_events` | `analytics_events_pkey` | `160 kB` | `0` |
| `public.users` | `users_telegram_id_key` | `152 kB` | `0` |
| `public.users` | `ix_users_hh_negotiation_id` | `144 kB` | `0` |
| `public.analytics_events` | `idx_analytics_events_user_id` | `120 kB` | `0` |
| `public.candidate_external_identities` | `uq_candidate_external_identity_negotiation` | `112 kB` | `0` |
| `public.analytics_events` | `idx_analytics_events_event_name` | `112 kB` | `0` |
| `public.hh_webhook_deliveries` | `ix_hh_webhook_deliveries_status` | `88 kB` | `0` |
| `public.audit_log` | `ix_audit_log_created_at` | `40 kB` | `0` |

## 6. Redis
| Параметр | Значение |
|----------|----------|
| Версия | `6.0.16` |
| used_memory | `3.68M` |
| used_memory_rss | `5.57M` |
| used_memory_peak | `4.52M` |
| maxmemory | `0B` (лимит не задан) |
| maxmemory-policy | `noeviction` |
| connected_clients | `18` |
| total_connections_received | `450` |
| dbsize | `390` |
| keyspace | `db0:keys=390,expires=385,avg_ttl=189227956` |
| save | `900 1 300 10 60 10000` |

Наблюдение:
- Redis сам по себе лёгкий и память сейчас не давит.

## 7. Приложение
### Как развёрнуто
- RecruitSmart production идёт через `systemd`, не через Docker:
  - `recruitsmart-admin.service`
  - `recruitsmart-bot.service`
- `recruitsmart-admin`:
  - `WorkingDirectory=/opt/recruitsmart_admin`
  - `ExecStart=/opt/recruitsmart_admin/.venv/bin/python -m uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8010 --timeout-keep-alive 30`
  - `EnvironmentFile=/opt/recruitsmart_admin/.env.prod`
- `recruitsmart-bot`:
  - `WorkingDirectory=/opt/recruitsmart_admin`
  - `ExecStart=/opt/recruitsmart_admin/.venv/bin/python -m backend.apps.bot.app`
  - `EnvironmentFile=/opt/recruitsmart_admin/.env.prod`
- `supervisor`: не используется.
- На сервере присутствуют старые `docker-compose.yml` в snapshot-каталогах, но текущий RecruitSmart runtime не docker-based.

### Количество worker'ов
- `recruitsmart-admin`: **1 uvicorn worker** (`ExecStart` без `--workers`).
- `recruitsmart-bot`: 1 процесс.
- Дополнительно на хосте живут:
  - `vpn-control` (`uvicorn` на `127.0.0.1:8000`)
  - `wg-admin` (`gunicorn --workers 2` на `127.0.0.1:8001`)
  - `recruitsmart_admin_hh_preview` (`uvicorn` на `127.0.0.1:8011`)

### Как раздаётся frontend
- `nginx` для `admin.recruitsmart.ru` проксирует весь трафик на `127.0.0.1:8010`.
- В текущем deploy есть `/opt/recruitsmart_admin/frontend/dist`.
- Inference: frontend bundle раздаётся FastAPI из live deploy, nginx используется только как reverse proxy/TLS termination.

### ENV-переменные (только ключи)
Активный runtime `.env.prod`:

```text
ADMIN_PASSWORD
ADMIN_USER
AI_DAILY_BUDGET_USD
AI_ENABLED
AI_MAX_REQUESTS_PER_PRINCIPAL_PER_DAY
AI_MAX_TOKENS
AI_PII_MODE
AI_PROVIDER
AI_TIMEOUT_SECONDS
BOT_BACKEND_URL
BOT_CALLBACK_SECRET
BOT_ENABLED
BOT_FAILFAST
BOT_TOKEN
BOT_USE_WEBHOOK
DATABASE_URL
DATA_DIR
ENVIRONMENT
HH_CLIENT_ID
HH_CLIENT_SECRET
HH_INTEGRATION_ENABLED
HH_REDIRECT_URI
HH_USER_AGENT
HH_WEBHOOK_BASE_URL
MIGRATIONS_DATABASE_URL
NOTIFICATION_BROKER
OPENAI_API_KEY
OPENAI_BASE_URL
OPENAI_MODEL
REDIS_URL
SESSION_COOKIE_SECURE
SESSION_SECRET
```

Дополнительно на сервере лежат архивные/локальные `.env` файлы в snapshot-каталогах и рядом с `n8n`, `smart_bot`.

### Важные layout-наблюдения
- **Текущий live deploy `/opt/recruitsmart_admin` использует `.venv` из snapshot-каталога `recruitsmart_admin_prev_20260315_124124`.**
- По `ls -la /opt/recruitsmart_admin` live deploy tree принадлежит `mikhail:staff`, а runtime-процессы идут от `root`.
- `recruitsmart-admin` и `recruitsmart-bot` стартовали `2026-03-15 13:58:19 MSK`, хотя host uptime `131+` days.

## 8. Логи
### Последние ошибки приложения
- `recruitsmart-admin`:
  - много `INFO` по HH sync и background jobs;
  - повторяющиеся warning'и по long-poll endpoint `GET /api/candidate-chat/threads/updates` с длительностью `~25.0-25.8s`.
- `recruitsmart-bot`:
  - **`aiogram.exceptions.TelegramBadRequest: chat not found`**
  - **`Failed to send waiting_slot notification to recruiter 7`**
  - `notification.worker.poll_stalled`

### Частые API-запросы (последние 1000 строк nginx access.log)
| Count | Endpoint |
|-------|----------|
| `83` | `/api/candidate-chat/threads/updates?...timeout=25` |
| `54` | `/mcp-server/http` |
| `44` | `/api/profile` |
| `29` | `/api/candidates/4017/chat/updates?...limit=120` |
| `25` | `/api/cities` |
| `24` | `/api/candidate-chat/threads?folder=inbox&limit=120` |
| `21` | `/manifest.json` |
| `21` | `/api/candidate-chat/threads` |
| `20` | `/api/slots?limit=500&sort_dir=desc` |
| `19` | `/api/hh-integration/webhooks/YoW5Y2AGc-2BUmAfN0D1lUYnWEm93eu8` |
| `17` | `/api/dashboard/incoming?limit=100` |
| `17` | `/api/candidate-chat/templates` |
| `16` | `/api/recruiters` |
| `16` | `/api/candidates/4017/chat?limit=120` |
| `15` | `/assets/index-BLRg8rYa.css` |

### Nginx error log
- **Повторяющиеся `connect() failed (111)` при обращении nginx к upstream `127.0.0.1:8010`.**
- Ошибки затрагивают:
  - `/api/candidate-chat/threads/updates`
  - `/api/candidates/.../chat/updates`
  - `/apple-touch-icon.png`
  - `/favicon.ico`
- Всплески ошибок видны около `13:07`, `13:46`, `13:58` MSK.

### PostgreSQL logs
- Массовые `could not receive data from client: Connection reset by peer` около тех же временных окон.
- Есть `unexpected EOF on client connection with an open transaction`.
- Отдельно фиксируется ошибка `relation "pg_stat_statements" does not exist`.

### OOM events
- В `dmesg` есть исторические OOM записи:
  - killed process `celery` inside Docker cgroup
  - повторный OOM-kill `celery` в memory cgroup
- В `journalctl -k` актуальных строк по OOM на момент аудита не вернулось.

## 9. Безопасность
### SSH конфигурация
| Параметр | Значение |
|----------|----------|
| PermitRootLogin | `yes` |
| PasswordAuthentication | `no` |

### Пользователи с shell
- `root`
- `admin`
- `mikhail`
- `postgres`

### Последние логины
- Последние `root`-логины шли с `10.8.0.30` и `10.8.0.3`.
- `wtmp` начинается с `2025-03-10`.

### Firewall
- `ufw` включён.
- Разрешены только `22`, `80`, `443`, `4433`, `51821/udp` и related profiles.

### Fail2ban
- Сервис активен.
- Jail list: `nginx-botsearch`, `nginx-http-auth`, `sshd`, `vpn-control`.

### Pending обновления
- В `apt list --upgradable` найдено `39` upgradable packages.
- Наиболее заметные группы:
  - `docker-ce`, `docker-ce-cli`, `docker-compose-plugin`, `containerd.io`
  - `systemd`, `systemd-sysv`, `systemd-timesyncd`, `libsystemd0`, `libudev1`
  - `cloud-init`, `snapd`, `linux-firmware`
  - `python3.12`, `python3.12-dev`, `python3.12-venv`

### Unattended upgrades
- `unattended-upgrades.service` активен.

## 10. Мониторинг и бэкапы
### Есть ли мониторинг
- `zabbix-agent.service` активен.
- Отдельных `prometheus`, `grafana`, `netdata`, `datadog`, `newrelic` не найдено.

### Есть ли бэкапы БД / данных
Найдены cron jobs:

| Cron file | Расписание | Команда |
|-----------|------------|---------|
| `/etc/cron.d/backup_recruitsmart` | `30 3 * * *` | `/usr/local/bin/backup_recruitsmart.sh >> /var/log/backup_recruitsmart.log 2>&1` |
| `/etc/cron.d/backup-n8n` | `15 3 * * *` | `/usr/local/bin/backup-n8n.sh` |
| `/etc/cron.d/n8n-health` | `*/5 * * * *` | `/usr/local/bin/n8n-health.sh` |

Найдены backup-артефакты:
- `/var/backups/recruitsmart` — `61.20 MiB`
- `/var/backups/n8n` — `303.81 MiB`
- `/root/backups/recruitsmart_admin` — `123.07 MiB`
- `/root/backups/n8n` — `500.17 MiB`
- Есть `prod_db.dump`, `.sqlc`, `.backup`, `.tar.gz`, `n8n_database_backup.sqlite`

### Logrotate
- Конфиги присутствуют для:
  - `nginx`
  - `postgresql`
  - `redis`
  - `letsencrypt`
- Это снижает риск бесконтрольного роста логов, но journal всё равно уже занимает `238.0M`.

## 11. Узкие места и рекомендации (предварительные)
- **Память — главный риск.** На хосте всего `1.93 GiB RAM`, свободно `21.87 MiB`, swap уже используется на `534.43 MiB`, исторически были OOM-kill'ы.
- **Хост перегружен по роли.** RecruitSmart делит ресурсы с `n8n`, `vpn-control`, `wg-admin`, `xray`, `zabbix-agent` и Docker-артефактами старого infra-стека.
- **Диск уже на `81%`, а основная масса места уходит не в live RecruitSmart, а в артефакты и соседние сервисы.**
- **На диске много legacy/backup-мусора:** `/var/lib/docker`, `n8n.ZOMBIE`, snapshot-каталоги RecruitSmart в `/opt`, старые Docker images/build cache/volumes.
- **Live deploy собран хрупко:** текущий `/opt/recruitsmart_admin` использует `.venv` как symlink в snapshot-каталог, а сервисы фактически идут от `root`.
- **PostgreSQL настроен не по размеру хоста:** `effective_cache_size = 4 GiB` на машине с `1.93 GiB RAM`, `max_parallel_workers = 8` при `2 vCPU`, `max_connections = 100` при `32 idle` connections.
- **У RecruitSmart недавно были upstream-флаппы:** nginx фиксирует `connect() failed` к `127.0.0.1:8010`, а PostgreSQL в те же минуты пишет `Connection reset by peer`.
- **Bot уже даёт функциональные ошибки:** `TelegramBadRequest: chat not found` и сбой отправки recruiter notification.
- `pg_stat_statements` недоступен, поэтому точных slow query данных нет.
- Для `botsmartservice.recruitsmart.ru` nginx настроен на `127.0.0.1:3000` и `127.0.0.1:8081`, но таких слушателей сейчас нет; конфигурация выглядит stale.

