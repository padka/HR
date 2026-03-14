import { useQuery } from '@tanstack/react-query'
import { useState, useMemo, useEffect, useCallback } from 'react'
import {
  deleteSlot as deleteSlotRequest,
  fetchSlots,
  rejectSlotBooking,
  submitSlotsBulkAction,
} from '@/api/services/slots'
import { apiFetch } from '@/api/client'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useProfile } from '@/app/hooks/useProfile'
import { useIsMobile } from '@/app/hooks/useIsMobile'
import { Link } from '@tanstack/react-router'
import { ModalPortal } from '@/shared/components/ModalPortal'
import {
  buildStatusCounts,
  statusLabel,
  matchesStatusFilter,
  normalizeSlotStatus,
  slotDateForFilter,
  slotHasCandidate,
  slotPurpose,
  slotRecruiterTimeLabel,
  slotRecruiterTimestamp,
  slotRecruiterTz,
  slotRegionTimeLabel,
  slotRegionTimestamp,
  slotRegionTz,
  type SlotApiItem,
  type SlotStatusFilter,
} from './slots.utils'
import {
  clearSlotsPersistedFilters,
  loadSlotsPersistedFilters,
  saveSlotsPersistedFilters,
  type SlotSortDir,
  type SlotSortField,
} from './slots.filters'
import { BookingModal, ManualBookingModal, RescheduleModal } from './slots-modals'

type CityOption = {
  id: number
  name: string
  tz?: string | null
  active?: boolean | null
}

type RecruiterOption = {
  id: number
  name: string
  active?: boolean | null
}

export function SlotsPage() {
  const profile = useProfile()
  const isMobile = useIsMobile()
  const canUse = Boolean(profile.data?.principal?.type)
  const isAdmin = profile.data?.principal.type === 'admin'
  const persistedFilters = useMemo(() => {
    if (typeof window === 'undefined') return {}
    return loadSlotsPersistedFilters(window.localStorage)
  }, [])
  const [statusFilter, setStatusFilter] = useState<SlotStatusFilter>(persistedFilters.statusFilter ?? 'ALL')
  const [purposeFilter, setPurposeFilter] = useState<string>(persistedFilters.purposeFilter ?? 'all')
  const [search, setSearch] = useState(persistedFilters.search ?? '')
  const [cityFilter, setCityFilter] = useState<string>(persistedFilters.cityFilter ?? 'all')
  const [recruiterFilter, setRecruiterFilter] = useState<string>(persistedFilters.recruiterFilter ?? 'all')
  const [candidateFilter, setCandidateFilter] = useState<'all' | 'with' | 'without'>(persistedFilters.candidateFilter ?? 'all')
  const [tzRelationFilter, setTzRelationFilter] = useState<'all' | 'same' | 'diff'>(persistedFilters.tzRelationFilter ?? 'all')
  const [dateFrom, setDateFrom] = useState(persistedFilters.dateFrom ?? '')
  const [dateTo, setDateTo] = useState(persistedFilters.dateTo ?? '')
  const [sortField, setSortField] = useState<SlotSortField>(persistedFilters.sortField ?? 'recruiter_time')
  const [sortDir, setSortDir] = useState<SlotSortDir>(persistedFilters.sortDir ?? 'desc')
  const [limit, setLimit] = useState<number>(persistedFilters.limit ?? 500)
  const [page, setPage] = useState<number>(persistedFilters.page ?? 1)
  const [perPage, setPerPage] = useState<number>(persistedFilters.perPage ?? 20)
  const [advancedFiltersOpen, setAdvancedFiltersOpen] = useState<boolean>(false)
  const [sheetSlot, setSheetSlot] = useState<SlotApiItem | null>(null)
  const [bookingSlot, setBookingSlot] = useState<SlotApiItem | null>(null)
  const [manualBookingSlot, setManualBookingSlot] = useState<SlotApiItem | null>(null)
  const [showStandaloneManualBooking, setShowStandaloneManualBooking] = useState(false)
  const [rescheduleTarget, setRescheduleTarget] = useState<SlotApiItem | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const modalOpen = Boolean(sheetSlot || bookingSlot || manualBookingSlot || showStandaloneManualBooking || rescheduleTarget)

  const citiesQuery = useQuery<CityOption[]>({
    queryKey: ['slot-booking-cities'],
    queryFn: () => apiFetch('/cities'),
    enabled: Boolean(canUse),
    staleTime: 60_000,
  })

  const recruitersQuery = useQuery<RecruiterOption[]>({
    queryKey: ['slot-booking-recruiters'],
    queryFn: () => apiFetch('/recruiters'),
    enabled: Boolean(canUse),
    staleTime: 60_000,
  })

  const allowedCityIds = profile.data?.recruiter?.cities?.map((city) => city.id) || []

  const queryPath = useMemo(() => {
    const params = new URLSearchParams()
    if (limit) params.set('limit', String(limit))
    params.set('sort_dir', 'desc')
    return params.toString()
  }, [limit])

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery<SlotApiItem[]>({
    queryKey: ['slots', { limit }],
    queryFn: () => fetchSlots<SlotApiItem[]>(queryPath),
    staleTime: 20_000,
    enabled: Boolean(canUse),
  })

  const allItems = useMemo(() => data || [], [data])

  const cityOptions = useMemo(() => {
    return Array.from(new Set(allItems.map((item) => item.city_name || '').filter(Boolean))).sort((a, b) =>
      a.localeCompare(b, 'ru'),
    )
  }, [allItems])

  const recruiterOptions = useMemo(() => {
    return Array.from(new Set(allItems.map((item) => item.recruiter_name || '').filter(Boolean))).sort((a, b) =>
      a.localeCompare(b, 'ru'),
    )
  }, [allItems])

  const purposeCounts = useMemo(() => {
    let interview = 0
    let intro_day = 0
    allItems.forEach((item) => {
      if (slotPurpose(item) === 'intro_day') intro_day += 1
      else interview += 1
    })
    return { interview, intro_day, all: allItems.length }
  }, [allItems])

  const filteredByPurpose = useMemo(() => {
    if (purposeFilter === 'all') return allItems
    return allItems.filter((item) => slotPurpose(item) === purposeFilter)
  }, [allItems, purposeFilter])

  const filteredBeforeStatus = useMemo(() => {
    const q = search.trim().toLowerCase()
    return filteredByPurpose.filter((item) => {
      if (cityFilter !== 'all' && (item.city_name || '') !== cityFilter) return false
      if (recruiterFilter !== 'all' && (item.recruiter_name || '') !== recruiterFilter) return false

      const hasCandidate = slotHasCandidate(item)
      if (candidateFilter === 'with' && !hasCandidate) return false
      if (candidateFilter === 'without' && hasCandidate) return false

      if (tzRelationFilter !== 'all') {
        const recruiterTz = slotRecruiterTz(item)
        const regionTz = slotRegionTz(item)
        if (!regionTz) return false
        const sameTz = recruiterTz === regionTz
        if (tzRelationFilter === 'same' && !sameTz) return false
        if (tzRelationFilter === 'diff' && sameTz) return false
      }

      const date = slotDateForFilter(item)
      if (dateFrom && date && date < dateFrom) return false
      if (dateTo && date && date > dateTo) return false

      if (!q) return true
      const searchable = [
        String(item.id),
        item.candidate_fio || '',
        String(item.candidate_tg_id || ''),
        item.city_name || '',
        item.recruiter_name || '',
        item.status || '',
        slotPurpose(item),
      ]
        .join(' ')
        .toLowerCase()
      return searchable.includes(q)
    })
  }, [
    candidateFilter,
    cityFilter,
    dateFrom,
    dateTo,
    filteredByPurpose,
    recruiterFilter,
    search,
    tzRelationFilter,
  ])

  const statusCounts = useMemo(() => buildStatusCounts(filteredBeforeStatus), [filteredBeforeStatus])

  const filteredByStatus = useMemo(() => {
    return filteredBeforeStatus.filter((item) => matchesStatusFilter(item, statusFilter))
  }, [filteredBeforeStatus, statusFilter])

  const sortedItems = useMemo(() => {
    const statusOrder: Record<string, number> = {
      FREE: 1,
      PENDING: 2,
      BOOKED: 3,
      CONFIRMED_BY_CANDIDATE: 4,
    }
    const compareText = (a: string, b: string) => a.localeCompare(b, 'ru')
    const multiplier = sortDir === 'asc' ? 1 : -1
    return [...filteredByStatus].sort((left, right) => {
      let result = 0
      if (sortField === 'recruiter_time') {
        result = slotRecruiterTimestamp(left) - slotRecruiterTimestamp(right)
      } else if (sortField === 'region_time') {
        result = slotRegionTimestamp(left) - slotRegionTimestamp(right)
      } else if (sortField === 'city') {
        result = compareText(left.city_name || '', right.city_name || '')
      } else if (sortField === 'candidate') {
        result = compareText(left.candidate_fio || '', right.candidate_fio || '')
      } else if (sortField === 'status') {
        result =
          (statusOrder[normalizeSlotStatus(left.status)] || 99) -
          (statusOrder[normalizeSlotStatus(right.status)] || 99)
      } else if (sortField === 'type') {
        result = compareText(slotPurpose(left), slotPurpose(right))
      }
      if (result === 0) {
        result = left.id - right.id
      }
      return result * multiplier
    })
  }, [filteredByStatus, sortDir, sortField])

  const total = sortedItems.length
  const hasActiveFilters = Boolean(
    search.trim()
      || cityFilter !== 'all'
      || recruiterFilter !== 'all'
      || candidateFilter !== 'all'
      || tzRelationFilter !== 'all'
      || dateFrom
      || dateTo
      || statusFilter !== 'ALL'
      || purposeFilter !== 'all'
      || sortField !== 'recruiter_time'
      || sortDir !== 'desc',
  )
  const pagesTotal = Math.max(1, Math.ceil(total / perPage))
  const pagedItems = sortedItems.slice((page - 1) * perPage, page * perPage)

  const canPrev = page > 1
  const canNext = page < pagesTotal

  const closeSheet = useCallback(() => setSheetSlot(null), [])

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 1800)
  }

  const deleteSlot = async (id: number) => {
    try {
      const result = await deleteSlotRequest(id)
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
      await rejectSlotBooking(id)
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
    if (pagedItems.length > 0 && pagedItems.every((item) => selectedIds.has(item.id))) {
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
      await submitSlotsBulkAction({
        action: 'delete',
        slot_ids: Array.from(selectedIds),
        force: false,
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
      await submitSlotsBulkAction({
        action: 'remind',
        slot_ids: Array.from(selectedIds),
      })
      showToast(`Напоминания запланированы для ${selectedIds.size} слотов`)
      clearSelection()
    } catch (err) {
      showToast(`Ошибка: ${(err as Error).message}`)
    }
  }

  useEffect(() => {
    setPage(1)
  }, [
    candidateFilter,
    cityFilter,
    dateFrom,
    dateTo,
    perPage,
    purposeFilter,
    recruiterFilter,
    search,
    sortDir,
    sortField,
    statusFilter,
    tzRelationFilter,
  ])

  useEffect(() => {
    if (page > pagesTotal) {
      setPage(pagesTotal)
    }
  }, [page, pagesTotal])

  useEffect(() => {
    if (typeof window === 'undefined') return
    saveSlotsPersistedFilters(window.localStorage, {
      statusFilter,
      purposeFilter,
      search,
      cityFilter,
      recruiterFilter,
      candidateFilter,
      tzRelationFilter,
      dateFrom,
      dateTo,
      sortField,
      sortDir,
      limit,
      page,
      perPage,
    })
  }, [
    candidateFilter,
    cityFilter,
    dateFrom,
    dateTo,
    limit,
    page,
    perPage,
    purposeFilter,
    recruiterFilter,
    search,
    sortDir,
    sortField,
    statusFilter,
    tzRelationFilter,
  ])

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

  const clearAllFilters = () => {
    if (typeof window !== 'undefined') {
      clearSlotsPersistedFilters(window.localStorage)
    }
    setStatusFilter('ALL')
    setPurposeFilter('all')
    setSearch('')
    setCityFilter('all')
    setRecruiterFilter('all')
    setCandidateFilter('all')
    setTzRelationFilter('all')
    setDateFrom('')
    setDateTo('')
    setSortField('recruiter_time')
    setSortDir('desc')
    setLimit(500)
    setPerPage(20)
    setPage(1)
  }

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className="page app-page app-page--ops slots-page">
        <header className="glass glass--elevated page-header page-header--row slots-page__hero app-page__hero">
          <div className="page-header__content">
            <h1 className="title">Слоты</h1>
            <p className="subtitle slots-hero-subtitle">
              Сортируйте и фильтруйте расписание по статусу, городу, времени и часовым поясам.
            </p>
            <div className="slots-summary slots-summary--primary" role="group" aria-label="Тип слотов">
              {[
                { key: 'all', label: 'Все', value: purposeCounts.all, tone: 'neutral' },
                { key: 'interview', label: 'Собеседования', value: purposeCounts.interview, tone: 'accent' },
                { key: 'intro_day', label: 'Ознакомительные дни', value: purposeCounts.intro_day, tone: 'success' },
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
                { key: 'all', label: 'Всего', value: statusCounts.total, status: 'ALL' as SlotStatusFilter, tone: 'neutral' },
                { key: 'free', label: 'Свободные', value: statusCounts.free, status: 'FREE' as SlotStatusFilter, tone: 'success' },
                { key: 'booked', label: 'Согласованные', value: statusCounts.booked, status: 'BOOKED' as SlotStatusFilter, tone: 'accent' },
                { key: 'confirmed', label: 'Подтверждены', value: statusCounts.confirmed, status: 'CONFIRMED_BY_CANDIDATE' as SlotStatusFilter, tone: 'accent' },
                { key: 'pending', label: 'Ожидают', value: statusCounts.pending, status: 'PENDING' as SlotStatusFilter, tone: 'warning' },
              ].map((item) => {
                const isActive = item.status === statusFilter
                return (
                  <button
                    key={item.key}
                    type="button"
                    className={`slots-summary__card slots-summary__card--${item.tone} ${isActive ? 'is-active' : ''}`}
                    onClick={() => {
                      setStatusFilter(item.status)
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
          <div className="page-header__actions">
            <button className="ui-btn ui-btn--ghost" onClick={() => refetch()}>
              {isFetching ? 'Обновляем…' : 'Обновить'}
            </button>
            <button className="ui-btn ui-btn--secondary" onClick={() => setShowStandaloneManualBooking(true)}>
              Записать вручную
            </button>
            <Link to="/app/slots/create" className="ui-btn ui-btn--primary" data-testid="slots-create-btn">
              + Создать слоты
            </Link>
          </div>
        </header>

        <section className="glass page-section slots-page__section app-page__section">
          <div className="slots-filters-grid slots-filters-grid--enhanced ui-filter ui-filter-bar--compact" data-testid="slots-filter-bar">
            <div className="slots-filters-grid slots-filters-grid--primary">
              <label className="filter-bar__item">
                <span className="filter-bar__label">Город</span>
                <select value={cityFilter} onChange={(e) => setCityFilter(e.target.value)}>
                  <option value="all">Все</option>
                  {cityOptions.map((city) => (
                    <option key={city} value={city}>{city}</option>
                  ))}
                </select>
              </label>
              <label className="filter-bar__item">
                <span className="filter-bar__label">Дата с</span>
                <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
              </label>
              <label className="filter-bar__item">
                <span className="filter-bar__label">Дата по</span>
                <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
              </label>
            </div>
            <div className="slots-filters-grid__actions">
              <button
                className="ui-btn ui-btn--ghost ui-btn--sm"
                type="button"
                onClick={() => setAdvancedFiltersOpen((current) => !current)}
                aria-expanded={advancedFiltersOpen}
                data-testid="slots-advanced-filters-toggle"
              >
                {advancedFiltersOpen ? 'Скрыть фильтры' : 'Ещё фильтры'}
              </button>
              <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={clearAllFilters}>
                Сбросить фильтры
              </button>
            </div>
            <div className={`ui-filter-bar__advanced ui-filter ${advancedFiltersOpen ? 'ui-filter-bar__advanced--open' : ''}`}>
              <label className="filter-bar__item">
                <span className="filter-bar__label">Поиск</span>
                <input
                  className="filter-bar__search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="ID, кандидат, город, рекрутёр, tg"
                />
              </label>
              <label className="filter-bar__item">
                <span className="filter-bar__label">Кандидат</span>
                <select value={candidateFilter} onChange={(e) => setCandidateFilter(e.target.value as 'all' | 'with' | 'without')}>
                  <option value="all">Любой</option>
                  <option value="with">Назначен</option>
                  <option value="without">Свободный слот</option>
                </select>
              </label>
              {isAdmin && (
                <label className="filter-bar__item">
                  <span className="filter-bar__label">Рекрутёр</span>
                  <select value={recruiterFilter} onChange={(e) => setRecruiterFilter(e.target.value)}>
                    <option value="all">Все</option>
                    {recruiterOptions.map((name) => (
                      <option key={name} value={name}>{name}</option>
                    ))}
                  </select>
                </label>
              )}
              <label className="filter-bar__item">
                <span className="filter-bar__label">TZ рекрутёр/регион</span>
                <select value={tzRelationFilter} onChange={(e) => setTzRelationFilter(e.target.value as 'all' | 'same' | 'diff')}>
                  <option value="all">Любое</option>
                  <option value="same">Совпадают</option>
                  <option value="diff">Разные</option>
                </select>
              </label>
              <label className="filter-bar__item">
                <span className="filter-bar__label">Сортировать</span>
                <select value={sortField} onChange={(e) => setSortField(e.target.value as SlotSortField)}>
                  <option value="recruiter_time">По времени рекрутёра</option>
                  <option value="region_time">По времени региона/кандидата</option>
                  <option value="city">По городу</option>
                  <option value="candidate">По кандидату</option>
                  <option value="status">По статусу</option>
                  <option value="type">По типу</option>
                </select>
              </label>
              <label className="filter-bar__item">
                <span className="filter-bar__label">Порядок</span>
                <select value={sortDir} onChange={(e) => setSortDir(e.target.value as SlotSortDir)}>
                  <option value="desc">Убывание</option>
                  <option value="asc">Возрастание</option>
                </select>
              </label>
              <label className="filter-bar__item">
                <span className="filter-bar__label">Лимит загрузки</span>
                <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
                  {[100, 300, 500].map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <div className="pagination app-page__toolbar">
            <span className="pagination__info">Показано: {total} · Страница {page} / {pagesTotal}</span>
            <button className="ui-btn ui-btn--ghost ui-btn--sm" disabled={!canPrev} onClick={() => setPage((p) => Math.max(1, p - 1))}>Назад</button>
            <button className="ui-btn ui-btn--ghost ui-btn--sm" disabled={!canNext} onClick={() => setPage((p) => p + 1)}>Вперёд</button>
            <label className="filter-bar__item">
              <span className="filter-bar__label">На странице</span>
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
          {isError && <ApiErrorBanner error={error} title="Не удалось загрузить слоты" onRetry={() => refetch()} />}

          {!isLoading && total === 0 && (
            <div className="empty-state" data-testid="slots-empty-state">
              <p className="empty-state__text">
                {hasActiveFilters
                  ? 'По текущим фильтрам слоты не найдены.'
                  : 'Слотов пока нет. Создайте первую сетку слотов для запуска воронки.'}
              </p>
              <div className="toolbar">
                {hasActiveFilters && (
                  <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={clearAllFilters}>
                    Сбросить фильтры
                  </button>
                )}
                <Link to="/app/slots/create" className="ui-btn ui-btn--primary ui-btn--sm">
                  + Создать слоты
                </Link>
              </div>
            </div>
          )}

          {selectedIds.size > 0 && (
            <div className="toolbar toolbar--accent app-page__toolbar">
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

          {!isLoading && total > 0 && (
            <>
              {isMobile && (
                <div className="mobile-card-list" data-testid="slots-mobile-cards">
                  {pagedItems.map((row: SlotApiItem) => {
                    const slotStatus = normalizeSlotStatus(row.status)
                    const recruiterTz = slotRecruiterTz(row)
                    const recruiterTimeLabel = slotRecruiterTimeLabel(row)
                    const hasCandidate = slotHasCandidate(row)
                    const regionTz = slotRegionTz(row)
                    const regionTimeLabel = slotRegionTimeLabel(row)
                    const isFree = slotStatus === 'FREE'
                    const candidateProfileId = row.candidate_id ? String(row.candidate_id) : null
                    return (
                      <article key={`mobile-slot-${row.id}`} className="slot-mobile-card glass glass--subtle">
                        <div className="slot-mobile-card__top">
                          <strong>#{row.id}</strong>
                          <span className={`cd-chip ${(row.purpose || 'interview') === 'intro_day' ? 'cd-chip--accent' : ''}`}>
                            {(row.purpose || 'interview') === 'intro_day' ? 'Ознакомительный день' : 'Собеседование'}
                          </span>
                          <span className={`status-badge status-badge--${
                            slotStatus === 'PENDING' ? 'warning' :
                            slotStatus === 'BOOKED' || slotStatus === 'CONFIRMED_BY_CANDIDATE' ? 'success' :
                            slotStatus === 'FREE' ? 'info' : 'muted'
                          }`}>
                            {statusLabel(row.status || undefined)}
                          </span>
                        </div>
                        <div className="slot-mobile-card__meta">
                          <div>
                            <div className="text-muted text-xs">Кандидат</div>
                            <div className="font-semibold">{row.candidate_fio || 'Свободный слот'}</div>
                            <div className="text-muted text-sm">
                              {row.candidate_tg_id ? `tg_id: ${row.candidate_tg_id}` : (hasCandidate ? 'Без tg_id' : 'Назначьте кандидата')}
                            </div>
                          </div>
                          <div>
                            <div className="text-muted text-xs">Локальное время рекрутёра</div>
                            <div className="font-semibold">{recruiterTimeLabel}</div>
                            <div className="text-muted text-sm">{recruiterTz}</div>
                          </div>
                          <div>
                            <div className="text-muted text-xs">Время региона/кандидата</div>
                            <div className="font-semibold">{regionTimeLabel}</div>
                            <div className="text-muted text-sm">{regionTz || '—'} · {hasCandidate ? 'кандидат' : 'город'}</div>
                          </div>
                          <div>
                            <div className="text-muted text-xs">Город</div>
                            <div className="font-semibold">{row.city_name || '—'}</div>
                          </div>
                        </div>
                        <div className="slot-mobile-card__actions">
                          <label className="messenger-checkbox">
                            <input
                              type="checkbox"
                              checked={selectedIds.has(row.id)}
                              onChange={() => toggleSelect(row.id)}
                            />
                            <span>Выбрать</span>
                          </label>
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
                          {isFree ? (
                            <>
                              <button
                                className="ui-btn ui-btn--ghost ui-btn--sm"
                                onClick={() => setBookingSlot(row)}
                              >
                                Через бота
                              </button>
                              <button
                                className="ui-btn ui-btn--secondary ui-btn--sm"
                                onClick={() => setManualBookingSlot(row)}
                              >
                                Вручную
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
                            data-testid="slot-details-btn-mobile"
                          >
                            Подробнее
                          </button>
                        </div>
                      </article>
                    )
                  })}
                </div>
              )}
              <div className="data-table-wrapper slots-table-wrapper">
                <table className="data-table" data-testid="slots-table">
                <thead>
                  <tr>
                    <th className="data-table__th--checkbox">
                      <input
                        type="checkbox"
                        checked={pagedItems.length > 0 && pagedItems.every((s) => selectedIds.has(s.id))}
                        onChange={selectAll}
                        title="Выбрать все"
                        data-testid="slots-select-all"
                      />
                    </th>
                    <th>Тип</th>
                    <th>Кандидат</th>
                    <th>Город</th>
                    <th>Время рекрутера</th>
                    <th>Время региона/кандидата</th>
                    <th>Статус</th>
                    <th>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {pagedItems.map((row: SlotApiItem) => {
                    const slotStatus = normalizeSlotStatus(row.status)
                    const recruiterTz = slotRecruiterTz(row)
                    const recruiterTimeLabel = slotRecruiterTimeLabel(row)
                    const hasCandidate = slotHasCandidate(row)
                    const regionTz = slotRegionTz(row)
                    const regionTimeLabel = slotRegionTimeLabel(row)
                    const isFree = slotStatus === 'FREE'
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
                            <div className="slot-time__primary">{recruiterTimeLabel}</div>
                            <div className="slot-time__secondary">{recruiterTz}</div>
                          </div>
                        </td>
                        <td>
                          <div className="slot-time">
                            <div className="slot-time__primary">{regionTimeLabel}</div>
                            <div className="slot-time__secondary">{regionTz || '—'} · {hasCandidate ? 'кандидат' : 'город'}</div>
                          </div>
                        </td>
                        <td>
                          <span className={`status-badge status-badge--${
                            slotStatus === 'PENDING' ? 'warning' :
                            slotStatus === 'BOOKED' || slotStatus === 'CONFIRMED_BY_CANDIDATE' ? 'success' :
                            slotStatus === 'FREE' ? 'info' : 'muted'
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
                            {isFree ? (
                              <>
                                <button
                                  className="ui-btn ui-btn--ghost ui-btn--sm"
                                  onClick={() => setBookingSlot(row)}
                                >
                                  Через бота
                                </button>
                                <button
                                  className="ui-btn ui-btn--secondary ui-btn--sm"
                                  onClick={() => setManualBookingSlot(row)}
                                >
                                  Вручную
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
                              data-testid="slot-details-btn"
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
              </div>
            </>
          )}

          {isMobile && (
            <Link to="/app/slots/create" className="ui-btn ui-btn--fab" aria-label="Создать слот">
              +
            </Link>
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
                    <strong>Время рекрутёра:</strong> {slotRecruiterTimeLabel(sheetSlot)} · {slotRecruiterTz(sheetSlot)}
                  </div>
                  <div className="modal__row">
                    <strong>Время региона/кандидата:</strong> {slotRegionTimeLabel(sheetSlot)} · {slotRegionTz(sheetSlot) || '—'}
                  </div>
                  <div className="modal__row"><strong>Кандидат:</strong> {sheetSlot.candidate_fio || 'Нет брони'} · tg_id: {sheetSlot.candidate_tg_id || '—'}</div>
                  <div className="modal__row"><strong>Статус:</strong> {statusLabel(sheetSlot.status || undefined)}</div>
                </div>
                <div className="modal__footer">
                  {normalizeSlotStatus(sheetSlot.status) === 'FREE' && (
                    <>
                      <button className="ui-btn ui-btn--primary" onClick={() => { closeSheet(); setBookingSlot(sheetSlot) }}>
                        Через бота
                      </button>
                      <button className="ui-btn ui-btn--secondary" onClick={() => { closeSheet(); setManualBookingSlot(sheetSlot) }}>
                        Записать вручную
                      </button>
                    </>
                  )}
                  {normalizeSlotStatus(sheetSlot.status) !== 'FREE' && (
                    <>
                      <button className="ui-btn ui-btn--ghost" onClick={() => setRescheduleTarget(sheetSlot)}>
                        Перенести
                      </button>
                      <button className="ui-btn ui-btn--danger" onClick={() => rejectSlot(sheetSlot.id)}>
                        Освободить
                      </button>
                    </>
                  )}
                  {normalizeSlotStatus(sheetSlot.status) === 'FREE' && (
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

          {(manualBookingSlot || showStandaloneManualBooking) && (
            <ManualBookingModal
              slot={manualBookingSlot}
              cities={citiesQuery.data || []}
              recruiters={recruitersQuery.data || []}
              isAdmin={isAdmin}
              defaultRecruiterId={profile.data?.recruiter?.id || null}
              allowedCityIds={allowedCityIds}
              onClose={() => {
                setManualBookingSlot(null)
                setShowStandaloneManualBooking(false)
              }}
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
