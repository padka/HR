import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import { STAGE_LABELS, TEMPLATE_META, templateStage, type TemplateStage } from './template_meta'

type Recruiter = { id: number; name: string; tz?: string | null }
type TimezoneOption = { value: string; label: string; region?: string; offset?: string }
type CityDetail = {
  id: number
  name: string
  tz?: string | null
  active?: boolean | null
  plan_week?: number | null
  plan_month?: number | null
  criteria?: string | null
  experts?: string | null
  intro_address?: string | null
  contact_name?: string | null
  contact_phone?: string | null
  recruiter_ids?: number[]
}

type TemplateItem = {
  id: number
  key: string
  city_id?: number | null
  city_name?: string | null
  is_global?: boolean
  preview?: string
  length?: number
}

const ALL_STAGES: TemplateStage[] = [
  'registration',
  'testing',
  'interview',
  'intro_day',
  'reminders',
  'results',
  'service',
]

function isValidTimezone(tz: string): boolean {
  try {
    new Intl.DateTimeFormat('ru-RU', { timeZone: tz }).format()
    return true
  } catch {
    return false
  }
}

function formatTimeInTz(tz: string): string {
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      timeZone: tz,
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }).format(new Date())
  } catch {
    return ''
  }
}

export function CityEditPage() {
  const params = useParams({ from: '/app/cities/$cityId/edit' })
  const cityId = Number(params.cityId)
  const navigate = useNavigate()

  const { data: recruiters } = useQuery<Recruiter[]>({
    queryKey: ['recruiters'],
    queryFn: () => apiFetch('/recruiters'),
  })
  const { data: timezones } = useQuery<TimezoneOption[]>({
    queryKey: ['timezones'],
    queryFn: () => apiFetch('/timezones'),
  })
  const templatesQuery = useQuery<{ custom_templates: TemplateItem[] }>({
    queryKey: ['templates-list'],
    queryFn: () => apiFetch('/templates/list'),
  })

  const detailQuery = useQuery<CityDetail>({
    queryKey: ['city-detail', cityId],
    queryFn: () => apiFetch(`/cities/${cityId}`),
  })

  const [form, setForm] = useState({
    name: '',
    tz: 'Europe/Moscow',
    active: true,
    plan_week: '',
    plan_month: '',
    criteria: '',
    experts: '',
    intro_address: '',
    contact_name: '',
    contact_phone: '',
    recruiter_ids: [] as number[],
  })
  const [recruiterSearch, setRecruiterSearch] = useState('')
  const [collapsedStages, setCollapsedStages] = useState<Record<string, boolean>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<{ name?: string; tz?: string; plan_week?: string; plan_month?: string }>({})

  useEffect(() => {
    if (!detailQuery.data) return
    setForm({
      name: detailQuery.data.name || '',
      tz: detailQuery.data.tz || 'Europe/Moscow',
      active: Boolean(detailQuery.data.active),
      plan_week: detailQuery.data.plan_week != null ? String(detailQuery.data.plan_week) : '',
      plan_month: detailQuery.data.plan_month != null ? String(detailQuery.data.plan_month) : '',
      criteria: detailQuery.data.criteria || '',
      experts: detailQuery.data.experts || '',
      intro_address: detailQuery.data.intro_address || '',
      contact_name: detailQuery.data.contact_name || '',
      contact_phone: detailQuery.data.contact_phone || '',
      recruiter_ids: detailQuery.data.recruiter_ids || [],
    })
  }, [detailQuery.data])

  const mutation = useMutation({
    mutationFn: async () => {
      setFormError(null)
      setFieldError({})
      if (!form.name.trim()) {
        setFieldError({ name: 'Укажите название города' })
        throw new Error('invalid_form')
      }
      if (!form.tz.trim()) {
        setFieldError({ tz: 'Укажите часовой пояс' })
        throw new Error('invalid_form')
      }
      if (!isValidTimezone(form.tz)) {
        setFieldError({ tz: 'Некорректная IANA TZ (например, Europe/Moscow)' })
        throw new Error('invalid_form')
      }
      if (form.plan_week && Number.isNaN(Number(form.plan_week))) {
        setFieldError({ plan_week: 'План/нед должен быть числом' })
        throw new Error('invalid_form')
      }
      if (form.plan_month && Number.isNaN(Number(form.plan_month))) {
        setFieldError({ plan_month: 'План/мес должен быть числом' })
        throw new Error('invalid_form')
      }
      const payload = {
        name: form.name,
        tz: form.tz,
        active: form.active,
        plan_week: form.plan_week ? Number(form.plan_week) : null,
        plan_month: form.plan_month ? Number(form.plan_month) : null,
        criteria: form.criteria || null,
        experts: form.experts || null,
        intro_address: form.intro_address || null,
        contact_name: form.contact_name || null,
        contact_phone: form.contact_phone || null,
        recruiter_ids: form.recruiter_ids,
      }
      return apiFetch(`/cities/${cityId}`, { method: 'PUT', body: JSON.stringify(payload) })
    },
    onSuccess: () => navigate({ to: '/app/cities' }),
    onError: (err) => {
      if (err instanceof Error && err.message === 'invalid_form') return
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
    mutationFn: async () => apiFetch(`/cities/${cityId}`, { method: 'DELETE' }),
    onSuccess: () => navigate({ to: '/app/cities' }),
  })

  const recruiterList = useMemo(() => recruiters || [], [recruiters])

  const cityTemplates = useMemo(() => {
    const items = templatesQuery.data?.custom_templates || []
    return items.filter((tmpl) => tmpl.city_id === cityId)
  }, [templatesQuery.data?.custom_templates, cityId])

  const groupedCityTemplates = useMemo(() => {
    const groups: Record<TemplateStage, TemplateItem[]> = {
      registration: [],
      testing: [],
      interview: [],
      intro_day: [],
      reminders: [],
      results: [],
      service: [],
    }
    cityTemplates.forEach((tmpl) => {
      const stage = templateStage(tmpl.key)
      groups[stage].push(tmpl)
    })
    ALL_STAGES.forEach((stage) => {
      groups[stage].sort((a, b) => {
        const titleA = TEMPLATE_META[a.key]?.title ?? a.key
        const titleB = TEMPLATE_META[b.key]?.title ?? b.key
        return titleA.localeCompare(titleB, 'ru')
      })
    })
    return groups
  }, [cityTemplates])

  const toggleStage = (stage: string) =>
    setCollapsedStages((prev) => ({ ...prev, [stage]: !prev[stage] }))

  const filteredRecruiters = useMemo(() => {
    const term = recruiterSearch.toLowerCase().trim()
    if (!term) return recruiterList
    return recruiterList.filter(r =>
      r.name.toLowerCase().includes(term) ||
      (r.tz && r.tz.toLowerCase().includes(term))
    )
  }, [recruiterList, recruiterSearch])

  const toggleRecruiter = (id: number) => {
    setForm(prev => ({
      ...prev,
      recruiter_ids: prev.recruiter_ids.includes(id)
        ? prev.recruiter_ids.filter(x => x !== id)
        : [...prev.recruiter_ids, id]
    }))
  }

  const tzOptions = useMemo(() => {
    const opts = timezones || []
    if (form.tz && !opts.find((o) => o.value === form.tz)) {
      return [...opts, { value: form.tz, label: form.tz }]
    }
    return opts
  }, [timezones, form.tz])

  const tzValid = isValidTimezone(form.tz)
  const tzNow = tzValid ? formatTimeInTz(form.tz) : ''
  const selectedRecruiterCount = form.recruiter_ids.length

  // Get selected recruiters for preview
  const selectedRecruiters = useMemo(() => {
    return recruiterList.filter(r => form.recruiter_ids.includes(r.id))
  }, [recruiterList, form.recruiter_ids])

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <div className="glass panel" style={{ display: 'grid', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <Link to="/app/cities" className="glass action-link">← К списку городов</Link>
          </div>

          {detailQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {detailQuery.isError && <p style={{ color: '#f07373' }}>Ошибка: {(detailQuery.error as Error).message}</p>}

          {!detailQuery.isLoading && (
            <>
              {/* Summary hero card */}
              <div className="glass" style={{ padding: 16 }}>
                <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                  <div style={{ flex: '1 1 240px', minWidth: 200 }}>
                    <p className="subtitle" style={{ marginBottom: 4 }}>Город</p>
                    <h1 style={{ margin: 0, fontSize: 26, fontWeight: 800 }}>{form.name || 'Без названия'}</h1>
                    <p className="subtitle" style={{ marginTop: 4 }}>
                      ID #{cityId} · {form.active ? 'Активен' : 'В архиве'}
                    </p>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 12, flex: '2 1 400px' }}>
                    <div className="glass" style={{ padding: '8px 12px', borderRadius: 8 }}>
                      <span className="subtitle" style={{ fontSize: 11 }}>Таймзона</span>
                      <div style={{ fontWeight: 600 }}>{form.tz}</div>
                    </div>
                    <div className="glass" style={{ padding: '8px 12px', borderRadius: 8 }}>
                      <span className="subtitle" style={{ fontSize: 11 }}>Ответственные</span>
                      <div style={{ fontWeight: 600 }}>
                        {selectedRecruiters.length > 0
                          ? selectedRecruiters.slice(0, 2).map(r => r.name).join(', ') + (selectedRecruiters.length > 2 ? ` +${selectedRecruiters.length - 2}` : '')
                          : 'Не назначены'
                        }
                      </div>
                    </div>
                    <div className="glass" style={{ padding: '8px 12px', borderRadius: 8 }}>
                      <span className="subtitle" style={{ fontSize: 11 }}>Привязанных рекрутёров</span>
                      <div style={{ fontWeight: 600 }}>{selectedRecruiterCount}</div>
                    </div>
                    <div
                      className="glass"
                      style={{
                        padding: '8px 12px',
                        borderRadius: 8,
                        background: form.active ? 'rgba(100, 200, 100, 0.1)' : 'rgba(150, 150, 150, 0.1)'
                      }}
                    >
                      <span className="subtitle" style={{ fontSize: 11 }}>Статус</span>
                      <div style={{ fontWeight: 600, color: form.active ? 'rgb(100, 200, 100)' : 'inherit' }}>
                        {form.active ? 'Активен' : 'В архиве'}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Quick nav */}
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <Link to="/app/templates" search={{ city_id: cityId }} className="ui-btn ui-btn--ghost">
                  Шаблоны города →
                </Link>
              </div>

              {/* City message templates */}
              <div className="glass" style={{ padding: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                  <div>
                    <h3 style={{ marginBottom: 4 }}>Шаблоны сообщений</h3>
                    <p className="subtitle" style={{ marginBottom: 0 }}>
                      Только персональные шаблоны для города — общие применяются автоматически.
                    </p>
                  </div>
                  <Link to="/app/templates/new" search={{ city_id: cityId }} className="ui-btn ui-btn--primary">
                    Переопределить шаблон
                  </Link>
                </div>

                {templatesQuery.isLoading && <p className="subtitle" style={{ marginTop: 12 }}>Загрузка шаблонов…</p>}
                {templatesQuery.isError && (
                  <p style={{ color: '#f07373', marginTop: 12 }}>Ошибка: {(templatesQuery.error as Error).message}</p>
                )}

                {!templatesQuery.isLoading && !templatesQuery.isError && cityTemplates.length === 0 && (
                  <p className="subtitle" style={{ marginTop: 12 }}>
                    Нет персональных шаблонов (используются общие).
                  </p>
                )}

                {!templatesQuery.isLoading && !templatesQuery.isError && cityTemplates.length > 0 && (
                  <div style={{ display: 'grid', gap: 12, marginTop: 12 }}>
                    {ALL_STAGES.map((stage) => {
                      const items = groupedCityTemplates[stage] || []
                      if (!items.length) return null
                      const label = STAGE_LABELS[stage]
                      const collapsed = collapsedStages[stage]
                      return (
                        <div key={stage}>
                          <div
                            style={{ cursor: 'pointer', userSelect: 'none', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                            onClick={() => toggleStage(stage)}
                          >
                            <div>
                              <h4 className="section-title" style={{ margin: 0 }}>
                                {collapsed ? '▸' : '▾'} {label.title}
                                <span className="text-muted" style={{ fontWeight: 400, fontSize: 13, marginLeft: 8 }}>
                                  ({items.length})
                                </span>
                              </h4>
                              <p className="text-muted" style={{ margin: '2px 0 0 0' }}>{label.desc}</p>
                            </div>
                          </div>
                          {!collapsed && (
                            <div className="template-grid" style={{ marginTop: 10 }}>
                              {items.map((tmpl) => {
                                const meta = TEMPLATE_META[tmpl.key]
                                return (
                                  <div key={tmpl.id} className="glass template-card">
                                    <div className="template-card__header">
                                      <div>
                                        <div style={{ fontWeight: 600, marginBottom: 2 }}>
                                          {meta?.title ?? tmpl.key}
                                        </div>
                                        {meta?.desc && (
                                          <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>{meta.desc}</div>
                                        )}
                                        <div className="template-tags">
                                          <span className="chip">{tmpl.key}</span>
                                          <span className="chip">ID #{tmpl.id}</span>
                                        </div>
                                      </div>
                                    </div>
                                    <div className="template-preview">{tmpl.preview || '—'}</div>
                                    <div className="template-actions">
                                      <Link
                                        to="/app/templates/$templateId/edit"
                                        params={{ templateId: String(tmpl.id) }}
                                        className="ui-btn ui-btn--ghost ui-btn--sm"
                                      >
                                        Редактировать
                                      </Link>
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Basic parameters */}
              <div className="glass" style={{ padding: 16 }}>
                <h3 style={{ marginBottom: 4 }}>Основные</h3>
                <p className="subtitle" style={{ marginBottom: 12 }}>Имя и рабочий регион</p>
                <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
                  <label style={{ display: 'grid', gap: 6 }}>
                    <span>Название <span style={{ color: 'var(--accent)' }}>*</span></span>
                    <input
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      placeholder="Например: Новосибирск"
                      required
                    />
                    {fieldError.name && <span style={{ color: '#f07373', fontSize: 12 }}>{fieldError.name}</span>}
                  </label>

                  <label style={{ display: 'grid', gap: 6 }}>
                    <span>Часовой пояс <span style={{ color: 'var(--accent)' }}>*</span></span>
                    <select
                      value={form.tz}
                      onChange={(e) => setForm({ ...form, tz: e.target.value })}
                      required
                    >
                      {tzOptions.map((tz) => (
                        <option key={tz.value} value={tz.value}>{tz.label}</option>
                      ))}
                    </select>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                      <span
                        style={{
                          padding: '2px 8px',
                          borderRadius: 6,
                          fontSize: 11,
                          background: tzValid ? 'rgba(100, 200, 100, 0.15)' : 'rgba(240, 115, 115, 0.15)',
                          border: tzValid ? '1px solid rgba(100, 200, 100, 0.3)' : '1px solid rgba(240, 115, 115, 0.3)',
                          color: tzValid ? 'rgb(100, 200, 100)' : '#f07373'
                        }}
                      >
                        {tzValid ? 'TZ OK' : 'Некорректная TZ'}
                      </span>
                      {tzNow && <span className="subtitle" style={{ fontSize: 11 }}>Сейчас там: {tzNow}</span>}
                    </div>
                    {fieldError.tz && <span style={{ color: '#f07373', fontSize: 12 }}>{fieldError.tz}</span>}
                  </label>
                </div>

                <div style={{ marginTop: 12 }}>
                  <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={form.active}
                      onChange={(e) => setForm({ ...form, active: e.target.checked })}
                    />
                    <span>Активен</span>
                  </label>
                </div>
              </div>

              {/* Plan section */}
              <div className="glass" style={{ padding: 16 }}>
                <h3 style={{ marginBottom: 12 }}>План найма</h3>
                <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
                  <div>
                    <label style={{ display: 'grid', gap: 6 }}>
                      <span>План, неделя</span>
                      <input
                        type="number"
                        min="0"
                        value={form.plan_week}
                        onChange={(e) => setForm({ ...form, plan_week: e.target.value })}
                        placeholder="0"
                      />
                    </label>
                    <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                      {[5, 10, 20].map(v => (
                        <button
                          key={v}
                          type="button"
                          className="ui-btn ui-btn--ghost"
                          style={{ padding: '4px 10px', fontSize: 12 }}
                          onClick={() => setForm({ ...form, plan_week: String(v) })}
                        >
                          {v}
                        </button>
                      ))}
                    </div>
                    {fieldError.plan_week && <span style={{ color: '#f07373', fontSize: 12 }}>{fieldError.plan_week}</span>}
                  </div>
                  <div>
                    <label style={{ display: 'grid', gap: 6 }}>
                      <span>План, месяц</span>
                      <input
                        type="number"
                        min="0"
                        value={form.plan_month}
                        onChange={(e) => setForm({ ...form, plan_month: e.target.value })}
                        placeholder="0"
                      />
                    </label>
                    <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                      {[30, 60, 100].map(v => (
                        <button
                          key={v}
                          type="button"
                          className="ui-btn ui-btn--ghost"
                          style={{ padding: '4px 10px', fontSize: 12 }}
                          onClick={() => setForm({ ...form, plan_month: String(v) })}
                        >
                          {v}
                        </button>
                      ))}
                    </div>
                    {fieldError.plan_month && <span style={{ color: '#f07373', fontSize: 12 }}>{fieldError.plan_month}</span>}
                  </div>
                </div>
              </div>

              {/* Additional info */}
              <div className="glass" style={{ padding: 16 }}>
                <h3 style={{ marginBottom: 12 }}>Дополнительно</h3>
                <div style={{ display: 'grid', gap: 12 }}>
                  <label style={{ display: 'grid', gap: 6 }}>
                    <span>Фильтр/Критерии</span>
                    <textarea
                      rows={3}
                      value={form.criteria}
                      onChange={(e) => setForm({ ...form, criteria: e.target.value })}
                      placeholder="Критерии отбора для города"
                    />
                  </label>

                  <label style={{ display: 'grid', gap: 6 }}>
                    <span>Контакты/Эксперты</span>
                    <textarea
                      rows={3}
                      value={form.experts}
                      onChange={(e) => setForm({ ...form, experts: e.target.value })}
                      placeholder="Контактные лица или эксперты для города"
                    />
                  </label>
                </div>
              </div>

              {/* Intro day section */}
              <div className="glass" style={{ padding: 16 }}>
                <h3 style={{ marginBottom: 4 }}>Ознакомительный день</h3>
                <p className="subtitle" style={{ marginBottom: 12 }}>Адрес и контактное лицо для приглашений на ознакомительный день</p>
                <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
                  <label style={{ display: 'grid', gap: 6 }}>
                    <span>Адрес проведения</span>
                    <input
                      value={form.intro_address}
                      onChange={(e) => setForm({ ...form, intro_address: e.target.value })}
                      placeholder="ул. Примерная, д. 1"
                    />
                  </label>
                  <label style={{ display: 'grid', gap: 6 }}>
                    <span>Контактное лицо</span>
                    <input
                      value={form.contact_name}
                      onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
                      placeholder="Иванов Иван Иванович"
                    />
                  </label>
                  <label style={{ display: 'grid', gap: 6 }}>
                    <span>Телефон контактного лица</span>
                    <input
                      value={form.contact_phone}
                      onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
                      placeholder="+7 (999) 123-45-67"
                    />
                  </label>
                </div>
              </div>

              {/* Recruiters section */}
              <div className="glass" style={{ padding: 16 }}>
                <h3 style={{ marginBottom: 4 }}>Ответственные рекрутёры</h3>
                <p className="subtitle" style={{ marginBottom: 12 }}>Выберите одного или нескольких рекрутёров</p>

                <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
                  <input
                    type="search"
                    placeholder="Поиск рекрутёра"
                    value={recruiterSearch}
                    onChange={(e) => setRecruiterSearch(e.target.value)}
                    style={{ flex: 1, minWidth: 180 }}
                  />
                  <span
                    style={{
                      background: selectedRecruiterCount > 0 ? 'var(--accent)' : 'rgba(150, 150, 150, 0.3)',
                      color: 'white',
                      padding: '6px 12px',
                      borderRadius: 16,
                      fontSize: 14,
                      fontWeight: 600,
                      minWidth: 90,
                      textAlign: 'center'
                    }}
                  >
                    {selectedRecruiterCount === 0 ? 'Нет выбранных' : selectedRecruiterCount === 1 ? '1 выбран' : `${selectedRecruiterCount} выбрано`}
                  </span>
                </div>

                {/* Selected recruiters preview pills */}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
                  {selectedRecruiters.length === 0 && (
                    <span className="subtitle">Рекрутёры пока не выбраны</span>
                  )}
                  {selectedRecruiters.slice(0, 4).map(rec => (
                    <span
                      key={rec.id}
                      style={{
                        background: 'rgba(105, 183, 255, 0.15)',
                        border: '1px solid rgba(105, 183, 255, 0.3)',
                        padding: '4px 10px',
                        borderRadius: 16,
                        fontSize: 13
                      }}
                    >
                      {rec.name}
                    </span>
                  ))}
                  {selectedRecruiters.length > 4 && (
                    <span
                      style={{
                        background: 'rgba(150, 150, 150, 0.15)',
                        border: '1px solid rgba(150, 150, 150, 0.3)',
                        padding: '4px 10px',
                        borderRadius: 16,
                        fontSize: 13
                      }}
                    >
                      +{selectedRecruiters.length - 4}
                    </span>
                  )}
                </div>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                    gap: 8,
                    maxHeight: 250,
                    overflowY: 'auto',
                    padding: 4
                  }}
                >
                  {filteredRecruiters.map(rec => {
                    const selected = form.recruiter_ids.includes(rec.id)
                    return (
                      <label
                        key={rec.id}
                        style={{
                          display: 'grid',
                          gap: 2,
                          padding: '10px 12px',
                          borderRadius: 8,
                          cursor: 'pointer',
                          background: selected ? 'rgba(105, 183, 255, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                          border: selected ? '2px solid var(--accent)' : '2px solid transparent',
                          position: 'relative',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleRecruiter(rec.id)}
                          style={{ position: 'absolute', opacity: 0, pointerEvents: 'none' }}
                        />
                        {selected && (
                          <span
                            style={{
                              position: 'absolute',
                              top: 6,
                              right: 6,
                              width: 18,
                              height: 18,
                              borderRadius: 4,
                              background: 'var(--accent)',
                              color: 'white',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: 12,
                              fontWeight: 'bold'
                            }}
                          >
                            ✓
                          </span>
                        )}
                        <span style={{ fontWeight: 500 }}>{rec.name}</span>
                        <span className="subtitle" style={{ fontSize: 11 }}>{rec.tz || '—'}</span>
                      </label>
                    )
                  })}
                </div>

                {filteredRecruiters.length === 0 && (
                  <p className="subtitle" style={{ marginTop: 8 }}>Рекрутёров не найдено</p>
                )}
              </div>

              <div className="action-row">
                <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
                  {mutation.isPending ? 'Сохраняем…' : 'Сохранить'}
                </button>
                <Link to="/app/cities" className="ui-btn ui-btn--ghost">Отмена</Link>
                <button
                  className="ui-btn ui-btn--danger"
                  onClick={() => window.confirm(`Удалить город ${form.name}? Это действие нельзя отменить.`) && deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                  style={{ marginLeft: 'auto' }}
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
