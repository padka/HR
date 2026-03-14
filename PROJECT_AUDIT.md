# PROJECT AUDIT — RecruitSmart Admin
## Дата: 2026-03-14

Аудит разбит на части из-за объёма кодовой базы и документации. Это соответствует правилу дробления для больших проектов.

## Состав аудита

- [PROJECT_AUDIT_01_OVERVIEW.md](PROJECT_AUDIT_01_OVERVIEW.md) — статистика, методология, конфиги, file tree, docs/config inventory.
- [PROJECT_AUDIT_02_COMPONENTS.md](PROJECT_AUDIT_02_COMPONENTS.md) — покомпонентный аудит runtime-кода, backend, migration, scripts и tests.
- [PROJECT_AUDIT_03_DEPENDENCIES.md](PROJECT_AUDIT_03_DEPENDENCIES.md) — dependency map, TypeScript types, API catalog, env catalog.
- [PROJECT_AUDIT_04_STYLES_DEBT.md](PROJECT_AUDIT_04_STYLES_DEBT.md) — CSS audit, style system, TODO/FIXME, large files, `any`, console/print, выводы.

## Ключевые цифры

- Файлов в покрытии: **915**
- Строк кода/документации: **236619**
- API-эндпоинтов FastAPI: **295**
- TypeScript типов/интерфейсов: **323**
- Файлов >500 строк: **104**
- Самый большой файл: `frontend/app/src/theme/global.css` (10104 строк)

## Покрытие

- Аудит покрывает исходники, тесты, миграции, scripts, configs и docs текущего workspace.
- Исключены только генерируемые/внешние каталоги: `.venv*`, `.claude-code`, `node_modules`, `dist`, `build`, `.next`, `artifacts`, `.local`, кэши и `frontend/app/test-results`.