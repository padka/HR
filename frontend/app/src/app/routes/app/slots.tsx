import { useQuery, useMutation } from '@tanstack/react-query'
import { useState, useMemo, useEffect, useCallback } from 'react'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useProfile } from '@/app/hooks/useProfile'
import { Link } from '@tanstack/react-router'

type CandidateSearchItem = {
  id: number
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
  tz_name?: string | null
  local_time?: string | null
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

type BookingModalProps = {
  slot: SlotApiItem
  onClose: () => void
  onSuccess: () => void
  showToast: (msg: string) => void
}

function BookingModal({ slot, onClose, onSuccess, showToast }: BookingModalProps) {
  const [search, setSearch] = useState('')
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateSearchItem | null>(null)

  const searchQuery = useQuery<{ items: CandidateSearchItem[] }>({
    queryKey: ['candidates-search', search],
    queryFn: () => apiFetch(`/candidates?search=${encodeURIComponent(search)}&per_page=10`),
    enabled: search.length >= 2,
  })

  const candidates = searchQuery.data?.items || []

  const bookMutation = useMutation({
    mutationFn: async () => {
      if (!selectedCandidate?.telegram_id) throw new Error('Кандидат без Telegram ID')
      return apiFetch(`/slots/${slot.id}/book`, {
        method: 'POST',
        body: JSON.stringify({
          candidate_tg_id: selectedCandidate.telegram_id,
          candidate_fio: selectedCandidate.fio,
        }),
      })
    },
    onSuccess: () => {
      showToast('Кандидат забронирован')
      onSuccess()
      onClose()
    },
    onError: (err: Error) => {
      showToast(`Ошибка: ${err.message}`)
    },
  })

  return (
    <div className="overlay" onClick={onClose}>
      <div className="glass sheet" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 500 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
          <div>
            <h2 style={{ margin: 0 }}>Забронировать слот</h2>
            <p className="subtitle" style={{ margin: '4px 0 0' }}>
              ID {slot.id} · {slot.local_time || formatLocal(slot.start_utc, slot.tz_name)}
            </p>
          </div>
          <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
        </div>

        <div style={{ marginTop: 16 }}>
          <label style={{ display: 'grid', gap: 6 }}>
            <span>Поиск кандидата (ФИО или Telegram)</span>
            <input
              type="text"
              placeholder="Введите минимум 2 символа..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setSelectedCandidate(null) }}
            />
          </label>

          {searchQuery.isLoading && <p className="subtitle" style={{ marginTop: 8 }}>Поиск...</p>}

          {candidates.length > 0 && !selectedCandidate && (
            <div style={{ marginTop: 8, maxHeight: 200, overflow: 'auto' }}>
              {candidates.map((c) => (
                <div
                  key={c.id}
                  className="glass"
                  style={{
                    padding: '8px 12px',
                    marginBottom: 4,
                    cursor: c.telegram_id ? 'pointer' : 'not-allowed',
                    opacity: c.telegram_id ? 1 : 0.5,
                  }}
                  onClick={() => c.telegram_id && setSelectedCandidate(c)}
                >
                  <div style={{ fontWeight: 600 }}>{c.fio || '—'}</div>
                  <div className="subtitle" style={{ fontSize: 12 }}>
                    {c.city || '—'} · tg: {c.telegram_id || 'нет'} · {c.status?.label || '—'}
                  </div>
                </div>
              ))}
            </div>
          )}

          {search.length >= 2 && candidates.length === 0 && !searchQuery.isLoading && (
            <p className="subtitle" style={{ marginTop: 8 }}>Кандидаты не найдены</p>
          )}

          {selectedCandidate && (
            <div className="glass" style={{ padding: 12, marginTop: 12, background: 'rgba(100, 200, 100, 0.1)' }}>
              <div style={{ fontWeight: 600 }}>{selectedCandidate.fio}</div>
              <div className="subtitle" style={{ fontSize: 12 }}>
                {selectedCandidate.city} · tg: {selectedCandidate.telegram_id}
              </div>
              <button
                className="ui-btn ui-btn--ghost"
                style={{ marginTop: 8, fontSize: 12 }}
                onClick={() => setSelectedCandidate(null)}
              >
                Выбрать другого
              </button>
            </div>
          )}
        </div>

        <div className="action-row" style={{ marginTop: 16 }}>
          <button
            className="ui-btn ui-btn--primary"
            disabled={!selectedCandidate || bookMutation.isPending}
            onClick={() => bookMutation.mutate()}
          >
            {bookMutation.isPending ? 'Бронируем...' : 'Забронировать'}
          </button>
          <button className="ui-btn ui-btn--ghost" onClick={onClose}>Отмена</button>
        </div>
      </div>
    </div>
  )
}

export function SlotsPage() {
  const profile = useProfile()
  const canUse = profile.data?.principal.type === 'recruiter'
  const [status, setStatus] = useState<string | undefined>(undefined)
  const [limit, setLimit] = useState<number>(100)
  const [recruiter, setRecruiter] = useState<string>('')
  const [page, setPage] = useState<number>(1)
  const [perPage, setPerPage] = useState<number>(20)
  const [view, setView] = useState<'table' | 'cards' | 'agenda'>('table')
  const [sheetSlot, setSheetSlot] = useState<SlotApiItem | null>(null)
  const [bookingSlot, setBookingSlot] = useState<SlotApiItem | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  const queryPath = useMemo(() => {
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    if (limit) params.set('limit', String(limit))
    params.set('page', String(page))
    params.set('per_page', String(perPage))
    if (recruiter.trim()) params.set('recruiter_id', recruiter.trim())
    return `/slots?${params.toString()}`
  }, [status, limit, recruiter, page, perPage])

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery<SlotApiItem[]>({
    queryKey: ['slots', { status, limit, recruiter }],
    queryFn: () => apiFetch<SlotApiItem[]>(queryPath),
    staleTime: 20_000,
    enabled: Boolean(canUse),
  })

  const total = data?.length || 0
  const pagesTotal = Math.max(1, Math.ceil(total / perPage))
  const pagedItems = data ? data.slice((page - 1) * perPage, page * perPage) : []

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    if (!data) return counts
    data.forEach((item) => {
      const key = String(item.status || 'UNKNOWN')
      counts[key] = (counts[key] || 0) + 1
    })
    return counts
  }, [data])

  const canPrev = page > 1
  const canNext = page < pagesTotal

  const agendaGroups = useMemo(() => {
    if (!data) return []
    const sorted = [...data].sort((a, b) => new Date(a.start_utc).getTime() - new Date(b.start_utc).getTime())
    const map = new Map<string, SlotListItem[]>()
    sorted.forEach((item) => {
      const d = new Date(item.start_utc)
      const key = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(item)
    })
    return Array.from(map.entries()).map(([key, items]) => {
      const [y, m, d] = key.split('-').map(Number)
      const dateLabel = new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'long', year: 'numeric' })
        .format(new Date(Date.UTC(y, m - 1, d)))
      return { dateLabel, items }
    })
  }, [data])

  const closeSheet = useCallback(() => setSheetSlot(null), [])

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 1800)
  }

  const deleteSlot = async (id: number) => {
    try {
      await apiFetch(`/slots/${id}?force=1`, { method: 'DELETE' })
      showToast('Слот удалён')
      closeSheet()
      refetch()
    } catch (err) {
      showToast(`Ошибка удаления: ${(err as Error).message}`)
    }
  }

  const setOutcome = async (id: number, outcome: string) => {
    try {
      await apiFetch(`/slots/${id}/outcome`, { method: 'POST', body: JSON.stringify({ outcome }) })
      showToast('Исход сохранён')
      refetch()
    } catch (err) {
      showToast(`Ошибка исхода: ${(err as Error).message}`)
    }
  }

  const approveSlot = async (id: number) => {
    try {
      await apiFetch(`/slots/${id}/approve_booking`, { method: 'POST' })
      showToast('Слот подтверждён')
      closeSheet()
      refetch()
    } catch (err) {
      showToast(`Ошибка: ${(err as Error).message}`)
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

  const rescheduleSlot = async (id: number) => {
    try {
      await apiFetch(`/slots/${id}/reschedule`, { method: 'POST' })
      showToast('Слот перенесён')
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
          force: true,
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

  const copyLink = async (id: number) => {
    try {
      const url = `${window.location.origin}/slots?slot=${id}`
      await navigator.clipboard.writeText(url)
      showToast('Ссылка скопирована')
    } catch {
      showToast('Не удалось скопировать')
    }
  }

  return (
    <RoleGuard allow={['recruiter']}>
      <div className="page">
      <div className="glass panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 className="title" style={{ margin: 0 }}>Слоты</h1>
          <p className="subtitle" style={{ margin: '4px 0 0' }}>
            Всего: {total} · Свободных: {statusCounts['FREE'] ?? 0} · Забронировано: {statusCounts['BOOKED'] ?? 0} · Ожидают: {statusCounts['PENDING'] ?? 0}
          </p>
        </div>
        <Link to="/app/slots/create" className="ui-btn ui-btn--primary">+ Создать слоты</Link>
      </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 12 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: 'var(--muted)' }}>Статус</span>
            <select value={status ?? ''} onChange={(e) => setStatus(e.target.value || undefined)}>
              <option value="">Любой</option>
              <option value="FREE">Свободные</option>
              <option value="PENDING">Ожидают</option>
              <option value="BOOKED">Забронированы</option>
              <option value="CONFIRMED_BY_CANDIDATE">Подтверждены</option>
            </select>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: 'var(--muted)' }}>Рекрутёр ID</span>
            <input
              type="text"
              placeholder="all"
              value={recruiter}
              onChange={(e) => setRecruiter(e.target.value)}
              style={{ width: 90 }}
            />
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: 'var(--muted)' }}>Лимит</span>
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

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 8, flexWrap: 'wrap' }}>
        <span style={{ color: 'var(--muted)' }}>Страница: {page} / {pagesTotal}</span>
        <button className="ui-btn ui-btn--ghost" disabled={!canPrev} onClick={() => setPage((p) => Math.max(1, p - 1))}>Назад</button>
        <button className="ui-btn ui-btn--ghost" disabled={!canNext} onClick={() => setPage((p) => p + 1)}>Вперёд</button>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: 'var(--muted)' }}>Per page</span>
          <select value={perPage} onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1) }}>
            {[10, 20, 50, 100].map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
        </label>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ color: 'var(--muted)' }}>Вид</span>
          <button className={`ui-btn ${view === 'table' ? 'ui-btn--primary' : 'ui-btn--ghost'}`} onClick={() => setView('table')}>Таблица</button>
          <button className={`ui-btn ${view === 'cards' ? 'ui-btn--primary' : 'ui-btn--ghost'}`} onClick={() => setView('cards')}>Карточки</button>
          <button className={`ui-btn ${view === 'agenda' ? 'ui-btn--primary' : 'ui-btn--ghost'}`} onClick={() => setView('agenda')}>Лента</button>
        </div>
      </div>

      {isLoading && (
        <div style={{ display: 'grid', gap: 8, marginTop: 12 }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="glass" style={{ height: 64, opacity: 0.6 }} />
          ))}
        </div>
      )}
      {isError && (
        <div className="glass" style={{ padding: 12, border: '1px solid #f07373', color: '#f07373' }}>
          Ошибка загрузки: {(error as Error).message}
        </div>
      )}

      {!isLoading && data && data.length === 0 && (
        <p className="subtitle">Слотов нет.</p>
      )}

      {/* Bulk actions toolbar */}
      {selectedIds.size > 0 && (
        <div
          className="glass"
          style={{
            display: 'flex',
            gap: 12,
            alignItems: 'center',
            padding: '8px 12px',
            marginTop: 12,
            borderRadius: 8,
            background: 'rgba(105, 183, 255, 0.1)',
            border: '1px solid rgba(105, 183, 255, 0.3)',
          }}
        >
          <span style={{ fontWeight: 600 }}>Выбрано: {selectedIds.size}</span>
          <button className="ui-btn ui-btn--ghost" onClick={bulkRemind}>
            Напоминания
          </button>
          <button className="ui-btn ui-btn--danger" onClick={bulkDelete}>
            Удалить
          </button>
          <button className="ui-btn ui-btn--ghost" onClick={clearSelection}>
            Снять выбор
          </button>
        </div>
      )}

      {!isLoading && data && data.length > 0 && view === 'table' && (
        <table className="table slot-table">
          <thead>
            <tr>
              <th style={{ width: 40 }}>
                <input
                  type="checkbox"
                  checked={pagedItems.length > 0 && pagedItems.every((s) => selectedIds.has(s.id))}
                  onChange={selectAll}
                  title="Выбрать все"
                />
              </th>
              <th align="left">ID</th>
              <th align="left">Время</th>
              <th align="left">Рекрутёр</th>
              <th align="left">Кандидат</th>
              <th align="left">Статус</th>
              <th align="left">Действия</th>
            </tr>
          </thead>
          <tbody>
            {pagedItems.map((row: SlotApiItem) => (
              <tr key={row.id} className="glass" style={{ background: selectedIds.has(row.id) ? 'rgba(105, 183, 255, 0.1)' : undefined }}>
                <td>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(row.id)}
                    onChange={() => toggleSelect(row.id)}
                  />
                </td>
                <td>{row.id}</td>
                <td>{row.local_time || formatLocal(row.start_utc, row.tz_name)}</td>
                <td>{row.recruiter_name || '—'}</td>
                <td>{row.candidate_fio || '—'}</td>
                <td>
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '2px 8px',
                      borderRadius: 6,
                      fontSize: 12,
                      background: row.status === 'PENDING' ? 'rgba(255, 200, 100, 0.15)' :
                        row.status === 'BOOKED' ? 'rgba(100, 200, 100, 0.15)' :
                        row.status === 'FREE' ? 'rgba(105, 183, 255, 0.1)' :
                        'rgba(105, 183, 255, 0.1)',
                      border: `1px solid ${
                        row.status === 'PENDING' ? 'rgba(255, 200, 100, 0.3)' :
                        row.status === 'BOOKED' ? 'rgba(100, 200, 100, 0.3)' :
                        'rgba(105, 183, 255, 0.2)'
                      }`,
                    }}
                  >
                    {statusLabel(row.status)}
                  </span>
                </td>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {row.status === 'FREE' && (
                      <button
                        className="ui-btn ui-btn--primary"
                        style={{ padding: '4px 8px', fontSize: 12 }}
                        onClick={() => setBookingSlot(row)}
                        title="Забронировать"
                      >
                        +
                      </button>
                    )}
                    {row.status === 'PENDING' && (
                      <>
                        <button
                          className="ui-btn ui-btn--primary"
                          style={{ padding: '4px 8px', fontSize: 12 }}
                          onClick={() => approveSlot(row.id)}
                          title="Подтвердить"
                        >
                          ✓
                        </button>
                        <button
                          className="ui-btn ui-btn--danger"
                          style={{ padding: '4px 8px', fontSize: 12 }}
                          onClick={() => rejectSlot(row.id)}
                          title="Отклонить"
                        >
                          ✗
                        </button>
                      </>
                    )}
                    <button
                      className="ui-btn ui-btn--ghost"
                      style={{ padding: '4px 8px', fontSize: 12 }}
                      onClick={() => setSheetSlot(row)}
                      title="Подробнее"
                    >
                      ...
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!isLoading && data && data.length > 0 && view === 'cards' && (
        <div className="slot-grid">
          {pagedItems.map((row: SlotApiItem) => (
            <article key={row.id} className="glass slot-card">
              <header className="slot-card__header">
                <div>
                  <div style={{ fontWeight: 700 }}>ID {row.id}</div>
                  <div className="slot-card__meta">{row.recruiter_name || '—'} · {row.tz_name || '—'}</div>
                </div>
                <span className="slot-chip">{statusLabel(row.status)}</span>
              </header>
              <div>
                <div className="slot-card__time">{row.local_time || formatLocal(row.start_utc, row.tz_name)}</div>
                <div className="slot-card__meta">UTC {row.start_utc}</div>
              </div>
              <div>
                <div style={{ fontWeight: 600 }}>{row.candidate_fio || 'Нет брони'}</div>
                <div className="slot-card__meta" style={{ fontSize: 12 }}>tg_id: {row.candidate_tg_id || '—'}</div>
              </div>
              <footer className="action-row">
                <button className="ui-btn ui-btn--ghost" onClick={() => setSheetSlot(row)}>Подробнее</button>
                <button className="ui-btn ui-btn--ghost" onClick={() => copyLink(row.id)}>Скопировать ссылку</button>
              </footer>
            </article>
          ))}
        </div>
      )}

      {!isLoading && data && data.length > 0 && view === 'agenda' && (
        <div className="slot-agenda">
          {agendaGroups.map((group) => (
            <section key={group.dateLabel} className="glass slot-agenda__day">
              <h3 style={{ margin: '0 0 8px' }}>{group.dateLabel}</h3>
              <div style={{ display: 'grid', gap: 8 }}>
                {group.items.map((row) => (
                  <div key={row.id} className="glass slot-agenda__item">
                    <div>
                      <div style={{ fontWeight: 700 }}>{row.local_time || formatLocal(row.start_utc, row.tz_name)}</div>
                      <div className="slot-card__meta" style={{ fontSize: 12 }}>{row.recruiter_name || '—'} · {row.tz_name || '—'}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div className="slot-chip">{statusLabel(row.status)}</div>
                      <button className="ui-btn ui-btn--ghost" onClick={() => setSheetSlot(row)}>Подробнее</button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {sheetSlot && (
        <div className="overlay" onClick={closeSheet}>
          <div className="glass sheet" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <div>
                <h2 style={{ margin: 0 }}>Слот ID {sheetSlot.id}</h2>
                <p className="subtitle" style={{ margin: 0 }}>{sheetSlot.recruiter_name || '—'} · {sheetSlot.tz_name || '—'}</p>
              </div>
              <button className="ui-btn ui-btn--ghost" onClick={closeSheet}>Закрыть</button>
            </div>
            <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
              <div><strong>Время:</strong> {sheetSlot.local_time || formatLocal(sheetSlot.start_utc, sheetSlot.tz_name)} (UTC {sheetSlot.start_utc})</div>
              <div><strong>Кандидат:</strong> {sheetSlot.candidate_fio || 'Нет брони'} · tg_id: {sheetSlot.candidate_tg_id || '—'}</div>
              <div><strong>Статус:</strong> {statusLabel(sheetSlot.status)}</div>
              <div><strong>TZ:</strong> {sheetSlot.tz_name || '—'}</div>
            </div>
            <div className="action-row" style={{ marginTop: 14, flexWrap: 'wrap' }}>
              {/* Actions for FREE slots */}
              {sheetSlot.status === 'FREE' && (
                <button className="ui-btn ui-btn--primary" onClick={() => { closeSheet(); setBookingSlot(sheetSlot) }}>
                  + Забронировать кандидата
                </button>
              )}
              {/* Actions for PENDING slots */}
              {sheetSlot.status === 'PENDING' && (
                <>
                  <button className="ui-btn ui-btn--primary" onClick={() => approveSlot(sheetSlot.id)}>
                    ✓ Подтвердить
                  </button>
                  <button className="ui-btn ui-btn--danger" onClick={() => rejectSlot(sheetSlot.id)}>
                    ✗ Отклонить
                  </button>
                </>
              )}
              {/* Actions for BOOKED slots */}
              {(sheetSlot.status === 'BOOKED' || sheetSlot.status === 'CONFIRMED_BY_CANDIDATE') && (
                <>
                  <button className="ui-btn ui-btn--ghost" onClick={() => setOutcome(sheetSlot.id, 'SUCCESS')}>
                    Исход: Успех
                  </button>
                  <button className="ui-btn ui-btn--ghost" onClick={() => setOutcome(sheetSlot.id, 'FAIL')}>
                    Исход: Отказ
                  </button>
                  <button className="ui-btn ui-btn--ghost" onClick={() => rescheduleSlot(sheetSlot.id)}>
                    Перенести
                  </button>
                </>
              )}
              <button className="ui-btn ui-btn--ghost" onClick={() => copyLink(sheetSlot.id)}>Ссылка</button>
              <button className="ui-btn ui-btn--danger" onClick={() => deleteSlot(sheetSlot.id)}>Удалить</button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="glass toast">{toast}</div>
      )}

      {bookingSlot && (
        <BookingModal
          slot={bookingSlot}
          onClose={() => setBookingSlot(null)}
          onSuccess={() => refetch()}
          showToast={showToast}
        />
      )}
      </div>
      </div>
    </RoleGuard>
  )
}
