import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useProfile } from '@/app/hooks/useProfile'

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
  body?: string | null
  preview?: string | null
  stage?: string | null
  scope?: 'global' | 'city'
  scope_label?: string | null
  can_edit?: boolean
  can_delete?: boolean
}

type TemplateCatalogItem = {
  key: string
  label: string
  default_text: string
  hint?: string | null
  stage?: string | null
  stage_label?: string | null
}

type TemplateHistoryItem = {
  id: number
  version: number
  updated_at: string
  updated_by?: string | null
  body: string
}

type MessageTemplatesPayload = {
  templates: MessageTemplate[]
  cities: { id: number | null; name: string }[]
  variables?: Array<{ name: string; label: string }>
  catalog?: TemplateCatalogItem[]
  stages?: Array<{ key: string; label: string }>
  permissions?: {
    role: 'admin' | 'recruiter'
    can_manage_global?: boolean
    editable_city_ids?: number[]
    editable_keys?: string[]
  }
  missing_required?: string[]
}

type PreviewResponse = {
  ok: boolean
  html?: string
  error?: string
}

type EditorState = {
  id: number
  key: string
  locale: string
  channel: string
  city_id: string
  version: string
  is_active: boolean
  body: string
}

const EMPTY_EDITOR: EditorState = {
  id: 0,
  key: '',
  locale: 'ru',
  channel: 'tg',
  city_id: '',
  version: '',
  is_active: true,
  body: '',
}

function extractApiError(error: unknown): string {
  let message = error instanceof Error ? error.message : 'Ошибка'
  try {
    const parsed = JSON.parse(message)
    if (Array.isArray(parsed?.errors)) return parsed.errors.join(', ')
    if (parsed?.detail?.message) return parsed.detail.message
    if (parsed?.error) return parsed.error
  } catch {
    return message
  }
  return message
}

function stageLabelFor(
  item: { stage?: string | null; stage_label?: string | null },
  stages: Array<{ key: string; label: string }>,
) {
  if (item.stage_label) return item.stage_label
  if (!item.stage) return 'Служебные'
  return stages.find((stage) => stage.key === item.stage)?.label || item.stage
}

export function MessageTemplatesPage() {
  const profile = useProfile()
  const isAdmin = profile.data?.principal.type === 'admin'
  const [filters, setFilters] = useState({
    key: '',
    city: '',
    status: '',
    stage: '',
  })
  const [editor, setEditor] = useState<EditorState>(EMPTY_EDITOR)
  const [formError, setFormError] = useState<string | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [previewHtml, setPreviewHtml] = useState<string>('')

  const queryString = useMemo(() => {
    const params = new URLSearchParams()
    if (filters.city) params.set('city', filters.city)
    if (filters.key) params.set('key', filters.key)
    params.set('channel', 'tg')
    if (filters.status) params.set('status', filters.status)
    return params.toString()
  }, [filters.city, filters.key, filters.status])

  const templatesQuery = useQuery<MessageTemplatesPayload>({
    queryKey: ['message-templates', queryString],
    queryFn: () => apiFetch(`/message-templates?${queryString}`),
  })

  const historyQuery = useQuery<{ items: TemplateHistoryItem[] }>({
    queryKey: ['message-template-history', editor.id],
    queryFn: () => apiFetch(`/message-templates/${editor.id}/history`),
    enabled: editor.id > 0,
  })

  const contextKeysQuery = useQuery<Record<string, string[]>>({
    queryKey: ['message-template-context-keys'],
    queryFn: () => apiFetch('/message-templates/context-keys'),
  })

  const permissions = templatesQuery.data?.permissions
  const editableCityIds = useMemo(() => permissions?.editable_city_ids || [], [permissions?.editable_city_ids])
  const recruiterEditableKeys = useMemo(() => permissions?.editable_keys || [], [permissions?.editable_keys])
  const cities = useMemo(() => templatesQuery.data?.cities || [], [templatesQuery.data?.cities])
  const variables = useMemo(() => templatesQuery.data?.variables || [], [templatesQuery.data?.variables])
  const stages = useMemo(() => templatesQuery.data?.stages || [], [templatesQuery.data?.stages])
  const catalog = useMemo(() => templatesQuery.data?.catalog || [], [templatesQuery.data?.catalog])
  const templateMap = useMemo(
    () => new Map((templatesQuery.data?.templates || []).map((item) => [item.id, item])),
    [templatesQuery.data?.templates],
  )

  const filteredTemplates = useMemo(() => {
    const items = templatesQuery.data?.templates || []
    if (!filters.stage) return items
    return items.filter((item) => (item.stage || 'other') === filters.stage)
  }, [filters.stage, templatesQuery.data?.templates])

  const groupedCatalog = useMemo(() => {
    const result = new Map<string, TemplateCatalogItem[]>()
    for (const item of catalog) {
      const stageKey = item.stage || 'other'
      const group = result.get(stageKey) || []
      group.push(item)
      result.set(stageKey, group)
    }
    return Array.from(result.entries()).map(([stageKey, items]) => ({
      stageKey,
      stageLabel: stageLabelFor({ stage: stageKey }, stages),
      items: items.sort((left, right) => left.label.localeCompare(right.label, 'ru')),
    }))
  }, [catalog, stages])

  const selectedTemplate = editor.id ? templateMap.get(editor.id) : null
  const isReadOnlyTemplate = Boolean(selectedTemplate && selectedTemplate.can_edit === false)
  const canDeleteSelected = Boolean(selectedTemplate?.can_delete)
  const canManageGlobal = Boolean(permissions?.can_manage_global)

  const availableCityOptions = useMemo(() => {
    if (isAdmin) return cities.filter((item) => item.id !== null)
    return cities.filter((item) => item.id !== null && editableCityIds.includes(Number(item.id)))
  }, [cities, editableCityIds, isAdmin])

  const canCreateCurrent = useMemo(() => {
    if (isAdmin) return true
    if (!editor.city_id) return false
    if (editor.key && recruiterEditableKeys.length > 0 && !recruiterEditableKeys.includes(editor.key)) return false
    return editableCityIds.includes(Number(editor.city_id))
  }, [editableCityIds, editor.city_id, editor.key, isAdmin, recruiterEditableKeys])

  useEffect(() => {
    if (isAdmin || editor.city_id || availableCityOptions.length === 0) return
    setEditor((prev) => ({ ...prev, city_id: String(availableCityOptions[0]?.id || '') }))
  }, [availableCityOptions, editor.city_id, isAdmin])

  const resetEditor = () => {
    setEditor({
      ...EMPTY_EDITOR,
      city_id: !isAdmin && availableCityOptions[0]?.id != null ? String(availableCityOptions[0].id) : '',
    })
    setFormError(null)
    setPreviewError(null)
    setPreviewHtml('')
  }

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
    setPreviewError(null)
  }

  const applyPreset = (preset: TemplateCatalogItem) => {
    setEditor((prev) => ({
      ...prev,
      id: 0,
      key: preset.key,
      version: '',
      body: prev.body.trim() ? prev.body : preset.default_text,
    }))
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
      }
      if (editor.id) {
        return apiFetch(`/message-templates/${editor.id}`, { method: 'PUT', body: JSON.stringify(payload) })
      }
      return apiFetch('/message-templates', { method: 'POST', body: JSON.stringify(payload) })
    },
    onSuccess: async () => {
      setFormError(null)
      await templatesQuery.refetch()
      if (editor.id) {
        await historyQuery.refetch()
      } else {
        resetEditor()
      }
    },
    onError: (error) => {
      setFormError(extractApiError(error))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => apiFetch(`/message-templates/${id}`, { method: 'DELETE' }),
    onSuccess: async () => {
      resetEditor()
      await templatesQuery.refetch()
    },
    onError: (error) => {
      setFormError(extractApiError(error))
    },
  })

  const previewMutation = useMutation({
    mutationFn: async () =>
      apiFetch<PreviewResponse>('/message-templates/preview', {
        method: 'POST',
        body: JSON.stringify({
          key: editor.key,
          city_id: editor.city_id ? Number(editor.city_id) : null,
          text: editor.body,
        }),
      }),
    onSuccess: (payload) => {
      setPreviewError(payload.ok ? null : payload.error || 'Не удалось собрать предпросмотр')
      setPreviewHtml(payload.html || '')
    },
    onError: (error) => {
      setPreviewError(extractApiError(error))
      setPreviewHtml('')
    },
  })
  const { mutate: runPreview } = previewMutation

  useEffect(() => {
    if (!editor.key.trim() || !editor.body.trim()) {
      setPreviewHtml('')
      setPreviewError(null)
      return
    }
    const timer = window.setTimeout(() => {
      runPreview()
    }, 350)
    return () => window.clearTimeout(timer)
  }, [editor.body, editor.city_id, editor.key, runPreview])

  return (
    <RoleGuard allow={['admin', 'recruiter']}>
      <div className="page" style={{ display: 'grid', gap: 12 }}>
        <section className="glass panel" style={{ display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ display: 'grid', gap: 6 }}>
              <h1 className="title">Шаблоны сообщений кандидату</h1>
              <p className="subtitle">
                Единый редактор для этапов воронки: шаблоны сгруппированы по шагам, есть live preview, история и подсказки по переменным.
              </p>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <span className="chip">{isAdmin ? 'Роль: администратор' : 'Роль: рекрутер'}</span>
                {!canManageGlobal && <span className="chip chip--warning">Глобальные шаблоны доступны только для чтения</span>}
              </div>
            </div>
            {isAdmin && (
              <Link to="/app/templates" className="ui-btn ui-btn--ghost ui-btn--sm">
                К системным шаблонам
              </Link>
            )}
          </div>

          {(templatesQuery.data?.missing_required || []).length > 0 && (
            <div className="ui-alert ui-alert--warning">
              Неактивные обязательные ключи: {(templatesQuery.data?.missing_required || []).join(', ')}
            </div>
          )}

          <div className="action-row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <input
              placeholder="Поиск по ключу"
              value={filters.key}
              onChange={(event) => setFilters((prev) => ({ ...prev, key: event.target.value }))}
              style={{ minWidth: 220 }}
            />
            <select value={filters.city} onChange={(event) => setFilters((prev) => ({ ...prev, city: event.target.value }))}>
              <option value="">Все области видимости</option>
              <option value="default">Глобальные</option>
              {cities.filter((item) => item.id !== null).map((item) => (
                <option key={String(item.id)} value={String(item.id)}>
                  {item.name}
                </option>
              ))}
            </select>
            <select value={filters.stage} onChange={(event) => setFilters((prev) => ({ ...prev, stage: event.target.value }))}>
              <option value="">Все этапы</option>
              {stages.map((stage) => (
                <option key={stage.key} value={stage.key}>
                  {stage.label}
                </option>
              ))}
            </select>
            <select value={filters.status} onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}>
              <option value="">Все статусы</option>
              <option value="active">Активные</option>
              <option value="draft">Черновики</option>
            </select>
            <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => templatesQuery.refetch()}>
              Обновить
            </button>
            <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={resetEditor}>
              Новый черновик
            </button>
          </div>

          {templatesQuery.isLoading && <p className="subtitle">Загрузка шаблонов…</p>}
          {templatesQuery.isError && <ApiErrorBanner error={templatesQuery.error} title="Не удалось загрузить шаблоны" onRetry={() => templatesQuery.refetch()} />}

          {!!templatesQuery.data && (
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 1.1fr) minmax(340px, 1fr)', gap: 16 }}>
              <div style={{ display: 'grid', gap: 12 }}>
                <div className="glass panel--tight" style={{ padding: 12, display: 'grid', gap: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong>Каталог этапов</strong>
                    <span className="text-muted text-xs">{filteredTemplates.length} шаблонов</span>
                  </div>
                  {groupedCatalog.map((group) => (
                    <div key={group.stageKey} style={{ display: 'grid', gap: 6 }}>
                      <div className="text-muted text-xs">{group.stageLabel}</div>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {group.items.map((item) => (
                          <button
                            key={item.key}
                            type="button"
                            className={`ui-btn ui-btn--ghost ui-btn--sm ${editor.key === item.key ? 'is-active' : ''}`}
                            onClick={() => applyPreset(item)}
                            title={item.hint || item.label}
                          >
                            {item.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="data-table-wrapper">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Этап / ключ</th>
                        <th>Область</th>
                        <th>Статус</th>
                        <th>Действие</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredTemplates.length === 0 && (
                        <tr>
                          <td colSpan={4} className="text-muted">Ничего не найдено.</td>
                        </tr>
                      )}
                      {filteredTemplates.map((tmpl) => (
                        <tr key={tmpl.id} style={editor.id === tmpl.id ? { background: 'rgba(105, 183, 255, 0.12)' } : undefined}>
                          <td>
                            <div style={{ fontWeight: 600 }}>{stageLabelFor(tmpl, stages)}</div>
                            <div className="text-muted" style={{ fontSize: 12 }}>{tmpl.key}</div>
                            {tmpl.preview && <div className="text-muted" style={{ fontSize: 11, marginTop: 4 }}>{tmpl.preview}</div>}
                          </td>
                          <td>
                            <div>{tmpl.city_name || 'Глобальный'}</div>
                            <div className="text-muted" style={{ fontSize: 11 }}>{tmpl.scope_label || tmpl.scope || '—'}</div>
                          </td>
                          <td>
                            <span className={`chip ${tmpl.is_active ? 'chip--success' : 'chip--warning'}`}>
                              {tmpl.is_active ? 'Активен' : 'Черновик'}
                            </span>
                            {tmpl.can_edit === false && <div className="text-muted" style={{ fontSize: 11, marginTop: 4 }}>read only</div>}
                          </td>
                          <td>
                            <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => selectTemplate(tmpl)}>
                              Открыть
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div style={{ display: 'grid', gap: 12 }}>
                <section className="glass panel" style={{ display: 'grid', gap: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                    <div>
                      <h2 className="title" style={{ fontSize: 20 }}>
                        {editor.id ? 'Редактирование шаблона' : 'Новый шаблон'}
                      </h2>
                      {selectedTemplate?.updated_at && (
                        <div className="text-muted text-xs">
                          Обновлён {new Date(selectedTemplate.updated_at).toLocaleString('ru-RU')}
                          {selectedTemplate.updated_by ? ` · ${selectedTemplate.updated_by}` : ''}
                        </div>
                      )}
                    </div>
                    {isReadOnlyTemplate && <span className="chip chip--warning">Только просмотр</span>}
                  </div>

                  <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 8 }}>
                    <label style={{ display: 'grid', gap: 4 }}>
                      Ключ
                      <input value={editor.key} onChange={(event) => setEditor((prev) => ({ ...prev, key: event.target.value }))} disabled={isReadOnlyTemplate} />
                    </label>
                    <label style={{ display: 'grid', gap: 4 }}>
                      Локаль
                      <input value={editor.locale} onChange={(event) => setEditor((prev) => ({ ...prev, locale: event.target.value }))} disabled={isReadOnlyTemplate} />
                    </label>
                    <label style={{ display: 'grid', gap: 4 }}>
                      Канал
                      <input value={editor.channel} onChange={(event) => setEditor((prev) => ({ ...prev, channel: event.target.value }))} disabled={isReadOnlyTemplate} />
                    </label>
                    <label style={{ display: 'grid', gap: 4 }}>
                      Версия
                      <input value={editor.version} onChange={(event) => setEditor((prev) => ({ ...prev, version: event.target.value }))} disabled={isReadOnlyTemplate} />
                    </label>
                    <label style={{ display: 'grid', gap: 4 }}>
                      Город
                      <select value={editor.city_id} onChange={(event) => setEditor((prev) => ({ ...prev, city_id: event.target.value }))} disabled={isReadOnlyTemplate || (!isAdmin && availableCityOptions.length === 0)}>
                        {canManageGlobal && <option value="">Глобальный</option>}
                        {!canManageGlobal && <option value="">Выберите город</option>}
                        {availableCityOptions.map((item) => (
                          <option key={String(item.id)} value={String(item.id)}>
                            {item.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <label style={{ display: 'grid', gap: 4 }}>
                    Текст сообщения
                    <textarea
                      rows={8}
                      value={editor.body}
                      onChange={(event) => setEditor((prev) => ({ ...prev, body: event.target.value }))}
                      disabled={isReadOnlyTemplate}
                    />
                  </label>

                  <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input
                      type="checkbox"
                      checked={editor.is_active}
                      onChange={(event) => setEditor((prev) => ({ ...prev, is_active: event.target.checked }))}
                      disabled={isReadOnlyTemplate}
                    />
                    Активный шаблон
                  </label>

                  {!isAdmin && !editor.city_id && (
                    <div className="ui-alert ui-alert--warning">
                      Для рекрутера шаблон должен быть привязан к одному из доступных городов.
                    </div>
                  )}
                  {!isAdmin && editor.key && recruiterEditableKeys.length > 0 && !recruiterEditableKeys.includes(editor.key) && (
                    <div className="ui-alert ui-alert--warning">
                      Этот ключ относится к system/global шаблонам. Рекрутер может просматривать его, но редактирование доступно только администратору.
                    </div>
                  )}
                  {formError && <p className="text-danger">Ошибка: {formError}</p>}

                  <div className="action-row" style={{ gap: 8, flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="ui-btn ui-btn--primary"
                      onClick={() => saveMutation.mutate()}
                      disabled={saveMutation.isPending || isReadOnlyTemplate || !canCreateCurrent}
                    >
                      {saveMutation.isPending ? 'Сохраняем…' : editor.id ? 'Сохранить изменения' : 'Создать шаблон'}
                    </button>
                    <button type="button" className="ui-btn ui-btn--ghost" onClick={resetEditor}>
                      Очистить
                    </button>
                    <button
                      type="button"
                      className="ui-btn ui-btn--danger"
                      onClick={() => editor.id && window.confirm('Удалить шаблон?') && deleteMutation.mutate(editor.id)}
                      disabled={!editor.id || deleteMutation.isPending || !canDeleteSelected}
                    >
                      Удалить
                    </button>
                  </div>
                </section>

                <section className="glass panel" style={{ display: 'grid', gap: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong>Переменные и предпросмотр</strong>
                    <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => runPreview()}>
                      Обновить preview
                    </button>
                  </div>

                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {variables.map((item) => (
                      <button
                        key={item.name}
                        type="button"
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        onClick={() => setEditor((prev) => ({ ...prev, body: `${prev.body}${prev.body ? '\n' : ''}{${item.name}}` }))}
                        disabled={isReadOnlyTemplate}
                        title={item.label}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>

                  {contextKeysQuery.data && editor.key && (
                    <div className="text-muted text-xs">
                      Контекст для ключа `{editor.key}`: {(contextKeysQuery.data[editor.key] || []).join(', ') || 'общий набор'}
                    </div>
                  )}

                  {previewError && <div className="ui-alert ui-alert--error">{previewError}</div>}
                  {!previewError && !previewHtml && <p className="subtitle">Введите текст и ключ шаблона, чтобы увидеть живой предпросмотр.</p>}
                  {previewHtml && (
                    <div className="glass panel--tight" style={{ padding: 12 }}>
                      <div className="text-muted text-xs" style={{ marginBottom: 8 }}>Предпросмотр для кандидата</div>
                      <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>{previewHtml}</div>
                    </div>
                  )}
                </section>

                <section className="glass panel" style={{ display: 'grid', gap: 10 }}>
                  <strong>История изменений</strong>
                  {editor.id === 0 && <p className="subtitle">История появится после первого сохранения шаблона.</p>}
                  {editor.id > 0 && historyQuery.isLoading && <p className="subtitle">Загрузка истории…</p>}
                  {editor.id > 0 && historyQuery.isError && <ApiErrorBanner error={historyQuery.error} title="Не удалось загрузить историю" onRetry={() => historyQuery.refetch()} />}
                  {editor.id > 0 && historyQuery.data?.items?.length === 0 && <p className="subtitle">История пока пустая.</p>}
                  {historyQuery.data?.items?.length ? (
                    <div style={{ display: 'grid', gap: 8 }}>
                      {historyQuery.data.items.map((item) => (
                        <div key={item.id} className="glass panel--tight" style={{ padding: 10 }}>
                          <div className="text-muted" style={{ fontSize: 12 }}>
                            v{item.version} · {new Date(item.updated_at).toLocaleString('ru-RU')} · {item.updated_by || 'system'}
                          </div>
                          <div style={{ marginTop: 6, whiteSpace: 'pre-wrap' }}>{item.body}</div>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </section>
              </div>
            </div>
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
