# Tech Strategy — Design System & Tooling

## Guiding Principles
1. **Liquid Glass minimalism** — большие плоскости с мягкой прозрачностью, контрастные акцентные элементы и чёткая типографика.
2. **Single source of truth** — токены (цвет, размер, тени) живут только в `backend/apps/admin_ui/static/css/tokens.css` и импортируются во все сборки.
3. **DX first** — быстрые итерации через единый `main.css`, `esbuild` для JS, предсказуемый `make ui`.
4. **A11y & performance budgets** — контраст ≥ WCAG AA, CSS bundle ≤70 KB gzip, TTI ключевых страниц ≤2.0 с.

## Token Architecture
- **Foundation tokens** (`--color-base-*`, `--space-*`, `--radius-*`, `--shadow-*`) описывают палитру Liquid Glass: `#93FEBF`, `#F96E65`, `#EF9A68`, `#FFD144`, нейтральные `#0F172A`, `#111827`, `#F8FAFC`.
- **Alias tokens** (`--color-surface-glass`, `--color-surface-contrast`, `--color-text-muted`, `--gradient-hero`) формируются из базовых и подбираются под сценарии (поверхность, фон, бейджи, акценты).
- **Component tokens** (`--badge-success-bg`, `--badge-neutral-border`, `--pill-hover-shadow`) живут в том же `tokens.css`, но группируются по компонентам.
- Документация токенов поддерживается в `docs/TECH_STRATEGY.md` + таблица в Storybook/Playwright-превью.
- Все inline-цвета, радиусы, тени удаляются в пользу `var(--token-name)`.

## Liquid Glass Patterns
- `.glass` — фон `rgba(255,255,255,0.14)`, blur `backdrop-filter: blur(24px)`, тонкая рамка `1px solid rgba(255,255,255,0.25)`.
- `.glass-elevated` — дополнительная тень `var(--shadow-lg)` и внутренний градиент `var(--gradient-hero)`.
- `.badge-*` — капсулы статуса с плотными цветами: success → `#93FEBF`, warn → `#FFD144`, danger → `#F96E65`, info → `#EF9A68`.
- `.pill` — интерактивные фильтры с прозрачностью 0.16, hover усиливает до 0.28, активное состояние закреплено цветом акцента.
- `.surface-muted` — вторичные панели, используют `--color-surface-muted` и лёгкий blur.

## Component Library Plan
- `components/` каталог для частичных шаблонов (`slot-kpi.html`, `candidate-row.html`, `recruiter-card.html`).
- Каждая сущность использует набор утилит: `glass`, `pill`, `badge`, `stack` (flex-gap), `toolbar`, `grid-fluid`.
- Никаких custom inline-стилей — всё через токены/Tailwind (`@apply` разрешён только для утилит, не для бизнес-логики).
- В PR добавляется скриншот компонента (desktop + tablet) в `previews/`.

## Tailwind & PostCSS Pipeline
- `tailwind.config.js` обновляется: `content` включает `templates/**/*.html`, `static/js/**/*.ts`, `components/**/*.html`.
- `main.css` импортирует `tokens.css`, `@tailwind base`, `@tailwind components`, `@tailwind utilities`, затем кастомные утилиты.
- Команда `npm run build:css` → `tailwindcss --minify` → `postcss` (autoprefixer). Добавляем `NODE_ENV` switch для `--watch`.
- Перформанс: включить `@tailwindcss/forms`/`typography`, purge активировать для всех шаблонов.
- CSS билд публикуется в `backend/apps/admin_ui/static/build/main.css`; sourcemap включён в dev (`--sourcemap`).

## JavaScript & Asset Pipeline
- Храним исходники в `backend/apps/admin_ui/static/js/src/` (ESM + TypeScript по желанию).
- `esbuild` собирает в `static/js/dist/` с code splitting по страницам: `dashboard-calendar`, `city-selector`, `candidates-inline`.
- Общий `vendor` чанк содержит повторно используемые утилиты (fetch wrappers, debounce).
- Build-команда: `npm run build:js` (esbuild config) + `npm run lint:js` (biome/eslint) в CI.
- Legacy файлы `*- copy.js` удаляются после миграции; fallback loader поддерживает feature flag `data-module` на шаблонах.

## Version Policy
- **Python:** 3.12.x (CPython). Обновить dev_doctor, Makefile, docker-compose. План перехода на 3.13 — после поддержки aiogram и Playwright (monitor Q1 2026).
- **Node.js:** 20 LTS. Зашить в `.nvmrc` и CI матрицу.
- **npm/pip:** lockfiles обязательны (`package-lock.json`, `requirements.lock`). Ежеквартальный аудит `npm audit`, `pip-audit`.

## DX Guardrails
- `make setup` выполняет `pip install -e .[dev]`, `npm ci`, `playwright install`.
- Pre-commit: Ruff, Black, isort, mypy, eslint/biome, stylelint (Tailwind plugin).
- CI матрица: Linux + macOS smoke, Python 3.12, Node 20. Playwright headless в GitHub Actions с `--project` для 3 viewport.
- Документация по запуску (`docs/DEV_GUIDE.md`) обновляется при каждом DX-изменении.

