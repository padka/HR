import { Link, useParams } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, useMemo, useEffect } from 'react'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'

type City = {
  id: number
  name: string
  tz?: string | null
}

type Recruiter = {
  id: number
  name: string
  tz?: string | null
  active?: boolean
}

type CandidateAction = {
  key: string
  label: string
  url?: string | null
  method?: string
  icon?: string | null
  variant?: string | null
  confirmation?: string | null
  target_status?: string | null
}

type CandidateSlot = {
  id: number
  status?: string | null
  purpose?: string | null
  start_utc?: string | null
  recruiter_name?: string | null
  city_name?: string | null
  candidate_tz?: string | null
}

type TestSection = {
  key: string
  title: string
  status?: string
  status_label?: string
  summary?: string
  completed_at?: string | null
  pending_since?: string | null
  report_url?: string | null
}

type CandidateDetail = {
  id: number
  fio?: string | null
  city?: string | null
  telegram_id?: number | null
  telegram_username?: string | null
  phone?: string | null
  is_active?: boolean
  stage?: string | null
  workflow_status_label?: string | null
  workflow_status_color?: string | null
  candidate_status_slug?: string | null
  candidate_status_color?: string | null
  telemost_url?: string | null
  telemost_source?: string | null
  responsible_recruiter?: { id?: number | null; name?: string | null } | null
  candidate_actions?: CandidateAction[]
  allowed_next_statuses?: Array<{ slug: string; label: string; color?: string; is_terminal?: boolean }>
  pipeline_stages?: Array<{ key: string; label: string; state?: string }>
  status_is_terminal?: boolean
  candidate_status_options?: Array<{ slug: string; label: string }>
  legacy_status_enabled?: boolean
  slots?: CandidateSlot[]
  test_sections?: TestSection[]
  stats?: { tests_total?: number; average_score?: number | null }
}

const STATUS_LABELS: Record<string, { label: string; icon: string; tone: string }> = {
  hired: { label: 'Закреплен на обучение', icon: '🎉', tone: 'success' },
  not_hired: { label: 'Не закреплен', icon: '⚠️', tone: 'warning' },
  interview_declined: { label: 'Отказ на собеседовании', icon: '❌', tone: 'danger' },
  test2_failed: { label: 'Не прошёл тест 2', icon: '❌', tone: 'danger' },
  waiting_slot: { label: 'Ожидает слот', icon: '⏳', tone: 'info' },
  slot_booked: { label: 'Слот забронирован', icon: '📅', tone: 'info' },
  intro_day_scheduled: { label: 'Ознакомительный день назначен', icon: '📅', tone: 'info' },
}

function getStatusDisplay(slug: string | null | undefined) {
  if (!slug) return { label: 'Нет статуса', icon: '—', tone: 'muted' }
  return STATUS_LABELS[slug] || { label: slug, icon: '•', tone: 'muted' }
}

function formatSlotTime(startUtc: string | null | undefined, tz: string | null | undefined): string {
  if (!startUtc) return '—'
  try {
    const d = new Date(startUtc)
    return new Intl.DateTimeFormat('ru-RU', {
      timeZone: tz || 'Europe/Moscow',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d)
  } catch {
    return startUtc
  }
}

type ChatMessage = {
  id: number
  direction: string
  text: string
  status?: string
  created_at: string
  author?: string | null
  can_retry?: boolean
}

type ChatPayload = {
  messages: ChatMessage[]
  has_more: boolean
}

function formatTzOffset(tz: string): string {
  try {
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      timeZoneName: 'shortOffset',
    })
    const parts = formatter.formatToParts(new Date())
    const offsetPart = parts.find((p) => p.type === 'timeZoneName')
    return offsetPart?.value || tz
  } catch {
    return tz
  }
}

function getTomorrowDate(): string {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}

type ScheduleSlotModalProps = {
  candidateId: number
  candidateFio: string
  candidateCity?: string | null
  onClose: () => void
  onSuccess: () => void
}

function ScheduleSlotModal({ candidateId, candidateFio, candidateCity, onClose, onSuccess }: ScheduleSlotModalProps) {
  const [form, setForm] = useState({
    recruiter_id: '',
    city_id: '',
    date: getTomorrowDate(),
    time: '10:00',
    custom_message: '',
  })
  const [error, setError] = useState<string | null>(null)

  const citiesQuery = useQuery<City[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
  })

  const recruitersQuery = useQuery<Recruiter[]>({
    queryKey: ['recruiters'],
    queryFn: () => apiFetch('/recruiters'),
  })

  const cities = citiesQuery.data || []
  const recruiters = (recruitersQuery.data || []).filter((r) => r.active !== false)

  // Auto-select city based on candidate's city
  useEffect(() => {
    if (candidateCity && cities.length > 0 && !form.city_id) {
      const match = cities.find((c) => c.name.toLowerCase() === candidateCity.toLowerCase())
      if (match) {
        setForm((f) => ({ ...f, city_id: String(match.id) }))
      }
    }
  }, [candidateCity, cities, form.city_id])

  const selectedCity = useMemo(() => cities.find((c) => String(c.id) === form.city_id), [cities, form.city_id])
  const cityTz = selectedCity?.tz || 'Europe/Moscow'

  const mutation = useMutation({
    mutationFn: async () => {
      return apiFetch(`/candidates/${candidateId}/schedule-slot`, {
        method: 'POST',
        body: JSON.stringify({
          recruiter_id: Number(form.recruiter_id),
          city_id: Number(form.city_id),
          date: form.date,
          time: form.time,
          custom_message: form.custom_message || null,
        }),
      })
    },
    onSuccess: () => {
      onSuccess()
      onClose()
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const canSubmit = form.recruiter_id && form.city_id && form.date && form.time

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: 16,
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="glass panel" style={{ maxWidth: 500, width: '100%', maxHeight: '90vh', overflow: 'auto' }}>
        <h2 className="title" style={{ marginBottom: 4 }}>Назначить собеседование</h2>
        <p className="subtitle" style={{ marginBottom: 16 }}>
          Кандидат: <strong>{candidateFio}</strong>
        </p>

        {error && (
          <div style={{ background: 'rgba(240, 115, 115, 0.15)', border: '1px solid rgba(240, 115, 115, 0.3)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
            <p style={{ color: '#f07373', margin: 0 }}>{error}</p>
          </div>
        )}

        <div style={{ display: 'grid', gap: 12 }}>
          <label style={{ display: 'grid', gap: 4 }}>
            <span>Рекрутёр</span>
            <select
              value={form.recruiter_id}
              onChange={(e) => setForm({ ...form, recruiter_id: e.target.value })}
              disabled={recruitersQuery.isLoading}
            >
              <option value="">— выберите рекрутёра —</option>
              {recruiters.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
          </label>

          <label style={{ display: 'grid', gap: 4 }}>
            <span>Город</span>
            <select
              value={form.city_id}
              onChange={(e) => setForm({ ...form, city_id: e.target.value })}
              disabled={citiesQuery.isLoading}
            >
              <option value="">— выберите город —</option>
              {cities.map((c) => (
                <option key={c.id} value={c.id}>{c.name} {c.tz ? `(${formatTzOffset(c.tz)})` : ''}</option>
              ))}
            </select>
            {selectedCity && (
              <span className="subtitle">Часовой пояс: {cityTz} ({formatTzOffset(cityTz)})</span>
            )}
          </label>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label style={{ display: 'grid', gap: 4 }}>
              <span>Дата</span>
              <input
                type="date"
                value={form.date}
                onChange={(e) => setForm({ ...form, date: e.target.value })}
              />
            </label>
            <label style={{ display: 'grid', gap: 4 }}>
              <span>Время</span>
              <input
                type="time"
                value={form.time}
                onChange={(e) => setForm({ ...form, time: e.target.value })}
              />
            </label>
          </div>

          <label style={{ display: 'grid', gap: 4 }}>
            <span>Персональное сообщение (опционально)</span>
            <textarea
              rows={3}
              value={form.custom_message}
              onChange={(e) => setForm({ ...form, custom_message: e.target.value })}
              placeholder="Введите текст сообщения для кандидата..."
            />
          </label>
        </div>

        <div className="action-row" style={{ marginTop: 16 }}>
          <button
            className="ui-btn ui-btn--primary"
            onClick={() => mutation.mutate()}
            disabled={!canSubmit || mutation.isPending}
          >
            {mutation.isPending ? 'Назначаем...' : 'Назначить собеседование'}
          </button>
          <button className="ui-btn ui-btn--ghost" onClick={onClose}>
            Отмена
          </button>
        </div>
      </div>
    </div>
  )
}

type ScheduleIntroDayModalProps = {
  candidateId: number
  candidateFio: string
  candidateCity?: string | null
  onClose: () => void
  onSuccess: () => void
}

function ScheduleIntroDayModal({ candidateId, candidateFio, candidateCity, onClose, onSuccess }: ScheduleIntroDayModalProps) {
  const [form, setForm] = useState({
    date: getTomorrowDate(),
    time: '10:00',
  })
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      return apiFetch(`/candidates/${candidateId}/schedule-intro-day`, {
        method: 'POST',
        body: JSON.stringify({
          date: form.date,
          time: form.time,
        }),
      })
    },
    onSuccess: () => {
      onSuccess()
      onClose()
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const canSubmit = form.date && form.time

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: 16,
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="glass panel" style={{ maxWidth: 400, width: '100%' }}>
        <h2 className="title" style={{ marginBottom: 4 }}>Назначить ознакомительный день</h2>
        <p className="subtitle" style={{ marginBottom: 16 }}>
          Кандидат: <strong>{candidateFio}</strong>
          {candidateCity && <><br />Город: {candidateCity}</>}
        </p>

        {error && (
          <div style={{ background: 'rgba(240, 115, 115, 0.15)', border: '1px solid rgba(240, 115, 115, 0.3)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
            <p style={{ color: '#f07373', margin: 0 }}>{error}</p>
          </div>
        )}

        <div style={{ display: 'grid', gap: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label style={{ display: 'grid', gap: 4 }}>
              <span>Дата</span>
              <input
                type="date"
                value={form.date}
                onChange={(e) => setForm({ ...form, date: e.target.value })}
              />
            </label>
            <label style={{ display: 'grid', gap: 4 }}>
              <span>Время</span>
              <input
                type="time"
                value={form.time}
                onChange={(e) => setForm({ ...form, time: e.target.value })}
              />
            </label>
          </div>
        </div>

        <p className="subtitle" style={{ marginTop: 12 }}>
          Адрес и контакт руководителя будут взяты из шаблона города.
        </p>

        <div className="action-row" style={{ marginTop: 16 }}>
          <button
            className="ui-btn ui-btn--primary"
            onClick={() => mutation.mutate()}
            disabled={!canSubmit || mutation.isPending}
          >
            {mutation.isPending ? 'Назначаем...' : 'Назначить ОД'}
          </button>
          <button className="ui-btn ui-btn--ghost" onClick={onClose}>
            Отмена
          </button>
        </div>
      </div>
    </div>
  )
}

export function CandidateDetailPage() {
  const queryClient = useQueryClient()
  const params = useParams({ from: 'candidateDetail' })
  const candidateId = Number(params.candidateId)
  const [chatText, setChatText] = useState('')
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [showScheduleSlotModal, setShowScheduleSlotModal] = useState(false)
  const [showScheduleIntroDayModal, setShowScheduleIntroDayModal] = useState(false)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [manualStatus, setManualStatus] = useState<string>('')

  const detailQuery = useQuery<CandidateDetail>({
    queryKey: ['candidate-detail', candidateId],
    queryFn: () => apiFetch(`/candidates/${candidateId}`),
  })

  const chatQuery = useQuery<ChatPayload>({
    queryKey: ['candidate-chat', candidateId],
    queryFn: () => apiFetch(`/candidates/${candidateId}/chat?limit=50`),
  })

  const sendMutation = useMutation({
    mutationFn: async (text: string) => {
      return apiFetch(`/candidates/${candidateId}/chat`, {
        method: 'POST',
        body: JSON.stringify({ text, client_request_id: String(Date.now()) }),
      })
    },
    onSuccess: () => {
      setChatText('')
      chatQuery.refetch()
    },
  })

  const actionMutation = useMutation({
    mutationFn: async (action: CandidateAction) => {
      return apiFetch(`/candidates/${candidateId}/actions/${action.key}`, { method: 'POST' })
    },
    onSuccess: () => {
      setActionMessage('Действие выполнено')
      detailQuery.refetch()
    },
    onError: (err: unknown) => {
      setActionMessage((err as Error).message)
    },
  })

  const detail = detailQuery.data
  const actions = detail?.candidate_actions || []
  const slots = detail?.slots || []
  const testSections = detail?.test_sections || []
  const chatMessages = (chatQuery.data?.messages || []).slice().reverse()
  const allowedNext = detail?.allowed_next_statuses || []
  const pipelineStages = detail?.pipeline_stages || []
  const legacyEnabled = Boolean(detail?.legacy_status_enabled)

  useEffect(() => {
    if (!detail) return
    if (detail.candidate_status_slug && !manualStatus) {
      setManualStatus(detail.candidate_status_slug)
    } else if (!manualStatus && detail.candidate_status_options?.length) {
      setManualStatus(detail.candidate_status_options[0].slug)
    }
  }, [detail, manualStatus])

  const onActionClick = (action: CandidateAction) => {
    if ((action.method || 'GET').toUpperCase() === 'GET') {
      if (action.url) {
        window.location.href = action.url
      }
      return
    }
    if (action.confirmation && !window.confirm(action.confirmation)) {
      return
    }
    actionMutation.mutate(action)
  }

  const statusDisplay = detail ? getStatusDisplay(detail.candidate_status_slug) : null
  const hasUpcomingSlot = slots.some((s) => s.status === 'BOOKED' || s.status === 'PENDING')
  const hasIntroDay = slots.some((s) => s.purpose === 'intro_day')

  const legacyStatusMutation = useMutation({
    mutationFn: async (statusSlug: string) => {
      setStatusError(null)
      const response = await fetch(`/candidates/${candidateId}/status`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: statusSlug }),
      })
      if (!response.ok) {
        const text = await response.text()
        throw new Error(text || 'Ошибка смены статуса')
      }
      return response.json().catch(() => ({}))
    },
    onSuccess: () => {
      detailQuery.refetch()
    },
    onError: (err: unknown) => {
      setStatusError((err as Error).message)
    },
  })

  const nextStatusActions = allowedNext.map((next) => {
    const action = actions.find((a) => a.target_status === next.slug)
    return { next, action }
  })

  return (
    <RoleGuard allow={['admin', 'recruiter']}>
      <div className="page">
        <div className="glass panel" style={{ display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <h1 className="title" style={{ margin: 0 }}>{detail?.fio || `Кандидат #${candidateId}`}</h1>
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                {detail?.city || 'Город не указан'}
                {detail?.telegram_id && (
                  <> · <a href={`https://t.me/${detail.telegram_id}`} target="_blank" rel="noopener" style={{ color: 'var(--accent)' }}>
                    tg: {detail.telegram_id}
                  </a></>
                )}
                {detail?.phone && <> · тел: {detail.phone}</>}
              </p>
            </div>
            <div className="action-row">
              <Link to="/app/candidates" className="glass action-link">← К списку</Link>
            </div>
          </div>

          {detailQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {detailQuery.isError && <p style={{ color: '#f07373' }}>Ошибка: {(detailQuery.error as Error).message}</p>}

          {detail && (
            <>
              {/* Status Badge */}
              {statusDisplay && (
                <div
                  className="glass panel--tight"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '8px 16px',
                    borderRadius: 12,
                    background: statusDisplay.tone === 'success'
                      ? 'rgba(100, 200, 100, 0.15)'
                      : statusDisplay.tone === 'danger'
                        ? 'rgba(240, 115, 115, 0.15)'
                        : statusDisplay.tone === 'warning'
                          ? 'rgba(255, 200, 100, 0.15)'
                          : 'rgba(105, 183, 255, 0.1)',
                    border: `1px solid ${
                      statusDisplay.tone === 'success'
                        ? 'rgba(100, 200, 100, 0.3)'
                        : statusDisplay.tone === 'danger'
                          ? 'rgba(240, 115, 115, 0.3)'
                          : statusDisplay.tone === 'warning'
                            ? 'rgba(255, 200, 100, 0.3)'
                            : 'rgba(105, 183, 255, 0.2)'
                    }`,
                  }}
                >
                  <span style={{ fontSize: 18 }}>{statusDisplay.icon}</span>
                  <span style={{ fontWeight: 600 }}>{statusDisplay.label}</span>
                </div>
              )}

              <div className="grid-cards">
                <div className="glass stat-card">
                  <div className="stat-label">Стадия воронки</div>
                  <div className="stat-value">{detail.stage || detail.workflow_status_label || '—'}</div>
                </div>
                <div className="glass stat-card">
                  <div className="stat-label">Тесты пройдено</div>
                  <div className="stat-value">{detail.stats?.tests_total ?? 0}</div>
                  <div className="stat-label" style={{ marginTop: 6 }}>
                    Средний балл: {detail.stats?.average_score ?? '—'}
                  </div>
                </div>
                <div className="glass stat-card">
                  <div className="stat-label">Ответственный</div>
                  <div className="stat-value">{detail.responsible_recruiter?.name || '—'}</div>
                  <div className="stat-label" style={{ marginTop: 6 }}>
                    Активен: {detail.is_active ? 'да' : 'нет'}
                  </div>
                </div>
                {detail.telemost_url && (
                  <div className="glass stat-card">
                    <div className="stat-label">Telemost</div>
                    <a href={detail.telemost_url} target="_blank" rel="noopener" className="stat-value" style={{ color: 'var(--accent)', fontSize: 14 }}>
                      Открыть ссылку →
                    </a>
                    <div className="stat-label" style={{ marginTop: 6 }}>
                      Источник: {detail.telemost_source || '—'}
                    </div>
                  </div>
                )}
              </div>

              {(pipelineStages.length > 0 || allowedNext.length > 0) && (
                <div className="glass panel--tight" style={{ display: 'grid', gap: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ width: 10, height: 10, borderRadius: 999, background: 'var(--accent)', display: 'inline-block' }} />
                      <strong>Статус-центр</strong>
                    </div>
                    {detail.status_is_terminal && (
                      <span className="chip">Финальный</span>
                    )}
                  </div>

                  {pipelineStages.length > 0 && (
                    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${pipelineStages.length}, minmax(80px, 1fr))`, gap: 6 }}>
                      {pipelineStages.map((stage, idx) => {
                        const state = stage.state || 'pending'
                        const bg =
                          state === 'active' ? 'rgba(105, 183, 255, 0.2)' :
                          state === 'passed' ? 'rgba(100, 200, 100, 0.2)' :
                          state === 'declined' ? 'rgba(240, 115, 115, 0.2)' :
                          'rgba(255,255,255,0.06)'
                        const border =
                          state === 'active' ? 'rgba(105, 183, 255, 0.4)' :
                          state === 'passed' ? 'rgba(100, 200, 100, 0.35)' :
                          state === 'declined' ? 'rgba(240, 115, 115, 0.35)' :
                          'rgba(255,255,255,0.12)'
                        return (
                          <div key={stage.key || idx} className="glass" style={{ padding: '8px 10px', textAlign: 'center', border: `1px solid ${border}`, background: bg }}>
                            <div style={{ fontSize: 12, fontWeight: 600 }}>{stage.label}</div>
                            <div className="subtitle" style={{ fontSize: 11 }}>{state}</div>
                          </div>
                        )
                      })}
                    </div>
                  )}

                  <div style={{ display: 'grid', gap: 8 }}>
                    <p className="subtitle" style={{ margin: 0 }}>Следующий статус:</p>
                    {nextStatusActions.length === 0 && (
                      <p className="subtitle">Нет доступных переходов.</p>
                    )}
                    {nextStatusActions.length > 0 && (
                      <div className="action-row" style={{ flexWrap: 'wrap' }}>
                        {nextStatusActions.map(({ next, action }) => {
                          const isTerminal = Boolean(next.is_terminal)
                          const label = next.label || next.slug
                          if (action) {
                            return (
                              <button
                                key={next.slug}
                                className={`ui-btn ${isTerminal ? 'ui-btn--danger' : 'ui-btn--primary'}`}
                                onClick={() => {
                                  if (isTerminal && !window.confirm(`Установить финальный статус «${label}»?`)) return
                                  actionMutation.mutate(action)
                                }}
                                disabled={actionMutation.isPending}
                              >
                                {label}
                              </button>
                            )
                          }
                          if (legacyEnabled) {
                            return (
                              <button
                                key={next.slug}
                                className={`ui-btn ${isTerminal ? 'ui-btn--danger' : 'ui-btn--primary'}`}
                                onClick={() => {
                                  if (isTerminal && !window.confirm(`Установить финальный статус «${label}»?`)) return
                                  legacyStatusMutation.mutate(next.slug)
                                }}
                                disabled={legacyStatusMutation.isPending}
                              >
                                {label}
                              </button>
                            )
                          }
                          return (
                            <button key={next.slug} className="ui-btn ui-btn--ghost" disabled>
                              {label}
                            </button>
                          )
                        })}
                      </div>
                    )}
                  </div>

                  {detail.candidate_status_options && detail.candidate_status_options.length > 0 && (
                    <div style={{ display: 'grid', gap: 8 }}>
                      <details>
                        <summary>Ручная коррекция статуса</summary>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 8 }}>
                          <select value={manualStatus} onChange={(e) => setManualStatus(e.target.value)}>
                            {detail.candidate_status_options.map((opt) => (
                              <option key={opt.slug} value={opt.slug}>{opt.label}</option>
                            ))}
                          </select>
                          <button
                            className="ui-btn ui-btn--ghost"
                            onClick={() => legacyStatusMutation.mutate(manualStatus)}
                            disabled={!legacyEnabled || legacyStatusMutation.isPending}
                          >
                            Применить
                          </button>
                        </div>
                        {!legacyEnabled && <p className="subtitle">Ручное изменение отключено в этой среде.</p>}
                      </details>
                    </div>
                  )}

                  {statusError && <p style={{ color: '#f07373' }}>{statusError}</p>}
                </div>
              )}

              <div>
                <h3 className="title" style={{ fontSize: 18, marginBottom: 8 }}>Действия</h3>
                <div className="action-row" style={{ flexWrap: 'wrap' }}>
                  {actions.length === 0 && <span className="subtitle">Нет доступных действий</span>}
                  {actions.map((action) => (
                    <button
                      key={action.key}
                      className={`ui-btn ${action.variant === 'primary' ? 'ui-btn--primary' : action.variant === 'danger' ? 'ui-btn--danger' : 'ui-btn--ghost'}`}
                      onClick={() => onActionClick(action)}
                      disabled={actionMutation.isPending}
                    >
                      {action.icon ? `${action.icon} ` : ''}{action.label}
                    </button>
                  ))}
                  {/* Scheduling actions - always show */}
                  {detail.telegram_id && !hasUpcomingSlot && (
                    <button className="ui-btn ui-btn--ghost" onClick={() => setShowScheduleSlotModal(true)}>
                      📅 Назначить собеседование
                    </button>
                  )}
                  {detail.telegram_id && !hasIntroDay && detail.candidate_status_slug && ['interview_passed', 'test2_passed'].includes(detail.candidate_status_slug) && (
                    <button className="ui-btn ui-btn--ghost" onClick={() => setShowScheduleIntroDayModal(true)}>
                      🏢 Назначить ознакомительный день
                    </button>
                  )}
                </div>
                {actionMessage && <p className="subtitle" style={{ marginTop: 8 }}>{actionMessage}</p>}
              </div>
            </>
          )}
        </div>

        <div className="glass panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h2 className="title" style={{ fontSize: 20, margin: 0 }}>Слоты и интервью</h2>
            {detail?.telegram_id && (
              <button className="ui-btn ui-btn--ghost" style={{ fontSize: 13 }} onClick={() => setShowScheduleSlotModal(true)}>
                + Назначить слот
              </button>
            )}
          </div>
          {slots.length === 0 && <p className="subtitle">Слоты не найдены</p>}
          {slots.length > 0 && (
            <table className="table slot-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Тип</th>
                  <th>Время</th>
                  <th>Статус</th>
                  <th>Рекрутёр</th>
                  <th>Город</th>
                </tr>
              </thead>
              <tbody>
                {slots.map((slot) => (
                  <tr key={slot.id} className="glass">
                    <td>{slot.id}</td>
                    <td>{slot.purpose === 'intro_day' ? '🏢 ОД' : '📅 Интервью'}</td>
                    <td>{formatSlotTime(slot.start_utc, slot.candidate_tz)}</td>
                    <td>{slot.status || '—'}</td>
                    <td>{slot.recruiter_name || '—'}</td>
                    <td>{slot.city_name || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="glass panel">
          <h2 className="title" style={{ fontSize: 20 }}>Тесты</h2>
          {testSections.length === 0 && <p className="subtitle">Данные по тестам отсутствуют.</p>}
          {testSections.length > 0 && (
            <div className="grid-cards">
              {testSections.map((section) => (
                <div key={section.key} className="glass stat-card">
                  <div className="stat-label">{section.title}</div>
                  <div className="stat-value">{section.status_label || section.status}</div>
                  <div className="stat-label" style={{ marginTop: 6 }}>{section.summary}</div>
                  {section.report_url && (
                    <a href={section.report_url} className="action-link" style={{ padding: 0, marginTop: 6 }}>
                      Отчёт →
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="glass panel">
          <h2 className="title" style={{ fontSize: 20 }}>Чат</h2>
          {chatQuery.isLoading && <p className="subtitle">Загрузка сообщений…</p>}
          {chatQuery.isError && <p style={{ color: '#f07373' }}>Ошибка: {(chatQuery.error as Error).message}</p>}
          {chatMessages.length > 0 && (
            <div style={{ display: 'grid', gap: 8, marginBottom: 12 }}>
              {chatMessages.map((msg) => (
                <div key={msg.id} className="glass panel--tight" style={{ display: 'grid', gap: 4 }}>
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                    {msg.direction === 'outbound' ? 'Исходящее' : 'Входящее'} · {new Date(msg.created_at).toLocaleString('ru-RU')}
                  </div>
                  <div>{msg.text}</div>
                </div>
              ))}
            </div>
          )}
          <div style={{ display: 'grid', gap: 8 }}>
            <textarea rows={3} value={chatText} onChange={(e) => setChatText(e.target.value)} placeholder="Написать сообщение…" />
            <button
              className="ui-btn ui-btn--primary"
              onClick={() => chatText.trim() && sendMutation.mutate(chatText.trim())}
              disabled={sendMutation.isPending}
            >
              {sendMutation.isPending ? 'Отправка…' : 'Отправить'}
            </button>
          </div>
        </div>
      </div>

      {/* Modals */}
      {showScheduleSlotModal && detail && (
        <ScheduleSlotModal
          candidateId={candidateId}
          candidateFio={detail.fio || `Кандидат #${candidateId}`}
          candidateCity={detail.city}
          onClose={() => setShowScheduleSlotModal(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['candidate-detail', candidateId] })
          }}
        />
      )}

      {showScheduleIntroDayModal && detail && (
        <ScheduleIntroDayModal
          candidateId={candidateId}
          candidateFio={detail.fio || `Кандидат #${candidateId}`}
          candidateCity={detail.city}
          onClose={() => setShowScheduleIntroDayModal(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['candidate-detail', candidateId] })
          }}
        />
      )}
    </RoleGuard>
  )
}
