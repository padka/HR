import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import { STAGE_LABELS, TEMPLATE_META, templateTitle, type TemplateStage } from './template_meta'

type City = { id: number; name: string }
type TemplateDetail = {
  id: number
  key: string
  text: string
  city_id?: number | null
  is_global?: boolean
  is_active?: boolean
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

export function TemplateEditPage() {
  const params = useParams({ from: '/app/templates/$templateId/edit' })
  const templateId = Number(params.templateId)
  const navigate = useNavigate()

  const { data: cities } = useQuery<City[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
  })
  const { data: contextMap } = useQuery<Record<string, string[]>>({
    queryKey: ['template-context-keys'],
    queryFn: () => apiFetch('/message-templates/context-keys'),
  })

  const detailQuery = useQuery<TemplateDetail>({
    queryKey: ['template-detail', templateId],
    queryFn: () => apiFetch(`/templates/${templateId}`),
  })

  // State declarations BEFORE any useMemo that depends on them
  const [form, setForm] = useState({
    key: '',
    text: '',
    city_id: '',
    is_active: true,
  })
  const [formError, setFormError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  const charCount = form.text.length

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

  useEffect(() => {
    if (!detailQuery.data) return
    setForm({
      key: detailQuery.data.key,
      text: detailQuery.data.text,
      city_id: detailQuery.data.city_id != null ? String(detailQuery.data.city_id) : '',
      is_active: detailQuery.data.is_active ?? true,
    })
  }, [detailQuery.data])

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

  const [serverPreview, setServerPreview] = useState<string | null>(null)

  const previewMutation = useMutation({
    mutationFn: async () => apiFetch('/message-templates/preview', {
      method: 'POST',
      body: JSON.stringify({
        text: form.text,
        key: form.key,
        city_id: form.city_id ? Number(form.city_id) : null,
      }),
    }),
    onSuccess: (data: any) => setServerPreview(data.html),
  })

  const title = templateTitle(form.key)
  const hasHumanTitle = title !== form.key

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <div className="glass panel" style={{ display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <div>
              <h1 className="title">
                {hasHumanTitle ? title : 'Редактирование шаблона'}
              </h1>
              <p className="subtitle">
                ID: {templateId}
                {hasHumanTitle && <> &middot; <code>{form.key}</code></>}
              </p>
            </div>
            <Link to="/app/templates" className="glass action-link">← Назад</Link>
          </div>

          {detailQuery.isLoading && <p className="subtitle">Загрузка...</p>}
          {detailQuery.isError && <p style={{ color: '#f07373' }}>Ошибка: {(detailQuery.error as Error).message}</p>}

          {!detailQuery.isLoading && detailQuery.data && (
            <>
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
                  {availableVars.length > 0
                    ? availableVars.map((v) => (
                        <button key={v} type="button" className="ui-btn ui-btn--ghost" onClick={() => insertToken(`{{${v}}}`)}>
                          {v}
                        </button>
                      ))
                    : PLACEHOLDERS.map((token) => (
                        <button key={token} type="button" className="ui-btn ui-btn--ghost" onClick={() => insertToken(token)}>
                          {token}
                        </button>
                      ))
                  }
                </div>
                <div className="action-row" style={{ justifyContent: 'space-between' }}>
                  <span className="subtitle">Символы: {charCount} / 4096</span>
                  {charCount > 4096 && <span style={{ color: '#f07373' }}>Превышен лимит Telegram</span>}
                </div>
              </label>

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
                    <pre
                      className="glass"
                      style={{ marginTop: 12, padding: 12, whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}
                    >
                      {serverPreview}
                    </pre>
                  )}
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
                <div className="action-row">
                  <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
                    {mutation.isPending ? 'Сохраняем...' : 'Сохранить'}
                  </button>
                  <button
                    className="ui-btn ui-btn--danger"
                    onClick={() => window.confirm('Удалить шаблон?') && deleteMutation.mutate()}
                    disabled={deleteMutation.isPending}
                  >
                    {deleteMutation.isPending ? 'Удаляем...' : 'Удалить'}
                  </button>
                </div>
              </div>
              {formError && <p style={{ color: '#f07373' }}>Ошибка: {formError}</p>}
              {deleteMutation.isError && <p style={{ color: '#f07373' }}>Ошибка: {(deleteMutation.error as Error).message}</p>}
            </>
          )}

          {!detailQuery.isLoading && !detailQuery.data && !detailQuery.isError && (
            <p className="text-muted">Шаблон не найден.</p>
          )}
        </div>
      </div>
    </RoleGuard>
  )
}
