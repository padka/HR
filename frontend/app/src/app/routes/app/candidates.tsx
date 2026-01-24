import { Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { apiFetch } from '@/api/client'

type Candidate = {
  id: number
  fio?: string | null
  city?: string | null
  status?: { slug?: string; label?: string; tone?: string }
  telegram_id?: string | null
  recruiter_id?: number | null
  recruiter_name?: string | null
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
  { value: 'slot_booked', label: '📅 Слот забронирован' },
  { value: 'interview_passed', label: '✅ Интервью пройдено' },
  { value: 'test2_passed', label: '✅ Тест 2 пройден' },
  { value: 'interview_declined', label: '❌ Отказ' },
]

export function CandidatesPage() {
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

  const total = data?.total ?? 0
  const pagesTotal = data?.pages_total ?? 1
  const kanbanColumns = data?.views?.kanban?.columns || []
  const calendarDays = data?.views?.calendar?.days || []
  const pipelineOptions = data?.pipeline_options || [
    { slug: 'interview', label: 'Интервью' },
    { slug: 'intro_day', label: 'Ознакомительный день' },
  ]

  return (
    <div className="page">
      <div className="glass panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <h1 className="title" style={{ margin: 0 }}>Кандидаты</h1>
          <Link to="/app/candidates/new" className="ui-btn ui-btn--primary">+ Новый кандидат</Link>
        </div>
        <div className="action-row" style={{ alignItems: 'center', marginTop: 12, flexWrap: 'wrap' }}>
          <input
            placeholder="Поиск по ФИО, городу, TG..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            style={{ minWidth: 200 }}
          />
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1) }}
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <select
            value={pipeline}
            onChange={(e) => { setPipeline(e.target.value); setPage(1) }}
          >
            {pipelineOptions.map((opt) => (
              <option key={opt.slug} value={opt.slug}>{opt.label}</option>
            ))}
          </select>
          <div className="action-row" style={{ gap: 6 }}>
            <button className={`ui-btn ${view === 'list' ? 'ui-btn--primary' : 'ui-btn--ghost'}`} onClick={() => setView('list')}>
              Список
            </button>
            <button className={`ui-btn ${view === 'kanban' ? 'ui-btn--primary' : 'ui-btn--ghost'}`} onClick={() => setView('kanban')}>
              Канбан
            </button>
            <button className={`ui-btn ${view === 'calendar' ? 'ui-btn--primary' : 'ui-btn--ghost'}`} onClick={() => setView('calendar')}>
              Календарь
            </button>
          </div>
          <span className="subtitle">Всего: {total}</span>
          <button className="ui-btn ui-btn--ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Назад</button>
          <span className="subtitle">{page} / {pagesTotal}</span>
          <button className="ui-btn ui-btn--ghost" disabled={page >= pagesTotal} onClick={() => setPage(page + 1)}>Вперёд →</button>
          <select value={perPage} onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1) }}>
            {[10, 20, 50, 100].map((v) => <option key={v} value={v}>{v} на стр.</option>)}
          </select>
        </div>

        {isLoading && <p className="subtitle">Загрузка…</p>}
        {isError && <p style={{ color: '#f07373' }}>Ошибка: {(error as Error).message}</p>}
        {data && data.items.length === 0 && (
          <p className="subtitle" style={{ marginTop: 16 }}>Кандидаты не найдены. Попробуйте изменить фильтры.</p>
        )}
        {view === 'calendar' && (
          <div style={{ marginTop: 16, display: 'grid', gap: 12 }}>
            <div className="action-row" style={{ gap: 12 }}>
              <label style={{ display: 'grid', gap: 4 }}>
                От
                <input type="date" value={calendarFrom} onChange={(e) => setCalendarFrom(e.target.value)} />
              </label>
              <label style={{ display: 'grid', gap: 4 }}>
                До
                <input type="date" value={calendarTo} onChange={(e) => setCalendarTo(e.target.value)} />
              </label>
            </div>
            {calendarDays.length === 0 && (
              <p className="subtitle">Нет событий за выбранный период.</p>
            )}
            {calendarDays.length > 0 && (
              <div style={{ display: 'grid', gap: 12 }}>
                {calendarDays.map((day) => (
                  <div key={day.date} className="glass" style={{ padding: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong>{day.label}</strong>
                      <span className="subtitle">Событий: {day.events.length}</span>
                    </div>
                    <div style={{ marginTop: 8, display: 'grid', gap: 8 }}>
                      {day.events.map((ev, idx) => (
                        <div key={`${day.date}-${idx}`} className="glass" style={{ padding: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div style={{ fontWeight: 600 }}>{ev.candidate?.fio || 'Кандидат'}</div>
                            <div className="subtitle">
                              {ev.candidate?.city || '—'} · {ev.candidate?.recruiter?.name || '—'}
                            </div>
                          </div>
                          {ev.candidate?.id ? (
                            <Link to="/app/candidates/$candidateId" params={{ candidateId: String(ev.candidate.id) }} className="action-link">
                              Открыть →
                            </Link>
                          ) : (
                            <span className="subtitle">—</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {view === 'kanban' && (
          <div style={{ marginTop: 16, overflowX: 'auto' }}>
            <div style={{ display: 'grid', gridAutoFlow: 'column', gridAutoColumns: 'minmax(260px, 1fr)', gap: 12 }}>
              {kanbanColumns.map((col) => (
                <div key={col.slug} className="glass" style={{ padding: 12, display: 'grid', gap: 10, minHeight: 220 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 600 }}>{col.icon ? `${col.icon} ` : ''}{col.label}</span>
                    <span className="subtitle">{col.total ?? col.candidates.length}</span>
                  </div>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {col.candidates.map((card) => (
                      <div key={card.id} className="glass" style={{ padding: 10 }}>
                        <div style={{ fontWeight: 600 }}>{card.fio || '—'}</div>
                        <div className="subtitle">{card.city || '—'}</div>
                        <div style={{ marginTop: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span className="subtitle">{card.recruiter?.name || '—'}</span>
                          <Link to="/app/candidates/$candidateId" params={{ candidateId: String(card.id) }} className="action-link">
                            Открыть →
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {view === 'list' && data && data.items.length > 0 && (
          <table className="table" style={{ marginTop: 10 }}>
            <thead>
              <tr>
                <th>ФИО</th>
                <th>Город</th>
                <th>Статус</th>
                <th>Рекрутёр</th>
                <th>Telegram</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((c) => {
                const tone = c.status?.tone
                const statusStyle = {
                  display: 'inline-block',
                  padding: '2px 8px',
                  borderRadius: 6,
                  fontSize: 12,
                  background:
                    tone === 'success' ? 'rgba(100, 200, 100, 0.15)' :
                    tone === 'danger' ? 'rgba(240, 115, 115, 0.15)' :
                    tone === 'warning' ? 'rgba(255, 200, 100, 0.15)' :
                    'rgba(105, 183, 255, 0.1)',
                  border: `1px solid ${
                    tone === 'success' ? 'rgba(100, 200, 100, 0.3)' :
                    tone === 'danger' ? 'rgba(240, 115, 115, 0.3)' :
                    tone === 'warning' ? 'rgba(255, 200, 100, 0.3)' :
                    'rgba(105, 183, 255, 0.2)'
                  }`,
                }
                return (
                  <tr key={c.id} className="glass">
                    <td>
                      <Link to="/app/candidates/$candidateId" params={{ candidateId: String(c.id) }} style={{ fontWeight: 600 }}>
                        {c.fio || '—'}
                      </Link>
                    </td>
                    <td>{c.city || '—'}</td>
                    <td>
                      <span style={statusStyle}>
                        {c.status?.label || c.status?.slug || '—'}
                      </span>
                    </td>
                    <td>{c.recruiter_name || '—'}</td>
                    <td>
                      {c.telegram_id ? (
                        <a href={`https://t.me/${c.telegram_id}`} target="_blank" rel="noopener" style={{ color: 'var(--accent)' }}>
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
      </div>
    </div>
  )
}
