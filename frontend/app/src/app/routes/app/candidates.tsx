import { Link } from '@tanstack/react-router'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { apiFetch } from '@/api/client'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import { useProfile } from '@/app/hooks/useProfile'

type CityOption = {
  id: number
  name: string
  tz?: string | null
  active?: boolean
}

type AICityCandidateRecommendation = {
  candidate_id: number
  fit_score?: number | null
  fit_level?: 'high' | 'medium' | 'low' | 'unknown'
  reason: string
  suggested_next_step?: string | null
}

type AICityRecommendationsResponse = {
  ok: boolean
  cached: boolean
  input_hash: string
  criteria_used?: boolean
  recommended: AICityCandidateRecommendation[]
  notes?: string | null
}

type Candidate = {
  id: number
  fio?: string | null
  city?: string | null
  status?: { slug?: string; label?: string; tone?: string }
  telegram_id?: string | null
  recruiter_id?: number | null
  recruiter_name?: string | null
  recruiter?: { id?: number | null; name?: string | null } | null
}

type CandidateCard = {
  id: number
  fio?: string | null
  city?: string | null
  telegram_id?: number | string | null
  status?: { slug?: string; label?: string; tone?: string; icon?: string }
  stage?: string | null
  primary_event_at?: string | null
  recruiter?: { id?: number | null; name?: string | null } | null
}

type KanbanColumn = {
  slug: string
  label: string
  icon?: string | null
  tone?: string | null
  total?: number
  candidates: CandidateCard[]
}

type CalendarDay = {
  date: string
  label: string
  events: Array<{
    candidate?: CandidateCard
    slot?: { start_utc?: string | null }
    status?: { slug?: string; label?: string; tone?: string }
  }>
  totals?: Record<string, number>
}

type CandidateListPayload = {
  items: Candidate[]
  total: number
  page: number
  pages_total: number
  filters?: Record<string, unknown>
  pipeline?: string
  pipeline_options?: Array<{ slug: string; label: string }>
  views?: {
    kanban?: { columns: KanbanColumn[] }
    calendar?: { days: CalendarDay[] }
  }
}

const STATUS_OPTIONS = [
  { value: '', label: 'Все статусы' },
  { value: 'hired', label: '🎉 Закреплён' },
  { value: 'not_hired', label: '⚠️ Не закреплён' },
  { value: 'waiting_slot', label: '⏳ Ожидает слот' },
  { value: 'slot_pending', label: '⌛ Ожидает подтверждения' },
  { value: 'slot_booked', label: '📅 Слот забронирован' },
  { value: 'interview_passed', label: '✅ Интервью пройдено' },
  { value: 'test2_passed', label: '✅ Тест 2 пройден' },
  { value: 'interview_declined', label: '❌ Отказ' },
]

export function CandidatesPage() {
  const profile = useProfile()
  const principalType = profile.data?.principal.type
  const isAdmin = principalType === 'admin'

  const initialFilters = useMemo(() => {
    const params = new URLSearchParams(window.location.search)
    return {
      search: params.get('search') ?? '',
      status: params.get('status') ?? '',
      pipeline: params.get('pipeline') ?? 'interview',
    }
  }, [])

  const [search, setSearch] = useState(initialFilters.search)
  const [status, setStatus] = useState(initialFilters.status)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(20)
  const [pipeline, setPipeline] = useState(initialFilters.pipeline)
  const [view, setView] = useState<'list' | 'kanban' | 'calendar'>('list')
  const [aiCityId, setAiCityId] = useState('')
  const [calendarFrom, setCalendarFrom] = useState(() => {
    const d = new Date()
    return d.toISOString().slice(0, 10)
  })
  const [calendarTo, setCalendarTo] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() + 6)
    return d.toISOString().slice(0, 10)
  })

  const params = new URLSearchParams()
  if (search) params.set('search', search)
  if (status) params.set('status', status)
  if (pipeline) params.set('pipeline', pipeline)
  params.set('page', String(page))
  params.set('per_page', String(perPage))
  if (view === 'calendar') {
    params.set('calendar_mode', 'day')
    params.set('date_from', calendarFrom)
    params.set('date_to', calendarTo)
  }

  const { data, isLoading, isError, error } = useQuery<CandidateListPayload>({
    queryKey: ['candidates', { search, status, page, perPage, pipeline, view, calendarFrom, calendarTo }],
    queryFn: () => apiFetch(`/candidates?${params.toString()}`),
  })

  const citiesQuery = useQuery<CityOption[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
    staleTime: 60_000,
  })

  const aiRecoQuery = useQuery<AICityRecommendationsResponse>({
    queryKey: ['ai-city-reco', aiCityId],
    queryFn: () => {
      if (!aiCityId) throw new Error('Выберите город')
      return apiFetch(`/ai/cities/${aiCityId}/candidates/recommendations?limit=30`)
    },
    enabled: false,
    retry: false,
  })

  const total = data?.total ?? 0
  const pagesTotal = data?.pages_total ?? 1
  const kanbanColumns = data?.views?.kanban?.columns || []
  const calendarDays = data?.views?.calendar?.days || []
  const pipelineOptions = data?.pipeline_options || [
    { slug: 'interview', label: 'Интервью' },
    { slug: 'intro_day', label: 'Ознакомительный день' },
  ]
  const hasActiveFilters = Boolean(search.trim() || status || pipeline !== 'interview')

  const resetFilters = () => {
    setSearch('')
    setStatus('')
    setPipeline('interview')
    setPage(1)
  }

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className="page">
        <header className="glass glass--elevated page-header page-header--row">
          <h1 className="title">Кандидаты</h1>
          <Link to="/app/candidates/new" className="ui-btn ui-btn--primary" data-testid="candidates-create-btn">+ Новый кандидат</Link>
        </header>

        <section className="glass page-section">
          <div className="filter-bar" data-testid="candidates-filter-bar">
            <input
              placeholder="Поиск по ФИО, городу, TG..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1) }}
              className="filter-bar__search"
            />
            <select
              aria-label="Статус кандидата"
              value={status}
              onChange={(e) => { setStatus(e.target.value); setPage(1) }}
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <select
              aria-label="Воронка"
              value={pipeline}
              onChange={(e) => { setPipeline(e.target.value); setPage(1) }}
            >
              {pipelineOptions.map((opt) => (
                <option key={opt.slug} value={opt.slug}>{opt.label}</option>
              ))}
            </select>
            <div className="view-toggle" data-testid="candidates-view-switcher">
              <button className={`ui-btn ui-btn--sm ${view === 'list' ? 'ui-btn--primary' : 'ui-btn--ghost'}`} onClick={() => setView('list')}>
                Список
              </button>
              <button className={`ui-btn ui-btn--sm ${view === 'kanban' ? 'ui-btn--primary' : 'ui-btn--ghost'}`} onClick={() => setView('kanban')}>
                Канбан
              </button>
              <button className={`ui-btn ui-btn--sm ${view === 'calendar' ? 'ui-btn--primary' : 'ui-btn--ghost'}`} onClick={() => setView('calendar')}>
                Календарь
              </button>
            </div>
          </div>

          <div className="glass ai-reco">
            <div className="ai-reco__header">
              <div>
                <div className="ai-reco__title">AI рекомендации</div>
                <div className="subtitle">Подбор кандидатов под критерии города.</div>
              </div>
              <div className="ai-reco__actions">
                <select
                  aria-label="Город для AI рекомендаций"
                  value={aiCityId}
                  onChange={(e) => setAiCityId(e.target.value)}
                >
                  <option value="">Выберите город…</option>
                  {(citiesQuery.data || []).map((c) => (
                    <option key={c.id} value={String(c.id)}>{c.name}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="ui-btn ui-btn--ghost ui-btn--sm"
                  disabled={!aiCityId || aiRecoQuery.isFetching}
                  onClick={() => aiRecoQuery.refetch()}
                >
                  {aiRecoQuery.isFetching ? 'Генерация…' : 'Сгенерировать'}
                </button>
                {aiRecoQuery.data && (
                  <span className={`cd-chip cd-chip--small ${aiRecoQuery.data.cached ? '' : 'cd-chip--accent'}`}>
                    {aiRecoQuery.data.cached ? 'Кэш' : 'Новый'}
                  </span>
                )}
              </div>
            </div>

            {aiRecoQuery.isError && (
              <div className="ai-reco__error">
                AI: {(aiRecoQuery.error as Error).message}
              </div>
            )}

            {aiRecoQuery.data && (
              <div className="ai-reco__body">
                {aiRecoQuery.data.notes && <div className="ai-reco__notes">{aiRecoQuery.data.notes}</div>}
                {aiRecoQuery.data.recommended.length === 0 ? (
                  <div className="subtitle">Нет рекомендаций.</div>
                ) : (
                  <div className="ai-reco__list">
                    {aiRecoQuery.data.recommended.map((r) => (
                      <div key={r.candidate_id} className="ai-reco__item glass glass--interactive">
                        <div className="ai-reco__main">
                          <div className="ai-reco__top">
                            <Link
                              to="/app/candidates/$candidateId"
                              params={{ candidateId: String(r.candidate_id) }}
                              className="font-semibold"
                            >
                              Кандидат #{r.candidate_id}
                            </Link>
                            <span className={`ai-reco__badge ai-reco__badge--${r.fit_level || 'unknown'}`}>
                              {r.fit_score != null ? `${r.fit_score}/100` : '—'}
                            </span>
                          </div>
                          <div className="ai-reco__reason">{r.reason}</div>
                          {r.suggested_next_step && <div className="ai-reco__next">{r.suggested_next_step}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="pagination">
            <span className="pagination__info">Всего: {total}</span>
            <button className="ui-btn ui-btn--ghost ui-btn--sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Назад</button>
            <span className="pagination__info">{page} / {pagesTotal}</span>
            <button className="ui-btn ui-btn--ghost ui-btn--sm" disabled={page >= pagesTotal} onClick={() => setPage(page + 1)}>Вперёд →</button>
            <select
              aria-label="Кандидатов на странице"
              value={perPage}
              onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1) }}
            >
              {[10, 20, 50, 100].map((v) => <option key={v} value={v}>{v} на стр.</option>)}
            </select>
          </div>

          {isLoading && <p className="text-muted">Загрузка…</p>}
          {isError && <ApiErrorBanner error={error} title="Не удалось загрузить кандидатов" />}
          {data && data.items.length === 0 && (
            <div className="empty-state" data-testid="candidates-empty-state">
              <p className="empty-state__text">
                {hasActiveFilters
                  ? 'Кандидаты не найдены по текущим фильтрам.'
                  : 'Список кандидатов пуст. Добавьте первого кандидата, чтобы начать работу.'}
              </p>
              <div className="toolbar">
                {hasActiveFilters && (
                  <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={resetFilters}>
                    Сбросить фильтры
                  </button>
                )}
                <Link to="/app/candidates/new" className="ui-btn ui-btn--primary ui-btn--sm">
                  + Новый кандидат
                </Link>
              </div>
            </div>
          )}
          {view === 'calendar' && (
            <div className="page-section__content">
              <div className="filter-bar">
                <label className="form-group">
                  <span className="form-group__label">От</span>
                  <input type="date" value={calendarFrom} onChange={(e) => setCalendarFrom(e.target.value)} />
                </label>
                <label className="form-group">
                  <span className="form-group__label">До</span>
                  <input type="date" value={calendarTo} onChange={(e) => setCalendarTo(e.target.value)} />
                </label>
              </div>
              {calendarDays.length === 0 && (
                <div className="empty-state">
                  <p className="empty-state__text">Нет событий за выбранный период.</p>
                </div>
              )}
              {calendarDays.length > 0 && (
                <div className="page-section__content">
                  {calendarDays.map((day) => (
                    <article key={day.date} className="glass glass--subtle list-item">
                      <div className="list-item__header">
                        <strong className="list-item__title">{day.label}</strong>
                        <span className="text-muted">Событий: {day.events.length}</span>
                      </div>
                      <div className="page-section__content">
                        {day.events.map((ev, idx) => (
                          <div key={`${day.date}-${idx}`} className="glass glass--interactive list-item list-item--horizontal">
                            <div>
                              <div className="font-semibold">{ev.candidate?.fio || 'Кандидат'}</div>
                              <div className="text-muted text-sm">
                                {ev.candidate?.city || '—'} · {ev.candidate?.recruiter?.name || '—'}
                              </div>
                            </div>
                            {ev.candidate?.id ? (
                              <Link to="/app/candidates/$candidateId" params={{ candidateId: String(ev.candidate.id) }} className="ui-btn ui-btn--ghost ui-btn--sm">
                                Открыть →
                              </Link>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </div>
          )}

          {view === 'kanban' && (
            <div className="kanban">
              {kanbanColumns.map((col) => (
                <article key={col.slug} className="glass kanban__column">
                  <div className="kanban__header">
                    <span className="kanban__title">{col.icon ? `${col.icon} ` : ''}{col.label}</span>
                    <span className="kanban__count">{col.total ?? col.candidates.length}</span>
                  </div>
                  <div className="kanban__cards">
                    {col.candidates.map((card) => (
                      <div key={card.id} className="glass glass--interactive kanban__card">
                        <div className="font-semibold">{card.fio || '—'}</div>
                        <div className="text-muted text-sm">{card.city || '—'}</div>
                        <div className="kanban__card-footer">
                          <span className="text-muted text-sm">{card.recruiter?.name || '—'}</span>
                          <Link to="/app/candidates/$candidateId" params={{ candidateId: String(card.id) }} className="ui-btn ui-btn--ghost ui-btn--sm">
                            Открыть →
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          )}

          {view === 'list' && data && data.items.length > 0 && (
            <table className="data-table" data-testid="candidates-table">
              <thead>
                <tr>
                  <th>ФИО</th>
                  <th>Город</th>
                  <th>Статус</th>
                  {isAdmin && <th>Рекрутёр</th>}
                  <th>Telegram</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((c) => {
                  const tone = c.status?.tone
                  const recruiterName = c.recruiter?.name || c.recruiter_name || '—'
                  return (
                    <tr key={c.id}>
                      <td>
                        <Link to="/app/candidates/$candidateId" params={{ candidateId: String(c.id) }} className="font-semibold">
                          {c.fio || '—'}
                        </Link>
                      </td>
                      <td>{c.city || '—'}</td>
                      <td>
                        <span className={`status-badge status-badge--${tone || 'muted'}`}>
                          {c.status?.label || c.status?.slug || '—'}
                        </span>
                      </td>
                      {isAdmin && <td>{recruiterName}</td>}
                      <td>
                        {c.telegram_id ? (
                          <a href={`https://t.me/${c.telegram_id}`} target="_blank" rel="noopener" className="text-accent">
                            {c.telegram_id}
                          </a>
                        ) : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
