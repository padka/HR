import { useQuery, useMutation } from '@tanstack/react-query'
import { useState, useMemo, useEffect, useCallback, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useProfile } from '@/app/hooks/useProfile'
import { Link } from '@tanstack/react-router'

type CandidateSearchItem = {
  id: number
  candidate_id: string;
  fio?: string | null
  city?: string | null
  telegram_id?: number | null
  status?: { slug?: string; label?: string }
}

type SlotApiItem = {
  id: number
  recruiter_id?: number | null
  recruiter_name?: string | null
  start_utc: string
  status?: string | null
  candidate_fio?: string | null
  candidate_tg_id?: string | null
  candidate_id?: number | null
  tz_name?: string | null
  local_time?: string | null
  recruiter_tz?: string | null
  recruiter_local_time?: string | null
  candidate_tz?: string | null
  candidate_local_time?: string | null
  city_name?: string | null
  purpose?: string | null
}

function statusLabel(status?: string) {
  switch (status) {
    case 'FREE':
      return 'Свободен'
    case 'PENDING':
      return 'Ожидает'
    case 'BOOKED':
      return 'Забронирован'
    case 'CONFIRMED_BY_CANDIDATE':
      return 'Подтверждён'
    default:
      return status || '—'
  }
}

function formatLocal(startUtc: string, tz?: string | null) {
  try {
    const d = new Date(startUtc)
    return new Intl.DateTimeFormat('ru-RU', {
      timeZone: tz || 'Europe/Moscow',
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d)
  } catch {
    return startUtc
  }
}

function formatLocalLabel(iso?: string | null) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d)
  } catch {
    return iso
  }
}

type BookingModalProps = {
  slot: SlotApiItem
  onClose: () => void
  onSuccess: () => void
  showToast: (msg: string) => void
}

function ModalPortal({ children }: { children: ReactNode }) {
  if (typeof document === 'undefined') return null
  return createPortal(children, document.body)
}

function BookingModal({ slot, onClose, onSuccess, showToast }: BookingModalProps) {
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateSearchItem | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  const searchQuery = useQuery<{ items: CandidateSearchItem[] }>({
    queryKey: ['candidates-search', debouncedSearch],
    queryFn: () => apiFetch(`/candidates?search=${encodeURIComponent(debouncedSearch)}&per_page=10`),
    enabled: debouncedSearch.length >= 2,
  })

  const candidates = searchQuery.data?.items || []

  const proposeMutation = useMutation({
    mutationFn: async () => {
      if (!selectedCandidate?.candidate_id) throw new Error('У кандидата нет ID')
      return apiFetch(`/slots/${slot.id}/propose`, {
        method: 'POST',
        body: JSON.stringify({
          candidate_id: selectedCandidate.candidate_id,
        }),
      })
    },
    onSuccess: () => {
      showToast('Предложение отправлено кандидату')
      onSuccess()
      onClose()
    },
    onError: (err: Error) => {
      showToast(`Ошибка: ${err.message}`)
    },
  })

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal modal--md" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <div>
            <h2 className="modal__title">Предложить слот</h2>
            <p className="modal__subtitle">
              {slot.recruiter_local_time
                ? formatLocalLabel(slot.recruiter_local_time)
                : formatLocal(slot.start_utc, slot.recruiter_tz || slot.tz_name || 'Europe/Moscow')}
            </p>
          </div>
          <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
        </div>

        <div className="modal__body">
          <div className="form-group">
            <label className="form-group__label">Поиск кандидата (ФИО или Telegram)</label>
            <input
              type="text"
              placeholder="Введите минимум 2 символа..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setSelectedCandidate(null) }}
            />
          </div>

          {searchQuery.isLoading && <p className="text-muted">Поиск...</p>}

          {candidates.length > 0 && !selectedCandidate && (
            <div className="modal__list">
              {candidates.map((c) => (
                <div
                  key={c.id}
                  className={`glass glass--interactive list-item list-item--compact ${!c.telegram_id ? 'list-item--disabled' : ''}`}
                  onClick={() => c.telegram_id && setSelectedCandidate(c)}
                >
                  <div className="font-semibold">{c.fio || '—'}</div>
                  <div className="text-muted text-sm">
                    {c.city || '—'} · tg: {c.telegram_id || 'нет'} · {c.status?.label || '—'}
                  </div>
                </div>
              ))}
            </div>
          )}

          {search.length >= 2 && candidates.length === 0 && !searchQuery.isLoading && (
            <p className="text-muted">Кандидаты не найдены</p>
          )}

          {selectedCandidate && (
            <div className="glass glass--subtle list-item list-item--selected">
              <div className="font-semibold">{selectedCandidate.fio}</div>
              <div className="text-muted text-sm">
                {selectedCandidate.city} · tg: {selectedCandidate.telegram_id}
              </div>
              <button
                className="ui-btn ui-btn--ghost ui-btn--sm"
                onClick={() => setSelectedCandidate(null)}
              >
                Выбрать другого
              </button>
            </div>
          )}
        </div>

        <div className="modal__footer">
          <button
            className="ui-btn ui-btn--primary"
            disabled={!selectedCandidate || proposeMutation.isPending}
            onClick={() => proposeMutation.mutate()}
          >
            {proposeMutation.isPending ? 'Отправляем...' : 'Предложить'}
          </button>
          <button className="ui-btn ui-btn--ghost" onClick={onClose}>Отмена</button>
        </div>
        </div>
      </div>
    </ModalPortal>
  )
}

type RescheduleModalProps = {
  slot: SlotApiItem
  onClose: () => void
  onSuccess: () => void
  showToast: (msg: string) => void
}

function getDateTimeParts(iso: string, tz?: string | null) {
  try {
    const d = new Date(iso)
    const fmt = new Intl.DateTimeFormat('en-CA', {
      timeZone: tz || 'Europe/Moscow',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
    const parts = fmt.formatToParts(d)
    const pick = (type: string) => parts.find((p) => p.type === type)?.value || ''
    const date = `${pick('year')}-${pick('month')}-${pick('day')}`
    const time = `${pick('hour')}:${pick('minute')}`
    return { date, time }
  } catch {
    return { date: '', time: '' }
  }
}

function RescheduleModal({ slot, onClose, onSuccess, showToast }: RescheduleModalProps) {
  const tzLabel = slot.recruiter_tz || slot.tz_name || 'Europe/Moscow'
  const baseIso = slot.recruiter_local_time || slot.start_utc
  const parts = getDateTimeParts(baseIso, tzLabel)
  const [date, setDate] = useState(parts.date)
  const [time, setTime] = useState(parts.time)
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const rescheduleMutation = useMutation({
    mutationFn: async () => {
      setError(null)
      if (!date || !time) {
        setError('Укажите дату и время')
        throw new Error('invalid_form')
      }
      if (!reason.trim()) {
        setError('Укажите причину переноса')
        throw new Error('invalid_form')
      }
      return apiFetch(`/slots/${slot.id}/reschedule`, {
        method: 'POST',
        body: JSON.stringify({ date, time, reason }),
      })
    },
    onSuccess: () => {
      showToast('Слот перенесён')
      onSuccess()
      onClose()
    },
    onError: (err: Error) => {
      if (err.message === 'invalid_form') return
      showToast(`Ошибка: ${err.message}`)
    },
  })

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal modal--md" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <div>
            <h2 className="modal__title">Перенести слот</h2>
            <p className="modal__subtitle">
              ID {slot.id} · {slot.candidate_fio || 'Без кандидата'}
            </p>
          </div>
          <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
        </div>

        <div className="modal__body">
          <div className="form-group">
            <label className="form-group__label">Новая дата</label>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-group__label">Новое время ({tzLabel})</label>
            <input type="time" value={time} onChange={(e) => setTime(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-group__label">Причина переноса</label>
            <textarea
              rows={3}
              placeholder="Опишите причину переноса..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          {error && <p className="text-muted" style={{ color: '#f07373' }}>{error}</p>}
        </div>

        <div className="modal__footer">
          <button
            className="ui-btn ui-btn--primary"
            disabled={rescheduleMutation.isPending}
            onClick={() => rescheduleMutation.mutate()}
          >
            {rescheduleMutation.isPending ? 'Отправляем…' : 'Перенести'}
          </button>
          <button className="ui-btn ui-btn--ghost" onClick={onClose}>Отмена</button>
        </div>
        </div>
      </div>
    </ModalPortal>
  )
}

export function SlotsPage() {
  const profile = useProfile()
  const canUse = profile.data?.principal.type === 'recruiter'
  const [status, setStatus] = useState<string | undefined>(undefined)
  const [purposeFilter, setPurposeFilter] = useState<string>('interview')
  const [limit, setLimit] = useState<number>(100)
  const [page, setPage] = useState<number>(1)
  const [perPage, setPerPage] = useState<number>(20)
  const [sheetSlot, setSheetSlot] = useState<SlotApiItem | null>(null)
  const [bookingSlot, setBookingSlot] = useState<SlotApiItem | null>(null)
  const [rescheduleTarget, setRescheduleTarget] = useState<SlotApiItem | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const modalOpen = Boolean(sheetSlot || bookingSlot || rescheduleTarget)

  const queryPath = useMemo(() => {
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    if (limit) params.set('limit', String(limit))
    params.set('page', String(page))
    params.set('per_page', String(perPage))
    return `/slots?${params.toString()}`
  }, [status, limit, page, perPage])

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery<SlotApiItem[]>({
    queryKey: ['slots', { status, limit, page, perPage }],
    queryFn: () => apiFetch<SlotApiItem[]>(queryPath),
    staleTime: 20_000,
    enabled: Boolean(canUse),
  })

  const filteredByPurpose = useMemo(() => {
    if (!data) return []
    if (purposeFilter === 'all') return data
    return data.filter((item) => (item.purpose || 'interview') === purposeFilter)
  }, [data, purposeFilter])

  const total = filteredByPurpose.length
  const pagesTotal = Math.max(1, Math.ceil(total / perPage))
  const pagedItems = filteredByPurpose.slice((page - 1) * perPage, page * perPage)

  const purposeCounts = useMemo(() => {
    if (!data) return { interview: 0, intro_day: 0 }
    let interview = 0, intro_day = 0
    data.forEach((item) => {
      if ((item.purpose || 'interview') === 'intro_day') intro_day++
      else interview++
    })
    return { interview, intro_day }
  }, [data])

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    filteredByPurpose.forEach((item) => {
      const key = String(item.status || 'UNKNOWN')
      counts[key] = (counts[key] || 0) + 1
    })
    return counts
  }, [filteredByPurpose])

  const canPrev = page > 1
  const canNext = page < pagesTotal

  const closeSheet = useCallback(() => setSheetSlot(null), [])

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 1800)
  }

  const deleteSlot = async (id: number) => {
    try {
      const result = await apiFetch<{ ok?: boolean; message?: string }>(`/slots/${id}`, { method: 'DELETE' })
      if (result?.ok === false) {
        throw new Error(result.message || 'Удаление не выполнено')
      }
      showToast('Слот удалён')
      setSelectedIds((prev) => {
        if (!prev.has(id)) return prev
        const next = new Set(prev)
        next.delete(id)
        return next
      })
      closeSheet()
      refetch()
    } catch (err) {
      showToast(`Ошибка удаления: ${(err as Error).message}`)
    }
  }

  const rejectSlot = async (id: number) => {
    try {
      await apiFetch(`/slots/${id}/reject_booking`, { method: 'POST' })
      showToast('Заявка отклонена')
      closeSheet()
      refetch()
    } catch (err) {
      showToast(`Ошибка: ${(err as Error).message}`)
    }
  }

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const selectAll = () => {
    if (pagedItems.length === selectedIds.size) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(pagedItems.map((s) => s.id)))
    }
  }

  const clearSelection = () => setSelectedIds(new Set())

  const bulkDelete = async () => {
    if (selectedIds.size === 0) return
    if (!window.confirm(`Удалить ${selectedIds.size} слотов?`)) return
    try {
      await apiFetch('/slots/bulk', {
        method: 'POST',
        body: JSON.stringify({
          action: 'delete',
          slot_ids: Array.from(selectedIds),
          force: false,
        }),
      })
      showToast(`Удалено ${selectedIds.size} слотов`)
      clearSelection()
      refetch()
    } catch (err) {
      showToast(`Ошибка: ${(err as Error).message}`)
    }
  }

  const bulkRemind = async () => {
    if (selectedIds.size === 0) return
    try {
      await apiFetch('/slots/bulk', {
        method: 'POST',
        body: JSON.stringify({
          action: 'remind',
          slot_ids: Array.from(selectedIds),
        }),
      })
      showToast(`Напоминания запланированы для ${selectedIds.size} слотов`)
      clearSelection()
    } catch (err) {
      showToast(`Ошибка: ${(err as Error).message}`)
    }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeSheet()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [closeSheet])

  useEffect(() => {
    if (typeof document === 'undefined') return
    if (!modalOpen) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [modalOpen])

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className="page">
        <section className="glass glass--elevated page-header page-header--row">
          <div>
            <h1 className="title">Слоты</h1>
            <div className="slots-summary" role="group" aria-label="Тип слотов" style={{ marginBottom: 8 }}>
              {[
                { key: 'interview', label: 'Собеседования', value: purposeCounts.interview, tone: 'accent' },
                { key: 'intro_day', label: 'Ознакомительные дни', value: purposeCounts.intro_day, tone: 'success' },
                { key: 'all', label: 'Все', value: (data?.length || 0), tone: 'neutral' },
              ].map((item) => {
                const isActive = item.key === purposeFilter
                return (
                  <button
                    key={item.key}
                    type="button"
                    className={`slots-summary__card slots-summary__card--${item.tone} ${isActive ? 'is-active' : ''}`}
                    onClick={() => { setPurposeFilter(item.key); setPage(1) }}
                    aria-pressed={isActive}
                  >
                    <span className="slots-summary__label">{item.label}</span>
                    <span className="slots-summary__value">{item.value}</span>
                  </button>
                )
              })}
            </div>
            <div className="slots-summary" role="group" aria-label="Сводка слотов">
              {[
                { key: 'all', label: 'Всего', value: total, status: undefined, tone: 'neutral' },
                { key: 'free', label: 'Свободные', value: statusCounts['FREE'] ?? 0, status: 'FREE', tone: 'success' },
                { key: 'booked', label: 'Забронировано', value: statusCounts['BOOKED'] ?? 0, status: 'BOOKED', tone: 'accent' },
                { key: 'pending', label: 'Ожидают', value: statusCounts['PENDING'] ?? 0, status: 'PENDING', tone: 'warning' },
              ].map((item) => {
                const isActive = item.status === status || (!item.status && !status)
                return (
                  <button
                    key={item.key}
                    type="button"
                    className={`slots-summary__card slots-summary__card--${item.tone} ${isActive ? 'is-active' : ''}`}
                    onClick={() => {
                      setStatus(item.status)
                      setPage(1)
                    }}
                    aria-pressed={isActive}
                  >
                    <span className="slots-summary__label">{item.label}</span>
                    <span className="slots-summary__value">{item.value}</span>
                  </button>
                )
              })}
            </div>
          </div>
          <Link to="/app/slots/create" className="ui-btn ui-btn--primary" style={{ marginBottom: '16px' }}>
            + Создать слоты
          </Link>

          <div className="filter-bar">
            <label className="filter-bar__item">
              <span className="filter-bar__label">Статус</span>
              <select value={status ?? ''} onChange={(e) => setStatus(e.target.value || undefined)}>
                <option value="">Любой</option>
                <option value="FREE">Свободные</option>
                <option value="PENDING">Ожидают</option>
                <option value="BOOKED">Забронированы</option>
                <option value="CONFIRMED_BY_CANDIDATE">Подтверждены</option>
              </select>
            </label>
            <label className="filter-bar__item">
              <span className="filter-bar__label">Лимит</span>
              <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
                {[50, 100, 200, 300, 500].map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </label>
            <button className="ui-btn ui-btn--primary" onClick={() => refetch()}>
              {isFetching ? 'Обновляем…' : 'Обновить'}
            </button>
          </div>

          <div className="pagination">
            <span className="pagination__info">Страница: {page} / {pagesTotal}</span>
            <button className="ui-btn ui-btn--ghost ui-btn--sm" disabled={!canPrev} onClick={() => setPage((p) => Math.max(1, p - 1))}>Назад</button>
            <button className="ui-btn ui-btn--ghost ui-btn--sm" disabled={!canNext} onClick={() => setPage((p) => p + 1)}>Вперёд</button>
            <label className="filter-bar__item">
              <span className="filter-bar__label">Per page</span>
              <select value={perPage} onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1) }}>
                {[10, 20, 50, 100].map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </label>
          </div>

          {isLoading && (
            <div className="loading-skeleton">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="loading-skeleton__row" />
              ))}
            </div>
          )}
          {isError && (
            <div className="glass page-section__error">
              Ошибка загрузки: {(error as Error).message}
            </div>
          )}

          {!isLoading && data && data.length === 0 && (
            <div className="empty-state">
              <p className="empty-state__text">Слотов нет.</p>
            </div>
          )}

          {selectedIds.size > 0 && (
            <div className="toolbar toolbar--accent">
              <span className="toolbar__label">Выбрано: {selectedIds.size}</span>
              <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={bulkRemind}>
                Напоминания
              </button>
              <button className="ui-btn ui-btn--danger ui-btn--sm" onClick={bulkDelete}>
                Удалить
              </button>
              <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={clearSelection}>
                Снять выбор
              </button>
            </div>
          )}

          {!isLoading && data && data.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th className="data-table__th--checkbox">
                    <input
                      type="checkbox"
                      checked={pagedItems.length > 0 && pagedItems.every((s) => selectedIds.has(s.id))}
                      onChange={selectAll}
                      title="Выбрать все"
                    />
                  </th>
                  <th>Тип</th>
                  <th>Кандидат</th>
                  <th>Город</th>
                  <th>Время</th>
                  <th>Статус</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {pagedItems.map((row: SlotApiItem) => {
                  const recruiterTz = row.recruiter_tz || row.tz_name || 'Europe/Moscow'
                  const recruiterTimeLabel = row.recruiter_local_time
                    ? formatLocalLabel(row.recruiter_local_time)
                    : formatLocal(row.start_utc, recruiterTz)
                  const candidateTz = row.candidate_tz
                  const candidateTimeLabel = row.candidate_local_time
                    ? formatLocalLabel(row.candidate_local_time)
                    : (candidateTz ? formatLocal(row.start_utc, candidateTz) : null)
                  const hasCandidate = Boolean(row.candidate_fio || row.candidate_tg_id)
                  const candidateProfileId = row.candidate_id ? String(row.candidate_id) : null
                  return (
                  <tr key={row.id} className={selectedIds.has(row.id) ? 'data-table__row--selected' : ''}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(row.id)}
                        onChange={() => toggleSelect(row.id)}
                      />
                    </td>
                    <td>
                      <span className={`cd-chip ${(row.purpose || 'interview') === 'intro_day' ? 'cd-chip--accent' : ''}`}>
                        {(row.purpose || 'interview') === 'intro_day' ? 'ОД' : 'Собес'}
                      </span>
                    </td>
                    <td>
                      <div className="slot-candidate">
                        <div className="slot-candidate__name">
                          {row.candidate_fio || 'Свободный слот'}
                        </div>
                        <div className="slot-candidate__meta">
                          {row.candidate_tg_id ? `tg_id: ${row.candidate_tg_id}` : (hasCandidate ? 'Без tg_id' : 'Назначьте кандидата')}
                        </div>
                      </div>
                    </td>
                    <td>{row.city_name || '—'}</td>
                    <td>
                  <div className="slot-time">
                    <div className="slot-time__primary">
                      {recruiterTimeLabel}
                      <span className="slot-time__tz">{recruiterTz}</span>
                    </div>
                    {candidateTimeLabel &&
                      (candidateTimeLabel !== recruiterTimeLabel || candidateTz !== recruiterTz) &&
                      candidateTz && (
                        <div className="slot-time__secondary">
                          {candidateTimeLabel} · {candidateTz}
                        </div>
                      )}
                  </div>
                </td>
                    <td>
                      <span className={`status-badge status-badge--${
                        row.status === 'PENDING' ? 'warning' :
                        row.status === 'BOOKED' ? 'success' :
                        row.status === 'FREE' ? 'info' : 'muted'
                      }`}>
                        {statusLabel(row.status || undefined)}
                      </span>
                    </td>
                    <td>
                      <div className="toolbar toolbar--compact">
                        {candidateProfileId ? (
                          <Link
                            to="/app/candidates/$candidateId"
                            params={{ candidateId: String(candidateProfileId) }}
                            className="ui-btn ui-btn--ghost ui-btn--sm"
                          >
                            Профиль
                          </Link>
                        ) : (
                          <button className="ui-btn ui-btn--ghost ui-btn--sm" disabled title="Нет кандидата">
                            Профиль
                          </button>
                        )}
                        {row.status === 'FREE' ? (
                          <>
                            <button
                              className="ui-btn ui-btn--ghost ui-btn--sm"
                              onClick={() => setBookingSlot(row)}
                            >
                              Назначить
                            </button>
                            <button
                              className="ui-btn ui-btn--danger ui-btn--sm"
                              onClick={() => deleteSlot(row.id)}
                            >
                              Удалить
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              className="ui-btn ui-btn--ghost ui-btn--sm"
                              onClick={() => setRescheduleTarget(row)}
                            >
                              Перенести
                            </button>
                            <button
                              className="ui-btn ui-btn--danger ui-btn--sm"
                              onClick={() => rejectSlot(row.id)}
                            >
                              Освободить
                            </button>
                          </>
                        )}
                        <button
                          className="ui-btn ui-btn--ghost ui-btn--sm"
                          onClick={() => setSheetSlot(row)}
                          title="Подробнее"
                        >
                          ...
                        </button>
                      </div>
                    </td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
          )}

          {sheetSlot && (
            <ModalPortal>
              <div className="modal-overlay" onClick={closeSheet} role="dialog" aria-modal="true">
                <div className="glass glass--elevated modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal__header">
                  <div>
                    <h2 className="modal__title">Слот</h2>
                    <p className="modal__subtitle">{sheetSlot.candidate_fio || 'Свободный слот'}</p>
                  </div>
                  <button className="ui-btn ui-btn--ghost" onClick={closeSheet}>Закрыть</button>
                </div>
                <div className="modal__body">
                  <div className="modal__row">
                    <strong>Время рекрутёра:</strong> {sheetSlot.recruiter_local_time
                      ? formatLocalLabel(sheetSlot.recruiter_local_time)
                      : formatLocal(sheetSlot.start_utc, sheetSlot.recruiter_tz || sheetSlot.tz_name || 'Europe/Moscow')} · {sheetSlot.recruiter_tz || sheetSlot.tz_name || 'Europe/Moscow'}
                  </div>
                  <div className="modal__row">
                    <strong>Время кандидата:</strong> {sheetSlot.candidate_local_time
                      ? formatLocalLabel(sheetSlot.candidate_local_time)
                      : (sheetSlot.candidate_tz ? formatLocal(sheetSlot.start_utc, sheetSlot.candidate_tz) : '—')} · {sheetSlot.candidate_tz || '—'}
                  </div>
                  <div className="modal__row"><strong>Кандидат:</strong> {sheetSlot.candidate_fio || 'Нет брони'} · tg_id: {sheetSlot.candidate_tg_id || '—'}</div>
                  <div className="modal__row"><strong>Статус:</strong> {statusLabel(sheetSlot.status || undefined)}</div>
                </div>
                <div className="modal__footer">
                  {sheetSlot.status === 'FREE' && (
                    <button className="ui-btn ui-btn--primary" onClick={() => { closeSheet(); setBookingSlot(sheetSlot) }}>
                      Назначить кандидата
                    </button>
                  )}
                  {sheetSlot.status !== 'FREE' && (
                    <>
                      <button className="ui-btn ui-btn--ghost" onClick={() => setRescheduleTarget(sheetSlot)}>
                        Перенести
                      </button>
                      <button className="ui-btn ui-btn--danger" onClick={() => rejectSlot(sheetSlot.id)}>
                        Освободить
                      </button>
                    </>
                  )}
                  {sheetSlot.status === 'FREE' && (
                    <button className="ui-btn ui-btn--danger" onClick={() => deleteSlot(sheetSlot.id)}>Удалить</button>
                  )}
                </div>
                </div>
              </div>
            </ModalPortal>
          )}

          {toast && (
            <div className="toast">{toast}</div>
          )}

          {bookingSlot && (
            <BookingModal
              slot={bookingSlot}
              onClose={() => setBookingSlot(null)}
              onSuccess={() => refetch()}
              showToast={showToast}
            />
          )}

          {rescheduleTarget && (
            <RescheduleModal
              slot={rescheduleTarget}
              onClose={() => setRescheduleTarget(null)}
              onSuccess={() => refetch()}
              showToast={showToast}
            />
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
