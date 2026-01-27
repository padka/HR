import { useQuery, useMutation } from '@tanstack/react-query'
import { useMemo, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Link } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { useProfile } from '@/app/hooks/useProfile'
import { RoleGuard } from '@/app/components/RoleGuard'

type IncomingCandidate = {
  id: number
  name: string | null
  city: string | null
  city_id?: number | null
  status_display?: string | null
  status_slug?: string | null
  waiting_hours?: number | null
  availability_window?: string | null
  availability_note?: string | null
  telegram_id?: number | null
  telegram_username?: string | null
  last_message?: string | null
  last_message_at?: string | null
  responsible_recruiter_id?: number | null
  responsible_recruiter_name?: string | null
  profile_url?: string | null
}

type IncomingPayload = {
  items: IncomingCandidate[]
}

function ModalPortal({ children }: { children: ReactNode }) {
  if (typeof document === 'undefined') return null
  return createPortal(children, document.body)
}

function toIsoDate(value: Date) {
  return value.toISOString().slice(0, 10)
}

export function IncomingPage() {
  const profile = useProfile()
  const isAdmin = profile.data?.principal.type === 'admin'
  const [toast, setToast] = useState<string | null>(null)
  const [incomingTarget, setIncomingTarget] = useState<IncomingCandidate | null>(null)
  const [incomingDate, setIncomingDate] = useState(toIsoDate(new Date()))
  const [incomingTime, setIncomingTime] = useState('10:00')
  const [incomingMessage, setIncomingMessage] = useState('')
  const [search, setSearch] = useState('')
  const [cityFilter, setCityFilter] = useState('all')

  const showToast = (message: string) => {
    setToast(message)
    window.clearTimeout((showToast as any)._t)
    ;(showToast as any)._t = window.setTimeout(() => setToast(null), 2400)
  }

  const incomingQuery = useQuery<IncomingPayload>({
    queryKey: ['dashboard-incoming'],
    queryFn: () => apiFetch('/dashboard/incoming'),
    refetchInterval: 20000,
  })

  const recruitersQuery = useQuery<{ id: number; name: string }[]>({
    queryKey: ['incoming-recruiters'],
    queryFn: () => apiFetch('/recruiters'),
    enabled: Boolean(isAdmin),
    staleTime: 60_000,
  })

  const [assignTargets, setAssignTargets] = useState<Record<number, string>>({})

  const assignRecruiter = useMutation({
    mutationFn: async (payload: { candidateId: number; recruiterId: number }) =>
      apiFetch(`/candidates/${payload.candidateId}/assign-recruiter`, {
        method: 'POST',
        body: JSON.stringify({ recruiter_id: payload.recruiterId }),
      }),
    onSuccess: () => {
      showToast('Рекрутёр назначен')
      incomingQuery.refetch()
    },
    onError: (error: Error) => showToast(error.message),
  })

  const scheduleIncoming = useMutation({
    mutationFn: async (payload: { candidate: IncomingCandidate; date: string; time: string; message?: string }) => {
      const recruiterId = profile.data?.recruiter?.id
      if (!recruiterId) {
        throw new Error('Нет данных рекрутера')
      }
      if (!payload.candidate.city_id) {
        throw new Error('Не удалось определить город кандидата')
      }
      return apiFetch(`/candidates/${payload.candidate.id}/schedule-slot`, {
        method: 'POST',
        body: JSON.stringify({
          recruiter_id: recruiterId,
          city_id: payload.candidate.city_id,
          date: payload.date,
          time: payload.time,
          custom_message: payload.message || '',
        }),
      })
    },
    onSuccess: (data: any) => {
      showToast(data?.message || 'Собеседование назначено')
      setIncomingTarget(null)
      incomingQuery.refetch()
    },
    onError: (error: Error) => showToast(error.message),
  })

  const rejectCandidate = useMutation({
    mutationFn: async (candidateId: number) =>
      apiFetch(`/candidates/${candidateId}/actions/reject`, { method: 'POST' }),
    onSuccess: (data: any) => {
      showToast(data?.message || 'Кандидат отклонён')
      incomingQuery.refetch()
    },
    onError: (error: Error) => showToast(error.message),
  })

  const openIncomingSchedule = (candidate: IncomingCandidate) => {
    setIncomingTarget(candidate)
    setIncomingDate(toIsoDate(new Date()))
    setIncomingTime('10:00')
    setIncomingMessage(candidate.availability_note || '')
  }

  const cityOptions = profile.data?.recruiter?.cities || []
  const filteredItems = useMemo(() => {
    let items = incomingQuery.data?.items || []
    if (cityFilter !== 'all') {
      const cityId = Number(cityFilter)
      items = items.filter((item) => item.city_id === cityId)
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      items = items.filter((item) =>
        [item.name, item.city, String(item.telegram_id || '')]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(q))
      )
    }
    return items
  }, [incomingQuery.data, cityFilter, search])

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className="page">
        <header className="glass glass--elevated page-header page-header--row">
          <div>
            <h1 className="title">Входящие</h1>
            <p className="subtitle">Кандидаты прошли тест 1 и ждут свободный слот.</p>
          </div>
          <button className="ui-btn ui-btn--ghost" onClick={() => incomingQuery.refetch()}>
            Обновить
          </button>
        </header>

        <section className="glass page-section">
          <div className="filter-bar">
            <input
              placeholder="Поиск по ФИО, городу, TG..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="filter-bar__search"
            />
            <select value={cityFilter} onChange={(e) => setCityFilter(e.target.value)}>
              <option value="all">Все города</option>
              {cityOptions.map((city) => (
                <option key={city.id} value={String(city.id)}>{city.name}</option>
              ))}
            </select>
          </div>

          {incomingQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {incomingQuery.isError && (
            <p className="text-danger">Ошибка: {(incomingQuery.error as Error).message}</p>
          )}
          {incomingQuery.data && filteredItems.length === 0 && (
            <div>
              <p className="subtitle">Нет кандидатов, ожидающих слот.</p>
              {cityOptions.length ? (
                <p className="text-muted text-sm">
                  Ваши города: {cityOptions.map((c) => c.name).join(', ')}. Кандидаты из других городов не попадут в список.
                </p>
              ) : (
                <p className="text-muted text-sm">
                  Проверьте, что к вашему профилю привязаны города — иначе входящие не появятся.
                </p>
              )}
            </div>
          )}
          {incomingQuery.data && filteredItems.length > 0 && (
            <div className="incoming-grid">
              {filteredItems.map((candidate) => {
                const isNew = candidate.last_message_at
                  ? Date.now() - new Date(candidate.last_message_at).getTime() < 24 * 60 * 60 * 1000
                  : false
                const telegramUsername = candidate.telegram_username?.replace(/^@/, '')
                const telegramLink = telegramUsername
                  ? `https://t.me/${telegramUsername}`
                  : candidate.telegram_id
                    ? `tg://user?id=${candidate.telegram_id}`
                    : null
                const selectedRecruiter =
                  assignTargets[candidate.id] ??
                  (candidate.responsible_recruiter_id ? String(candidate.responsible_recruiter_id) : '')
                return (
                  <div key={candidate.id} className="glass glass--subtle incoming-card">
                    <div className="incoming-card__main">
                      <div>
                        <div className="incoming-card__name">
                          {candidate.name || 'Без имени'}
                          {isNew && <span className="incoming-card__badge">NEW</span>}
                        </div>
                        <div className="incoming-card__meta">
                          <span>{candidate.city || 'Город не указан'}</span>
                          {candidate.waiting_hours != null && (
                            <span>· ждёт {candidate.waiting_hours} ч</span>
                          )}
                          {candidate.availability_window && (
                            <span>· {candidate.availability_window}</span>
                          )}
                        </div>
                        {candidate.availability_note && (
                          <div className="incoming-card__note">
                            ✉️ {candidate.availability_note}
                          </div>
                        )}
                        {candidate.last_message && candidate.last_message !== candidate.availability_note && (
                          <div className="incoming-card__note">
                            💬 {candidate.last_message}
                            {candidate.last_message_at && (
                              <span className="incoming-card__note-time">
                                {new Date(candidate.last_message_at).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                              </span>
                            )}
                          </div>
                        )}
                        {isAdmin && (
                          <div className="incoming-card__note">
                            Ответственный: {candidate.responsible_recruiter_name || 'не назначен'}
                          </div>
                        )}
                      </div>
                      {candidate.status_display && (
                        <span
                          className={`status-pill status-pill--${
                            candidate.status_slug === 'stalled_waiting_slot' ? 'danger' : 'warning'
                          }`}
                        >
                          {candidate.status_display}
                        </span>
                      )}
                    </div>
                    {isAdmin && (
                      <div className="incoming-card__assign">
                        <select
                          value={selectedRecruiter}
                          onChange={(e) =>
                            setAssignTargets((prev) => ({ ...prev, [candidate.id]: e.target.value }))
                          }
                        >
                          <option value="">Выберите рекрутёра</option>
                          {(recruitersQuery.data || []).map((rec) => (
                            <option key={rec.id} value={String(rec.id)}>{rec.name}</option>
                          ))}
                        </select>
                        <button
                          className="ui-btn ui-btn--primary ui-btn--sm"
                          type="button"
                          disabled={!selectedRecruiter || assignRecruiter.isPending}
                          onClick={() =>
                            assignRecruiter.mutate({ candidateId: candidate.id, recruiterId: Number(selectedRecruiter) })
                          }
                        >
                          Назначить
                        </button>
                      </div>
                    )}
                    <div className="incoming-card__actions">
                      <Link
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        to="/app/candidates/$candidateId"
                        params={{ candidateId: String(candidate.id) }}
                      >
                        Профиль
                      </Link>
                      {telegramLink && (
                        <a className="ui-btn ui-btn--ghost ui-btn--sm" href={telegramLink} target="_blank" rel="noopener">
                          Telegram
                        </a>
                      )}
                      {!isAdmin && (
                        <button
                          className="ui-btn ui-btn--primary ui-btn--sm"
                          type="button"
                          onClick={() => openIncomingSchedule(candidate)}
                        >
                          Назначить
                        </button>
                      )}
                      <button
                        className="ui-btn ui-btn--danger ui-btn--sm"
                        type="button"
                        onClick={() => rejectCandidate.mutate(candidate.id)}
                      >
                        Отказать
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </section>
      </div>

      {incomingTarget && (
        <ModalPortal>
          <div
            className="modal-overlay"
            onClick={(e) => e.target === e.currentTarget && setIncomingTarget(null)}
            role="dialog"
            aria-modal="true"
          >
            <div className="glass glass--elevated modal modal--sm" onClick={(e) => e.stopPropagation()}>
              <div className="modal__header">
                <div>
                  <h2 className="modal__title">Назначить собеседование</h2>
                  <p className="modal__subtitle">{incomingTarget.name || 'Кандидат'}</p>
                </div>
                <button className="ui-btn ui-btn--ghost" onClick={() => setIncomingTarget(null)}>
                  Закрыть
                </button>
              </div>
              <div className="modal__body">
                <div className="form-grid">
                  <label>
                    Дата
                    <input type="date" value={incomingDate} onChange={(e) => setIncomingDate(e.target.value)} />
                  </label>
                  <label>
                    Время (локальное)
                    <input type="time" value={incomingTime} onChange={(e) => setIncomingTime(e.target.value)} />
                  </label>
                </div>
                <label>
                  Сообщение кандидату (необязательно)
                  <textarea
                    rows={3}
                    value={incomingMessage}
                    onChange={(e) => setIncomingMessage(e.target.value)}
                    placeholder="Например: подойдёт ли это время?"
                  />
                </label>
              </div>
              <div className="modal__footer">
                <button
                  className="ui-btn ui-btn--primary"
                  onClick={() => {
                    if (!incomingDate || !incomingTime) {
                      showToast('Укажите дату и время')
                      return
                    }
                    scheduleIncoming.mutate({
                      candidate: incomingTarget,
                      date: incomingDate,
                      time: incomingTime,
                      message: incomingMessage,
                    })
                  }}
                  disabled={scheduleIncoming.isPending}
                >
                  {scheduleIncoming.isPending ? 'Отправка…' : 'Назначить'}
                </button>
                <button className="ui-btn ui-btn--ghost" onClick={() => setIncomingTarget(null)}>
                  Отмена
                </button>
              </div>
            </div>
          </div>
        </ModalPortal>
      )}

      {toast && <div className="toast">{toast}</div>}
    </RoleGuard>
  )
}

export default IncomingPage
