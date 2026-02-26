# AI Interview Script Runbook

## Что это
`Interview Script` генерирует структурированный JSON сценария интервью кандидата через OpenAI API (Responses API), с кэшем, RAG-контекстом и сбором фидбека для последующего fine-tuning.

## Env переменные
- `AI_ENABLED`, `AI_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`
- `AI_INTERVIEW_SCRIPT_TIMEOUT_SECONDS`
- `AI_INTERVIEW_SCRIPT_MAX_TOKENS`
- `AI_INTERVIEW_SCRIPT_CACHE_TTL_HOURS`
- `AI_INTERVIEW_SCRIPT_FT_MODEL`
- `AI_INTERVIEW_SCRIPT_AB_PERCENT`
- `AI_INTERVIEW_SCRIPT_FT_MIN_SAMPLES`
- `AI_INTERVIEW_SCRIPT_PII_MODE` (`redacted` по умолчанию)

## API
- `GET /api/ai/candidates/{candidate_id}/interview-script`
- `POST /api/ai/candidates/{candidate_id}/interview-script/refresh` (CSRF)
- `PUT /api/ai/candidates/{candidate_id}/hh-resume` (CSRF)
- `POST /api/ai/candidates/{candidate_id}/interview-script/feedback` (CSRF)

## Кэш и инвалидация
- Ключ: `input_hash` от `(candidate_profile + hh_resume_norm + office_context + rag_keys + model + prompt_version)`.
- TTL: `AI_INTERVIEW_SCRIPT_CACHE_TTL_HOURS` (по умолчанию 24ч).
- `refresh` форсирует регенерацию.

## RAG
- Источник: Knowledge Base (`knowledge_base_documents/chunks`).
- Категории: `product_position`, `od_rules`, `objections`, `field_day`, `city_office`, `general`.
- В логах/кэше для RAG сохраняются только `doc_id/chunk_index`, без сырого текста PII.

## Feedback и gold edits
Сохраняются:
- `input_redacted_json`
- `output_original_json`
- `output_final_json` (если рекрутер редактировал)
- `labels_json` (`helped`, `edited`, `quick_reasons`, `outcome`, `outcome_reason`)
- `model`, `prompt_version`, `input_hash`
- `idempotency_key` (защита от дубликатов)

## Экспорт датасета
```bash
python3 scripts/export_interview_script_dataset.py \
  --out ./tmp/interview_script_ft_dataset.jsonl
```

Опции:
- `--all` включает не только quality/gold samples
- `--limit N`
- `--min-samples N` (readiness threshold)

Код выхода:
- `0`: датасет готов (`>= threshold`)
- `2`: собран, но порог не достигнут

## Запуск fine-tuning (manual CLI)
```bash
python3 scripts/run_interview_script_finetune.py \
  --dataset ./tmp/interview_script_ft_dataset.jsonl
```

С ожиданием результата:
```bash
python3 scripts/run_interview_script_finetune.py \
  --dataset ./tmp/interview_script_ft_dataset.jsonl \
  --wait
```

После `succeeded`:
- установить `AI_INTERVIEW_SCRIPT_FT_MODEL=<fine_tuned_model_id>`
- задать `AI_INTERVIEW_SCRIPT_AB_PERCENT` (например 20)

## A/B логика
- Сплит детерминированный по `candidate_id` hash.
- Если `AI_INTERVIEW_SCRIPT_FT_MODEL` пустой или `AB_PERCENT=0`, используется `OPENAI_MODEL`.

## Мониторинг
- Таблица `ai_request_logs`: latency/tokens/error rate.
- Таблица `ai_interview_script_feedback`: edit rate, helped/not helped, outcome.
- Ключевые метрики: `OD assigned`, `showed_up`, доля ручных правок, время рекрутера до отправки.
