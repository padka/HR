# Frontend Canonical Docs

## Purpose
Этот пакет - canonical source of truth по фронтенду RecruitSmart Admin. Он описывает текущий React SPA, Telegram Mini App, shell/navigation, тему и границы ответственности между модулями. Candidate browser portal route files могут существовать исторически, но не считаются active mounted frontend surface.

## Owner
Frontend platform / UI engineering.

## Status
Canonical.

## Last Reviewed
2026-04-16.

## Source Paths
- `frontend/app/src/app/main.tsx`
- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/theme/*`
- `frontend/app/src/app/routes/app/*`
- `frontend/app/src/app/routes/tg-app/*`

## Related Diagrams
- `docs/frontend/route-map.md`
- `docs/frontend/screen-inventory.md`
- `docs/frontend/state-flows.md`
- `docs/frontend/design-system.md`
- `docs/frontend/component-ownership.md`

## Change Policy
- Любое изменение маршрутов, навигации, темы, shell или экранов должно обновлять этот пакет в том же PR.
- Если код и документы расходятся, source of truth - код в `frontend/app/src/app/main.tsx`, `frontend/app/src/app/routes/__root.tsx` и `frontend/app/src/theme/*`.
- Старые или фрагментарные frontend-доки вне `docs/frontend/` не считаются canonical для UI-решений.

## What This Pack Covers
- SPA route tree и роль `main.tsx` как единого маршрутизатора.
- Admin shell, desktop/mobile navigation, role gating, unread chat state.
- Telegram Mini App flows.
- Theme system: tokens, surfaces, motion, responsive overrides.
- Ownership boundaries между route modules, shared components и theme layer.

## Reading Order
1. `route-map.md`
2. `screen-inventory.md`
3. `state-flows.md`
4. `design-system.md`
5. `component-ownership.md`

## Canonical Rules
- `frontend/app/src/app/main.tsx` - единственный источник правды по route tree и code-splitting.
- `frontend/app/src/app/routes/__root.tsx` - единственный источник правды по shell/navigation.
- `frontend/app/src/theme/tokens.css` и `frontend/app/src/theme/global.css` - единственный источник правды по визуальной системе.
- Page-level CSS может уточнять экран, но не должен переопределять основу токенов.
