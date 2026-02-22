import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'

type MessageTemplate = {
  id: number
  key: string
  locale: string
  channel: string
  city_id?: number | null
  city_name?: string | null
  version?: number
  is_active?: boolean
  updated_at?: string | null
  body?: string | null
}

type MessageTemplatesPayload = {
  templates: MessageTemplate[]
  cities: { id: number | null; name: string }[]
}

type TemplateHistoryItem = {
  id: number
  template_id: number
  updated_at: string
  updated_by?: string | null
  body: string
}

export function MessageTemplatesPage() {
  const [filters, setFilters] = useState({
    key: '',
    city: '',
    status: '',
  })

  const [editor, setEditor] = useState({
    id: 0,
    key: '',
    locale: 'ru',
    channel: 'tg',
    city_id: '',
    version: '',
    is_active: true,
    body: '',
  })
  const [formError, setFormError] = useState<string | null>(null)

  const queryString = useMemo(() => {
    const params = new URLSearchParams()
    if (filters.city) params.set('city', filters.city)
    if (filters.key) params.set('key', filters.key)
    params.set('channel', 'tg')
    if (filters.status) params.set('status', filters.status)
    return params.toString()
  }, [filters])

  const templatesQuery = useQuery<MessageTemplatesPayload>({
    queryKey: ['message-templates', filters],
    queryFn: () => apiFetch(`/message-templates?${queryString}`),
  })

  const selectTemplate = (tmpl: MessageTemplate) => {
    setEditor({
      id: tmpl.id,
      key: tmpl.key,
      locale: tmpl.locale || 'ru',
      channel: tmpl.channel || 'tg',
      city_id: tmpl.city_id != null ? String(tmpl.city_id) : '',
      version: tmpl.version != null ? String(tmpl.version) : '',
      is_active: Boolean(tmpl.is_active),
      body: tmpl.body || '',
    })
    setFormError(null)
  }

  const resetEditor = () => {
    setEditor({
      id: 0,
      key: '',
      locale: 'ru',
      channel: 'tg',
      city_id: '',
      version: '',
      is_active: true,
      body: '',
    })
    setFormError(null)
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        key: editor.key,
        locale: editor.locale,
        channel: editor.channel,
        body: editor.body,
        city_id: editor.city_id ? Number(editor.city_id) : null,
        version: editor.version ? Number(editor.version) : null,
        is_active: editor.is_active,
        updated_by: 'admin',
      }
      if (editor.id) {
        return apiFetch(`/message-templates/${editor.id}`, { method: 'PUT', body: JSON.stringify(payload) })
      }
      return apiFetch('/message-templates', { method: 'POST', body: JSON.stringify(payload) })
    },
    onSuccess: async () => {
      resetEditor()
      await templatesQuery.refetch()
    },
    onError: (err) => {
      let message = err instanceof Error ? err.message : 'Ошибка'
      try {
        const parsed = JSON.parse(message)
        if (parsed?.errors) {
          message = parsed.errors.join(', ')
        } else if (parsed?.error) {
          message = parsed.error
        }
      } catch {
        // ignore parsing errors
      }
      setFormError(message)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => apiFetch(`/message-templates/${id}`, { method: 'DELETE' }),
    onSuccess: async () => {
      if (editor.id) resetEditor()
      await templatesQuery.refetch()
    },
  })

  const historyQuery = useQuery<{ items: TemplateHistoryItem[] }>({
    queryKey: ['message-template-history', editor.id],
    queryFn: () => apiFetch(`/message-templates/${editor.id}/history`),
    enabled: Boolean(editor.id),
  })

  return (
    <RoleGuard allow={['admin']}>
      <div className="page" style={{ display: 'grid', gap: 12 }}>
        <section className="glass panel" style={{ display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <div>
              <h1 className="title">Шаблоны уведомлений</h1>
              <p className="subtitle">Упрощенный режим: выберите шаблон слева, редактируйте справа.</p>
            </div>
            <Link to="/app/templates" className="ui-btn ui-btn--ghost ui-btn--sm">К системным шаблонам</Link>
          </div>

          <div className="action-row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <input
              placeholder="Поиск по ключу"
              value={filters.key}
              onChange={(e) => setFilters((prev) => ({ ...prev, key: e.target.value }))}
              style={{ minWidth: 240 }}
            />
            <select value={filters.city} onChange={(e) => setFilters((prev) => ({ ...prev, city: e.target.value }))}>
              <option value="">Все города</option>
              <option value="default">Общий</option>
              {(templatesQuery.data?.cities || []).map((c) => (
                <option key={String(c.id)} value={String(c.id)}>{c.name}</option>
              ))}
            </select>
            <select value={filters.status} onChange={(e) => setFilters((prev) => ({ ...prev, status: e.target.value }))}>
              <option value="">Все статусы</option>
              <option value="active">Активные</option>
              <option value="draft">Черновики</option>
            </select>
            <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => templatesQuery.refetch()}>
              Обновить
            </button>
          </div>

          {templatesQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {templatesQuery.isError && <p className="text-danger">Ошибка: {(templatesQuery.error as Error).message}</p>}

          {!!templatesQuery.data && (
            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Ключ</th>
                    <th>Город</th>
                    <th>Версия</th>
                    <th>Статус</th>
                    <th>Действие</th>
                  </tr>
                </thead>
                <tbody>
                  {templatesQuery.data.templates.length === 0 && (
                    <tr>
                      <td colSpan={5} className="text-muted">Ничего не найдено.</td>
                    </tr>
                  )}
                  {templatesQuery.data.templates.map((tmpl) => (
                    <tr key={tmpl.id} style={editor.id === tmpl.id ? { background: 'rgba(105, 183, 255, 0.12)' } : undefined}>
                      <td>
                        <div style={{ fontWeight: 600 }}>{tmpl.key}</div>
                        <div className="text-muted" style={{ fontSize: 11 }}>ID: {tmpl.id}</div>
                      </td>
                      <td>{tmpl.city_name || 'Общий'}</td>
                      <td>{tmpl.version ?? '—'}</td>
                      <td>
                        <span className={`chip ${tmpl.is_active ? 'chip--success' : 'chip--warning'}`}>
                          {tmpl.is_active ? 'Активен' : 'Черновик'}
                        </span>
                      </td>
                      <td>
                        <div className="action-row" style={{ gap: 6 }}>
                          <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => selectTemplate(tmpl)}>
                            Редактировать
                          </button>
                          <button
                            type="button"
                            className="ui-btn ui-btn--danger ui-btn--sm"
                            onClick={() => window.confirm('Удалить шаблон?') && deleteMutation.mutate(tmpl.id)}
                            disabled={deleteMutation.isPending}
                          >
                            Удалить
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="glass panel" style={{ display: 'grid', gap: 10 }}>
          <h2 className="title" style={{ fontSize: 20 }}>{editor.id ? 'Редактирование шаблона' : 'Новый шаблон'}</h2>

          <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 8 }}>
            <label style={{ display: 'grid', gap: 4 }}>
              Ключ
              <input value={editor.key} onChange={(e) => setEditor((prev) => ({ ...prev, key: e.target.value }))} />
            </label>
            <label style={{ display: 'grid', gap: 4 }}>
              Локаль
              <input value={editor.locale} onChange={(e) => setEditor((prev) => ({ ...prev, locale: e.target.value }))} />
            </label>
            <label style={{ display: 'grid', gap: 4 }}>
              Канал
              <input value={editor.channel} onChange={(e) => setEditor((prev) => ({ ...prev, channel: e.target.value }))} />
            </label>
            <label style={{ display: 'grid', gap: 4 }}>
              Версия
              <input value={editor.version} onChange={(e) => setEditor((prev) => ({ ...prev, version: e.target.value }))} />
            </label>
            <label style={{ display: 'grid', gap: 4 }}>
              Город
              <select value={editor.city_id} onChange={(e) => setEditor((prev) => ({ ...prev, city_id: e.target.value }))}>
                <option value="">Общий</option>
                {(templatesQuery.data?.cities || []).map((c) => (
                  <option key={String(c.id)} value={String(c.id)}>{c.name}</option>
                ))}
              </select>
            </label>
          </div>

          <label style={{ display: 'grid', gap: 4 }}>
            Текст
            <textarea rows={6} value={editor.body} onChange={(e) => setEditor((prev) => ({ ...prev, body: e.target.value }))} />
          </label>

          <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={editor.is_active}
              onChange={(e) => setEditor((prev) => ({ ...prev, is_active: e.target.checked }))}
            />
            Активен
          </label>

          <div className="action-row" style={{ gap: 8 }}>
            <button type="button" className="ui-btn ui-btn--primary" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? 'Сохраняем…' : 'Сохранить'}
            </button>
            <button type="button" className="ui-btn ui-btn--ghost" onClick={resetEditor}>Очистить</button>
          </div>

          {formError && <p className="text-danger">Ошибка: {formError}</p>}

          {editor.id > 0 && (
            <div className="glass panel--tight" style={{ display: 'grid', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <strong>История изменений</strong>
                <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => historyQuery.refetch()}>
                  Обновить
                </button>
              </div>
              {historyQuery.isLoading && <p className="subtitle">Загрузка…</p>}
              {historyQuery.isError && <p className="text-danger">Ошибка: {(historyQuery.error as Error).message}</p>}
              {historyQuery.data?.items?.length ? (
                <div style={{ display: 'grid', gap: 8 }}>
                  {historyQuery.data.items.map((item) => (
                    <div key={item.id} className="glass panel--tight" style={{ padding: 10 }}>
                      <div className="text-muted" style={{ fontSize: 12 }}>
                        {new Date(item.updated_at).toLocaleString('ru-RU')} · {item.updated_by || 'system'}
                      </div>
                      <div style={{ marginTop: 6, whiteSpace: 'pre-wrap' }}>{item.body}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="subtitle">История пока пустая.</p>
              )}
            </div>
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
