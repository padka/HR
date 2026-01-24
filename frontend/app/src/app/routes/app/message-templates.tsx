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
  updated_by?: string | null
  preview?: string | null
  body?: string | null
}

type MessageTemplatesPayload = {
  templates: MessageTemplate[]
  missing_required: string[]
  known_hints: Record<string, string>
  cities: { id: number | null; name: string }[]
  filters: { city: string | number | null; key: string; channel: string; status: string }
  variables: string[]
  mock_context: Record<string, string>
  coverage: Array<{ key: string; missing_default: boolean; missing_cities: { id: number; name: string }[] }>
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
    city: '',
    key: '',
    channel: '',
    status: '',
  })

  const queryString = useMemo(() => {
    const params = new URLSearchParams()
    if (filters.city) params.set('city', filters.city)
    if (filters.key) params.set('key', filters.key)
    if (filters.channel) params.set('channel', filters.channel)
    if (filters.status) params.set('status', filters.status)
    return params.toString()
  }, [filters])

  const { data, isLoading, isError, error, refetch } = useQuery<MessageTemplatesPayload>({
    queryKey: ['message-templates', filters],
    queryFn: () => apiFetch(`/message-templates${queryString ? `?${queryString}` : ''}`),
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
    onSuccess: () => {
      resetEditor()
      refetch()
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
    onSuccess: () => {
      resetEditor()
      refetch()
    },
  })

  const historyQuery = useQuery<{ items: TemplateHistoryItem[] }>({
    queryKey: ['message-template-history', editor.id],
    queryFn: () => apiFetch(`/message-templates/${editor.id}/history`),
    enabled: Boolean(editor.id),
  })

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <div className="glass panel" style={{ display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <h1 className="title">Шаблоны уведомлений</h1>
            <Link to="/app/templates" className="glass action-link">← К обычным шаблонам</Link>
          </div>
          <div className="action-row">
            <input
              placeholder="Ключ"
              value={filters.key}
              onChange={(e) => setFilters({ ...filters, key: e.target.value })}
            />
            <select value={filters.city} onChange={(e) => setFilters({ ...filters, city: e.target.value })}>
              <option value="">Все города</option>
              <option value="default">Только общий</option>
              {(data?.cities || []).map((c) => (
                <option key={String(c.id)} value={String(c.id)}>{c.name}</option>
              ))}
            </select>
            <select value={filters.channel} onChange={(e) => setFilters({ ...filters, channel: e.target.value })}>
              <option value="">Все каналы</option>
              <option value="tg">TG</option>
              <option value="sms">SMS</option>
              <option value="email">Email</option>
            </select>
            <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
              <option value="">Все статусы</option>
              <option value="active">Активные</option>
              <option value="draft">Черновики</option>
            </select>
          </div>

          {isLoading && <p className="subtitle">Загрузка…</p>}
          {isError && <p style={{ color: '#f07373' }}>Ошибка: {(error as Error).message}</p>}
          {data && (
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Ключ</th>
                  <th>Город</th>
                  <th>Канал</th>
                  <th>Версия</th>
                  <th>Статус</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {data.templates.map((tmpl) => (
                  <tr key={tmpl.id} className="glass">
                    <td>{tmpl.id}</td>
                    <td>{tmpl.key}</td>
                    <td>{tmpl.city_name || 'Общий'}</td>
                    <td>{tmpl.channel}</td>
                    <td>{tmpl.version ?? '—'}</td>
                    <td>{tmpl.is_active ? 'Активен' : 'Черновик'}</td>
                    <td>
                      <button className="ui-btn ui-btn--ghost" onClick={() => selectTemplate(tmpl)}>
                        Редактировать
                      </button>
                      <button
                        className="ui-btn ui-btn--danger"
                        onClick={() => window.confirm('Удалить шаблон?') && deleteMutation.mutate(tmpl.id)}
                        disabled={deleteMutation.isPending}
                      >
                        Удалить
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="glass panel" style={{ display: 'grid', gap: 12 }}>
          <h2 className="title" style={{ fontSize: 20 }}>{editor.id ? 'Редактирование' : 'Новый шаблон'}</h2>
          <label style={{ display: 'grid', gap: 6 }}>
            Ключ
            <input value={editor.key} onChange={(e) => setEditor({ ...editor, key: e.target.value })} />
          </label>
          <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))' }}>
            <label style={{ display: 'grid', gap: 6 }}>
              Локаль
              <input value={editor.locale} onChange={(e) => setEditor({ ...editor, locale: e.target.value })} />
            </label>
            <label style={{ display: 'grid', gap: 6 }}>
              Канал
              <input value={editor.channel} onChange={(e) => setEditor({ ...editor, channel: e.target.value })} />
            </label>
            <label style={{ display: 'grid', gap: 6 }}>
              Версия
              <input value={editor.version} onChange={(e) => setEditor({ ...editor, version: e.target.value })} />
            </label>
            <label style={{ display: 'grid', gap: 6 }}>
              Город
              <select value={editor.city_id} onChange={(e) => setEditor({ ...editor, city_id: e.target.value })}>
                <option value="">Общий</option>
                {(data?.cities || []).map((c) => (
                  <option key={String(c.id)} value={String(c.id)}>{c.name}</option>
                ))}
              </select>
            </label>
          </div>
          <label style={{ display: 'grid', gap: 6 }}>
            Текст
            <textarea rows={6} value={editor.body} onChange={(e) => setEditor({ ...editor, body: e.target.value })} />
          </label>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={editor.is_active}
              onChange={(e) => setEditor({ ...editor, is_active: e.target.checked })}
            />
            Активен
          </label>
          <div className="action-row">
            <button className="ui-btn ui-btn--primary" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? 'Сохраняем…' : 'Сохранить'}
            </button>
            <button className="ui-btn ui-btn--ghost" onClick={resetEditor}>Очистить</button>
          </div>
          {formError && <p style={{ color: '#f07373' }}>Ошибка: {formError}</p>}
          {editor.id ? (
            <div className="glass panel--tight" style={{ display: 'grid', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <strong>История изменений</strong>
                <button className="ui-btn ui-btn--ghost" onClick={() => historyQuery.refetch()}>
                  Обновить
                </button>
              </div>
              {historyQuery.isLoading && <p className="subtitle">Загрузка истории…</p>}
              {historyQuery.isError && <p style={{ color: '#f07373' }}>Ошибка: {(historyQuery.error as Error).message}</p>}
              {historyQuery.data?.items?.length ? (
                <div style={{ display: 'grid', gap: 10 }}>
                  {historyQuery.data.items.map((item) => (
                    <div key={item.id} className="glass" style={{ padding: 12 }}>
                      <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                        {new Date(item.updated_at).toLocaleString('ru-RU')} · {item.updated_by || 'system'}
                      </div>
                      <div style={{ marginTop: 6, whiteSpace: 'pre-wrap' }}>{item.body}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="subtitle">История изменений пока пуста.</p>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </RoleGuard>
  )
}
