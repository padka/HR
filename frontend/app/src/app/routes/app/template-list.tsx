import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'

type TemplateItem = {
  id: number
  key: string
  city_id?: number | null
  city_name?: string | null
  city_name_plain?: string | null
  is_global?: boolean
  preview?: string
  length?: number
}

type StageItem = {
  key: string
  title: string
  description: string
  value: string
  default: string
  is_custom: boolean
}

type StageCity = {
  city: { id: number; name: string; tz?: string | null }
  stages: StageItem[]
}

type TemplatesOverview = {
  cities: StageCity[]
  global: { stages: StageItem[] }
}

type TemplateOverview = {
  overview?: TemplatesOverview
  custom_templates: TemplateItem[]
}

type MessageTemplateSummary = {
  templates: Array<{
    id: number
    key: string
    locale: string
    channel: string
    city_id?: number | null
    city_name?: string | null
    version?: number
    is_active?: boolean
    updated_by?: string | null
    preview?: string | null
    body?: string | null
    stage?: string
  }>
  missing_required: string[]
  coverage: Array<{ key: string; missing_default: boolean; missing_cities: { id: number; name: string }[] }>
}

export function TemplateListPage() {
  const queryClient = useQueryClient()
  const { data, isLoading, isError, error } = useQuery<TemplateOverview>({
    queryKey: ['templates-list'],
    queryFn: () => apiFetch('/templates/list'),
  })
  const messageTemplatesQuery = useQuery<MessageTemplateSummary>({
    queryKey: ['message-templates-summary'],
    queryFn: () => apiFetch('/message-templates'),
  })

  const overview = data?.overview
  const [stageCity, setStageCity] = useState<string>('global')
  const [stageDrafts, setStageDrafts] = useState<Record<string, string>>({})
  const [filters, setFilters] = useState({ search: '', city: 'all', key: '' })
  const [messageFilters, setMessageFilters] = useState({ search: '', stage: 'all' })

  const stageCityOptions = useMemo(() => {
    const cityList = overview?.cities || []
    return [
      { id: 'global', name: 'Глобальные' },
      ...cityList.map((item: any) => ({ id: String(item.city?.id ?? ''), name: item.city?.name ?? 'Город' })),
    ]
  }, [overview])

  useEffect(() => {
    if (!overview) return
    const cityEntry =
      stageCity === 'global'
        ? overview.global
        : (overview.cities || []).find((item: any) => String(item.city?.id) === stageCity)
    const stages = cityEntry?.stages || []
    const nextDrafts: Record<string, string> = {}
    stages.forEach((stage: any) => {
      nextDrafts[stage.key] = stage.value || ''
    })
    setStageDrafts(nextDrafts)
  }, [overview, stageCity])

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        city_id: stageCity === 'global' ? null : Number(stageCity),
        templates: stageDrafts,
      }
      return apiFetch('/templates/save', { method: 'POST', body: JSON.stringify(payload) })
    },
  })

  const cityFilterOptions = useMemo(() => {
    const cities = data?.custom_templates || []
    const unique = new Map<number, string>()
    cities.forEach((tmpl) => {
      if (tmpl.city_id != null) {
        unique.set(tmpl.city_id, tmpl.city_name_plain || tmpl.city_name || `Город ${tmpl.city_id}`)
      }
    })
    return Array.from(unique.entries()).map(([id, name]) => ({ id: String(id), name }))
  }, [data?.custom_templates])

  const keyOptions = useMemo(() => {
    const keys = new Set<string>()
    ;(data?.custom_templates || []).forEach((tmpl) => keys.add(tmpl.key))
    return Array.from(keys.values()).sort()
  }, [data?.custom_templates])

  const filteredTemplates = useMemo(() => {
    const items = data?.custom_templates || []
    const search = filters.search.trim().toLowerCase()
    return items.filter((tmpl) => {
      const matchesSearch =
        !search ||
        tmpl.key.toLowerCase().includes(search) ||
        (tmpl.preview || '').toLowerCase().includes(search)
      const matchesCity =
        filters.city === 'all' ||
        (filters.city === 'global' ? tmpl.is_global : String(tmpl.city_id) === filters.city)
      const matchesKey = !filters.key || tmpl.key === filters.key
      return matchesSearch && matchesCity && matchesKey
    })
  }, [data?.custom_templates, filters])

  const stageSpecs = useMemo(
    () => [
      { code: 'interview', title: 'Этап 1: Собеседование', desc: 'Приглашения, подтверждения слота, итоги.' },
      { code: 'intro', title: 'Этап 2: Ознакомительный день', desc: 'Приглашения, адреса, инструкции.' },
      { code: 'reminder', title: 'Напоминания', desc: 'Сообщения за 6/2 часа, подтверждения.' },
      { code: 'other', title: 'Прочее', desc: 'Сервисные тексты, отказы, общие уведомления.' },
    ],
    [],
  )

  const filteredMessageTemplates = useMemo(() => {
    const items = messageTemplatesQuery.data?.templates || []
    const search = messageFilters.search.trim().toLowerCase()
    return items.filter((tmpl) => {
      const matchesStage =
        messageFilters.stage === 'all' || (tmpl.stage || 'other') === messageFilters.stage
      const matchesSearch =
        !search ||
        tmpl.key.toLowerCase().includes(search) ||
        (tmpl.preview || '').toLowerCase().includes(search) ||
        (tmpl.body || '').toLowerCase().includes(search)
      return matchesStage && matchesSearch
    })
  }, [messageTemplatesQuery.data?.templates, messageFilters])

  const groupedTemplates = useMemo(() => {
    const grouped: Record<string, MessageTemplateSummary['templates']> = {
      interview: [],
      intro: [],
      reminder: [],
      other: [],
    }
    filteredMessageTemplates.forEach((tmpl) => {
      const key = tmpl.stage || 'other'
      if (!grouped[key]) {
        grouped[key] = []
      }
      grouped[key].push(tmpl)
    })
    return grouped
  }, [filteredMessageTemplates])

  const toggleMutation = useMutation({
    mutationFn: async (tmpl: MessageTemplateSummary['templates'][number]) => {
      const payload = {
        key: tmpl.key,
        locale: tmpl.locale,
        channel: tmpl.channel,
        body: tmpl.body || '',
        is_active: !tmpl.is_active,
        city_id: tmpl.city_id ?? null,
        updated_by: 'admin',
        version: tmpl.version ?? null,
      }
      return apiFetch(`/message-templates/${tmpl.id}`, { method: 'PUT', body: JSON.stringify(payload) })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['message-templates-summary'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (tmplId: number) =>
      apiFetch(`/message-templates/${tmplId}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['message-templates-summary'] })
    },
  })

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <div className="glass panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <h1 className="title">Шаблоны (CRM)</h1>
            <Link to="/app/templates/new" className="glass action-link">+ Новый</Link>
          </div>
          {overview && (
            <div className="glass panel--tight" style={{ marginTop: 12, display: 'grid', gap: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                <div>
                  <h2 className="section-title">Stage templates</h2>
                  <p className="subtitle">Редактируйте шаблоны этапов по городам или глобально.</p>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <select value={stageCity} onChange={(e) => setStageCity(e.target.value)}>
                    {stageCityOptions.map((opt) => (
                      <option key={opt.id} value={opt.id}>{opt.name}</option>
                    ))}
                  </select>
                  <button className="ui-btn ui-btn--primary" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
                    {saveMutation.isPending ? 'Сохраняем…' : 'Сохранить'}
                  </button>
                </div>
              </div>
              <div style={{ display: 'grid', gap: 12 }}>
                {(stageCity === 'global' ? overview.global?.stages : (overview.cities || []).find((item: any) => String(item.city?.id) === stageCity)?.stages || []).map((stage: any) => (
                  <div key={stage.key} className="glass" style={{ padding: 12, display: 'grid', gap: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <div>
                        <strong>{stage.title}</strong>
                        <div className="subtitle">{stage.description}</div>
                      </div>
                      <span className="chip">{stage.is_custom ? 'custom' : 'default'}</span>
                    </div>
                    <textarea
                      rows={4}
                      value={stageDrafts[stage.key] ?? ''}
                      onChange={(e) => setStageDrafts((prev) => ({ ...prev, [stage.key]: e.target.value }))}
                    />
                  </div>
                ))}
              </div>
              {saveMutation.isError && <p style={{ color: '#f07373' }}>Ошибка: {(saveMutation.error as Error).message}</p>}
            </div>
          )}
          {isLoading && <p className="subtitle">Загрузка…</p>}
          {isError && <p style={{ color: '#f07373' }}>Ошибка: {(error as Error).message}</p>}
          {data && (
            <>
              <div className="glass panel--tight" style={{ marginTop: 12, display: 'grid', gap: 10 }}>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  <input
                    placeholder="Поиск по ключу или тексту"
                    value={filters.search}
                    onChange={(e) => setFilters((prev) => ({ ...prev, search: e.target.value }))}
                  />
                  <select
                    value={filters.city}
                    onChange={(e) => setFilters((prev) => ({ ...prev, city: e.target.value }))}
                  >
                    <option value="all">Все города</option>
                    <option value="global">Только global</option>
                    {cityFilterOptions.map((city) => (
                      <option key={city.id} value={city.id}>{city.name}</option>
                    ))}
                  </select>
                  <select
                    value={filters.key}
                    onChange={(e) => setFilters((prev) => ({ ...prev, key: e.target.value }))}
                  >
                    <option value="">Все ключи</option>
                    {keyOptions.map((key) => (
                      <option key={key} value={key}>{key}</option>
                    ))}
                  </select>
                </div>
                <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
                  <div className="glass stat-card">
                    <div className="stat-label">Всего шаблонов</div>
                    <div className="stat-value">{data.custom_templates.length}</div>
                  </div>
                  <div className="glass stat-card">
                    <div className="stat-label">Global</div>
                    <div className="stat-value">{data.custom_templates.filter((t) => t.is_global).length}</div>
                  </div>
                  <div className="glass stat-card">
                    <div className="stat-label">Городские</div>
                    <div className="stat-value">{data.custom_templates.filter((t) => !t.is_global).length}</div>
                  </div>
                  <div className="glass stat-card">
                    <div className="stat-label">Missing required (TG)</div>
                    <div className="stat-value">{messageTemplatesQuery.data?.missing_required?.length ?? '—'}</div>
                  </div>
                </div>
              </div>

            <div className="glass panel--tight" style={{ marginTop: 12, display: 'grid', gap: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                <div>
                  <h2 className="section-title">Уведомления: контроль</h2>
                  <p className="subtitle">Проверка обязательных ключей и покрытие по городам.</p>
                </div>
                <Link to="/app/message-templates" className="glass action-link">Открыть уведомления →</Link>
              </div>
              {messageTemplatesQuery.isLoading && <p className="subtitle">Загрузка…</p>}
              {messageTemplatesQuery.isError && (
                <p style={{ color: '#f07373' }}>Ошибка: {(messageTemplatesQuery.error as Error).message}</p>
              )}
              {messageTemplatesQuery.data && (
                <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
                  <div className="glass stat-card">
                    <div className="stat-label">Missing required keys</div>
                    <div className="stat-value">
                      {messageTemplatesQuery.data.missing_required.length || 0}
                    </div>
                    <div className="subtitle" style={{ marginTop: 6 }}>
                      {messageTemplatesQuery.data.missing_required.length
                        ? messageTemplatesQuery.data.missing_required.join(', ')
                        : 'Все обязательные ключи есть'}
                    </div>
                  </div>
                  <div className="glass stat-card">
                    <div className="stat-label">Coverage gaps</div>
                    <div className="stat-value">
                      {messageTemplatesQuery.data.coverage.length || 0}
                    </div>
                    <div className="subtitle" style={{ marginTop: 6 }}>
                      {messageTemplatesQuery.data.coverage.length
                        ? `Проблемные ключи: ${messageTemplatesQuery.data.coverage
                            .slice(0, 4)
                            .map((item) => item.key)
                            .join(', ')}${messageTemplatesQuery.data.coverage.length > 4 ? '…' : ''}`
                        : 'Покрытие без пропусков'}
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="glass panel--tight" style={{ marginTop: 12, display: 'grid', gap: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                <div>
                  <h2 className="section-title">Уведомления</h2>
                  <p className="subtitle">Шаблоны сообщений, которые видят кандидаты и рекрутёры.</p>
                </div>
                <Link to="/app/message-templates" className="glass action-link">+ Новое уведомление</Link>
              </div>
              <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
                {stageSpecs.map((stage) => (
                  <div key={stage.code} className="glass stat-card">
                    <div className="stat-label">{stage.title}</div>
                    <div className="subtitle" style={{ marginTop: 6 }}>{stage.desc}</div>
                  </div>
                ))}
              </div>
              <div className="glass panel--tight" style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                <input
                  placeholder="Поиск по ключу или тексту"
                  value={messageFilters.search}
                  onChange={(e) => setMessageFilters((prev) => ({ ...prev, search: e.target.value }))}
                />
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    className="ui-btn ui-btn--ghost"
                    onClick={() => setMessageFilters((prev) => ({ ...prev, stage: 'all' }))}
                  >
                    Все этапы
                  </button>
                  {stageSpecs.map((stage) => (
                    <button
                      key={stage.code}
                      type="button"
                      className="ui-btn ui-btn--ghost"
                      onClick={() => setMessageFilters((prev) => ({ ...prev, stage: stage.code }))}
                    >
                      {stage.title}
                    </button>
                  ))}
                </div>
              </div>

              {stageSpecs.map((stage) => {
                const items = groupedTemplates[stage.code] || []
                if (!items.length) return null
                return (
                  <div key={stage.code} style={{ display: 'grid', gap: 10 }}>
                    <div>
                      <h3 className="section-title">{stage.title}</h3>
                      <p className="subtitle">{stage.desc}</p>
                    </div>
                    <div className="template-grid">
                      {items.map((tmpl) => (
                        <div key={tmpl.id} className="glass template-card">
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                            <div>
                              <div className="template-key">
                                <code>{tmpl.key}</code>
                              </div>
                              <div className="template-tags">
                                <span className="chip">{tmpl.channel?.toUpperCase?.() || 'TG'}</span>
                                <span className="chip">{tmpl.locale || 'ru'}</span>
                                <span className="chip">{tmpl.city_name || 'Общий'}</span>
                                <span className="chip">v{tmpl.version ?? '—'}</span>
                              </div>
                            </div>
                            <label className="template-toggle">
                              <input
                                type="checkbox"
                                checked={Boolean(tmpl.is_active)}
                                onChange={() => toggleMutation.mutate(tmpl)}
                                disabled={toggleMutation.isPending}
                              />
                              <span>{tmpl.is_active ? 'Активен' : 'Отключён'}</span>
                            </label>
                          </div>
                          <div className="template-preview">{tmpl.preview || '—'}</div>
                          <div className="template-actions">
                            <Link to="/app/message-templates" className="ui-btn ui-btn--ghost">
                              Редактировать
                            </Link>
                            <button
                              className="ui-btn ui-btn--danger"
                              onClick={() => window.confirm('Удалить шаблон?') && deleteMutation.mutate(tmpl.id)}
                              disabled={deleteMutation.isPending}
                            >
                              Удалить
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
              {filteredMessageTemplates.length === 0 && (
                <p className="subtitle">По выбранным фильтрам уведомления не найдены.</p>
              )}
            </div>

            <table className="table" style={{ marginTop: 12 }}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Ключ</th>
                  <th>Город</th>
                  <th>Preview</th>
                  <th>Длина</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {filteredTemplates.map((tmpl) => (
                  <tr key={tmpl.id} className="glass">
                    <td>{tmpl.id}</td>
                    <td>{tmpl.key}</td>
                    <td>{tmpl.city_name || (tmpl.is_global ? 'Global' : '—')}</td>
                    <td>{tmpl.preview || '—'}</td>
                    <td>{tmpl.length ?? '—'}</td>
                    <td>
                      <Link to="/app/templates/$templateId/edit" params={{ templateId: String(tmpl.id) }}>
                        Редактировать
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredTemplates.length === 0 && (
              <p className="subtitle">По выбранным фильтрам шаблоны не найдены.</p>
            )}
          </>
          )}
        </div>
      </div>
    </RoleGuard>
  )
}
