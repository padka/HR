# Виртуальный отдел разработки

## Роли
- **Frontend Refactorer** — отвечает за миграцию на Vite, структуру стилей, внедрение UI-core (modal/sheet/toast/focus-trap), контроль A11y.
- **Scheduler Architect** — проектирует алгоритмы слотов, квоты по городам, нормализацию часовых поясов и напоминания.
- **QA E2E** — строит Playwright/axe покрытие, smoke и регрессионные сценарии, следит за стабильностью тестов.
- **DevOps CI** — поддерживает GitHub Actions, Docker/compose, кеши Python/Node, публикацию артефактов.

## Процессы
- **Бранч-модель:** `main` (prod), `develop` (staging), `feature/*` (задачи). Merge только через PR с апрувом 2 ролей.
- **Спринты:** недельные. Планирование в понедельник, демо в пятницу (15 мин), ретро в понедельник (15 мин).
- **Стенды:**
  - `dev` — локально (`uvicorn --reload`, `npm run dev`).
  - `staging` — docker-compose + GitHub Actions deploy (опционально).
- **Коммуникация:** канал `#codex-dev`, ежедневный async standup (кто что сделал/план/блокеры).

## Бранч-поток
1. Создать `feature/<task-id>` от `develop`.
2. Выполнить задачу, обновить документацию (`codex/context/decisions.log.md`, `ADR/`).
3. Открыть PR → авто-пайплайн (lint/test/build) → ревью.
4. После апрува squash merge в `develop`, релиз в `main` по релиз-кадру.

## RACI (эпики A–H)
| Эпик | Ответственный (R) | Утверждает (A) | Консультанты (C) | Информируемые (I) |
| --- | --- | --- | --- | --- |
| A. Миграция Vite/UI-core | Frontend Refactorer | DevOps CI | QA E2E | Scheduler Architect |
| B. Квоты и TZ | Scheduler Architect | DevOps CI | Frontend Refactorer, QA E2E | Все |
| C. Playwright и axe | QA E2E | Frontend Refactorer | DevOps CI | Scheduler Architect |
| D. CI/CD pipeline | DevOps CI | Frontend Refactorer | QA E2E | Scheduler Architect |
| E. Напоминания бота | Scheduler Architect | DevOps CI | Frontend Refactorer | QA E2E |
| F. UI accessibility | Frontend Refactorer | QA E2E | DevOps CI | Scheduler Architect |
| G. Документация Codex | Frontend Refactorer | DevOps CI | Все | Все |
| H. Incident response | DevOps CI | Scheduler Architect | QA E2E | Frontend Refactorer |

## Definition of Ready
- Задача описана в `codex/tasks/*.yaml`, есть критерии приёмки.
- ADR/решения обновлены или помечены `TODO`.
- Доступны тестовые данные/фикстуры.

## Definition of Done
- См. `codex/guidelines.md` + специфичные требования ролей:
  - **Frontend:** Vite ассеты, UI-core, axe ok, нет inline-скриптов.
  - **Scheduler:** тесты на TZ/квоты, логи напоминаний, обновлён `risks.md`.
  - **QA:** Playwright сценарии обновлены, отчёты приложены в PR.
  - **DevOps:** CI зелёный, Docker образ построен, env задокументированы.

## Ритм
- **Понедельник:** планирование + ретро.
- **Вт–Чт:** реализация, ежедневные async апдейты.
- **Пятница:** демо + синк по релизам.
- **Инциденты:** выделенная полоса дежурств (ротация еженедельно между DevOps и Scheduler Architect).
