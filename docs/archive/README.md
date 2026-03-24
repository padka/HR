# Archive Boundary

## Purpose
Зафиксировать, что `docs/archive/` является историческим каталогом и не используется как active source of truth для текущих инженерных решений.

## Owner
Platform Engineering

## Status
Historical

## Last Reviewed
2026-03-25

## Source Paths
- `docs/archive/*`
- `docs/README.md`

## Related Diagrams
- `docs/README.md`

## Change Policy
В архив добавляются завершенные или устаревшие материалы. Existing files не переписываются под новую реальность вместо canonical docs; для актуального состояния создаются или обновляются документы вне `docs/archive/`.

## Rules
- Архив не переопределяет `docs/architecture/*`, `docs/data/*`, `docs/frontend/*`, `docs/security/*`, `docs/qa/*`, `docs/runbooks/*` и `docs/adr/*`.
- Ссылки из архива допустимы только как historical context.
- Если документ нужен как живая инструкция, он должен быть перенесен или заново оформлен в canonical tree.
