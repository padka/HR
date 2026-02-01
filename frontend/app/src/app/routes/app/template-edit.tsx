import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'

type City = { id: number; name: string }
type TemplateDetail = {
  id: number
  key: string
  text: string
  city_id?: number | null
  is_global?: boolean
}

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

function renderPreview(text: string, preview: Record<string, string>) {
  let output = text || ''
  Object.entries(preview).forEach(([key, value]) => {
    const token = `{{${key}}}`
    output = output.split(token).join(value)
  })
  return output
}

export function TemplateEditPage() {
  const params = useParams({ from: '/app/templates/$templateId/edit' })
  const templateId = Number(params.templateId)
  const navigate = useNavigate()

  const { data: cities } = useQuery<City[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
  })
  const { data: presets } = useQuery<Record<string, string>>({
    queryKey: ['template-presets'],
    queryFn: () => apiFetch('/template_presets'),
  })

  const { data: contextMap } = useQuery<Record<string, string[]>>({
    queryKey: ['template-context-keys'],
    queryFn: () => apiFetch('/message-templates/context-keys'),
  })

  const availableVars = useMemo(() => {
    if (!contextMap) return []
    const k = form.key.toLowerCase()
    let type = 'other'
    if (k.includes('intro')) type = 'intro_day'
    else if (k.includes('interview') || k.includes('reschedule') || k.includes('invite')) type = 'interview'
    else if (k.includes('remind') || k.includes('confirm')) type = 'reminder'
    else if (k.includes('reject') || k.includes('fail')) type = 'rejection'
    
    return contextMap[type] || contextMap['other'] || []
  }, [form.key, contextMap])

  const detailQuery = useQuery<TemplateDetail>({
    queryKey: ['template-detail', templateId],
    queryFn: () => apiFetch(`/templates/${templateId}`),
  })

  const [form, setForm] = useState({
    key: '',
    text: '',
    city_id: '',
    is_global: true,
  })
  const [formError, setFormError] = useState<string | null>(null)
  const [presetKey, setPresetKey] = useState('')
  const [cityFilter, setCityFilter] = useState('')
  const [preview, setPreview] = useState(DEFAULT_PREVIEW)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const hasCities = (cities?.length || 0) > 0

  useEffect(() => {
    if (!detailQuery.data) return
    setForm({
      key: detailQuery.data.key,
      text: detailQuery.data.text,
      city_id: detailQuery.data.city_id != null ? String(detailQuery.data.city_id) : '',
      is_global: Boolean(detailQuery.data.is_global),
    })
  }, [detailQuery.data])

  useEffect(() => {
    if (!hasCities) {
      setForm((prev) => ({ ...prev, is_global: true, city_id: '' }))
    }
  }, [hasCities])

  const mutation = useMutation({
    mutationFn: async () => {
      setFormError(null)
      if (!form.text.trim()) {
        throw new Error('Введите текст шаблона')
      }
      if (!form.is_global && !form.city_id) {
        throw new Error('Выберите город или отметьте шаблон как глобальный')
      }
      const payload = {
        key: form.key,
        text: form.text,
        city_id: form.is_global ? null : form.city_id ? Number(form.city_id) : null,
      }
      return apiFetch(`/templates/${templateId}`, { method: 'PUT', body: JSON.stringify(payload) })
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

  const deleteMutation = useMutation({
    mutationFn: async () => apiFetch(`/templates/${templateId}`, { method: 'DELETE' }),
    onSuccess: () => navigate({ to: '/app/templates' }),
  })

  const cityOptions = useMemo(() => (cities || []).map((c) => ({ value: c.id, label: c.name })), [cities])
  const filteredCities = useMemo(() => {
    if (!cityFilter.trim()) return cityOptions
    const needle = cityFilter.toLowerCase()
    return cityOptions.filter((c) => c.label.toLowerCase().includes(needle))
  }, [cityFilter, cityOptions])

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

  const [serverPreview, setServerPreview] = useState<string | null>(null)
  
  const previewMutation = useMutation({
    mutationFn: async () => apiFetch('/message-templates/preview', {
        method: 'POST', 
        body: JSON.stringify({ text: form.text })
    }),
    onSuccess: (data) => setServerPreview(data.html)
  })

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <div className="glass panel" style={{ display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <div>
              <h1 className="title">Редактирование шаблона</h1>
              <p className="subtitle">ID: {templateId}</p>
            </div>
            <Link to="/app/templates" className="glass action-link">← Назад</Link>
          </div>

          {detailQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {detailQuery.isError && <p style={{ color: '#f07373' }}>Ошибка: {(detailQuery.error as Error).message}</p>}

          {!detailQuery.isLoading && (
            <>
              <label style={{ display: 'grid', gap: 6 }}>
                Ключ
                <input value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value })} />
              </label>

              <label style={{ display: 'grid', gap: 6 }}>
                Быстрый пресет
                <select
                  value={presetKey}
                  onChange={(e) => {
                    const key = e.target.value
                    setPresetKey(key)
                    if (key && presets?.[key]) {
                      setForm((prev) => ({ ...prev, key, text: presets[key] }))
                    }
                  }}
                >
                  <option value="">— не выбирать —</option>
                  {presets && Object.keys(presets).map((key) => (
                    <option key={key} value={key}>{key}</option>
                  ))}
                </select>
              </label>

              <label style={{ display: 'grid', gap: 6 }}>
                Текст шаблона
                <textarea
                  ref={textareaRef}
                  rows={8}
                  value={form.text}
                  onChange={(e) => setForm({ ...form, text: e.target.value })}
                />
                <div className="action-row" style={{ gap: 8, flexWrap: 'wrap' }}>
                  {availableVars.map((v) => (
                    <button key={v} type="button" className="ui-btn ui-btn--ghost" onClick={() => insertToken(`{{${v}}}`)}>
                      {v}
                    </button>
                  ))}
                </div>
                <div className="action-row" style={{ justifyContent: 'space-between' }}>
                  <span className="subtitle">Символы: {charCount} / 4096</span>
                  {charCount > 4096 && <span style={{ color: '#f07373' }}>Превышен лимит Telegram</span>}
                </div>
              </label>

              <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={form.is_global}
                  onChange={(e) => setForm({ ...form, is_global: e.target.checked })}
                  disabled={!hasCities}
                />
                Глобальный шаблон
              </label>

              {!form.is_global && (
                <label style={{ display: 'grid', gap: 6 }}>
                  Город
                  <input
                    placeholder="Поиск по городам…"
                    value={cityFilter}
                    onChange={(e) => setCityFilter(e.target.value)}
                  />
                  <select value={form.city_id} onChange={(e) => setForm({ ...form, city_id: e.target.value })}>
                    <option value="">— выберите —</option>
                    {filteredCities.map((c) => (
                      <option key={c.value} value={String(c.value)}>{c.label}</option>
                    ))}
                  </select>
                </label>
              )}

              <details className="glass panel--tight">
                <summary>Предпросмотр (Jinja2)</summary>
                <div style={{ padding: 12 }}>
                    <button 
                        type="button"
                        className="ui-btn ui-btn--ghost ui-btn--sm" 
                        onClick={() => previewMutation.mutate()} 
                        disabled={previewMutation.isPending}
                    >
                        {previewMutation.isPending ? 'Загрузка...' : 'Обновить'}
                    </button>
                    {serverPreview && (
                        <div 
                            className="glass" 
                            style={{ marginTop: 12, padding: 12, whiteSpace: 'pre-wrap' }} 
                            dangerouslySetInnerHTML={{ __html: serverPreview }} 
                        />
                    )}
                </div>
              </details>

              <div className="action-row">
                <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
                  {mutation.isPending ? 'Сохраняем…' : 'Сохранить'}
                </button>
                <button
                  className="ui-btn ui-btn--danger"
                  onClick={() => window.confirm('Удалить шаблон?') && deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending ? 'Удаляем…' : 'Удалить'}
                </button>
              </div>
              {formError && <p style={{ color: '#f07373' }}>Ошибка: {formError}</p>}
              {deleteMutation.isError && <p style={{ color: '#f07373' }}>Ошибка: {(deleteMutation.error as Error).message}</p>}
            </>
          )}
        </div>
      </div>
    </RoleGuard>
  )
}
