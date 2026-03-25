# ADR Index

## Header
- Purpose: Индекс архитектурных решений для canonical docs, Mermaid-диаграмм, Phase 0 стабилизации и Telegram/MAX reliability hardening.
- Owner: Architecture / QA
- Status: Canonical, P0
- Last Reviewed: 2026-03-25
- Source Paths: `docs/adr/*`, `docs/architecture/*`, `docs/data/*`, `docs/frontend/*`, `docs/security/*`, `docs/qa/*`
- Related Diagrams: `docs/adr/adr-0001-canonical-docs-and-mermaid.md`, `docs/adr/adr-0002-phase0-stabilization-before-feature-work.md`, `docs/adr/adr-0003-telegram-max-channel-ownership-and-session-invalidation.md`
- Change Policy: Добавлять ADR при изменении базового принципа документации, quality gate или release policy.

## Назначение
ADR фиксируют решения, которые должны быть устойчивыми и понятными для backend, frontend, QA, design и analytics команд.

## Reading order
1. `adr-0001-canonical-docs-and-mermaid.md`
2. `adr-0002-phase0-stabilization-before-feature-work.md`
3. `adr-0003-telegram-max-channel-ownership-and-session-invalidation.md`

## Правила
- Один ADR = одно решение.
- ADR пишет причину, контекст, решение и последствия.
- Устаревшие ADR не удаляются, а маркируются как historical.
- Canonical docs на русском, Markdown + Mermaid.
