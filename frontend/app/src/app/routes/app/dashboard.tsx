import { useQuery, useMutation } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import {
  fetchCurrentKpis,
  fetchDashboardIncoming,
  fetchDashboardRecruiters,
  fetchDashboardSummary,
  fetchRecruiterPerformance,
  rejectDashboardCandidate,
  scheduleDashboardIncomingSlot,
  type IncomingCandidate,
  type IncomingPayload,
  type KPIResponse,
  type LeaderboardPayload,
  type RecruiterOption,
  type SummaryPayload,
} from '@/api/services/dashboard'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import { useProfile } from '@/app/hooks/useProfile'
import { useIsMobile } from '@/app/hooks/useIsMobile'
import { browserTimeZone, buildSlotTimePreview, formatTzOffset } from '@/app/lib/timezonePreview'
import { ModalPortal } from '@/shared/components/ModalPortal'
import { Link } from '@tanstack/react-router'
import '@/theme/pages/dashboard.css'
import { fadeIn, listItem, stagger } from '@/shared/motion'
import { resolveIncomingDemoCount, withDemoIncomingCandidates } from './incoming-demo'
import { IncomingPage } from './incoming'
import { DashboardMetric } from './DashboardMetric'
import {
  dashboardTrendTone,
  formatAiRecommendation,
  formatAiRelevance,
  getDefaultRange,
  leaderboardRankClass,
  toIsoDate,
} from './dashboard.utils'

type IncomingFilter = 'all' | 'new' | 'stalled' | 'pending' | 'requested_other_time'

const DASHBOARD_INCOMING_FILTERS_KEY = 'dashboardIncomingFilters:v1'
const INCOMING_FETCH_LIMIT = 100
const INCOMING_PAGE_SIZE_OPTIONS = [25, 50, 100] as const

export function DashboardPage() {
  const profile = useProfile()
  const isMobile = useIsMobile()
  const prefersReducedMotion = useReducedMotion()
  const profileReady = profile.isSuccess || Boolean(profile.data)
  const isAdmin = profile.data?.principal.type === 'admin'
  const initialRange = useMemo(() => getDefaultRange(), [])
  const [rangeFrom, setRangeFrom] = useState(initialRange.from)
  const [rangeTo, setRangeTo] = useState(initialRange.to)
  const [recruiterId, setRecruiterId] = useState('')
  const [toast, setToast] = useState<string | null>(null)
  const [incomingTarget, setIncomingTarget] = useState<IncomingCandidate | null>(null)
  const [incomingDate, setIncomingDate] = useState('')
  const [incomingTime, setIncomingTime] = useState('')
  const [incomingMessage, setIncomingMessage] = useState('')
  const [incomingSearch, setIncomingSearch] = useState('')
  const [incomingCityFilter, setIncomingCityFilter] = useState('all')
  const [incomingFilter, setIncomingFilter] = useState<IncomingFilter>('all')
  const [incomingSort, setIncomingSort] = useState<'waiting' | 'recent' | 'name'>('waiting')
  const [incomingPage, setIncomingPage] = useState(1)
  const [incomingPageSize, setIncomingPageSize] = useState<number>(50)
  const [showIncomingAdvancedFilters, setShowIncomingAdvancedFilters] = useState(false)
  const [expandedIncomingCards, setExpandedIncomingCards] = useState<Record<number, boolean>>({})
  const [hasAnimatedLists, setHasAnimatedLists] = useState(false)
  const recruiterTz = profile.data?.recruiter?.tz || browserTimeZone()
  const toastTimeoutRef = useRef<number | null>(null)

  const showToast = (message: string) => {
    setToast(message)
    if (toastTimeoutRef.current != null) {
      window.clearTimeout(toastTimeoutRef.current)
    }
    toastTimeoutRef.current = window.setTimeout(() => setToast(null), 2400)
  }

  const summaryQuery = useQuery<SummaryPayload>({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
    enabled: profileReady && Boolean(isAdmin),
  })

  const recruitersQuery = useQuery<RecruiterOption[]>({
    queryKey: ['dashboard-recruiters'],
    queryFn: fetchDashboardRecruiters,
    enabled: profileReady && Boolean(isAdmin),
    staleTime: 60_000,
  })

  const incomingQuery = useQuery<IncomingPayload>({
    queryKey: ['dashboard-incoming'],
    queryFn: () => fetchDashboardIncoming(INCOMING_FETCH_LIMIT),
    enabled: false,
    refetchInterval: 20000,
  })

  const kpiParams = useMemo(() => {
    if (!recruiterId) return ''
    const params = new URLSearchParams()
    params.set('recruiter', recruiterId)
    return `?${params.toString()}`
  }, [recruiterId])

  const kpiQuery = useQuery<KPIResponse>({
    queryKey: ['dashboard-kpis', kpiParams],
    queryFn: () => fetchCurrentKpis(kpiParams),
    enabled: profileReady && Boolean(isAdmin),
  })

  const leaderboardParams = useMemo(() => {
    const params = new URLSearchParams()
    if (rangeFrom) params.set('from', rangeFrom)
    if (rangeTo) params.set('to', rangeTo)
    return params.toString()
  }, [rangeFrom, rangeTo])

  const leaderboardQuery = useQuery<LeaderboardPayload>({
    queryKey: ['dashboard-leaderboard', leaderboardParams],
    queryFn: () => fetchRecruiterPerformance(leaderboardParams),
    enabled: profileReady && Boolean(isAdmin),
  })

  const rejectCandidate = useMutation({
    mutationFn: rejectDashboardCandidate,
    onSuccess: (data) => {
      showToast(data?.message || 'Кандидат отклонён')
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
      return scheduleDashboardIncomingSlot(payload.candidate.id, {
        recruiter_id: recruiterId,
        city_id: payload.candidate.city_id,
        date: payload.date,
        time: payload.time,
        custom_message: payload.message || '',
      })
    },
    onSuccess: (data) => {
      showToast(data?.message || 'Предложение отправлено кандидату')
      setIncomingTarget(null)
      incomingQuery.refetch()
    },
    onError: (error: Error) => showToast(error.message),
  })

  const openIncomingSchedule = (candidate: IncomingCandidate) => {
    const selected = toIsoDate(new Date())
    setIncomingTarget(candidate)
    setIncomingDate(selected)
    setIncomingTime('10:00')
    setIncomingMessage(candidate.requested_another_time_comment || candidate.availability_note || '')
  }


  const cityTzMap = useMemo(() => {
    const map = new Map<number, string>()
    const options = profile.data?.profile?.city_options || []
    for (const city of options) {
      if (city?.id && city?.tz) map.set(city.id, city.tz)
    }
    return map
  }, [profile.data?.profile?.city_options])

  const incomingCandidateTz = useMemo(() => {
    if (!incomingTarget) return recruiterTz
    const byCity = incomingTarget.city_id ? cityTzMap.get(incomingTarget.city_id) : null
    return byCity || recruiterTz
  }, [incomingTarget, cityTzMap, recruiterTz])

  const incomingPreview = useMemo(
    () => buildSlotTimePreview(incomingDate, incomingTime, recruiterTz, incomingCandidateTz),
    [incomingDate, incomingTime, recruiterTz, incomingCandidateTz],
  )

  const summaryCards = useMemo(() => {
    const data = summaryQuery.data
    if (!data) return []
    return [
      { label: 'Рекрутёры', value: data.recruiters },
      { label: 'Города', value: data.cities },
      { label: 'Слоты (всего)', value: data.slots_total },
      { label: 'Свободные', value: data.slots_free },
      { label: 'Ожидают', value: data.slots_pending },
      { label: 'Забронированы', value: data.slots_booked },
      { label: 'Ждут слота', value: data.waiting_candidates_total },
      { label: 'Отказы тест1', value: data.test1_rejections_total },
      { label: '% отказов тест1', value: data.test1_rejections_percent },
    ]
  }, [summaryQuery.data])

  const incomingCityOptions = useMemo(
    () => profile.data?.recruiter?.cities || [],
    [profile.data?.recruiter?.cities],
  )
  const incomingDemoCount = useMemo(() => {
    if (isAdmin || typeof window === 'undefined') return 0
    return resolveIncomingDemoCount({
      envValue: import.meta.env.VITE_INCOMING_DEMO_COUNT,
      hostname: window.location.hostname,
      search: window.location.search,
    })
  }, [isAdmin])
  const incomingBaseItems = useMemo(
    () =>
      withDemoIncomingCandidates(incomingQuery.data?.items || [], {
        targetCount: incomingDemoCount,
        cityOptions: incomingCityOptions,
      }),
    [incomingDemoCount, incomingCityOptions, incomingQuery.data?.items],
  )

  const incomingItems = useMemo(() => {
    const base = [...incomingBaseItems]
    const search = incomingSearch.trim().toLowerCase()
    const now = Date.now()

    const filtered = base.filter((candidate) => {
      if (incomingCityFilter !== 'all' && candidate.city_id !== Number(incomingCityFilter)) {
        return false
      }

      if (incomingFilter === 'new') {
        if (!candidate.last_message_at) return false
        const ageMs = now - new Date(candidate.last_message_at).getTime()
        if (!Number.isFinite(ageMs) || ageMs > 24 * 60 * 60 * 1000) return false
      }

      if (incomingFilter === 'stalled') {
        const stalledByStatus = candidate.status_slug === 'stalled_waiting_slot'
        const stalledByTime = (candidate.waiting_hours || 0) >= 24
        if (!stalledByStatus && !stalledByTime) return false
      }

      if (incomingFilter === 'pending' && candidate.status_slug !== 'slot_pending') {
        return false
      }

      if (incomingFilter === 'requested_other_time' && !candidate.requested_another_time) {
        return false
      }

      if (!search) return true
      const haystack = [
        candidate.name,
        candidate.city,
        candidate.status_display,
        candidate.telegram_username,
        String(candidate.telegram_id || ''),
        candidate.last_message,
        candidate.availability_note,
        candidate.requested_another_time_comment,
        candidate.responsible_recruiter_name,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return haystack.includes(search)
    })

    filtered.sort((a, b) => {
      const aRequested = a.requested_another_time ? 1 : 0
      const bRequested = b.requested_another_time ? 1 : 0
      if (bRequested !== aRequested) return bRequested - aRequested

      if (incomingSort === 'name') {
        return (a.name || '').localeCompare(b.name || '', 'ru')
      }
      if (incomingSort === 'recent') {
        const aTime = a.last_message_at ? new Date(a.last_message_at).getTime() : 0
        const bTime = b.last_message_at ? new Date(b.last_message_at).getTime() : 0
        return bTime - aTime
      }
      const aw = a.waiting_hours ?? -1
      const bw = b.waiting_hours ?? -1
      if (bw !== aw) return bw - aw
      const aTime = a.last_message_at ? new Date(a.last_message_at).getTime() : 0
      const bTime = b.last_message_at ? new Date(b.last_message_at).getTime() : 0
      return bTime - aTime
    })

    return filtered
  }, [incomingBaseItems, incomingCityFilter, incomingFilter, incomingSearch, incomingSort])

  const incomingStats = useMemo(() => {
    const base = incomingBaseItems
    const total = base.length
    const pending = base.filter((item) => item.status_slug === 'slot_pending').length
    const requested = base.filter((item) => Boolean(item.requested_another_time)).length
    const stalled = base.filter((item) => item.status_slug === 'stalled_waiting_slot' || (item.waiting_hours || 0) >= 24).length
    const fresh = base.filter((item) => {
      if (!item.last_message_at) return false
      const ageMs = Date.now() - new Date(item.last_message_at).getTime()
      return Number.isFinite(ageMs) && ageMs <= 24 * 60 * 60 * 1000
    }).length
    return { total, pending, requested, stalled, fresh }
  }, [incomingBaseItems])

  useEffect(() => {
    if (typeof window === 'undefined' || isAdmin) return
    try {
      const raw = window.localStorage.getItem(DASHBOARD_INCOMING_FILTERS_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw) as {
        search?: string
        city?: string
        filter?: IncomingFilter
        sort?: 'waiting' | 'recent' | 'name'
        pageSize?: number
      }
      if (typeof parsed.search === 'string') setIncomingSearch(parsed.search)
      if (typeof parsed.city === 'string') setIncomingCityFilter(parsed.city)
      if (parsed.filter && ['all', 'new', 'stalled', 'pending', 'requested_other_time'].includes(parsed.filter)) {
        setIncomingFilter(parsed.filter)
      }
      if (parsed.sort && ['waiting', 'recent', 'name'].includes(parsed.sort)) {
        setIncomingSort(parsed.sort)
      }
      if (typeof parsed.pageSize === 'number' && INCOMING_PAGE_SIZE_OPTIONS.includes(parsed.pageSize as typeof INCOMING_PAGE_SIZE_OPTIONS[number])) {
        setIncomingPageSize(parsed.pageSize)
      }
    } catch {
      // ignore local storage parse errors
    }
  }, [isAdmin])

  useEffect(() => {
    if (typeof window === 'undefined' || isAdmin) return
    const payload = {
      search: incomingSearch,
      city: incomingCityFilter,
      filter: incomingFilter,
      sort: incomingSort,
      pageSize: incomingPageSize,
    }
    window.localStorage.setItem(DASHBOARD_INCOMING_FILTERS_KEY, JSON.stringify(payload))
  }, [incomingCityFilter, incomingFilter, incomingPageSize, incomingSearch, incomingSort, isAdmin])

  const resetIncomingFilters = () => {
    setIncomingSearch('')
    setIncomingCityFilter('all')
    setIncomingFilter('all')
    setIncomingSort('waiting')
    setIncomingPage(1)
    setIncomingPageSize(50)
    setShowIncomingAdvancedFilters(false)
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(DASHBOARD_INCOMING_FILTERS_KEY)
    }
  }

  const toggleIncomingCardExpanded = (candidateId: number) => {
    setExpandedIncomingCards((prev) => ({ ...prev, [candidateId]: !prev[candidateId] }))
  }

  useEffect(() => {
    setIncomingPage(1)
  }, [incomingCityFilter, incomingFilter, incomingSearch, incomingSort, incomingPageSize])

  const incomingPagesTotal = useMemo(() => {
    if (!incomingItems.length) return 1
    return Math.ceil(incomingItems.length / incomingPageSize)
  }, [incomingItems.length, incomingPageSize])

  useEffect(() => {
    if (incomingPage > incomingPagesTotal) {
      setIncomingPage(incomingPagesTotal)
    }
  }, [incomingPage, incomingPagesTotal])

  const incomingPageStart = useMemo(
    () => (incomingPage - 1) * incomingPageSize,
    [incomingPage, incomingPageSize],
  )
  const incomingPageEnd = incomingPageStart + incomingPageSize
  const incomingPageItems = useMemo(
    () => incomingItems.slice(incomingPageStart, incomingPageEnd),
    [incomingItems, incomingPageEnd, incomingPageStart],
  )
  const firstRenderAnimation = !hasAnimatedLists && !prefersReducedMotion
  const leaderboardAnimationKey = [leaderboardParams, recruiterId].join('|')
  const kpiAnimationKey = [kpiParams, kpiQuery.data?.current.label || ''].join('|')

  useEffect(() => {
    setHasAnimatedLists(true)
  }, [])

  if (!profileReady) {
    return (
      <div className="page app-page app-page--ops">
        <p className="subtitle">Загрузка…</p>
      </div>
    )
  }

  if (!isAdmin) {
    return <IncomingPage />
  }

  return (
    <div className="page app-page app-page--ops dashboard-page">
      {isAdmin && (
        <header className="glass glass--elevated panel dashboard-header dashboard-hero ui-hero--quiet app-page__hero">
          <div className="dashboard-hero__content">
            <h1 className="title title--lg">Дашборд</h1>
            <p className="subtitle">Метрики отдела, KPI и эффективность рекрутеров.</p>
          </div>
          <div className="dashboard-filters">
            <div className="filter-group">
              <label className="filter-field">
                <span>От</span>
                <input
                  type="date"
                  value={rangeFrom}
                  onChange={(e) => {
                    const next = e.target.value
                    setRangeFrom(next)
                    if (rangeTo && next > rangeTo) setRangeTo(next)
                  }}
                />
              </label>
              <label className="filter-field">
                <span>До</span>
                <input
                  type="date"
                  value={rangeTo}
                  onChange={(e) => {
                    const next = e.target.value
                    setRangeTo(next)
                    if (rangeFrom && next < rangeFrom) setRangeFrom(next)
                  }}
                />
              </label>
            </div>
            <label className="filter-field">
              <span>Рекрутёр</span>
              <select
                value={recruiterId}
                onChange={(e) => setRecruiterId(e.target.value)}
              >
                <option value="">Все специалисты</option>
                {(recruitersQuery.data || []).map((rec) => (
                  <option key={rec.id} value={rec.id}>
                    {rec.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </header>
      )}

      {isAdmin && (
        <section className="glass panel dashboard-summary app-page__section">
          <div className="dashboard-section-header app-page__section-head">
            <h2 className="section-title">Общая сводка</h2>
            {summaryQuery.isFetching && <span className="text-muted text-xs">Обновление…</span>}
          </div>
          
          {summaryQuery.isLoading && (
            <div className="grid-cards">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="glass glass--subtle stat-card skeleton dashboard-summary__skeleton-card" />
              ))}
            </div>
          )}
          
          {summaryQuery.isError && <ApiErrorBanner error={summaryQuery.error} title="Ошибка загрузки сводки" onRetry={() => summaryQuery.refetch()} />}
          
          {summaryCards.length > 0 && (
            <motion.div
              key={summaryCards.map((card) => `${card.label}:${card.value}`).join('|')}
              className="grid-cards dashboard-summary-grid"
              initial={prefersReducedMotion ? false : firstRenderAnimation ? 'initial' : { opacity: 0 }}
              animate={prefersReducedMotion ? undefined : firstRenderAnimation ? 'animate' : { opacity: 1 }}
              variants={firstRenderAnimation ? stagger(0.03) : undefined}
              transition={prefersReducedMotion || firstRenderAnimation ? undefined : fadeIn.transition}
            >
              {summaryCards.map((card) => (
                <motion.div key={card.label} variants={firstRenderAnimation ? listItem : undefined}>
                  <DashboardMetric title={card.label} value={card.value} />
                </motion.div>
              ))}
            </motion.div>
          )}
        </section>
      )}

      <div className={`dashboard-main-grid ${!isAdmin ? 'dashboard-main-grid--incoming-only' : ''}`}>
        {isAdmin && (
          <div className="glass panel dashboard-panel dashboard-leaderboard app-page__section">
            <div className="dashboard-section-header app-page__section-head">
              <div>
                <h2 className="section-title">Лидерборд эффективности</h2>
                <p className="subtitle">
                  Оценка по конверсии, подтверждениям и загрузке слотов
                </p>
              </div>
              <button
                className="ui-btn ui-btn--ghost"
                onClick={() => leaderboardQuery.refetch()}
              >
                Обновить
              </button>
            </div>
            {leaderboardQuery.isLoading && <p className="subtitle">Загрузка…</p>}
            {leaderboardQuery.isError && <ApiErrorBanner error={leaderboardQuery.error} title="Ошибка загрузки лидерборда" />}
            {leaderboardQuery.data?.items?.length ? (
              <motion.div
                key={leaderboardAnimationKey}
                className={`leaderboard-list ${isMobile ? 'leaderboard-list--mobile' : ''}`}
                data-testid={isMobile ? 'dashboard-leaderboard-mobile' : 'dashboard-leaderboard-list'}
                initial={prefersReducedMotion ? false : firstRenderAnimation ? 'initial' : { opacity: 0 }}
                animate={prefersReducedMotion ? undefined : firstRenderAnimation ? 'animate' : { opacity: 1 }}
                variants={firstRenderAnimation ? stagger(0.03) : undefined}
                transition={prefersReducedMotion || firstRenderAnimation ? undefined : fadeIn.transition}
              >
                {leaderboardQuery.data.items.map((item) => {
                  const isSelected = recruiterId && Number(recruiterId) === item.recruiter_id
                  const rankClass = leaderboardRankClass(item.rank)
                  return (
                    <motion.article
                      key={item.recruiter_id}
                      className={`leaderboard-item ${isSelected ? 'is-selected' : ''}`}
                      variants={firstRenderAnimation ? listItem : undefined}
                    >
                      <span className={`leaderboard-rank ${rankClass}`}>{item.rank}</span>
                      <div className="leaderboard-item__content">
                        <div className="leaderboard-item__main">
                          <strong className="leaderboard-item__name">{item.name}</strong>
                          <span className="leaderboard-score">{item.score}</span>
                        </div>
                        <div className="leaderboard-item__stats">
                          <span>Конверсия: {item.conversion_interview}%</span>
                          <span>Подтв.: {item.confirmation_rate}%</span>
                          <span>Заполн.: {item.fill_rate}%</span>
                          <span>Кандидаты: {item.throughput}</span>
                          <span>Нанято: {item.hired_total}</span>
                          <span>Отказ: {item.declined_total}</span>
                        </div>
                      </div>
                    </motion.article>
                  )
                })}
              </motion.div>
            ) : (
              <p className="subtitle">Нет данных за выбранный период.</p>
            )}
          </div>
        )}

        {!isAdmin && (
          <section className="glass panel dashboard-panel dashboard-incoming dashboard-incoming--fullscreen app-page__section" data-testid="dashboard-incoming-fullscreen">
            <div className="dashboard-section-header app-page__section-head">
              <div>
                <h2 className="section-title">Входящие</h2>
                <p className="subtitle">Рабочая лента согласования: фильтруйте очередь и обрабатывайте кандидатов без переключения страниц.</p>
              </div>
              <div className="dashboard-incoming__header-actions">
                <button className="ui-btn ui-btn--ghost" onClick={() => incomingQuery.refetch()}>
                  Обновить
                </button>
                <Link className="ui-btn ui-btn--ghost" to="/app/incoming">
                  Расширенный режим
                </Link>
              </div>
            </div>
            {incomingDemoCount > 0 && (
              <div className="dashboard-incoming__demo-note">
                Тестовый режим: показываем {incomingDemoCount} карточек с имитацией разных кандидатов.
              </div>
            )}

            <div className="dashboard-incoming__kpis">
              <button
                type="button"
                className={`dashboard-incoming__kpi-chip ${incomingFilter === 'all' ? 'dashboard-incoming__kpi-chip--active' : ''}`}
                onClick={() => setIncomingFilter('all')}
              >
                Все: {incomingStats.total}
              </button>
              <button
                type="button"
                className={`dashboard-incoming__kpi-chip ${incomingFilter === 'pending' ? 'dashboard-incoming__kpi-chip--active' : ''}`}
                onClick={() => setIncomingFilter('pending')}
              >
                На согласовании: {incomingStats.pending}
              </button>
              <button
                type="button"
                className={`dashboard-incoming__kpi-chip ${incomingFilter === 'requested_other_time' ? 'dashboard-incoming__kpi-chip--active' : ''}`}
                onClick={() => setIncomingFilter('requested_other_time')}
              >
                Запросили другое время: {incomingStats.requested}
              </button>
              <button
                type="button"
                className={`dashboard-incoming__kpi-chip ${incomingFilter === 'stalled' ? 'dashboard-incoming__kpi-chip--active' : ''}`}
                onClick={() => setIncomingFilter('stalled')}
              >
                Застряли {'>'}24ч: {incomingStats.stalled}
              </button>
              <button
                type="button"
                className={`dashboard-incoming__kpi-chip ${incomingFilter === 'new' ? 'dashboard-incoming__kpi-chip--active' : ''}`}
                onClick={() => setIncomingFilter('new')}
              >
                NEW (24ч): {incomingStats.fresh}
              </button>
            </div>

            {incomingQuery.isLoading && <p className="subtitle">Загрузка…</p>}
            {incomingQuery.isError && <ApiErrorBanner error={incomingQuery.error} title="Ошибка загрузки входящих" />}
            {incomingQuery.data && incomingBaseItems.length === 0 && (
              <div className="dashboard-incoming__empty-state">
                <p className="subtitle">Сейчас в очереди нет кандидатов.</p>
              </div>
            )}
            {incomingQuery.data && incomingBaseItems.length > 0 && (
              <>
                <div className="incoming-toolbar dashboard-incoming__toolbar ui-filter app-page__toolbar">
                  <div className="incoming-toolbar__stats">
                    <strong>{incomingItems.length}</strong>
                    <span className="text-muted text-sm">из {incomingBaseItems.length} кандидатов</span>
                    <span className="text-muted text-sm">· страница {incomingPage} / {incomingPagesTotal}</span>
                    {incomingDemoCount > 0 && <span className="status-pill status-pill--info">Тестовые данные</span>}
                  </div>
                  <div className="incoming-toolbar__controls">
                    <input
                      className="incoming-toolbar__search"
                      type="search"
                      placeholder="Поиск: имя, город, TG, комментарий..."
                      value={incomingSearch}
                      onChange={(e) => setIncomingSearch(e.target.value)}
                    />
                    <select
                      className="incoming-toolbar__select"
                      value={incomingCityFilter}
                      onChange={(e) => setIncomingCityFilter(e.target.value)}
                    >
                      <option value="all">Все города</option>
                      {incomingCityOptions.map((city) => (
                        <option key={city.id} value={String(city.id)}>
                          {city.name}
                        </option>
                      ))}
                    </select>
                    <select
                      className="incoming-toolbar__select"
                      value={incomingFilter}
                      onChange={(e) => setIncomingFilter(e.target.value as IncomingFilter)}
                    >
                      <option value="all">Все статусы</option>
                      <option value="pending">На согласовании</option>
                      <option value="requested_other_time">Запросили другое время</option>
                      <option value="stalled">Застряли {'>'}24ч</option>
                      <option value="new">NEW (24ч)</option>
                    </select>
                    <button
                      className="ui-btn ui-btn--ghost ui-btn--sm"
                      type="button"
                      onClick={() => setShowIncomingAdvancedFilters((prev) => !prev)}
                    >
                      {showIncomingAdvancedFilters ? 'Скрыть доп.' : 'Доп. фильтры'}
                    </button>
                    <button className="ui-btn ui-btn--ghost ui-btn--sm" type="button" onClick={resetIncomingFilters}>
                      Сбросить фильтры
                    </button>
                  </div>
                </div>
                <div className={`ui-filter-bar__advanced ui-filter ${showIncomingAdvancedFilters ? 'ui-filter-bar__advanced--open' : ''}`}>
                  <select
                    className="incoming-toolbar__select"
                    value={incomingSort}
                    onChange={(e) => setIncomingSort(e.target.value as 'waiting' | 'recent' | 'name')}
                  >
                    <option value="waiting">Сначала кто дольше ждёт</option>
                    <option value="recent">Последние сообщения</option>
                    <option value="name">По имени</option>
                  </select>
                  <select
                    className="incoming-toolbar__select"
                    value={String(incomingPageSize)}
                    onChange={(e) => setIncomingPageSize(Number(e.target.value))}
                  >
                    {INCOMING_PAGE_SIZE_OPTIONS.map((size) => (
                      <option key={size} value={String(size)}>
                        По {size}
                      </option>
                    ))}
                  </select>
                </div>

                {incomingItems.length === 0 ? (
                  <div className="dashboard-incoming__empty-filters">
                    <p className="subtitle">По текущим фильтрам кандидатов нет.</p>
                    <button className="ui-btn ui-btn--ghost ui-btn--sm" type="button" onClick={resetIncomingFilters}>
                      Сбросить фильтры
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="incoming-list incoming-list--fullscreen">
                      {incomingPageItems.map((candidate) => {
                        const isRequested = Boolean(candidate.requested_another_time)
                        const isPending = candidate.status_slug === 'slot_pending'
                        const statusTone =
                          isRequested ? 'warning' :
                          isPending ? 'info' :
                          candidate.status_slug === 'stalled_waiting_slot' ? 'danger' : 'muted'
                        const telegramUsername = candidate.telegram_username?.replace(/^@/, '')
                        const telegramLink = telegramUsername
                          ? `https://t.me/${telegramUsername}`
                          : candidate.telegram_id
                            ? `tg://user?id=${candidate.telegram_id}`
                            : null
                        const isExpanded = Boolean(expandedIncomingCards[candidate.id])
                        return (
                          <article key={candidate.id} className="incoming-min-card incoming-min-card--wide ui-reveal">
                            <div className="incoming-min-card__head">
                              <div className="incoming-min-card__identity">
                                <div className="incoming-min-card__name">{candidate.name || 'Без имени'}</div>
                                <div className="incoming-min-card__city">{candidate.city || 'Город не указан'}</div>
                              </div>
                              <span className="incoming-min-card__waiting">
                                {candidate.waiting_hours != null ? `Ждёт ${candidate.waiting_hours} ч` : 'Без ожидания'}
                              </span>
                            </div>

                            <div className="incoming-min-card__status-row">
                              {candidate.status_display && (
                                <span className={`status-pill status-pill--${statusTone}`}>{candidate.status_display}</span>
                              )}
                              {isRequested && <span className="status-pill status-pill--warning">Запросил другое время</span>}
                              {candidate.responsible_recruiter_name && (
                                <span className="status-pill status-pill--muted">Ответственный: {candidate.responsible_recruiter_name}</span>
                              )}
                            </div>

                            <div className="incoming-min-card__chips">
                              <span className="incoming-min-chip incoming-min-chip--time">
                                Предпочтение: {candidate.availability_window || 'не указано'}
                              </span>
                              <span className="incoming-min-chip incoming-min-chip--ai">
                                AI: {formatAiRelevance(candidate)}
                              </span>
                              {formatAiRecommendation(candidate) && (
                                <span className="incoming-min-chip incoming-min-chip--ai">
                                  {formatAiRecommendation(candidate)}
                                </span>
                              )}
                            </div>

                            {candidate.ai_risk_hint && (
                              <div className="incoming-min-card__note incoming-min-card__note--block">
                                <span>AI: {candidate.ai_risk_hint}</span>
                              </div>
                            )}

                            {candidate.requested_another_time_comment && isExpanded && (
                              <div className="incoming-min-card__note incoming-min-card__note--requested incoming-min-card__note--block">
                                <span>🔁 Комментарий по переносу: {candidate.requested_another_time_comment}</span>
                                {candidate.requested_another_time_at && (
                                  <span className="incoming-min-card__time">
                                    {new Date(candidate.requested_another_time_at).toLocaleString('ru-RU', {
                                      day: '2-digit',
                                      month: '2-digit',
                                      hour: '2-digit',
                                      minute: '2-digit',
                                    })}
                                  </span>
                                )}
                              </div>
                            )}

                            {candidate.last_message && (
                              <div className={`incoming-min-card__note incoming-min-card__note--block ${!isExpanded ? 'incoming-min-card__note--clamped' : ''}`}>
                                <span>💬 {candidate.last_message}</span>
                                {candidate.last_message_at && (
                                  <span className="incoming-min-card__time">
                                    {new Date(candidate.last_message_at).toLocaleString('ru-RU', {
                                      day: '2-digit',
                                      month: '2-digit',
                                      hour: '2-digit',
                                      minute: '2-digit',
                                    })}
                                  </span>
                                )}
                              </div>
                            )}

                            <div className="incoming-min-card__actions">
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
                              <button
                                className="ui-btn ui-btn--primary ui-btn--sm"
                                type="button"
                                onClick={() => openIncomingSchedule(candidate)}
                              >
                                Согласовать время
                              </button>
                              <button
                                className="ui-btn ui-btn--danger ui-btn--sm"
                                type="button"
                                onClick={() => rejectCandidate.mutate(candidate.id)}
                              >
                                Отказать
                              </button>
                              <button
                                type="button"
                                className="ui-btn ui-btn--ghost ui-btn--sm"
                                onClick={() => toggleIncomingCardExpanded(candidate.id)}
                              >
                                {isExpanded ? 'Скрыть детали' : 'Подробнее'}
                              </button>
                            </div>
                          </article>
                        )
                      })}
                    </div>

                    <div className="pagination incoming-pagination">
                      <span className="pagination__info">
                        Показано {incomingPageStart + 1}–{Math.min(incomingPageEnd, incomingItems.length)} из {incomingItems.length}
                      </span>
                      <button
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        type="button"
                        onClick={() => setIncomingPage(1)}
                        disabled={incomingPage <= 1}
                      >
                        ⏮
                      </button>
                      <button
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        type="button"
                        onClick={() => setIncomingPage((prev) => Math.max(1, prev - 1))}
                        disabled={incomingPage <= 1}
                      >
                        Назад
                      </button>
                      <button
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        type="button"
                        onClick={() => setIncomingPage((prev) => Math.min(incomingPagesTotal, prev + 1))}
                        disabled={incomingPage >= incomingPagesTotal}
                      >
                        Вперёд
                      </button>
                      <button
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        type="button"
                        onClick={() => setIncomingPage(incomingPagesTotal)}
                        disabled={incomingPage >= incomingPagesTotal}
                      >
                        ⏭
                      </button>
                    </div>
                  </>
                )}
              </>
            )}
          </section>
        )}
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
                  <h2 className="modal__title">Предложить время собеседования</h2>
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
                    Время ({recruiterTz} · {formatTzOffset(recruiterTz)})
                    <input type="time" value={incomingTime} onChange={(e) => setIncomingTime(e.target.value)} />
                  </label>
                </div>
                {incomingPreview && (
                  <div className="glass slot-preview">
                    <div>
                      <div className="slot-preview__label">Вы вводите (ваша TZ)</div>
                      <div className="slot-preview__value">{incomingPreview.recruiterLabel}</div>
                      <div className="slot-preview__hint">
                        {incomingPreview.recruiterTz} · {formatTzOffset(incomingPreview.recruiterTz)}
                      </div>
                    </div>
                    <div>
                      <div className="slot-preview__label">Кандидат увидит</div>
                      <div className="slot-preview__value">{incomingPreview.candidateLabel}</div>
                      <div className="slot-preview__hint">
                        {incomingPreview.candidateTz} · {formatTzOffset(incomingPreview.candidateTz)}
                      </div>
                    </div>
                  </div>
                )}
                <label>
                  Сообщение кандидату (необязательно)
                  <textarea
                    rows={3}
                    value={incomingMessage}
                    onChange={(e) => setIncomingMessage(e.target.value)}
                    placeholder="Например: Мы предлагаем собеседование в это время. Подойдёт ли вам?"
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
                  {scheduleIncoming.isPending ? 'Отправка…' : 'Отправить предложение'}
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

      {isAdmin && (
        <div className="glass panel dashboard-panel dashboard-kpi app-page__section">
          <div className="dashboard-section-header app-page__section-head">
            <div>
              <h2 className="section-title">Weekly KPI</h2>
              <p className="subtitle">{kpiQuery.data?.current.label}</p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={() => kpiQuery.refetch()}>
              Обновить
            </button>
          </div>
          {kpiQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {kpiQuery.isError && <ApiErrorBanner error={kpiQuery.error} title="Ошибка загрузки KPI" />}
          {kpiQuery.data?.current?.metrics && (
            <motion.div
              key={kpiAnimationKey}
              className="kpi-grid"
              initial={prefersReducedMotion ? false : firstRenderAnimation ? 'initial' : { opacity: 0 }}
              animate={prefersReducedMotion ? undefined : firstRenderAnimation ? 'animate' : { opacity: 1 }}
              variants={firstRenderAnimation ? stagger(0.03) : undefined}
              transition={prefersReducedMotion || firstRenderAnimation ? undefined : fadeIn.transition}
            >
              {kpiQuery.data.current.metrics.map((metric) => (
                <motion.article key={metric.key} className="kpi-card" variants={firstRenderAnimation ? listItem : undefined}>
                  <div className="kpi-card__header">
                    <span className="kpi-card__icon">{metric.icon}</span>
                    <span className="kpi-label">{metric.label}</span>
                  </div>
                  <div className="kpi-value">{metric.value}</div>
                  <div className={`kpi-delta kpi-delta--${dashboardTrendTone(metric.trend?.display)}`}>
                    {metric.trend?.display || '—'}
                  </div>
                </motion.article>
              ))}
            </motion.div>
          )}
        </div>
      )}
    </div>
  )
}
