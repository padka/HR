import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import { STAGE_LABELS, TEMPLATE_META, type TemplateStage } from './template_meta'

type City = { id: number; name: string }

const PLACEHOLDERS = [
  '{{candidate_fio}}',
  '{{city_name}}',
  '{{slot_date_local}}',
  '{{slot_time_local}}',
  '{{recruiter_name}}',
  '{{recruiter_phone}}',
  '{{address}}',
  '{{whatsapp_link}}',
]

const DEFAULT_PREVIEW = {
  candidate_fio: 'Иван Иванов',
  city_name: 'Москва',
  slot_date_local: '21.09',
  slot_time_local: '10:30',
  recruiter_name: 'Михаил',
  recruiter_phone: '+7 (900) 000-00-00',
  address: 'ул. Пушкина, 10',
  whatsapp_link: 'https://wa.me/79000000000',
}

const TEMPLATE_GROUPS = (() => {
  const grouped = new Map<TemplateStage, Array<{ key: string; title: string; desc: string }>>()
  Object.entries(TEMPLATE_META).forEach(([key, meta]) => {
    const items = grouped.get(meta.stage) || []
    items.push({ key, title: meta.title, desc: meta.desc })
    grouped.set(meta.stage, items)
  })
  const stageOrder = Object.keys(STAGE_LABELS) as TemplateStage[]
  stageOrder.forEach((stage) => {
    const items = grouped.get(stage)
    if (items) {
      items.sort((a, b) => a.title.localeCompare(b.title, 'ru'))
    }
  })
  return stageOrder
    .map((stage) => ({
      stage,
      title: STAGE_LABELS[stage].title,
      desc: STAGE_LABELS[stage].desc,
      items: grouped.get(stage) || [],
    }))
    .filter((group) => group.items.length > 0)
})()

function renderPreview(text: string, preview: Record<string, string>) {
  let output = text || ''
  Object.entries(preview).forEach(([key, value]) => {
    const token = `{{${key}}}`
    output = output.split(token).join(value)
  })
  return output
}

export function TemplateNewPage() {
  const navigate = useNavigate()
  const search = useSearch({ from: '/app/templates/new' }) as { city_id?: string | number; key?: string }
  const initialCityId =
    typeof search.city_id === 'number'
      ? String(search.city_id)
      : typeof search.city_id === 'string'
        ? search.city_id
        : ''
  const initialKey = typeof search.key === 'string' ? search.key : ''
  const { data: cities } = useQuery<City[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
  })
  const [form, setForm] = useState({
    key: initialKey,
    text: '',
    city_id: initialCityId,
    is_active: true,
  })
  const [formError, setFormError] = useState<string | null>(null)
  const [preview, setPreview] = useState(DEFAULT_PREVIEW)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    if (!initialCityId) return
    setForm((prev) => (prev.city_id === initialCityId ? prev : { ...prev, city_id: initialCityId }))
  }, [initialCityId])

  useEffect(() => {
    if (!initialKey) return
    setForm((prev) => (prev.key === initialKey ? prev : { ...prev, key: initialKey }))
  }, [initialKey])

  const mutation = useMutation({
    mutationFn: async () => {
      setFormError(null)
      if (!form.key) {
        throw new Error('Выберите тип сообщения')
      }
      if (!form.text.trim()) {
        throw new Error('Введите текст шаблона')
      }
      const payload = {
        key: form.key,
        text: form.text,
        city_id: form.city_id ? Number(form.city_id) : null,
        locale: 'ru',
        channel: 'tg',
        version: 1,
        is_active: form.is_active,
      }
      return apiFetch('/templates', { method: 'POST', body: JSON.stringify(payload) })
    },
    onSuccess: () => navigate({ to: '/app/templates' }),
    onError: (err) => {
      let message = err instanceof Error ? err.message : 'Ошибка'
      try {
        const parsed = JSON.parse(message)
        if (parsed?.error) {
          message = parsed.error
        }
      } catch {
        // ignore parsing errors
      }
      setFormError(message)
    },
  })

  const cityOptions = useMemo(
    () => [{ value: '', label: 'Общий' }, ...(cities || []).map((c) => ({ value: String(c.id), label: c.name }))],
    [cities],
  )

  const templateGroups = TEMPLATE_GROUPS
  const selectedMeta = form.key ? TEMPLATE_META[form.key] : undefined

  const insertToken = (token: string) => {
    const el = textareaRef.current
    const text = form.text || ''
    if (!el) {
      setForm((prev) => ({ ...prev, text: text + token }))
      return
    }
    const start = el.selectionStart ?? text.length
    const end = el.selectionEnd ?? start
    const next = text.slice(0, start) + token + text.slice(end)
    setForm((prev) => ({ ...prev, text: next }))
    requestAnimationFrame(() => {
      el.focus()
      const caret = start + token.length
      el.setSelectionRange(caret, caret)
    })
  }

  const previewText = renderPreview(form.text, preview)
  const charCount = form.text.length

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <div className="glass panel" style={{ display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <div>
              <h1 className="title">Новый шаблон</h1>
              <p className="subtitle">Создайте шаблон для рассылок и уведомлений.</p>
            </div>
            <Link to="/app/templates" className="glass action-link">← Назад</Link>
          </div>

          <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
            <label style={{ display: 'grid', gap: 6 }}>
              Город
              <select value={form.city_id} onChange={(e) => setForm({ ...form, city_id: e.target.value })}>
                {cityOptions.map((c) => (
                  <option key={c.value || 'global'} value={c.value}>{c.label}</option>
                ))}
              </select>
            </label>

            <label style={{ display: 'grid', gap: 6 }}>
              Тип сообщения
              <select value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value })}>
                <option value="">— выберите тип —</option>
                {templateGroups.map((group) => (
                  <optgroup key={group.stage} label={group.title}>
                    {group.items.map((item) => (
                      <option key={item.key} value={item.key}>{item.title}</option>
                    ))}
                  </optgroup>
                ))}
                {form.key && !selectedMeta && (
                  <optgroup label="Другое">
                    <option value={form.key}>{form.key}</option>
                  </optgroup>
                )}
              </select>
              {selectedMeta && <span className="subtitle">{selectedMeta.desc}</span>}
            </label>
          </div>

          <label style={{ display: 'grid', gap: 6 }}>
            Текст шаблона
            <textarea
              ref={textareaRef}
              rows={8}
              value={form.text}
              onChange={(e) => setForm({ ...form, text: e.target.value })}
            />
            <div className="action-row" style={{ gap: 8, flexWrap: 'wrap' }}>
              {PLACEHOLDERS.map((token) => (
                <button key={token} type="button" className="ui-btn ui-btn--ghost" onClick={() => insertToken(token)}>
                  {token}
                </button>
              ))}
            </div>
            <div className="action-row" style={{ justifyContent: 'space-between' }}>
              <span className="subtitle">Символы: {charCount} / 4096</span>
              {charCount > 4096 && <span style={{ color: '#f07373' }}>Превышен лимит Telegram</span>}
            </div>
          </label>

          <details className="glass panel--tight">
            <summary>Предпросмотр</summary>
            <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 8 }}>
                {Object.entries(preview).map(([key, value]) => (
                  <label key={key} style={{ display: 'grid', gap: 4 }}>
                    {key}
                    <input value={value} onChange={(e) => setPreview((prev) => ({ ...prev, [key]: e.target.value }))} />
                  </label>
                ))}
              </div>
              <div className="glass" style={{ padding: 12, whiteSpace: 'pre-wrap' }}>
                {previewText || '—'}
              </div>
            </div>
          </details>

          <div className="action-row" style={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              Активен
            </label>
            <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
              {mutation.isPending ? 'Сохраняем…' : 'Создать'}
            </button>
          </div>
          {formError && <p style={{ color: '#f07373' }}>Ошибка: {formError}</p>}
        </div>
      </div>
    </RoleGuard>
  )
}
