# Карта проекта

```
backend/
  apps/
    admin_ui/
      app.py              # фабрика FastAPI, монтирование статики и роутов
      config.py           # настройки шаблонов и глобальных фильтров
      routers/            # обработчики страниц и API (slots, candidates, recruiters...)
      services/           # бизнес-логика, работа с БД и ботом
      static/
        css/              # tokens.css, ui.css, исходники Tailwind
        js/modules/       # ES-модули страниц (candidates-list, slots, answers-modal)
        build/            # main.css (артефакт Tailwind, планируется манифест Vite)
      templates/
        base.html         # основной layout, подключение CSS и скриптов
        page_primitives.html # макросы: таблицы, фильтры, KPI, модалки
        partials/         # переиспользуемые блоки форм и тулбаров
    bot/                  # Telegram бот и интеграция (используется косвенно)
  core/                   # настройки, bootstrap БД, общая инфраструктура
  domain/                 # ORM-модели и схемы
  migrations/             # миграции (не изменяем в Codex-PR)

admin_server/             # вспомогательный сервис (if any, legacy)
app_demo.py               # демо-запуск
bot.py                    # CLI для Telegram-бота
codex/                    # текущий Codex (манифест, агенты, задачи)
docs/                     # документация, скриншоты, аудиты
node_modules/             # зависимости Node (исключить из индекса)
package.json              # Tailwind build script
pyproject.toml            # Python зависимости, настройка проекта
requirements*.txt         # списки зависимостей
scripts/, tools/          # CLI-утилиты и вспомогательные скрипты
```
