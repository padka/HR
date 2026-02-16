# AI Coach Runbook

## Purpose

`AI Coach` помогает рекрутеру по кандидату:

- оценка релевантности (`relevance_score`, `relevance_level`)
- сильные стороны и риски
- вопросы для интервью
- следующий лучший шаг
- черновики сообщений

## API

- `GET /api/ai/candidates/{candidate_id}/coach`
- `POST /api/ai/candidates/{candidate_id}/coach/refresh`
- `POST /api/ai/candidates/{candidate_id}/coach/drafts`

`mode` для drafts: `short | neutral | supportive`.

## Preconditions

- `AI_ENABLED=true`
- корректно заданы `AI_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`
- пользователь авторизован как `recruiter` или `admin`

## Error handling

- `501 {"error":"ai_disabled"}` — AI отключен
- `429 {"error":"rate_limited"}` — превышен лимит запросов
- `502 {"message":"AI provider error"}` — ошибка провайдера

## Validation checklist

1. Открыть карточку кандидата `/app/candidates/:id`.
2. Нажать `Сгенерировать Coach`.
3. Проверить вывод score/risks/questions/next action.
4. Нажать режим черновиков и `Вставить в чат`.
5. Убедиться, что сообщение отправляется через чат кандидата.
