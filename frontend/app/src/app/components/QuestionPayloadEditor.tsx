import { useEffect, useMemo, useRef, useState } from 'react'

type BuilderState = {
  type: 'choice' | 'text'
  prompt: string
  explanation: string
  options: string[]
  correct: number
  validation: { min_length?: number | null; max_length?: number | null }
  validationExtra: Record<string, unknown>
  extra: Record<string, unknown>
}

type PreviewItem =
  | { kind: 'prompt'; value: string }
  | { kind: 'options'; options: string[]; correct?: number }
  | { kind: 'validation'; value: string }
  | { kind: 'explanation'; value: string }

const CHOICE_TEMPLATE = {
  prompt: 'Выберите правильный вариант',
  options: ['Вариант 1', 'Вариант 2', 'Вариант 3'],
  correct: 0,
  explanation: 'Комментарий появляется после ответа',
}

const TEXT_TEMPLATE = {
  prompt: 'Расскажите о своём опыте',
  validation: {
    min_length: 30,
    max_length: 500,
  },
}

const BUILDER_DISABLED_DEFAULT =
  'Конструктор поддерживает базовые структуры с prompt/options/correct или prompt/validation.'

function normalizeOption(value: unknown) {
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function convertPayloadToState(payload: unknown): BuilderState | null {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null
  const data = payload as Record<string, unknown>
  const prompt = typeof data.prompt === 'string' ? data.prompt : ''
  const explanation = typeof data.explanation === 'string' ? data.explanation : ''

  const extras: Record<string, unknown> = {}
  Object.entries(data).forEach(([key, value]) => {
    if (['prompt', 'options', 'correct', 'explanation', 'validation'].includes(key)) return
    extras[key] = value
  })

  if (Array.isArray(data.options)) {
    const options = data.options.length ? data.options.map(normalizeOption) : ['Вариант 1', 'Вариант 2']
    let correct = typeof data.correct === 'number' ? data.correct : 0
    if (Number.isNaN(correct) || correct < 0) correct = 0
    if (correct >= options.length) correct = options.length - 1
    return {
      type: 'choice',
      prompt,
      explanation,
      options,
      correct,
      validation: {},
      validationExtra: {},
      extra: extras,
    }
  }

  let min: number | null = null
  let max: number | null = null
  let validationExtra: Record<string, unknown> = {}
  if (data.validation && typeof data.validation === 'object' && !Array.isArray(data.validation)) {
    const { min_length, max_length, ...rest } = data.validation as Record<string, unknown>
    if (typeof min_length === 'number') min = min_length
    if (typeof max_length === 'number') max = max_length
    validationExtra = rest
  }

  return {
    type: 'text',
    prompt,
    explanation,
    options: [],
    correct: 0,
    validation: { min_length: min ?? undefined, max_length: max ?? undefined },
    validationExtra,
    extra: extras,
  }
}

function buildPayloadFromState(state: BuilderState): Record<string, unknown> {
  const payload: Record<string, unknown> = { ...state.extra }
  const prompt = state.prompt.trim()
  if (prompt) payload.prompt = prompt

  const explanation = state.explanation.trim()
  if (explanation) payload.explanation = explanation

  if (state.type === 'choice') {
    const options = state.options.map((opt) => opt.trim()).filter((opt) => opt.length)
    const safeOptions = options.length ? options : ['Вариант 1', 'Вариант 2']
    let correct = state.correct
    if (Number.isNaN(correct) || correct < 0) correct = 0
    if (correct >= safeOptions.length) correct = safeOptions.length - 1
    payload.options = safeOptions
    payload.correct = correct

    if (state.validationExtra && Object.keys(state.validationExtra).length) {
      payload.validation = { ...state.validationExtra }
    }
  } else {
    const validation: Record<string, unknown> = { ...state.validationExtra }
    const min = state.validation?.min_length
    const max = state.validation?.max_length
    if (typeof min === 'number' && !Number.isNaN(min)) validation.min_length = min
    if (typeof max === 'number' && !Number.isNaN(max)) validation.max_length = max
    if (Object.keys(validation).length) payload.validation = validation
  }

  return payload
}

function buildPreview(payload: Record<string, unknown>): PreviewItem[] {
  const items: PreviewItem[] = []
  if (typeof payload.prompt === 'string' && payload.prompt.trim()) {
    items.push({ kind: 'prompt', value: payload.prompt })
  }
  if (Array.isArray(payload.options)) {
    items.push({
      kind: 'options',
      options: payload.options.map(normalizeOption),
      correct: typeof payload.correct === 'number' ? payload.correct : undefined,
    })
  }
  if (payload.validation) {
    items.push({ kind: 'validation', value: JSON.stringify(payload.validation, null, 2) })
  }
  if (typeof payload.explanation === 'string' && payload.explanation.trim()) {
    items.push({ kind: 'explanation', value: payload.explanation })
  }
  return items
}

type PayloadEditorProps = {
  value: string
  onChange: (next: string) => void
  onValidityChange?: (ok: boolean) => void
}

export function QuestionPayloadEditor({ value, onChange, onValidityChange }: PayloadEditorProps) {
  const [status, setStatus] = useState<{ state: 'empty' | 'ok' | 'error'; message: string }>({
    state: 'empty',
    message: 'Введите JSON для вопроса.',
  })
  const [previewItems, setPreviewItems] = useState<PreviewItem[]>([])
  const [builderState, setBuilderState] = useState<BuilderState | null>(null)
  const [builderEnabled, setBuilderEnabled] = useState(false)
  const [builderMessage, setBuilderMessage] = useState(BUILDER_DISABLED_DEFAULT)
  const syncingFromBuilder = useRef(false)
  const parseTimer = useRef<number | null>(null)

  const setBuilderEnabledState = (enabled: boolean, message?: string) => {
    setBuilderEnabled(enabled)
    setBuilderMessage(message || BUILDER_DISABLED_DEFAULT)
  }

  const applyParsedPayload = (payloadObj: Record<string, unknown>, skipBuilderUpdate: boolean) => {
    setStatus({ state: 'ok', message: 'JSON корректен' })
    onValidityChange?.(true)
    setPreviewItems(buildPreview(payloadObj))

    if (skipBuilderUpdate) return
    const nextState = convertPayloadToState(payloadObj)
    if (!nextState) {
      setBuilderState(null)
      setBuilderEnabledState(false)
      return
    }
    setBuilderState(nextState)
    setBuilderEnabledState(true)
  }

  useEffect(() => {
    if (syncingFromBuilder.current) {
      syncingFromBuilder.current = false
      return
    }
    if (parseTimer.current) {
      window.clearTimeout(parseTimer.current)
    }
    parseTimer.current = window.setTimeout(() => {
      const raw = value.trim()
      if (!raw) {
        setStatus({ state: 'empty', message: 'Введите JSON для вопроса.' })
        setPreviewItems([])
        onValidityChange?.(false)
        setBuilderState(null)
        setBuilderEnabledState(false, 'Введите JSON или воспользуйтесь шаблоном.')
        return
      }
      try {
        const parsed = JSON.parse(raw)
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
          setStatus({ state: 'error', message: 'JSON должен быть объектом.' })
          setPreviewItems([])
          onValidityChange?.(false)
          setBuilderState(null)
          setBuilderEnabledState(false, 'Конструктор работает только с объектами JSON.')
          return
        }
        applyParsedPayload(parsed as Record<string, unknown>, false)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Некорректный JSON'
        setStatus({ state: 'error', message: `Ошибка JSON: ${message}` })
        setPreviewItems([])
        onValidityChange?.(false)
        setBuilderState(null)
        setBuilderEnabledState(false, 'Конструктор недоступен: JSON содержит ошибку.')
      }
    }, 200)

    return () => {
      if (parseTimer.current) {
        window.clearTimeout(parseTimer.current)
      }
    }
  }, [value, onValidityChange])

  const updateFromBuilder = (nextState: BuilderState) => {
    setBuilderState(nextState)
    const payload = buildPayloadFromState(nextState)
    const serialized = JSON.stringify(payload, null, 2)
    syncingFromBuilder.current = true
    onChange(serialized)
    applyParsedPayload(payload, true)
  }

  const handleFormat = () => {
    try {
      const formatted = JSON.stringify(JSON.parse(value), null, 2)
      onChange(formatted)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ошибка форматирования'
      setStatus({ state: 'error', message: `Не удалось форматировать: ${message}` })
    }
  }

  const handleTemplate = (template: Record<string, unknown>) => {
    const serialized = JSON.stringify(template, null, 2)
    onChange(serialized)
  }

  const builderOptions = builderState?.options ?? []
  const canUseBuilder = builderEnabled && builderState

  const previewContent = useMemo(() => previewItems, [previewItems])

  return (
    <div className="payload-shell">
      <div className="payload-toolbar">
        <button type="button" className="ui-btn ui-btn--ghost" onClick={handleFormat}>
          Форматировать JSON
        </button>
        <button type="button" className="ui-btn ui-btn--ghost" onClick={() => handleTemplate(CHOICE_TEMPLATE)}>
          Шаблон «Варианты»
        </button>
        <button type="button" className="ui-btn ui-btn--ghost" onClick={() => handleTemplate(TEXT_TEMPLATE)}>
          Шаблон «Свободный ответ»
        </button>
      </div>

      <div className={`payload-designer ${canUseBuilder ? 'is-ready' : 'is-disabled'}`}>
        <div className="payload-designer__header">
          <div>
            <h3>Конструктор вопроса</h3>
            <p className="subtitle">Меняйте поля ниже — JSON обновится автоматически.</p>
          </div>
          <div className="payload-designer__type">
            <label>Тип вопроса</label>
            <select
              value={builderState?.type ?? 'choice'}
              onChange={(event) => {
                if (!builderState) return
                const nextType = event.target.value === 'text' ? 'text' : 'choice'
                updateFromBuilder({
                  ...builderState,
                  type: nextType,
                  validation: nextType === 'text' ? builderState.validation || { min_length: null, max_length: null } : {},
                })
              }}
              disabled={!canUseBuilder}
            >
              <option value="choice">С вариантами</option>
              <option value="text">Свободный ответ</option>
            </select>
          </div>
        </div>

        <fieldset className="payload-designer__body" disabled={!canUseBuilder}>
          <label className="designer-field">
            <span>Формулировка</span>
            <textarea
              rows={3}
              value={builderState?.prompt ?? ''}
              onChange={(event) => {
                if (!builderState) return
                updateFromBuilder({ ...builderState, prompt: event.target.value })
              }}
            />
          </label>

          {builderState?.type === 'choice' ? (
            <div className="builder-section">
              <div className="designer-subheader">
                <span>Варианты ответов</span>
                <button
                  type="button"
                  className="ui-btn ui-btn--ghost"
                  onClick={() => {
                    if (!builderState) return
                    updateFromBuilder({
                      ...builderState,
                      options: [...builderOptions, `Новый вариант ${builderOptions.length + 1}`],
                    })
                  }}
                >
                  + Добавить вариант
                </button>
              </div>
              <div className="builder-options">
                {builderOptions.map((option, idx) => (
                  <div key={`${idx}-${option}`} className="builder-option">
                    <div className="builder-option__input">
                      <span className="chip">{idx + 1}</span>
                      <input
                        type="text"
                        value={option}
                        onChange={(event) => {
                          if (!builderState) return
                          const next = [...builderOptions]
                          next[idx] = event.target.value
                          updateFromBuilder({ ...builderState, options: next })
                        }}
                      />
                    </div>
                    <div className="builder-option__controls">
                      <label className="builder-option__correct">
                        <input
                          type="radio"
                          name="option_correct"
                          checked={builderState?.correct === idx}
                          onChange={() => {
                            if (!builderState) return
                            updateFromBuilder({ ...builderState, correct: idx })
                          }}
                        />
                        Верный
                      </label>
                      <button
                        type="button"
                        className="ui-btn ui-btn--ghost"
                        onClick={() => {
                          if (!builderState) return
                          const next = builderOptions.filter((_, index) => index !== idx)
                          const nextCorrect = Math.min(builderState.correct, Math.max(next.length - 1, 0))
                          updateFromBuilder({ ...builderState, options: next, correct: nextCorrect })
                        }}
                      >
                        Удалить
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="builder-section">
              <div className="designer-subheader">
                <span>Ограничения по длине ответа</span>
              </div>
              <div className="designer-grid">
                <label>
                  Минимум (символов)
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={builderState?.validation?.min_length ?? ''}
                    onChange={(event) => {
                      if (!builderState) return
                      const value = event.target.value === '' ? null : Number(event.target.value)
                      updateFromBuilder({
                        ...builderState,
                        validation: { ...builderState.validation, min_length: Number.isNaN(value) ? null : value },
                      })
                    }}
                  />
                </label>
                <label>
                  Максимум (символов)
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={builderState?.validation?.max_length ?? ''}
                    onChange={(event) => {
                      if (!builderState) return
                      const value = event.target.value === '' ? null : Number(event.target.value)
                      updateFromBuilder({
                        ...builderState,
                        validation: { ...builderState.validation, max_length: Number.isNaN(value) ? null : value },
                      })
                    }}
                  />
                </label>
              </div>
            </div>
          )}

          <label className="designer-field">
            <span>Пояснение (опционально)</span>
            <textarea
              rows={2}
              value={builderState?.explanation ?? ''}
              onChange={(event) => {
                if (!builderState) return
                updateFromBuilder({ ...builderState, explanation: event.target.value })
              }}
            />
          </label>
        </fieldset>

        {!canUseBuilder && <div className="designer-disabled">{builderMessage}</div>}
      </div>

      <label className="payload-editor">
        <span>JSON</span>
        <textarea rows={14} value={value} onChange={(event) => onChange(event.target.value)} />
      </label>

      <p className={`payload-status payload-status--${status.state}`}>{status.message}</p>

      <div className="payload-preview">
        {previewContent.length ? (
          <dl className="preview-list">
            {previewContent.map((item, index) => {
              if (item.kind === 'prompt') {
                return (
                  <div key={`prompt-${index}`}>
                    <dt>Формулировка</dt>
                    <dd>{item.value}</dd>
                  </div>
                )
              }
              if (item.kind === 'options') {
                return (
                  <div key={`options-${index}`}>
                    <dt>Варианты</dt>
                    <dd>
                      <ol className="preview-options">
                        {item.options.map((option, idx) => (
                          <li key={`${idx}-${option}`} data-correct={item.correct === idx}>
                            <span className="chip">{idx + 1}</span>
                            {option}
                          </li>
                        ))}
                      </ol>
                    </dd>
                  </div>
                )
              }
              if (item.kind === 'validation') {
                return (
                  <div key={`validation-${index}`}>
                    <dt>Валидация</dt>
                    <dd>
                      <pre>
                        <code>{item.value}</code>
                      </pre>
                    </dd>
                  </div>
                )
              }
              if (item.kind === 'explanation') {
                return (
                  <div key={`explanation-${index}`}>
                    <dt>Пояснение</dt>
                    <dd>{item.value}</dd>
                  </div>
                )
              }
              return null
            })}
          </dl>
        ) : (
          <p className="subtitle">Нет данных для предпросмотра.</p>
        )}
      </div>

      <div className="question-help">
        <div>
          <h3>Вопрос с выбором ответа</h3>
          <pre>
            <code>{`{
  "prompt": "Выберите правильный ответ",
  "options": ["Вариант А", "Вариант B", "Вариант C"],
  "correct": 1,
  "explanation": "Можно указать пояснение"
}`}</code>
          </pre>
        </div>
        <div>
          <h3>Вопрос со свободным ответом</h3>
          <pre>
            <code>{`{
  "prompt": "Расскажите о своём опыте",
  "validation": {
    "min_length": 20,
    "max_length": 600
  }
}`}</code>
          </pre>
        </div>
      </div>
    </div>
  )
}
