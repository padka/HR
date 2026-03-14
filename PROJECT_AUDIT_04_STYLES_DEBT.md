# PROJECT AUDIT 04 — Styles and Technical Debt
## Дата: 2026-03-14

## 8. Стилевая система

- Основная frontend-тема живёт в `frontend/app/src/theme/*.css` и route/component-level CSS файлах.
- Tailwind config отсутствует; визуальная система опирается на handcrafted CSS и Framer Motion.
- Motion-ориентированные файлы: `frontend/app/package-lock.json`, `frontend/app/package.json`, `frontend/app/src/app/components/CandidatePipeline/CandidatePipeline.tsx`, `frontend/app/src/app/components/CandidatePipeline/PipelineConnector.tsx`, `frontend/app/src/app/components/CandidatePipeline/PipelineStage.tsx`, `frontend/app/src/app/components/CandidatePipeline/StageDetailPanel.tsx`, `frontend/app/src/app/components/CandidatePipeline/StageIndicator.tsx`, `frontend/app/src/app/components/CandidatePipeline/pipeline.variants.ts`, `frontend/app/src/app/components/InterviewScript/InterviewScript.tsx`, `frontend/app/src/app/components/InterviewScript/RatingScale.tsx`, `frontend/app/src/app/components/InterviewScript/ScriptScorecard.tsx`, `frontend/app/src/app/components/InterviewScript/script.variants.ts`

### CSS-переменные

- `--interactive` — встречается в 6 файлах
- `--primary` — встречается в 4 файлах
- `--danger` — встречается в 4 файлах
- `--success` — встречается в 4 файлах
- `--bg-elevated` — встречается в 3 файлах
- `--border-strong` — встречается в 3 файлах
- `--border-subtle` — встречается в 3 файлах
- `--radius-full` — встречается в 3 файлах
- `--radius-lg` — встречается в 3 файлах
- `--radius-sm` — встречается в 3 файлах
- `--radius-xl` — встречается в 3 файлах
- `--text-primary` — встречается в 3 файлах
- `--text-secondary` — встречается в 3 файлах
- `--text-tertiary` — встречается в 3 файлах
- `--glass-highlight` — встречается в 3 файлах
- `--glass-border` — встречается в 3 файлах
- `--warning` — встречается в 3 файлах
- `--bg-canvas` — встречается в 2 файлах
- `--bg-overlay` — встречается в 2 файлах
- `--bg-surface` — встречается в 2 файлах
- `--border-default` — встречается в 2 файлах
- `--ease-in` — встречается в 2 файлах
- `--ease-in-out` — встречается в 2 файлах
- `--ease-out` — встречается в 2 файлах
- `--font-sans` — встречается в 2 файлах
- `--radius-2xl` — встречается в 2 файлах
- `--radius-md` — встречается в 2 файлах
- `--shadow-glass-lg` — встречается в 2 файлах
- `--shadow-glow-success` — встречается в 2 файлах
- `--shadow-lg` — встречается в 2 файлах
- `--shadow-md` — встречается в 2 файлах
- `--shadow-sm` — встречается в 2 файлах
- `--shadow-xl` — встречается в 2 файлах
- `--text-2xl` — встречается в 2 файлах
- `--text-3xl` — встречается в 2 файлах
- `--text-base` — встречается в 2 файлах
- `--text-inverse` — встречается в 2 файлах
- `--text-lg` — встречается в 2 файлах
- `--text-sm` — встречается в 2 файлах
- `--text-xl` — встречается в 2 файлах
- `--text-xs` — встречается в 2 файлах
- `--transition-transform` — встречается в 2 файлах
- `--z-base` — встречается в 2 файлах
- `--z-sticky` — встречается в 2 файлах
- `--glass-noise-opacity` — встречается в 2 файлах
- `--ghost` — встречается в 2 файлах
- `--glass-bg-elevated` — встречается в 2 файлах
- `--accent` — встречается в 2 файлах
- `--accent-soft` — встречается в 2 файлах
- `--bg` — встречается в 2 файлах
- `--danger-soft` — встречается в 2 файлах
- `--elevation-1` — встречается в 2 файлах
- `--elevation-2` — встречается в 2 файлах
- `--fg` — встречается в 2 файлах
- `--focus-ring` — встречается в 2 файлах
- `--glass-bg` — встречается в 2 файлах
- `--glass-shadow` — встречается в 2 файлах
- `--muted` — встречается в 2 файлах
- `--radius-xs` — встречается в 2 файлах
- `--success-soft` — встречается в 2 файлах
- `--warning-soft` — встречается в 2 файлах
- `--header-height` — встречается в 2 файлах
- `--bg-danger` — встречается в 1 файлах
- `--bg-info` — встречается в 1 файлах
- `--bg-success` — встречается в 1 файлах
- `--bg-warning` — встречается в 1 файлах
- `--breakpoint-2xl` — встречается в 1 файлах
- `--breakpoint-lg` — встречается в 1 файлах
- `--breakpoint-md` — встречается в 1 файлах
- `--breakpoint-sm` — встречается в 1 файлах
- `--breakpoint-xl` — встречается в 1 файлах
- `--color-danger-100` — встречается в 1 файлах
- `--color-danger-50` — встречается в 1 файлах
- `--color-danger-500` — встречается в 1 файлах
- `--color-danger-700` — встречается в 1 файлах
- `--color-danger-900` — встречается в 1 файлах
- `--color-info-100` — встречается в 1 файлах
- `--color-info-50` — встречается в 1 файлах
- `--color-info-500` — встречается в 1 файлах
- `--color-info-700` — встречается в 1 файлах
- `--color-info-900` — встречается в 1 файлах
- `--color-neutral-0` — встречается в 1 файлах
- `--color-neutral-100` — встречается в 1 файлах
- `--color-neutral-200` — встречается в 1 файлах
- `--color-neutral-300` — встречается в 1 файлах
- `--color-neutral-400` — встречается в 1 файлах
- `--color-neutral-50` — встречается в 1 файлах
- `--color-neutral-500` — встречается в 1 файлах
- `--color-neutral-600` — встречается в 1 файлах
- `--color-neutral-700` — встречается в 1 файлах
- `--color-neutral-800` — встречается в 1 файлах
- `--color-neutral-900` — встречается в 1 файлах
- `--color-primary-100` — встречается в 1 файлах
- `--color-primary-200` — встречается в 1 файлах
- `--color-primary-300` — встречается в 1 файлах
- `--color-primary-400` — встречается в 1 файлах
- `--color-primary-50` — встречается в 1 файлах
- `--color-primary-500` — встречается в 1 файлах
- `--color-primary-600` — встречается в 1 файлах
- `--color-primary-700` — встречается в 1 файлах
- `--color-primary-800` — встречается в 1 файлах
- `--color-primary-900` — встречается в 1 файлах
- `--color-secondary-500` — встречается в 1 файлах
- `--color-secondary-600` — встречается в 1 файлах
- `--color-success-100` — встречается в 1 файлах
- `--color-success-50` — встречается в 1 файлах
- `--color-success-500` — встречается в 1 файлах
- `--color-success-700` — встречается в 1 файлах
- `--color-success-900` — встречается в 1 файлах
- `--color-warning-100` — встречается в 1 файлах
- `--color-warning-50` — встречается в 1 файлах
- `--color-warning-500` — встречается в 1 файлах
- `--color-warning-700` — встречается в 1 файлах
- `--color-warning-900` — встречается в 1 файлах
- `--duration-base` — встречается в 1 файлах
- `--duration-fast` — встречается в 1 файлах
- `--duration-instant` — встречается в 1 файлах
- `--duration-slow` — встречается в 1 файлах
- `--duration-slower` — встречается в 1 файлах
- `--ease-bounce` — встречается в 1 файлах

### CSS-файлы

### `backend/apps/admin_ui/static/css/design-system.css`
- Строк кода: ~729
- Назначение: CSS-стили для `design-system`.
- Ключевые секции: *; ============================================================================; PRIMARY BRAND COLORS — мягкий синий акцент; SECONDARY ACCENT; NEUTRALS — светлая система; SEMANTIC COLORS; ============================================================================; Backgrounds
- CSS-переменные: `--bg-canvas`, `--bg-danger`, `--bg-elevated`, `--bg-info`, `--bg-overlay`, `--bg-success`, `--bg-surface`, `--bg-warning`, `--border-default`, `--border-strong`, `--border-subtle`, `--breakpoint-2xl`, `--breakpoint-lg`, `--breakpoint-md`, `--breakpoint-sm`, `--breakpoint-xl`, `--color-danger-100`, `--color-danger-50`, `--color-danger-500`, `--color-danger-700`
- Media queries: L643: @media (prefers-reduced-motion: reduce) {; L661: @media (pointer: coarse) {; L675: @media print {
- Тяжёлые / проблемные места: `!important`: 11

### `backend/apps/admin_ui/static/css/forms.css`
- Строк кода: ~693
- Назначение: CSS-стили для `forms`.
- Ключевые секции: Admin UI form surfaces and inputs; Required field indicator; Optional: subtle border styling for required inputs; Error states for form fields; Success state (optional enhancement)
- CSS-переменные: `--primary`, `--shell-padding`, `--shell-radius`
- Media queries: L272: @media (max-width: 720px) {; L662: @media (min-width: 880px) {; L673: @media (max-width: 960px) {; L680: @media (max-width: 640px) {
- Тяжёлые / проблемные места: Явных CSS-хаков статический сканер не отметил

### `backend/apps/admin_ui/static/css/glass-surfaces.css`
- Строк кода: ~188
- Назначение: CSS-стили для `glass-surfaces`.
- Ключевые секции: *; Base; Applied surfaces
- CSS-переменные: `--glass-blur`, `--glass-highlight`, `--glass-inner-shadow`, `--glass-noise-img`, `--glass-noise-opacity`, `--glass-sat`, `--glass-shadow-strong`, `--glass-tint`, `--interactive`
- Media queries: L148: @media (prefers-reduced-motion: reduce) {; L159: @media (max-width: 1024px) {; L167: @media (max-width: 768px) {; L174: @media (max-width: 480px) {
- Тяжёлые / проблемные места: `!important`: 3

### `backend/apps/admin_ui/static/css/liquid-glass-integration.css`
- Строк кода: ~2552
- Назначение: CSS-стили для `liquid-glass-integration`.
- Ключевые секции: *; ============================================; 1. Slot Summary Cards - Enhanced; Tone-specific styling; 2. Page Header Enhancement; 3. Enhanced Alert with Liquid Glass; 4. City/Slot Table Integration; Enhanced table row hover
- CSS-переменные: `--danger`, `--secondary`, `--shine-active`
- Media queries: L233: @media (max-width: 640px) {; L650: @media (max-width: 1280px) {; L656: @media (max-width: 1024px) {; L962: @media (max-width: 720px) {; L1299: @media (max-width: 720px) {; L1409: @media (max-width: 960px) {; L1425: @media (max-width: 640px) {; L1450: @media print {; L1484: @media (prefers-contrast: high) {; L1922: @media (max-width: 960px) {
- Тяжёлые / проблемные места: `!important`: 15

### `backend/apps/admin_ui/static/css/liquid-glass.css`
- Строк кода: ~613
- Назначение: CSS-стили для `liquid-glass`.
- Ключевые секции: ============================================; 1. Liquid Glass Variables; Glass blur intensities; Glass backgrounds; Glass borders; Gradients for backgrounds; Gradients for interactive elements; Shadows with multiple layers
- CSS-переменные: `--ease-glass`, `--ease-glass-in`, `--ease-glass-out`, `--ghost`, `--glass-bg-active`, `--glass-bg-elevated`, `--glass-bg-hover`, `--glass-bg-primary`, `--glass-bg-secondary`, `--glass-blur-lg`, `--glass-blur-md`, `--glass-blur-sm`, `--glass-blur-xl`, `--glass-border`, `--glass-border-bright`, `--glass-border-subtle`, `--gradient-blue`, `--gradient-glass-bg`, `--gradient-glass-highlight`, `--gradient-primary`
- Media queries: L544: @media (max-width: 768px) {; L564: @media (prefers-reduced-motion: reduce) {; L596: @media print {
- Тяжёлые / проблемные места: `!important`: 11

### `backend/apps/admin_ui/static/css/theme-tokens.css`
- Строк кода: ~250
- Назначение: CSS-стили для `theme-tokens`.
- Ключевые секции: *; Base palette (light); Motion tokens; Neutral surfaces; Core brand; Borders & outlines; Elevation (soft, non-harsh); Semantic
- CSS-переменные: `--accent`, `--accent-2`, `--accent-contrast`, `--accent-fg`, `--accent-hover`, `--accent-pressed`, `--accent-soft`, `--bad`, `--bg`, `--bg-canvas`, `--bg-elevated`, `--bg-overlay`, `--bg-surface`, `--border`, `--border-1`, `--border-2`, `--border-default`, `--border-strong`, `--border-subtle`, `--border-w`
- Тяжёлые / проблемные места: Явных CSS-хаков статический сканер не отметил

### `frontend/app/src/app/components/Calendar/calendar.css`
- Строк кода: ~357
- Назначение: UI/feature-компонент `calendar`.
- Ключевые секции: FullCalendar Glassmorphism Theme for RecruitSmart; CSS Custom Properties for theming; Use when the calendar is rendered inside an existing glass panel (e.g. Dashboard).; Loading overlay; Error state; Toolbar styling; Table header; Time grid
- CSS-переменные: `--fc-border-color`, `--fc-button-active-bg-color`, `--fc-button-active-border-color`, `--fc-button-bg-color`, `--fc-button-border-color`, `--fc-button-hover-bg-color`, `--fc-button-hover-border-color`, `--fc-button-text-color`, `--fc-event-border-color`, `--fc-highlight-color`, `--fc-list-event-hover-bg-color`, `--fc-neutral-bg-color`, `--fc-non-business-color`, `--fc-now-indicator-color`, `--fc-page-bg-color`, `--fc-today-bg-color`
- Media queries: L313: @media (max-width: 768px) {
- Тяжёлые / проблемные места: `!important`: 25

### `frontend/app/src/app/components/CandidatePipeline/candidate-pipeline.css`
- Строк кода: ~536
- Назначение: UI/feature-компонент `candidate-pipeline`.
- CSS-переменные: `--completed`, `--current`, `--pipeline-bg`, `--pipeline-card`, `--pipeline-card-border`, `--pipeline-card-border-hover`, `--pipeline-card-hover`, `--pipeline-completed`, `--pipeline-completed-muted`, `--pipeline-current-glow`, `--pipeline-rail-bg`, `--pipeline-text-muted`, `--pipeline-text-primary`, `--pipeline-text-secondary`, `--pipeline-upcoming`
- Media queries: L494: @media (max-width: 1023px) {; L505: @media (max-width: 767px) {; L527: @media (prefers-reduced-motion: reduce) {
- Тяжёлые / проблемные места: `!important`: 3

### `frontend/app/src/app/components/CandidateTimeline/candidate-timeline.css`
- Строк кода: ~116
- Назначение: UI/feature-компонент `candidate-timeline`.
- Тяжёлые / проблемные места: Явных CSS-хаков статический сканер не отметил

### `frontend/app/src/app/components/CohortComparison/cohort-comparison.css`
- Строк кода: ~107
- Назначение: UI/feature-компонент `cohort-comparison`.
- Media queries: L97: @media (max-width: 767px) {
- Тяжёлые / проблемные места: Явных CSS-хаков статический сканер не отметил

### `frontend/app/src/app/components/InterviewScript/interview-script.css`
- Строк кода: ~465
- Назначение: UI/feature-компонент `interview-script`.
- Media queries: L412: @media (max-width: 1279px) {; L427: @media (max-width: 767px) {
- Тяжёлые / проблемные места: `!important`: 1

### `frontend/app/src/theme/components.css`
- Строк кода: ~777
- Назначение: CSS-стили для `components`.
- CSS-переменные: `--ui-field-error-color`, `--ui-field-support-color`, `--ui-field-support-gap`, `--ui-form-actions-gap`, `--ui-form-divider-color`, `--ui-form-section-gap`
- Media queries: L366: @media (max-width: 768px) {; L393: @media (max-width: 480px) {
- Тяжёлые / проблемные места: Явных CSS-хаков статический сканер не отметил

### `frontend/app/src/theme/global.css`
- Строк кода: ~10104
- Назначение: CSS-стили для `global`.
- Ключевые секции: Base tokens are centralized in tokens.css.; === Pulse Animation (The Talent Pulse) ===; Liquid Glass Physics; Border & Volume; Bouncy spring; Typography; === Layered 3D Glassmorphism Background ===; Layer 1: Far back, large, slow, very blurred
- CSS-переменные: `--button`, `--danger`, `--error`, `--ghost`, `--header-height`, `--interactive`, `--pop-origin-x`, `--pop-origin-y`, `--pop-rot`, `--pop-rot-end`, `--pop-shift-x`, `--pop-shift-y`, `--primary`, `--success`, `--warning`
- Media queries: L124: @media (max-width: 768px) {; L130: @media (max-width: 480px) {; L295: @media (max-width: 760px) {; L635: @media (max-width: 768px) {; L659: @media (max-width: 900px) {; L766: @media (max-width: 1100px) {; L787: @media (max-width: 720px) {; L840: @media (max-width: 768px) {; L846: @media (max-width: 480px) {; L864: @media (max-width: 768px) {
- Тяжёлые / проблемные места: `!important`: 6

### `frontend/app/src/theme/material.css`
- Строк кода: ~125
- Назначение: CSS-стили для `material`.
- Тяжёлые / проблемные места: Явных CSS-хаков статический сканер не отметил

### `frontend/app/src/theme/mobile.css`
- Строк кода: ~1122
- Назначение: CSS-стили для `mobile`.
- Ключевые секции: Mobile layer: loaded last to override desktop defaults
- CSS-переменные: `--interactive`
- Media queries: L3: @media (max-width: 768px) {; L982: @media (max-width: 768px) and (hover: none) {; L993: @media (max-width: 768px) {; L1006: @media (max-width: 1024px) {
- Тяжёлые / проблемные места: `!important`: 1

### `frontend/app/src/theme/motion.css`
- Строк кода: ~166
- Назначение: CSS-стили для `motion`.
- CSS-переменные: `--interactive`
- Media queries: L115: @media (max-width: 768px) {; L157: @media (prefers-reduced-motion: reduce) {
- Тяжёлые / проблемные места: `!important`: 8

### `frontend/app/src/theme/pages.css`
- Строк кода: ~848
- Назначение: CSS-стили для `pages`.
- CSS-переменные: `--interactive`
- Тяжёлые / проблемные места: Явных CSS-хаков статический сканер не отметил

### `frontend/app/src/theme/tokens.css`
- Строк кода: ~313
- Назначение: CSS-стили для `tokens`.
- CSS-переменные: `--accent`, `--accent-light`, `--accent-medium`, `--accent-soft`, `--bg`, `--bg-elevated`, `--blur`, `--blur-lg`, `--blur-sm`, `--blur-xl`, `--border-focus`, `--border-strong`, `--border-subtle`, `--bp-desktop`, `--bp-desktop-lg`, `--bp-mobile`, `--bp-mobile-lg`, `--bp-tablet`, `--danger`, `--danger-soft`
- Media queries: L292: @media (max-width: 768px) {
- Тяжёлые / проблемные места: Явных CSS-хаков статический сканер не отметил

### `splash.css`
- Строк кода: ~156
- Назначение: CSS-стили для `splash`.
- Ключевые секции: Splash Screen Styles - The Talent Pulse; Sequence Classes
- CSS-переменные: `--logo-accent`, `--logo-accent-2`, `--marker-color`, `--radar-border`, `--radar-color`, `--splash-bg`, `--text-color`
- Тяжёлые / проблемные места: Явных CSS-хаков статический сканер не отметил

## 9. Технический долг

### TODO / FIXME / HACK

| Файл | Строка | Комментарий |
|---|---:|---|
| `AGENTS.md` | 91 | - If you create a temporary prompt/TODO/spec/checklist markdown file, delete it before closing the task unless the user explicitly asked for a durable artifact. |
| `README.md` | 127 | - Temporary markdown files for prompts/TODO/specs must be deleted after the task is closed. |
| `REPOSITORY_WORKFLOW_GUIDE.md` | 43 | - If a prompt/TODO/spec/checklist file is no longer active, delete it. |
| `backend/apps/max_bot/app.py` | 291 | # TODO: Route callback actions (confirm_assignment, reschedule, etc.) |
| `codex/context/dev_department.md` | 37 | - ADR/решения обновлены или помечены `TODO`. |
| `docs/archive/ND21.md` | 37 | - Telegram sandbox и e2e логирование (ND21_TZ п.1.5/2.3) всё ещё TODO; ручных инструкций для QA нет. |
| `docs/archive/features/dashboard/LIQUID_GLASS_IMPLEMENTATION.md` | 471 | ## 📝 TODO (Optional Enhancements) |
| `docs/frontend-migration-log.md` | 50 | ## TODO next |
| `docs/migration-map.md` | 8 | - **TODO**: No React page or only stub. |
| `engine.md` | 47 | - TODO lists |

### Крупные файлы (>500 строк)

| Файл | Строк | Категория |
|---|---:|---|
| `frontend/app/src/theme/global.css` | 10104 | styles |
| `frontend/app/package-lock.json` | 8553 | config |
| `backend/apps/bot/services.py` | 7627 | misc |
| `frontend/app/openapi.json` | 5915 | config |
| `frontend/app/src/api/schema.ts` | 4828 | frontend-api |
| `backend/apps/admin_ui/services/candidates.py` | 3984 | backend-services |
| `backend/apps/admin_ui/routers/api.py` | 3638 | backend-routers |
| `frontend/app/src/app/routes/app/candidate-detail.tsx` | 3458 | frontend-routes |
| `backend/apps/admin_ui/static/css/liquid-glass-integration.css` | 2552 | styles |
| `backend/core/ai/service.py` | 2478 | backend-core |
| `backend/apps/admin_ui/services/dashboard.py` | 2292 | backend-services |
| `backend/apps/admin_ui/services/slots.py` | 2041 | backend-services |
| `docs/archive/qa/QA_COMPREHENSIVE_REPORT.md` | 2006 | docs |
| `docs/archive/REDESIGN_STRATEGY.md` | 1764 | docs |
| `docs/archive/features/dashboard/DASHBOARD_CHANGELOG.md` | 1706 | docs |
| `frontend/app/src/app/routes/app/messenger.tsx` | 1612 | frontend-routes |
| `backend/domain/repositories.py` | 1583 | backend-domain |
| `frontend/app/src/app/routes/app/slots.tsx` | 1559 | frontend-routes |
| `backend/apps/admin_ui/routers/candidates.py` | 1422 | backend-routers |
| `tests/test_admin_candidate_schedule_slot.py` | 1416 | tests |
| `frontend/app/src/app/routes/__root.tsx` | 1368 | frontend-routes |
| `backend/domain/models.py` | 1250 | backend-domain |
| `backend/apps/bot/reminders.py` | 1206 | misc |
| `frontend/app/src/app/routes/app/city-edit.tsx` | 1158 | frontend-routes |
| `frontend/app/src/app/routes/app/test-builder-graph.tsx` | 1148 | frontend-routes |
| `frontend/app/src/app/routes/app/incoming.tsx` | 1135 | frontend-routes |
| `tests/test_notification_retry.py` | 1134 | tests |
| `backend/apps/admin_ui/services/staff_chat.py` | 1129 | backend-services |
| `frontend/app/src/theme/mobile.css` | 1122 | styles |
| `backend/domain/slot_assignment_service.py` | 1119 | backend-domain |
| `backend/core/ai/llm_script_generator.py` | 1107 | backend-core |
| `frontend/app/src/app/routes/app/dashboard.tsx` | 1063 | frontend-routes |
| `tests/test_admin_slots_api.py` | 1061 | tests |
| `tests/test_admin_candidates_service.py` | 1013 | tests |
| `frontend/app/src/app/routes/app/calendar.tsx` | 963 | frontend-routes |
| `tests/test_bot_confirmation_flows.py` | 946 | tests |
| `backend/apps/admin_ui/app.py` | 914 | misc |
| `backend/apps/admin_ui/services/message_templates.py` | 878 | backend-services |
| `docs/archive/DESIGN_SYSTEM_CANDIDATES_PAGE.md` | 873 | docs |
| `frontend/app/src/theme/pages.css` | 848 | styles |
| `frontend/app/src/app/routes/app/candidates.tsx` | 832 | frontend-routes |
| `tests/test_ai_copilot.py` | 828 | tests |
| `frontend/app/src/app/routes/app/ui-cosmetics.test.tsx` | 826 | frontend-routes |
| `backend/core/settings.py` | 824 | backend-core |
| `frontend/app/src/app/routes/app/system.tsx` | 798 | frontend-routes |
| `backend/core/ai/context.py` | 790 | backend-core |
| `tests/test_reminder_service.py` | 789 | tests |
| `frontend/app/src/theme/components.css` | 777 | styles |
| `backend/apps/admin_ui/services/candidate_chat_threads.py` | 766 | backend-services |
| `backend/apps/admin_ui/routers/content_api.py` | 764 | backend-routers |
| `tests/test_admin_candidate_chat_actions.py` | 764 | tests |
| `backend/apps/admin_ui/routers/slots.py` | 754 | backend-routers |
| `tests/services/test_dashboard_and_slots.py` | 742 | tests |
| `backend/apps/admin_ui/services/kpis.py` | 739 | backend-services |
| `backend/apps/admin_api/webapp/routers.py` | 729 | backend-routers |
| `backend/apps/admin_ui/static/css/design-system.css` | 729 | styles |
| `backend/apps/admin_ui/static/css/forms.css` | 693 | styles |
| `scripts/formal_gate_sprint12.py` | 691 | scripts |
| `frontend/app/src/api/services/candidates.ts` | 690 | frontend-api |
| `tests/test_bot_test1_validation.py` | 677 | tests |
| `frontend/app/src/app/routes/app/profile.tsx` | 676 | frontend-routes |
| `backend/apps/bot/slot_assignment_flow.py` | 670 | misc |
| `tests/test_candidate_chat_threads_api.py` | 668 | tests |
| `backend/domain/candidates/services.py` | 656 | backend-domain |
| `docs/archive/LIQUID_GLASS_GUIDE.md` | 656 | docs |
| `frontend/app/src/app/routes/app/slots-create.tsx` | 633 | frontend-routes |
| `docs/archive/FINAL_SUMMARY.md` | 626 | docs |
| `frontend/app/src/app/routes/app/message-templates.tsx` | 625 | frontend-routes |
| `docs/archive/features/dashboard/INTERFACE_IMPROVEMENTS_PHASE_2.md` | 616 | docs |
| `backend/apps/admin_ui/static/css/liquid-glass.css` | 613 | styles |
| `backend/domain/hh_integration/importer.py` | 612 | backend-domain |
| `docs/candidate_channels/CANDIDATE_EXPERIENCE_TARGET_ARCHITECTURE.md` | 603 | docs |
| `docs/archive/optimization/PHASE2_PERFORMANCE.md` | 601 | docs |
| `backend/core/ai/candidate_scorecard.py` | 600 | backend-core |
| `backend/apps/admin_ui/services/detailization.py` | 597 | backend-services |
| `frontend/app/src/app/routes/app/detailization.tsx` | 588 | frontend-routes |
| `tests/test_intro_day_recruiter_scope.py` | 581 | tests |
| `scripts/loadtest_profiles/analyze_step.py` | 577 | scripts |
| `backend/apps/admin_ui/services/test_builder_preview.py` | 569 | backend-services |
| `frontend/app/src/app/routes/app/recruiter-edit.tsx` | 568 | frontend-routes |
| `backend/apps/bot/recruiter_service.py` | 565 | misc |
| `backend/apps/admin_ui/routers/hh_integration.py` | 564 | backend-routers |
| `docs/archive/BUGFIX_TELEGRAM_CHAT_LINK.md` | 562 | docs |
| `backend/apps/admin_ui/services/bot_service.py` | 553 | backend-services |
| `backend/apps/admin_ui/state.py` | 545 | misc |
| `backend/apps/admin_ui/services/cities.py` | 544 | backend-services |
| `docs/archive/features/dashboard/ANIMATED_COUNTER_IMPLEMENTATION.md` | 544 | docs |
| `frontend/app/src/app/components/CandidatePipeline/candidate-pipeline.css` | 536 | frontend-components |
| `frontend/app/src/app/components/QuestionPayloadEditor.tsx` | 535 | frontend-components |
| `backend/apps/admin_ui/routers/profile_api.py` | 531 | backend-routers |
| `frontend/app/src/app/routes/app/template-list.tsx` | 531 | frontend-routes |
| `docs/archive/features/dashboard/LIQUID_GLASS_IMPLEMENTATION.md` | 530 | docs |
| `backend/apps/admin_ui/security.py` | 527 | misc |
| `backend/apps/admin_ui/services/slots/crud.py` | 525 | backend-services |
| `backend/apps/admin_ui/services/recruiters.py` | 524 | backend-services |
| `backend/apps/admin_ui/services/questions.py` | 523 | backend-services |
| `backend/apps/admin_ui/services/slots/bot.py` | 522 | backend-services |
| `frontend/app/src/app/routes/app/candidate-new.tsx` | 520 | frontend-routes |
| `docs/archive/features/dashboard/DASHBOARD_BACKEND_INTEGRATION.md` | 517 | docs |
| `docs/archive/qa/TEST_REPORT.md` | 511 | docs |
| `tests/test_hh_integration_import.py` | 505 | tests |
| `docs/archive/qa/REAL_BUG_REPORT.md` | 504 | docs |
| `backend/apps/admin_ui/routers/auth.py` | 502 | backend-routers |
| `docs/archive/BUGFIX_INTEGRITYERROR_IDEMPOTENCY.md` | 501 | docs |

### Использование `any` в TypeScript

| Файл | Кол-во `any` |
|---|---:|
| `frontend/app/src/app/routes/app/test-builder-graph.tsx` | 13 |
| `frontend/app/src/app/routes/app/copilot.tsx` | 9 |
| `frontend/app/src/app/routes/app/questions.tsx` | 5 |
| `frontend/app/src/app/routes/app/slots-create.tsx` | 5 |
| `frontend/app/src/app/routes/app/incoming.tsx` | 4 |
| `frontend/app/src/app/routes/app/candidates.test.tsx` | 3 |
| `frontend/app/src/api/client.ts` | 2 |
| `frontend/app/src/app/routes/app/candidate-new.test.tsx` | 2 |
| `frontend/app/src/app/routes/app/dashboard.tsx` | 2 |
| `frontend/app/src/app/routes/app/template-edit.tsx` | 2 |
| `frontend/app/src/app/routes/tg-app/candidate.tsx` | 2 |
| `frontend/app/src/app/routes/__root.tsx` | 1 |
| `frontend/app/src/app/routes/app/candidate-detail.tsx` | 1 |
| `frontend/app/src/app/routes/app/ui-cosmetics.test.tsx` | 1 |
| `frontend/app/src/app/routes/tg-app/incoming.tsx` | 1 |
| `frontend/app/src/app/routes/tg-app/index.tsx` | 1 |

### Console / print в коде

| Файл | Вхождений |
|---|---:|
| `scripts/diagnose_notifications.py` | 39 |
| `scripts/check_slot_2_notification.py` | 36 |
| `scripts/diagnose_server.py` | 34 |
| `scripts/update_notification_templates.py` | 34 |
| `scripts/test_create_intro_day.py` | 33 |
| `scripts/check_failed_notifications.py` | 31 |
| `scripts/fix_slot_2_notification.py` | 24 |
| `scripts/test_bot_init.py` | 24 |
| `scripts/check_candidate.py` | 20 |
| `tests/test_intro_day_e2e.py` | 11 |
| `tests/test_slot_timezone_moscow_novosibirsk.py` | 11 |
| `scripts/run_interview_script_finetune.py` | 10 |
| `scripts/dev_server.py` | 9 |
| `backend/core/settings.py` | 8 |
| `frontend/app/src/app/hooks/useCalendarWebSocket.ts` | 8 |
| `scripts/loadtest_profiles/summarize_profile.py` | 8 |
| `tests/test_bulk_slots_timezone_moscow_novosibirsk.py` | 8 |
| `scripts/dev_doctor.py` | 7 |
| `scripts/summarize_autocannon.py` | 7 |
| `scripts/verify_jwt.py` | 7 |
| `tests/test_slot_creation_timezone_validation.py` | 7 |
| `scripts/collect_ux.py` | 5 |
| `scripts/export_interview_script_dataset.py` | 5 |
| `scripts/seed_message_templates.py` | 5 |
| `scripts/seed_tests.py` | 5 |
| `backend/apps/admin_ui/static/js/modules/slots-notion.js` | 4 |
| `docs/archive/guides/CACHE_CLEAR_INSTRUCTIONS.md` | 4 |
| `scripts/formal_gate_sprint12.py` | 4 |
| `scripts/migrate_legacy_templates.py` | 4 |
| `audit/run_smoke_checks.py` | 3 |
| `docs/archive/features/dashboard/CARD_TILT_IMPLEMENTATION.md` | 3 |
| `docs/archive/features/dashboard/NEURAL_NETWORK_IMPLEMENTATION.md` | 3 |
| `run_migrations.py` | 3 |
| `scripts/migrate_city_templates.py` | 3 |
| `scripts/seed_default_templates.py` | 3 |
| `.env.local` | 2 |
| `.env.local.example` | 2 |
| `backend/core/result.py` | 2 |
| `docs/archive/SERVER_STABILITY.md` | 2 |
| `docs/archive/features/dashboard/REAL_DATA_INTEGRATION_COMPLETE.md` | 2 |
| `docs/archive/optimization/OPTIMIZATION_SUMMARY.md` | 2 |
| `docs/archive/optimization/PHASE2_PERFORMANCE.md` | 2 |
| `scripts/loadtest_profiles/analyze_step.py` | 2 |
| `scripts/seed_test_candidates.py` | 2 |
| `tests/reproduce_issue_1.py` | 2 |
| `backend/core/metrics.py` | 1 |
| `docs/LOCAL_DEV.md` | 1 |
| `docs/archive/LIQUID_GLASS_QUICKSTART.md` | 1 |
| `docs/archive/features/dashboard/ANIMATED_COUNTER_IMPLEMENTATION.md` | 1 |
| `docs/archive/features/dashboard/INTERFACE_IMPROVEMENTS_PHASE_2.md` | 1 |
| `docs/archive/optimization/README_OPTIMIZATION.md` | 1 |
| `docs/archive/qa/QA_COMPREHENSIVE_REPORT.md` | 1 |
| `frontend/app/src/app/components/ErrorBoundary.tsx` | 1 |
| `frontend/app/src/app/routes/app/candidate-detail.tsx` | 1 |
| `max_bot.py` | 1 |
| `scripts/e2e_notifications_sandbox.py` | 1 |
| `scripts/generate_waiting_candidates.py` | 1 |
| `scripts/loadtest_notifications.py` | 1 |
| `scripts/seed_auth_accounts.py` | 1 |
| `scripts/seed_city_templates.py` | 1 |
| `scripts/seed_incoming_candidates.py` | 1 |
| `scripts/seed_legacy_templates.py` | 1 |
| `scripts/seed_test_users.py` | 1 |
| `tools/render_previews.py` | 1 |

## 10. Выводы и рекомендации

- Наиболее сложные зоны по объёму и изменчивости: `frontend/app/src/app/routes/app/candidate-detail.tsx`, `backend/apps/admin_ui/services/candidates.py`, `backend/apps/admin_ui/routers/api.py`, `backend/apps/bot/services.py`, `frontend/app/src/theme/global.css`.
- Проект уже вырос в многослойную монорепу: backend FastAPI + bot + frontend SPA + насыщенный test harness + большой исторический docs-слой.
- Главный риск сопровождения — сверхкрупные модули и накопленная логика в сервисах/роутерах без дальнейшего выделения bounded contexts.
- Второй риск — дублирование знаний между `docs/archive`, `codex/*`, `audit/*` и живым кодом. Для онбординга полезно держать отдельную canonical карту активных подсистем.
- Третий риск — theme/CSS слой: много глобальных правил и route-specific стилей, что повышает вероятность регрессий при UI-изменениях.