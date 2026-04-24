import { useEffect, useMemo, useState, type ReactNode } from 'react'

import './miniapp.css'
import {
  bindMaxBackButton,
  bridgeInitData,
  bridgeStartParam,
  openExternalLink,
  prepareMaxBridge,
  requestMaxContact,
  setClosingConfirmation,
} from './maxBridge'

type LaunchBindingStatus =
  | 'bound'
  | 'contact_required'
  | 'manual_review_required'
  | 'outside_max_client'
  | 'launch_error'

type MiniAppPanel =
  | 'home'
  | 'test1'
  | 'test2'
  | 'booking-city'
  | 'booking-recruiter'
  | 'booking-slots'
  | 'manual-availability'
  | 'booked'
  | 'intro-day'
  | 'help'

type LaunchResponse = {
  binding: {
    status: LaunchBindingStatus | string
    code?: string | null
    message: string
    requires_contact?: boolean
    start_param?: string | null
    chat_url?: string | null
  }
  candidate?: {
    id: number
    candidate_id: string
    application_id?: number | null
  } | null
  session?: {
    session_id: string
  } | null
  capabilities?: {
    request_contact: boolean
    open_link: boolean
    open_max_link: boolean
  }
}

type CandidateDecision = {
  outcome: string
  explanation: string
  required_next_action: string
}

type TestQuestionOption = {
  label: string
  value: string
}

type TestQuestion = {
  id: string
  prompt: string
  helper?: string | null
  placeholder?: string | null
  question_index: number
  options: TestQuestionOption[]
}

type Test1Response = {
  journey_step: string
  questions: TestQuestion[]
  draft_answers: Record<string, string>
  is_completed: boolean
  screening_decision?: CandidateDecision | null
  required_next_action?: string | null
}

type Test2QuestionOption = {
  label: string
  value: string
}

type Test2Question = {
  id: string
  prompt: string
  question_index: number
  options: Test2QuestionOption[]
}

type Test2Response = {
  journey_step: string
  questions: Test2Question[]
  current_question_index?: number | null
  attempts: Record<string, unknown>
  is_started: boolean
  is_completed: boolean
  score?: number | null
  correct_answers?: number | null
  total_questions: number
  passed?: boolean | null
  rating?: string | null
  required_next_action?: string | null
  result_message?: string | null
}

type IntroDayResponse = {
  booking_id: number
  city_name?: string | null
  recruiter_name?: string | null
  start_utc: string
  end_utc: string
  address?: string | null
  intro_contact?: string | null
  contact_name?: string | null
  contact_phone?: string | null
  status: string
}

type JourneyTimelineStep = {
  key: string
  label: string
  state: string
  state_label: string
  detail?: string | null
}

type JourneyPrimaryAction = {
  key: string
  label: string
  kind: string
  detail?: string | null
}

type JourneyCard = {
  title: string
  body: string
  tone?: string
}

type JourneyResponse = {
  active_booking?: Booking | null
  timeline: JourneyTimelineStep[]
  primary_action?: JourneyPrimaryAction | null
  status_card?: JourneyCard | null
  prep_card?: JourneyCard | null
  company_card?: JourneyCard | null
  help_card?: JourneyCard | null
}

type BookingContext = {
  city_id?: number | null
  city_name?: string | null
  recruiter_id?: number | null
  recruiter_name?: string | null
  source: string
  is_explicit: boolean
}

type CityInfo = {
  city_id: number
  city_name: string
  tz: string
  has_available_recruiters: boolean
  available_recruiters: number
  available_slots: number
}

type RecruiterInfo = {
  recruiter_id: number
  recruiter_name: string
  tz: string
  available_slots: number
  next_slot_utc?: string | null
}

type SlotInfo = {
  slot_id: number
  recruiter_id: number
  recruiter_name: string
  start_utc: string
  end_utc: string
  duration_minutes: number
  city_id?: number | null
  city_name?: string | null
}

type Booking = {
  booking_id: number
  recruiter_name: string
  start_utc: string
  end_utc: string
  status: string
  candidate_can_confirm_pending?: boolean
  meet_link?: string | null
}

type ContactBindResponse = {
  status: string
  message: string
  start_param?: string | null
}

type ManualAvailabilityResponse = {
  status: string
  message: string
  recruiters_notified: boolean
}

type BridgeCapabilities = NonNullable<LaunchResponse['capabilities']>

type ApiErrorInfo = {
  code?: string | null
  message: string
}

type BookingNotice = {
  title: string
  body: string
  tone: 'success' | 'progress' | 'warn'
}

type SurfaceTone = 'success' | 'progress' | 'warn' | 'neutral' | 'accent'

type TimelineVisualState = 'done' | 'current' | 'pending' | 'review'

type MaterialCardKind = 'prep' | 'company' | 'help'

type MaterialCardItem = {
  key: MaterialCardKind
  eyebrow: string
  tone: SurfaceTone
  card: JourneyCard
}

type MiniAppStateCardProps = {
  eyebrow: string
  title: string
  body: string
  tone?: SurfaceTone
  badge?: string
  actions?: ReactNode
  children?: ReactNode
  className?: string
  role?: 'status' | 'alert'
  testId?: string
}

const DEFAULT_CAPABILITIES: BridgeCapabilities = {
  request_contact: false,
  open_link: false,
  open_max_link: false,
}

function joinClassNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(' ')
}

function normalizeTone(value?: string | null): SurfaceTone {
  const normalized = String(value || '').trim().toLowerCase()
  if (normalized === 'success') return 'success'
  if (normalized === 'warn' || normalized === 'warning') return 'warn'
  if (normalized === 'accent') return 'accent'
  if (normalized === 'progress' || normalized === 'info') return 'progress'
  return 'neutral'
}

function normalizeTimelineState(value?: string | null): TimelineVisualState {
  const normalized = String(value || '').trim().toLowerCase()
  if (normalized === 'done' || normalized === 'current' || normalized === 'pending' || normalized === 'review') {
    return normalized
  }
  return 'pending'
}

function toneLabel(value?: string | null) {
  switch (normalizeTone(value)) {
    case 'success':
      return 'Готово'
    case 'warn':
      return 'Проверка'
    case 'accent':
      return 'Материалы'
    case 'progress':
      return 'В работе'
    default:
      return 'На контроле'
  }
}

function toneEyebrow(value?: string | null) {
  switch (normalizeTone(value)) {
    case 'success':
      return 'Шаг готов'
    case 'warn':
      return 'Нужна проверка'
    case 'accent':
      return 'Материалы'
    case 'progress':
      return 'Следим за шагом'
    default:
      return 'Статус шага'
  }
}

function actionBadge(action?: JourneyPrimaryAction | null) {
  switch (String(action?.kind || '').trim().toLowerCase()) {
    case 'test1':
      return 'Анкета'
    case 'test2':
      return 'Тест 2'
    case 'booking':
      return 'Запись'
    case 'intro_day':
      return 'Ознакомительный день'
    case 'help':
      return 'Статус'
    default:
      return 'Дальше'
  }
}

function nextStepDescription({
  journey,
  test1,
}: {
  journey: JourneyResponse | null
  test1: Test1Response | null
}) {
  const explicitDetail = journey?.primary_action?.detail?.trim()
  if (explicitDetail) return explicitDetail
  if (!test1?.is_completed) {
    return 'Ответьте на оставшиеся вопросы. После этого покажем следующий шаг здесь, без смены сценария.'
  }
  if (journey?.active_booking) {
    return 'Проверьте время встречи, памятку и дальнейшие действия по текущему шагу.'
  }
  if (test1?.required_next_action === 'select_interview_slot') {
    return 'Выберите удобное время собеседования. Если подходящего слота нет, можно отправить пожелания.'
  }
  return journey?.status_card?.body || 'Когда сервер обновит шаг, покажем здесь, что делать дальше.'
}

function materialCardEyebrow(kind: MaterialCardKind, tone?: string | null) {
  if (kind === 'prep') return 'Подготовка'
  if (kind === 'company') return 'О RecruitSmart'
  if (normalizeTone(tone) === 'warn') return 'Нужна помощь'
  return 'Поддержка'
}

function collectMaterialCards(journey: JourneyResponse | null): MaterialCardItem[] {
  const source: Array<{ key: MaterialCardKind; card: JourneyCard | null | undefined }> = [
    { key: 'prep', card: journey?.prep_card },
    { key: 'company', card: journey?.company_card },
    { key: 'help', card: journey?.help_card },
  ]

  return source
    .filter((item): item is { key: MaterialCardKind; card: JourneyCard } => Boolean(item.card))
    .map((item) => ({
      key: item.key,
      eyebrow: materialCardEyebrow(item.key, item.card.tone),
      tone: normalizeTone(item.card.tone),
      card: item.card,
    }))
}

function busyMessage(panel: MiniAppPanel, hasSession: boolean) {
  if (!hasSession) {
    return 'Проверяем launch-контекст MAX и загружаем текущий шаг кандидата.'
  }
  if (panel === 'test1') return 'Сохраняем ответ и перечитываем следующий шаг.'
  if (panel === 'test2') return 'Сохраняем ответ на Тест 2 и обновляем следующий шаг.'
  if (panel === 'booking-city' || panel === 'booking-recruiter' || panel === 'booking-slots') {
    return 'Обновляем доступные слоты и синхронизируем запись.'
  }
  if (panel === 'manual-availability') return 'Передаём пожелания по времени рекрутеру.'
  if (panel === 'booked') return 'Обновляем детали встречи и памятку.'
  if (panel === 'intro-day') return 'Проверяем детали ознакомительного дня и синхронизируем подтверждение.'
  return 'Синхронизируем шаг кандидата.'
}

function MiniAppStateCard({
  eyebrow,
  title,
  body,
  tone = 'neutral',
  badge,
  actions,
  children,
  className,
  role = 'status',
  testId,
}: MiniAppStateCardProps) {
  return (
    <section
      className={joinClassNames('max-card', 'max-stack', 'max-state-card', `max-state-card--${tone}`, className)}
      data-testid={testId}
      role={role}
    >
      <div className="max-state-card__head">
        <div className="max-state-card__copy">
          <p className="max-card__eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
        {badge ? <span className={`max-pill max-pill--${tone}`}>{badge}</span> : null}
      </div>
      <p>{body}</p>
      {children}
      {actions ? <div className="max-actions">{actions}</div> : null}
    </section>
  )
}

function detectInitData() {
  if (typeof window === 'undefined') return ''
  const query = new URLSearchParams(window.location.search)
  const direct = query.get('initData')
  if (direct) return direct
  return bridgeInitData()
}

function detectStartParam() {
  if (typeof window === 'undefined') return ''
  const query = new URLSearchParams(window.location.search)
  return query.get('startapp') || query.get('start_param') || bridgeStartParam()
}

async function maxApi<T>(
  path: string,
  {
    method = 'GET',
    body,
    initData,
    sessionId,
  }: {
    method?: string
    body?: unknown
    initData: string
    sessionId?: string | null
  },
): Promise<T> {
  const headers = new Headers({
    'Content-Type': 'application/json',
    'X-Max-Init-Data': initData,
  })
  if (sessionId) headers.set('X-Candidate-Access-Session', sessionId)

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    body: body == null ? undefined : JSON.stringify(body),
    credentials: 'include',
  })

  if (!response.ok) {
    let errorInfo: ApiErrorInfo = { message: response.statusText }
    try {
      const payload = await response.json()
      errorInfo = extractApiError(payload, response.statusText)
    } catch {}
    const error = new Error(errorInfo.message || 'Request failed')
    ;(error as Error & { code?: string | null }).code = errorInfo.code
    throw error
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

function formatDate(value?: string | null, timeZone = 'Europe/Moscow') {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      timeZone,
      weekday: 'short',
      day: '2-digit',
      month: 'long',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  } catch {
    return date.toLocaleString('ru-RU', {
      weekday: 'short',
      day: '2-digit',
      month: 'long',
      hour: '2-digit',
      minute: '2-digit',
    })
  }
}

function dateKeyInTimeZone(date: Date, timeZone: string) {
  try {
    const formatter = new Intl.DateTimeFormat('en-CA', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    })
    const parts = formatter.formatToParts(date)
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
    const year = values.year || '0000'
    const month = values.month || '00'
    const day = values.day || '00'
    return `${year}-${month}-${day}`
  } catch {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
  }
}

function formatBookingStatus(value?: string | null) {
  const normalized = String(value || '').trim().toLowerCase()
  if (normalized === 'pending') return 'На согласовании'
  if (normalized === 'booked') return 'Нужно подтвердить'
  if (normalized === 'confirmed' || normalized === 'confirmed_by_candidate') return 'Подтверждено'
  if (normalized === 'rescheduled') return 'Перенесено'
  if (normalized === 'cancelled' || normalized === 'canceled') return 'Отменено'
  if (!normalized) return 'Статус уточняется'
  return normalized.replaceAll('_', ' ')
}

function minutesUntilStart(value?: string | null) {
  if (!value) return null
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) return null
  return Math.round((timestamp - Date.now()) / 60000)
}

function groupSlotsByDay(slots: SlotInfo[], timeZone: string) {
  const groups = new Map<string, SlotInfo[]>()
  slots.forEach((slot) => {
    const date = new Date(slot.start_utc)
    if (Number.isNaN(date.getTime())) return
    const key = dateKeyInTimeZone(date, timeZone)
    groups.set(key, [...(groups.get(key) || []), slot])
  })
  return Array.from(groups.entries()).map(([key, items]) => ({
    key,
    label: formatDate(items[0]?.start_utc, timeZone),
    items,
  }))
}

function flattenValidationErrors(value: unknown): string | null {
  if (!Array.isArray(value)) return null
  const messages = value
    .map((item) => {
      if (!item || typeof item !== 'object') return null
      const typedItem = item as { msg?: unknown; loc?: unknown }
      const message = typeof typedItem.msg === 'string' ? typedItem.msg.trim() : ''
      const location = Array.isArray(typedItem.loc)
        ? typedItem.loc.filter((part) => typeof part === 'string' || typeof part === 'number').join('.')
        : ''
      if (!message) return null
      return location ? `${location}: ${message}` : message
    })
    .filter((item): item is string => Boolean(item))
  return messages.length ? messages.join('\n') : null
}

function extractApiError(payload: unknown, fallback: string): ApiErrorInfo {
  if (typeof payload === 'string' && payload.trim()) {
    return { message: payload.trim() }
  }
  if (!payload || typeof payload !== 'object') {
    return { message: fallback }
  }
  const typedPayload = payload as {
    code?: unknown
    message?: unknown
    detail?: unknown
    error?: unknown
  }
  const detail = typedPayload.detail
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const typedDetail = detail as { code?: unknown; message?: unknown }
    const message = typeof typedDetail.message === 'string' && typedDetail.message.trim()
      ? typedDetail.message.trim()
      : typeof typedPayload.message === 'string' && typedPayload.message.trim()
        ? typedPayload.message.trim()
        : fallback
    return {
      code: typeof typedDetail.code === 'string' ? typedDetail.code : typeof typedPayload.code === 'string' ? typedPayload.code : null,
      message,
    }
  }
  if (Array.isArray(detail)) {
    return {
      code: typeof typedPayload.code === 'string' ? typedPayload.code : null,
      message: flattenValidationErrors(detail) || fallback,
    }
  }
  if (typeof detail === 'string' && detail.trim()) {
    return {
      code: typeof typedPayload.code === 'string' ? typedPayload.code : null,
      message: detail.trim(),
    }
  }
  if (typeof typedPayload.message === 'string' && typedPayload.message.trim()) {
    return {
      code: typeof typedPayload.code === 'string' ? typedPayload.code : null,
      message: typedPayload.message.trim(),
    }
  }
  return { message: fallback }
}

function launchErrorBinding(message: string, code?: string | null): LaunchResponse['binding'] {
  return {
    status: code === 'outside_max_client' ? 'outside_max_client' : 'launch_error',
    code: code || null,
    message,
    requires_contact: false,
    start_param: null,
    chat_url: null,
  }
}

function resolveBookingPanel(context: BookingContext | null): MiniAppPanel {
  if (!context?.city_id) return 'booking-city'
  if (!context.recruiter_id) return 'booking-recruiter'
  return 'booking-slots'
}

function detectClientTimeZone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Moscow'
  } catch {
    return 'Europe/Moscow'
  }
}

function sanitizeInlineMarkup(value?: string | null) {
  const source = String(value || '')
  if (!source.trim()) return ''
  return source
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/&lt;(\/?(?:b|strong|i|em))&gt;/gi, '<$1>')
    .replace(/&lt;br\s*\/?&gt;/gi, '<br />')
}

export function MaxMiniAppPage() {
  const [initData, setInitData] = useState('')
  const [accessSessionId, setAccessSessionId] = useState<string | null>(null)
  const [binding, setBinding] = useState<LaunchResponse['binding'] | null>(null)
  const [capabilities, setCapabilities] = useState<BridgeCapabilities>(DEFAULT_CAPABILITIES)
  const [journey, setJourney] = useState<JourneyResponse | null>(null)
  const [test1, setTest1] = useState<Test1Response | null>(null)
  const [test2, setTest2] = useState<Test2Response | null>(null)
  const [introDay, setIntroDay] = useState<IntroDayResponse | null>(null)
  const [cities, setCities] = useState<CityInfo[]>([])
  const [recruiters, setRecruiters] = useState<RecruiterInfo[]>([])
  const [slots, setSlots] = useState<SlotInfo[]>([])
  const [bookingContext, setBookingContext] = useState<BookingContext | null>(null)
  const [selectedDay, setSelectedDay] = useState('')
  const [draftValue, setDraftValue] = useState('')
  const [phoneInput, setPhoneInput] = useState('')
  const [manualAvailabilityNote, setManualAvailabilityNote] = useState('')
  const [manualWindowStart, setManualWindowStart] = useState('')
  const [manualWindowEnd, setManualWindowEnd] = useState('')
  const [manualAvailabilityNotice, setManualAvailabilityNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rescheduleBookingId, setRescheduleBookingId] = useState<number | null>(null)
  const [activePanel, setActivePanel] = useState<MiniAppPanel>('home')
  const [panelHistory, setPanelHistory] = useState<MiniAppPanel[]>([])
  const [bookingNotice, setBookingNotice] = useState<BookingNotice | null>(null)

  const currentTest2Question = useMemo(() => {
    if (!test2 || test2.is_completed || test2.current_question_index == null) return null
    return test2.questions.find((question) => question.question_index === test2.current_question_index) || null
  }, [test2])

  const currentQuestion = useMemo(() => {
    if (!test1 || test1.is_completed) return null
    return test1.questions.find((question) => !(question.id in test1.draft_answers)) || null
  }, [test1])

  const bookingTimeZone = useMemo(
    () => cities.find((city) => city.city_id === bookingContext?.city_id)?.tz || 'Europe/Moscow',
    [bookingContext?.city_id, cities],
  )

  const dayGroups = useMemo(() => groupSlotsByDay(slots, bookingTimeZone), [bookingTimeZone, slots])
  const visibleSlots = useMemo(() => {
    if (!selectedDay) return slots
    return dayGroups.find((group) => group.key === selectedDay)?.items || []
  }, [dayGroups, selectedDay, slots])
  const materialCards = useMemo(() => collectMaterialCards(journey), [journey])

  const canChooseBooking = Boolean(
    test1?.is_completed
    && (test1.required_next_action === 'select_interview_slot' || journey?.active_booking),
  )

  const showBackButton = Boolean(accessSessionId && panelHistory.length > 0 && activePanel !== 'home')
  const shouldWarnOnClose = Boolean(accessSessionId && activePanel === 'test1' && !test1?.is_completed)
  const hasBookingFlow = Boolean(canChooseBooking && accessSessionId)

  function pushPanel(nextPanel: MiniAppPanel) {
    if (nextPanel === activePanel) return
    setPanelHistory((prev) => [...prev, activePanel])
    setActivePanel(nextPanel)
  }

  function replacePanel(nextPanel: MiniAppPanel) {
    setActivePanel(nextPanel)
  }

  function goBack() {
    setPanelHistory((prev) => {
      if (!prev.length) {
        setActivePanel('home')
        return prev
      }
      const nextHistory = [...prev]
      const previousPanel = nextHistory.pop() || 'home'
      setActivePanel(previousPanel)
      return nextHistory
    })
  }

  async function loadSessionState(sessionId: string, currentInitData = initData) {
    const [journeyResponse, test1Response] = await Promise.all([
      maxApi<JourneyResponse>('/candidate-access/journey', { initData: currentInitData, sessionId }),
      maxApi<Test1Response>('/candidate-access/test1', { initData: currentInitData, sessionId }),
    ])
    setJourney(journeyResponse)
    setTest1(test1Response)
    return { journeyResponse, test1Response }
  }

  async function loadBookingState(
    sessionId: string,
    nextState?: { journeyResponse: JourneyResponse; test1Response: Test1Response },
    currentInitData = initData,
  ) {
    const nextContext = await maxApi<BookingContext>('/candidate-access/booking-context', {
      initData: currentInitData,
      sessionId,
    })
    setBookingContext(nextContext)

    const bookingAllowed = Boolean(
      nextState
        ? (nextState.test1Response.is_completed
          && (nextState.test1Response.required_next_action === 'select_interview_slot' || nextState.journeyResponse.active_booking))
        : canChooseBooking,
    )
    if (!bookingAllowed) {
      setCities([])
      setRecruiters([])
      setSlots([])
      setSelectedDay('')
      return nextContext
    }

    const cityList = await maxApi<CityInfo[]>('/candidate-access/cities', {
      initData: currentInitData,
      sessionId,
    })
    setCities(cityList)

    if (nextContext.city_id) {
      const nextRecruiters = await maxApi<RecruiterInfo[]>(
        `/candidate-access/recruiters?city_id=${nextContext.city_id}`,
        { initData: currentInitData, sessionId },
      )
      setRecruiters(nextRecruiters)
      if (nextContext.recruiter_id) {
        const query = new URLSearchParams({
          city_id: String(nextContext.city_id),
          recruiter_id: String(nextContext.recruiter_id),
        })
        const nextSlots = await maxApi<SlotInfo[]>(`/candidate-access/slots?${query.toString()}`, {
          initData: currentInitData,
          sessionId,
        })
        const nextDayGroups = groupSlotsByDay(nextSlots, bookingTimeZone)
        setSlots(nextSlots)
        setSelectedDay((previous) => {
          if (previous && nextDayGroups.some((group) => group.key === previous)) return previous
          return nextDayGroups[0]?.key || ''
        })
      } else {
        setSlots([])
        setSelectedDay('')
      }
    } else {
      setRecruiters([])
      setSlots([])
      setSelectedDay('')
    }

    return nextContext
  }

  async function refreshCandidateState(
    sessionId: string,
    currentInitData = initData,
  ) {
    const nextState = await loadSessionState(sessionId, currentInitData)
    const nextContext = await loadBookingState(sessionId, nextState, currentInitData)
    return { ...nextState, bookingContext: nextContext }
  }

  async function loadTest2State(sessionId: string, currentInitData = initData) {
    try {
      const response = await maxApi<Test2Response>('/candidate-access/test2', {
        initData: currentInitData,
        sessionId,
      })
      setTest2(response)
      return response
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Не удалось загрузить Тест 2'
      setTest2(null)
      throw new Error(message)
    }
  }

  async function loadIntroDayState(sessionId: string, currentInitData = initData) {
    try {
      const response = await maxApi<IntroDayResponse>('/candidate-access/intro-day', {
        initData: currentInitData,
        sessionId,
      })
      setIntroDay(response)
      return response
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Не удалось загрузить детали ознакомительного дня'
      setIntroDay(null)
      throw new Error(message)
    }
  }

  async function bootstrap(nextStartParam?: string | null) {
    const resolvedInitData = detectInitData()
    const resolvedStartParam = nextStartParam ?? detectStartParam()
    setInitData(resolvedInitData)
    setBusy(true)
    setError(null)
    setBookingNotice(null)
    setManualAvailabilityNotice(null)
    if (!resolvedInitData) {
      setBinding(launchErrorBinding('Откройте кабинет кандидата из клиента MAX, чтобы передать защищённый launch-контекст.', 'outside_max_client'))
      setCapabilities(DEFAULT_CAPABILITIES)
      setAccessSessionId(null)
      setJourney(null)
      setTest1(null)
      setTest2(null)
      setIntroDay(null)
      setBookingContext(null)
      setCities([])
      setRecruiters([])
      setSlots([])
      setSelectedDay('')
      setPanelHistory([])
      setActivePanel('home')
      setError(null)
      setBusy(false)
      return
    }
    try {
      const launch = await fetch('/api/max/launch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          init_data: resolvedInitData,
          start_param: resolvedStartParam || undefined,
        }),
      })
      if (!launch.ok) {
        const payload = await launch.json().catch(() => ({}))
        const errorInfo = extractApiError(payload, 'Не удалось запустить mini app')
        const error = new Error(errorInfo.message)
        ;(error as Error & { code?: string | null }).code = errorInfo.code
        throw error
      }
      const payload = (await launch.json()) as LaunchResponse
      setBinding(payload.binding)
      setCapabilities(payload.capabilities || DEFAULT_CAPABILITIES)
      if (payload.session?.session_id) {
        setAccessSessionId(payload.session.session_id)
        const nextState = await refreshCandidateState(payload.session.session_id, resolvedInitData)
        setPanelHistory([])
        const nextPrimaryKind = String(nextState.journeyResponse.primary_action?.kind || '').trim().toLowerCase()
        if (nextPrimaryKind === 'test2') {
          await loadTest2State(payload.session.session_id, resolvedInitData)
          setIntroDay(null)
          setActivePanel('test2')
        } else if (nextPrimaryKind === 'intro_day') {
          await loadIntroDayState(payload.session.session_id, resolvedInitData)
          setTest2(null)
          setActivePanel('intro-day')
        } else if (!nextState.test1Response.is_completed) {
          setTest2(null)
          setIntroDay(null)
          setActivePanel('test1')
        } else if (nextState.journeyResponse.active_booking) {
          setTest2(null)
          setIntroDay(null)
          setActivePanel('booked')
        } else {
          setTest2(null)
          setIntroDay(null)
          setActivePanel('home')
        }
      } else {
        setAccessSessionId(null)
        setJourney(null)
        setTest1(null)
        setTest2(null)
        setIntroDay(null)
        setBookingContext(null)
        setCities([])
        setRecruiters([])
        setSlots([])
        setSelectedDay('')
        setPanelHistory([])
        setActivePanel('home')
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Не удалось запустить mini app'
      const code = err instanceof Error ? (err as Error & { code?: string | null }).code : null
      setBinding(launchErrorBinding(message, code))
      setCapabilities(DEFAULT_CAPABILITIES)
      setAccessSessionId(null)
      setJourney(null)
      setTest1(null)
      setTest2(null)
      setIntroDay(null)
      setBookingContext(null)
      setCities([])
      setRecruiters([])
      setSlots([])
      setSelectedDay('')
      setError(null)
    } finally {
      setBusy(false)
    }
  }

  async function saveBookingContext(sessionId: string, cityId: number, recruiterId?: number | null) {
    setBusy(true)
    setError(null)
    try {
      await maxApi('/candidate-access/booking-context', {
        method: 'POST',
        initData,
        sessionId,
        body: { city_id: cityId, recruiter_id: recruiterId || null },
      })
      const nextState = await refreshCandidateState(sessionId)
      replacePanel(resolveBookingPanel(nextState.bookingContext))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось обновить выбор')
    } finally {
      setBusy(false)
    }
  }

  async function saveAnswer(questionId: string, value: string) {
    if (!accessSessionId || !value.trim()) return
    setBusy(true)
    setError(null)
    try {
      const response = await maxApi<Test1Response>('/candidate-access/test1/answers', {
        method: 'POST',
        initData,
        sessionId: accessSessionId,
        body: { answers: { [questionId]: value.trim() } },
      })
      setTest1(response)
      setDraftValue('')
      const nextState = await refreshCandidateState(accessSessionId)
      if (response.is_completed && nextState.journeyResponse.active_booking) {
        replacePanel('booked')
      } else if (response.is_completed && response.required_next_action === 'select_interview_slot') {
        replacePanel(resolveBookingPanel(nextState.bookingContext))
      } else {
        replacePanel('test1')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить ответ')
    } finally {
      setBusy(false)
    }
  }

  async function completeTest1() {
    if (!accessSessionId) return
    setBusy(true)
    setError(null)
    try {
      const response = await maxApi<Test1Response>('/candidate-access/test1/complete', {
        method: 'POST',
        initData,
        sessionId: accessSessionId,
      })
      setTest1(response)
      const nextState = await refreshCandidateState(accessSessionId)
      if (nextState.journeyResponse.active_booking) {
        replacePanel('booked')
      } else if (response.required_next_action === 'select_interview_slot') {
        replacePanel(resolveBookingPanel(nextState.bookingContext))
      } else {
        replacePanel('home')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось завершить анкету')
    } finally {
      setBusy(false)
    }
  }

  async function submitTest2Answer(questionIndex: number, answerIndex: number) {
    if (!accessSessionId) return
    setBusy(true)
    setError(null)
    try {
      const response = await maxApi<Test2Response>('/candidate-access/test2/answers', {
        method: 'POST',
        initData,
        sessionId: accessSessionId,
        body: { question_index: questionIndex, answer_index: answerIndex },
      })
      setTest2(response)
      const nextState = await refreshCandidateState(accessSessionId)
      if (response.is_completed && nextState.journeyResponse.primary_action?.kind === 'intro_day') {
        try {
          await loadIntroDayState(accessSessionId)
        } catch {
          // Intro day can remain pending on the home screen until details are available.
        }
      }
      replacePanel(response.is_completed ? 'home' : 'test2')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить ответ Теста 2')
    } finally {
      setBusy(false)
    }
  }

  async function confirmIntroDay() {
    if (!accessSessionId) return
    setBusy(true)
    setError(null)
    try {
      const response = await maxApi<IntroDayResponse>('/candidate-access/intro-day/confirm', {
        method: 'POST',
        initData,
        sessionId: accessSessionId,
      })
      setIntroDay(response)
      await refreshCandidateState(accessSessionId)
      setBookingNotice({
        title: 'Участие подтверждено',
        body: 'Ознакомительный день подтверждён. Если детали встречи изменятся, мы обновим их здесь и в чате MAX.',
        tone: 'success',
      })
      replacePanel('intro-day')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось подтвердить ознакомительный день')
    } finally {
      setBusy(false)
    }
  }

  async function createOrRescheduleBooking(slotId: number) {
    if (!accessSessionId) return
    setBusy(true)
    setError(null)
    try {
      if (rescheduleBookingId) {
        await maxApi<Booking>(`/candidate-access/bookings/${rescheduleBookingId}/reschedule`, {
          method: 'POST',
          initData,
          sessionId: accessSessionId,
          body: { new_slot_id: slotId },
        })
      } else {
        await maxApi<Booking>('/candidate-access/bookings', {
          method: 'POST',
          initData,
          sessionId: accessSessionId,
          body: { slot_id: slotId },
        })
      }
      setRescheduleBookingId(null)
      setBookingNotice({
        title: 'Слот отправлен на согласование',
        body: 'Мы просматриваем ваше резюме и результаты Test 1. Совсем скоро сообщим решение. Если слот согласуют, детали встречи появятся здесь и в чате MAX.',
        tone: 'progress',
      })
      await refreshCandidateState(accessSessionId)
      replacePanel('booked')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось обновить запись')
    } finally {
      setBusy(false)
    }
  }

  async function confirmBooking() {
    if (!accessSessionId || !journey?.active_booking) return
    setBusy(true)
    setError(null)
    try {
      await maxApi(`/candidate-access/bookings/${journey.active_booking.booking_id}/confirm`, {
        method: 'POST',
        initData,
        sessionId: accessSessionId,
      })
      setBookingNotice({
        title: 'Встреча подтверждена',
        body: `Мы закрепили время ${formatDate(journey.active_booking.start_utc, bookingTimeZone)}. Проверьте памятку и детали встречи на этом экране.`,
        tone: 'success',
      })
      await refreshCandidateState(accessSessionId)
      replacePanel('booked')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось подтвердить встречу')
    } finally {
      setBusy(false)
    }
  }

  async function cancelBooking() {
    if (!accessSessionId || !journey?.active_booking) return
    setBusy(true)
    setError(null)
    try {
      await maxApi(`/candidate-access/bookings/${journey.active_booking.booking_id}/cancel`, {
        method: 'POST',
        initData,
        sessionId: accessSessionId,
        body: { reason: 'candidate_requested' },
      })
      setBookingNotice({
        title: 'Запись отменена',
        body: 'Выберите другое время, когда будете готовы вернуться к записи.',
        tone: 'progress',
      })
      const nextState = await refreshCandidateState(accessSessionId)
      replacePanel(nextState.test1Response.required_next_action === 'select_interview_slot'
        ? resolveBookingPanel(nextState.bookingContext)
        : 'home')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось отменить запись')
    } finally {
      setBusy(false)
    }
  }

  async function submitManualAvailability() {
    if (!accessSessionId) return
    if (!manualAvailabilityNote.trim() && !manualWindowStart && !manualWindowEnd) {
      setError('Опишите удобное время или укажите хотя бы один интервал.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const response = await maxApi<ManualAvailabilityResponse>('/candidate-access/manual-availability', {
        method: 'POST',
        initData,
        sessionId: accessSessionId,
        body: {
          note: manualAvailabilityNote.trim() || null,
          window_start: manualWindowStart ? new Date(manualWindowStart).toISOString() : null,
          window_end: manualWindowEnd ? new Date(manualWindowEnd).toISOString() : null,
          timezone_label: detectClientTimeZone(),
        },
      })
      await refreshCandidateState(accessSessionId)
      setManualAvailabilityNotice(response.message)
      setManualAvailabilityNote('')
      setManualWindowStart('')
      setManualWindowEnd('')
      replacePanel('home')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось отправить пожелания по времени')
    } finally {
      setBusy(false)
    }
  }

  function openMeetingLink(url?: string | null) {
    const meetingUrl = String(url || '').trim()
    if (!meetingUrl) {
      setError('Ссылка на подключение пока недоступна. Попробуйте чуть позже.')
      return
    }
    const opened = openExternalLink(meetingUrl)
    if (!opened) {
      setError('Не удалось открыть ссылку на встречу автоматически. Попробуйте перейти по ней позже.')
    }
  }

  async function bindByPhone(rawPhone?: string | null, contact?: Record<string, unknown> | null) {
    const phone = (rawPhone || phoneInput).trim()
    if (!phone) {
      setError('Введите номер телефона, чтобы найти анкету.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const response = await maxApi<ContactBindResponse>('/candidate-access/contact', {
        method: 'POST',
        initData,
        body: {
          phone,
          contact: contact || undefined,
        },
      })
      setBinding((previous) => ({
        status: response.status,
        message: response.message,
        requires_contact: response.status !== 'bound',
        start_param: response.start_param,
        chat_url: previous?.chat_url ?? null,
      }))
      if (response.start_param) {
        await bootstrap(response.start_param)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось найти анкету')
    } finally {
      setBusy(false)
    }
  }

  function handleHomePrimaryAction() {
    if (!journey?.primary_action) {
      pushPanel('help')
      return
    }
    if (!accessSessionId) {
      pushPanel('help')
      return
    }
    if (journey.primary_action.kind === 'booking') {
      if (journey.active_booking) {
        pushPanel('booked')
        return
      }
      if (hasBookingFlow) {
        pushPanel(resolveBookingPanel(bookingContext))
      }
      return
    }
    if (journey.primary_action.kind === 'test2') {
      setBusy(true)
      setError(null)
      void loadTest2State(accessSessionId)
        .then(() => {
          pushPanel('test2')
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : 'Не удалось открыть Тест 2')
        })
        .finally(() => {
          setBusy(false)
        })
      return
    }
    if (journey.primary_action.kind === 'intro_day') {
      setBusy(true)
      setError(null)
      void loadIntroDayState(accessSessionId)
        .then(() => {
          pushPanel('intro-day')
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : 'Не удалось открыть детали ознакомительного дня')
        })
        .finally(() => {
          setBusy(false)
        })
      return
    }
    if (journey.primary_action.kind === 'help') {
      pushPanel('help')
      return
    }
    if (journey.primary_action.kind === 'test1') {
      pushPanel('test1')
      return
    }
    pushPanel('help')
  }

  useEffect(() => {
    let cancelled = false
    void (async () => {
      await prepareMaxBridge()
      if (!cancelled) {
        await bootstrap()
      }
    })()
    return () => {
      cancelled = true
    }
    // bootstrap intentionally runs once per MAX launch; subsequent state refreshes are explicit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!showBackButton) return undefined
    return bindMaxBackButton(() => {
      goBack()
    })
  }, [showBackButton, activePanel, panelHistory.length])

  useEffect(() => {
    setClosingConfirmation(shouldWarnOnClose)
    return () => {
      setClosingConfirmation(false)
    }
  }, [shouldWarnOnClose])

  const heroAction = journey?.primary_action?.label || 'Проверить следующий шаг'

  function renderLoadingState() {
    if (!busy || binding || accessSessionId) return null
    return (
      <MiniAppStateCard
        eyebrow="Загрузка"
        title="Подготавливаем ваш шаг"
        body="Проверяем launch-контекст MAX и загружаем текущее состояние кандидата."
        tone="progress"
        badge="Безопасный запуск"
        testId="miniapp-loading"
      />
    )
  }

  function renderPrebind() {
    if (!binding || accessSessionId) return null

    if (binding.status === 'manual_review_required') {
      return (
        <MiniAppStateCard
          eyebrow="Проверка доступа"
          title="Нужна ручная проверка"
          body={binding.message}
          tone="warn"
          badge="Безопасный режим"
        testId="miniapp-manual-review"
        actions={(
          <>
            <button
              type="button"
              className="max-btn max-btn--primary"
              disabled={busy}
              onClick={() => replacePanel('help')}
            >
                Что делать дальше
              </button>
            </>
          )}
        >
          <p className="max-muted">
            Мы не связываем анкету автоматически, если есть неоднозначность. Дождитесь следующего сообщения RecruitSmart или обратитесь к рекрутеру.
          </p>
        </MiniAppStateCard>
      )
    }

    if (binding.status === 'outside_max_client') {
      return (
        <MiniAppStateCard
          eyebrow="Доступ"
          title="Откройте кабинет внутри MAX"
          body={binding.message}
          tone="neutral"
          badge="Только MAX"
          testId="miniapp-outside-max"
        >
          <p className="max-muted">
            Этот экран работает только внутри MAX mini app. Отдельного браузерного входа для этого шага нет.
          </p>
        </MiniAppStateCard>
      )
    }

    if (binding.status === 'launch_error') {
      const title = binding.code === 'invalid_init_data'
        ? 'Нужен корректный запуск из MAX'
        : binding.code === 'max_adapter_disabled'
          ? 'MAX pilot сейчас недоступен'
          : 'Не удалось открыть mini app'
      return (
        <MiniAppStateCard
          eyebrow="Запуск"
          title={title}
          body={binding.message}
          tone={binding.code === 'max_adapter_disabled' ? 'warn' : 'neutral'}
          badge="Bounded pilot"
          testId="miniapp-launch-error"
          role="alert"
        actions={(
          <>
            <button type="button" className="max-btn max-btn--primary" disabled={busy} onClick={() => void bootstrap()}>
              Попробовать снова
            </button>
          </>
        )}
      />
      )
    }

    return (
      <MiniAppStateCard
        eyebrow="Восстановление доступа"
        title="Восстановим доступ к анкете"
        body={binding.message}
        tone="progress"
        badge="По номеру телефона"
        testId="miniapp-prebind"
        actions={(
          <>
            <button type="button" className="max-btn max-btn--primary" disabled={busy} onClick={() => void bindByPhone()}>
              Найти анкету
            </button>
            <button
              type="button"
              className="max-btn max-btn--ghost"
              disabled={busy || !capabilities.request_contact}
              onClick={() => {
                void requestMaxContact().then(({ phone, contact }) => {
                  if (phone) {
                    setPhoneInput(phone)
                    void bindByPhone(phone, contact)
                  } else {
                    setError('MAX не передал номер автоматически. Введите его вручную.')
                  }
                })
              }}
            >
              Взять номер из MAX
            </button>
          </>
        )}
      >
        <p className="max-muted">Используем номер только для поиска текущего шага и безопасного восстановления этой сессии.</p>
        <label className="max-field">
          <span>Телефон</span>
          <input
            value={phoneInput}
            onChange={(event) => setPhoneInput(event.target.value)}
            placeholder="+7 999 123-45-67"
          />
        </label>
      </MiniAppStateCard>
    )
  }

  function renderHome() {
    if (!accessSessionId || !journey || !test1 || activePanel !== 'home') return null
    const statusTone = normalizeTone(journey.status_card?.tone)
    return (
      <>
        {manualAvailabilityNotice ? (
          <div className="max-banner max-banner--success" data-testid="miniapp-manual-availability-success" role="status">
            <p className="max-banner__eyebrow">Пожелания отправлены</p>
            <p className="max-banner__body">{manualAvailabilityNotice}</p>
          </div>
        ) : null}
        {journey.status_card ? (
          <section className={`max-card max-status max-status--${statusTone}`} role="status">
            <div className="max-state-card__head">
              <div className="max-state-card__copy">
                <p className="max-card__eyebrow">{toneEyebrow(journey.status_card.tone)}</p>
                <h2>{journey.status_card.title}</h2>
              </div>
              <span className={`max-pill max-pill--${statusTone}`}>{toneLabel(journey.status_card.tone)}</span>
            </div>
            <p className="max-status__copy">{journey.status_card.body}</p>
          </section>
        ) : null}

        <section className="max-card max-next-step" data-testid="miniapp-home">
          <div className="max-section-head">
            <div>
              <p className="max-card__eyebrow">Следующий шаг</p>
              <h2>{heroAction}</h2>
            </div>
            <span className={`max-pill max-pill--${normalizeTone(journey.status_card?.tone)}`}>{actionBadge(journey.primary_action)}</span>
          </div>
          <div className="max-next-step__body">
            <p>{nextStepDescription({ journey, test1 })}</p>
          </div>
          <div className="max-actions">
            <button
              type="button"
              className="max-btn max-btn--primary"
              disabled={busy}
              onClick={handleHomePrimaryAction}
            >
              {heroAction}
            </button>
          </div>
        </section>

        <section className="max-card">
          <div className="max-section-head">
            <div>
              <p className="max-card__eyebrow">Статус шага</p>
              <h2>Как движется путь кандидата</h2>
            </div>
            <span className="max-pill max-pill--neutral">Обновляется с сервера</span>
          </div>
          <div className="max-timeline">
            {journey.timeline.map((item) => (
              <article key={item.key} className={`max-step max-step--${normalizeTimelineState(item.state)}`}>
                <div className="max-step__meta">
                  <strong>{item.label}</strong>
                  <span className={`max-step__state max-step__state--${normalizeTimelineState(item.state)}`}>{item.state_label}</span>
                </div>
                {item.detail ? <p>{item.detail}</p> : null}
              </article>
            ))}
          </div>
        </section>

        {journey.active_booking ? (
          <section className="max-card max-stack">
            <div className="max-section-head">
              <div>
                <p className="max-card__eyebrow">Встреча в расписании</p>
                <h2>Встреча уже назначена</h2>
              </div>
              <span className="max-pill max-pill--success">{formatBookingStatus(journey.active_booking.status)}</span>
            </div>
            <div className="max-booking-card">
              <strong className="ui-tabular-nums">{formatDate(journey.active_booking.start_utc, bookingTimeZone)}</strong>
              <p>Рекрутёр: {journey.active_booking.recruiter_name}</p>
            </div>
            <div className="max-actions">
              <button type="button" className="max-btn max-btn--primary" disabled={busy} onClick={() => pushPanel('booked')}>
                Проверить детали встречи
              </button>
              <button type="button" className="max-btn max-btn--ghost" disabled={busy} onClick={() => pushPanel('help')}>
                Что взять с собой
              </button>
            </div>
          </section>
        ) : null}

        {materialCards.length ? (
          <section className="max-grid max-grid--cards">
            {materialCards.map((item) => (
              <article
                key={`${item.key}-${item.card.title}`}
                className={`max-card max-card--compact max-inline-card max-inline-card--${item.tone}`}
              >
                <p className="max-card__eyebrow">{item.eyebrow}</p>
                <h3>{item.card.title}</h3>
                <p>{item.card.body}</p>
              </article>
            ))}
          </section>
        ) : null}
      </>
    )
  }

  function renderTest1() {
    if (!accessSessionId || !test1 || activePanel !== 'test1' || test1.is_completed) return null
    const allAnswersCaptured = Object.keys(test1.draft_answers).length >= test1.questions.length
    if (!currentQuestion && allAnswersCaptured) {
      return (
        <section className="max-card max-stack" data-testid="miniapp-test1-review">
          <div className="max-section-head">
            <div>
              <p className="max-card__eyebrow">Короткая анкета</p>
              <h2>Проверьте анкету и завершите Test 1</h2>
            </div>
            <span className="max-pill">Готово к отправке</span>
          </div>
          <div className="max-banner max-banner--progress" role="status">
            <p className="max-banner__eyebrow">Последний шаг</p>
            <p className="max-banner__body">
              Все ответы сохранены. Отправьте анкету, и мы сразу откроем следующий шаг без повторного показа первого вопроса.
            </p>
          </div>
          <button type="button" className="max-btn max-btn--primary" disabled={busy} onClick={() => void completeTest1()}>
            Завершить анкету
          </button>
        </section>
      )
    }
    if (!currentQuestion) return null
    return (
      <section className="max-card max-stack" data-testid="miniapp-test1">
        <div className="max-section-head">
          <div>
            <p className="max-card__eyebrow">Короткая анкета</p>
            <h2>Test 1</h2>
          </div>
          <span className="max-pill">Шаг {currentQuestion.question_index + 1}</span>
        </div>
        <article className="max-question-card">
          <p className="max-card__eyebrow">Текущий вопрос</p>
          <h3 dangerouslySetInnerHTML={{ __html: sanitizeInlineMarkup(currentQuestion.prompt) }} />
          {currentQuestion.helper ? <p dangerouslySetInnerHTML={{ __html: sanitizeInlineMarkup(currentQuestion.helper) }} /> : null}
        </article>
        {currentQuestion.options.length ? (
          <div className="max-options">
            {currentQuestion.options.map((option) => (
              <button
                key={option.value}
                type="button"
                className="max-option"
                disabled={busy}
                onClick={() => void saveAnswer(currentQuestion.id, option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        ) : (
          <>
            <label className="max-field">
              <span>Ответ</span>
              <input
                value={draftValue}
                onChange={(event) => setDraftValue(event.target.value)}
                placeholder={currentQuestion.placeholder || 'Введите ответ'}
              />
            </label>
            <div className="max-actions max-actions--sticky">
              <button
                type="button"
                className="max-btn max-btn--primary"
                disabled={busy || !draftValue.trim()}
                onClick={() => void saveAnswer(currentQuestion.id, draftValue)}
              >
                Сохранить ответ
              </button>
            </div>
          </>
        )}
        {allAnswersCaptured ? (
          <button type="button" className="max-btn max-btn--primary" disabled={busy} onClick={() => void completeTest1()}>
            Завершить анкету
          </button>
        ) : null}
      </section>
    )
  }

  function renderTest2() {
    if (!accessSessionId || activePanel !== 'test2' || !test2) return null
    if (test2.is_completed) {
      return (
        <section className="max-card max-stack" data-testid="miniapp-test2">
          <div className="max-section-head">
            <div>
              <p className="max-card__eyebrow">Тест 2</p>
              <h2>Тест завершён</h2>
            </div>
            <span className={`max-pill max-pill--${test2.passed ? 'success' : 'warn'}`}>
              {test2.passed ? 'Пройден' : 'Проверка'}
            </span>
          </div>
          <div className={`max-banner max-banner--${test2.passed ? 'success' : 'progress'}`} role="status">
            <p className="max-banner__eyebrow">Результат</p>
            <p className="max-banner__body">{test2.result_message || 'Тест 2 завершён.'}</p>
          </div>
          <div className="max-grid max-grid--cards">
            <article className="max-card max-card--compact max-inline-card max-inline-card--neutral">
              <p className="max-card__eyebrow">Баллы</p>
              <h3>{test2.score ?? '—'}</h3>
              <p>{test2.correct_answers ?? 0} из {test2.total_questions} верных ответов</p>
            </article>
            <article className="max-card max-card--compact max-inline-card max-inline-card--accent">
              <p className="max-card__eyebrow">Следующий шаг</p>
              <h3>{test2.required_next_action === 'wait_intro_day_invitation' ? 'Ожидайте приглашение' : 'Ожидайте решение'}</h3>
              <p>{test2.rating ? `Рейтинг: ${test2.rating}` : 'Мы обновим статус здесь и в чате MAX.'}</p>
            </article>
          </div>
          <div className="max-actions">
            <button type="button" className="max-btn max-btn--primary" disabled={busy} onClick={() => replacePanel('home')}>
              Вернуться на главный экран
            </button>
          </div>
        </section>
      )
    }

    return (
      <section className="max-card max-stack" data-testid="miniapp-test2">
        <div className="max-section-head">
          <div>
            <p className="max-card__eyebrow">Пост-интервью шаг</p>
            <h2>Тест 2</h2>
          </div>
          <span className="max-pill">{currentTest2Question ? `Вопрос ${currentTest2Question.question_index + 1}` : 'Продолжить'}</span>
        </div>
        {currentTest2Question ? (
          <>
            <p>{currentTest2Question.prompt}</p>
            <div className="max-options">
              {currentTest2Question.options.map((option, optionIndex) => (
                <button
                  key={`${currentTest2Question.id}-${option.value}`}
                  type="button"
                  className="max-option"
                  disabled={busy}
                  onClick={() => void submitTest2Answer(currentTest2Question.question_index, optionIndex)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </>
        ) : (
          <div className="max-banner max-banner--progress" role="status">
            <p className="max-banner__eyebrow">Тест уже открыт</p>
            <p className="max-banner__body">Продолжите тест здесь. Когда статус изменится, экран обновится автоматически.</p>
          </div>
        )}
        <div className="max-actions">
          <button type="button" className="max-btn max-btn--ghost" disabled={busy} onClick={() => replacePanel('help')}>
            Что делать дальше
          </button>
        </div>
      </section>
    )
  }

  function renderBookingEmptyState(
    title: string,
    body: string,
    actionLabel: string,
    action: () => void,
  ) {
    return (
      <article className="max-empty-state">
        <p className="max-card__eyebrow">Запись на собеседование</p>
        <h3>{title}</h3>
        <p>{body}</p>
        <div className="max-actions">
          <button type="button" className="max-btn max-btn--primary" disabled={busy} onClick={action}>
            {actionLabel}
          </button>
        </div>
      </article>
    )
  }

  function renderBookingPanel() {
    if (!accessSessionId || !hasBookingFlow) return null

    if (activePanel === 'booking-city') {
      return (
        <section className="max-card max-stack" data-testid="miniapp-booking-cities">
          <div className="max-section-head">
            <h2>Выберите город</h2>
            <span className="max-pill">{rescheduleBookingId ? 'Перенос' : 'Запись'}</span>
          </div>
          {cities.length ? (
            <div className="max-grid">
              {cities.map((city) => (
                <button
                  key={city.city_id}
                  type="button"
                  className="max-select-card"
                  disabled={busy}
                  onClick={() => void saveBookingContext(accessSessionId, city.city_id)}
                >
                  <strong>{city.city_name}</strong>
                  <span>{city.available_slots} слотов · {city.available_recruiters} рекрутеров</span>
                </button>
              ))}
            </div>
          ) : renderBookingEmptyState(
            'Слоты ещё не опубликованы',
            'Пока нет доступных городов для записи. Оставьте пожелания по времени, и мы свяжемся с вами вручную.',
            'Оставить пожелания',
            () => pushPanel('manual-availability'),
          )}
        </section>
      )
    }

    if (activePanel === 'booking-recruiter') {
      return (
        <section className="max-card max-stack" data-testid="miniapp-booking-recruiters">
          <div className="max-section-head">
            <h2>Выберите рекрутёра</h2>
            <span className="max-pill">{bookingContext?.city_name || 'Город выбран'}</span>
          </div>
          {recruiters.length ? (
            <div className="max-grid">
              {recruiters.map((recruiter, index) => (
                <button
                  key={recruiter.recruiter_id}
                  type="button"
                  className="max-select-card"
                  disabled={busy}
                  onClick={() => void saveBookingContext(accessSessionId, bookingContext?.city_id || 0, recruiter.recruiter_id)}
                >
                  <strong>{recruiter.recruiter_name}</strong>
                  <span>{index === 0 ? 'Рекомендуем' : 'Доступные слоты'}{recruiter.next_slot_utc ? ` · ${formatDate(recruiter.next_slot_utc, bookingTimeZone)}` : ''}</span>
                </button>
              ))}
            </div>
          ) : renderBookingEmptyState(
            'В этом городе пока нет рекрутёров',
            'Выберите другой город или отправьте удобное время, чтобы рекрутер подобрал слот вручную.',
            'Оставить пожелания',
            () => pushPanel('manual-availability'),
          )}
        </section>
      )
    }

    if (activePanel === 'booking-slots') {
      return (
        <section className="max-card max-stack" data-testid="miniapp-booking-slots">
          <div className="max-section-head">
            <h2>Выберите время собеседования</h2>
            <span className="max-pill">{bookingContext?.recruiter_name || 'Рекрутёр выбран'}</span>
          </div>
          {dayGroups.length ? (
            <>
              <div className="max-day-rail ui-segmented ui-segmented--compact">
                {dayGroups.map((group) => (
                  <button
                    key={group.key}
                    type="button"
                    className={`max-day-pill ui-segmented__item${selectedDay === group.key ? ' is-active' : ''}`}
                    onClick={() => setSelectedDay(group.key)}
                  >
                    {group.label}
                  </button>
                ))}
              </div>
              <div className="max-grid">
                {visibleSlots.map((slot) => (
                  <article key={slot.slot_id} className="max-slot-card">
                    <strong className="ui-tabular-nums">{formatDate(slot.start_utc, bookingTimeZone)}</strong>
                    <p>{slot.recruiter_name}</p>
                    <button type="button" className="max-btn max-btn--primary" disabled={busy} onClick={() => void createOrRescheduleBooking(slot.slot_id)}>
                      Выбрать
                    </button>
                  </article>
                ))}
              </div>
              <div className="max-actions">
                <button
                  type="button"
                  className="max-btn max-btn--ghost"
                  disabled={busy}
                  onClick={() => void saveBookingContext(accessSessionId, bookingContext?.city_id || 0, null)}
                >
                  Сменить рекрутёра
                </button>
              </div>
            </>
          ) : renderBookingEmptyState(
            'Свободные интервалы закончились',
            'У выбранного рекрутёра сейчас нет свободных слотов. Оставьте удобное время, и мы вернёмся с предложением вручную.',
            'Оставить пожелания',
            () => pushPanel('manual-availability'),
          )}
        </section>
      )
    }

    return null
  }

  function renderManualAvailabilityPanel() {
    if (!accessSessionId || activePanel !== 'manual-availability') return null
    return (
      <section className="max-card max-stack" data-testid="miniapp-manual-availability">
        <div className="max-section-head">
          <div>
            <p className="max-card__eyebrow">Запись на собеседование</p>
            <h2>Укажите удобное время</h2>
          </div>
          <span className="max-pill max-pill--warn">Без свободных слотов</span>
        </div>
        <p className="max-muted">
          Если подходящего интервала сейчас нет, оставьте пожелания по дате и времени. Рекрутер подберёт следующий слот вручную.
        </p>
        <label className="max-field">
          <span>Комментарий</span>
          <textarea
            value={manualAvailabilityNote}
            onChange={(event) => setManualAvailabilityNote(event.target.value)}
            placeholder="Например: удобно в будни после 18:00 или в субботу утром"
            rows={4}
          />
        </label>
        <div className="max-grid max-grid--cards">
          <label className="max-field">
            <span>С</span>
            <input
              type="datetime-local"
              value={manualWindowStart}
              onChange={(event) => setManualWindowStart(event.target.value)}
            />
          </label>
          <label className="max-field">
            <span>По</span>
            <input
              type="datetime-local"
              value={manualWindowEnd}
              onChange={(event) => setManualWindowEnd(event.target.value)}
            />
          </label>
        </div>
        <div className="max-actions max-actions--sticky">
          <button type="button" className="max-btn max-btn--primary" disabled={busy} onClick={() => void submitManualAvailability()}>
            Отправить пожелания
          </button>
        </div>
      </section>
    )
  }

  function renderBookedPanel() {
    if (!accessSessionId || !journey?.active_booking || activePanel !== 'booked') return null
    const bookingStatus = formatBookingStatus(journey.active_booking.status)
    const rawBookingStatus = String(journey.active_booking.status || '').trim().toLowerCase()
    const canConfirmPending = rawBookingStatus === 'pending' && Boolean(journey.active_booking.candidate_can_confirm_pending)
    const isPendingReview = rawBookingStatus === 'pending' && !canConfirmPending
    const isCandidateConfirmed = rawBookingStatus === 'confirmed_by_candidate'
    const meetingLink = String(journey.active_booking.meet_link || '').trim()
    const minutesUntilInterview = minutesUntilStart(journey.active_booking.start_utc)
    const isUrgentInterviewConfirmation = !isPendingReview
      && !isCandidateConfirmed
      && minutesUntilInterview != null
      && minutesUntilInterview <= 120
    const bookingTone = bookingNotice?.tone || (isPendingReview ? 'progress' : 'success')
    const defaultTitle = isPendingReview
      ? 'Слот на согласовании'
      : (canConfirmPending ? 'Мы предлагаем время собеседования' : (isCandidateConfirmed ? 'Встреча подтверждена' : 'Собеседование назначено'))
    const defaultBody = isPendingReview
      ? 'Мы просматриваем ваше резюме и результаты Test 1. Совсем скоро сообщим решение. Если слот согласуют, детали встречи появятся здесь и в чате MAX.'
      : (canConfirmPending
        ? 'Если это время вам подходит, подтвердите встречу здесь. Сразу после подтверждения пришлём детали и ссылку в чат MAX.'
      : (isCandidateConfirmed
        ? 'Встреча уже подтверждена. Здесь остаются только детали, перенос или отмена записи.'
        : (isUrgentInterviewConfirmation
          ? 'До собеседования осталось меньше двух часов. Подтвердите участие сейчас: после подтверждения сразу покажем ссылку здесь и в чате MAX.'
          : 'Проверьте детали встречи, памятку и при необходимости подтвердите запись.')))
    return (
      <section className="max-card max-stack max-booking-success" data-testid="miniapp-booked">
        <div className="max-section-head">
          <div>
            <p className="max-card__eyebrow">Встреча в расписании</p>
            <h2>{bookingNotice?.title || defaultTitle}</h2>
          </div>
          <span className="max-pill max-pill--success">{bookingStatus}</span>
        </div>
        <div className="max-booking-card">
          <strong className="ui-tabular-nums">{formatDate(journey.active_booking.start_utc, bookingTimeZone)}</strong>
          <p>Рекрутёр: {journey.active_booking.recruiter_name}</p>
        </div>
        <div className={`max-banner max-banner--${bookingTone}`} data-testid="miniapp-booking-success" role="status">
          <p className="max-banner__eyebrow">Что важно сейчас</p>
          <p className="max-banner__body">
            {bookingNotice?.body || defaultBody}
          </p>
        </div>
        {isCandidateConfirmed && meetingLink ? (
          <article className="max-card max-card--compact max-inline-card max-inline-card--success">
            <p className="max-card__eyebrow">Подключение</p>
            <h3>Ссылка на видеовстречу</h3>
            <p>{meetingLink}</p>
            <div className="max-actions">
              <button type="button" className="max-btn max-btn--primary" onClick={() => openMeetingLink(meetingLink)}>
                Открыть конференцию
              </button>
            </div>
          </article>
        ) : null}
        {journey.prep_card ? (
          <article className={`max-card max-card--compact max-inline-card max-inline-card--${normalizeTone(journey.prep_card.tone)}`}>
            <p className="max-card__eyebrow">Подготовка</p>
            <h3>{journey.prep_card.title}</h3>
            <p>{journey.prep_card.body}</p>
          </article>
        ) : null}
        <div className="max-actions">
          {!isPendingReview ? (
            <>
              {!isCandidateConfirmed ? (
                <button type="button" className="max-btn max-btn--primary" disabled={busy} onClick={() => void confirmBooking()}>
                  Подтвердить встречу
                </button>
              ) : null}
              {!canConfirmPending ? (
                <>
                  <button
                    type="button"
                    className="max-btn max-btn--ghost"
                    disabled={busy}
                    onClick={() => {
                      setRescheduleBookingId(journey.active_booking?.booking_id || null)
                      pushPanel(resolveBookingPanel(bookingContext))
                    }}
                  >
                    Выбрать другое время
                  </button>
                  <button type="button" className="max-btn max-btn--ghost" disabled={busy} onClick={() => void cancelBooking()}>
                    Отменить запись
                  </button>
                </>
              ) : null}
            </>
          ) : null}
        </div>
      </section>
    )
  }

  function renderIntroDayPanel() {
    if (!accessSessionId || activePanel !== 'intro-day' || !introDay) return null
    const contactSummary = introDay.intro_contact || [introDay.contact_name, introDay.contact_phone].filter(Boolean).join(', ')
    const confirmed = ['confirmed', 'confirmed_by_candidate'].includes(String(introDay.status || '').trim().toLowerCase())
    const minutesUntilIntroDay = minutesUntilStart(introDay.start_utc)
    const isUrgentIntroConfirmation = !confirmed && minutesUntilIntroDay != null && minutesUntilIntroDay <= 180
    return (
      <section className="max-card max-stack" data-testid="miniapp-intro-day">
        <div className="max-section-head">
          <div>
            <p className="max-card__eyebrow">Следующий очный шаг</p>
            <h2>Ознакомительный день</h2>
          </div>
          <span className={`max-pill max-pill--${confirmed ? 'success' : 'progress'}`}>
            {confirmed ? 'Подтверждено' : 'Нужно подтвердить'}
          </span>
        </div>
        <div className="max-booking-card">
          <strong className="ui-tabular-nums">{formatDate(introDay.start_utc)}</strong>
          <p>{introDay.city_name ? `Город: ${introDay.city_name}` : 'Детали обновляются'}</p>
          {introDay.recruiter_name ? <p>Рекрутёр: {introDay.recruiter_name}</p> : null}
          {introDay.address ? <p>Адрес: {introDay.address}</p> : null}
          {contactSummary ? <p>Контакт: {contactSummary}</p> : null}
        </div>
        <div className={`max-banner max-banner--${confirmed ? 'success' : 'progress'}`} role="status">
          <p className="max-banner__eyebrow">Что важно сейчас</p>
          <p className="max-banner__body">
            {confirmed
              ? 'Участие подтверждено. Если детали встречи изменятся, мы обновим их здесь и в чате MAX.'
              : (isUrgentIntroConfirmation
                ? 'До ознакомительного дня осталось меньше трёх часов. Подтвердите участие сейчас, чтобы не потерять место и сразу увидеть финальные детали.'
                : 'Проверьте адрес, время и подтвердите участие. Если нужен fallback, продолжите в чате MAX.')}
          </p>
        </div>
        <div className="max-actions">
          {!confirmed ? (
            <button type="button" className="max-btn max-btn--primary" disabled={busy} onClick={() => void confirmIntroDay()}>
              Подтвердить участие
            </button>
          ) : (
            <button type="button" className="max-btn max-btn--primary" disabled={busy} onClick={() => replacePanel('home')}>
              Вернуться на главный экран
            </button>
          )}
        </div>
      </section>
    )
  }

  function renderHelpPanel() {
    if (activePanel !== 'help') return null
    return (
      <section className="max-card max-stack" data-testid="miniapp-help">
        <div className="max-section-head">
          <div>
            <p className="max-card__eyebrow">Подсказки по шагу</p>
            <h2>Что делать дальше</h2>
          </div>
          <span className="max-pill max-pill--accent">Материалы</span>
        </div>
        <p className="max-muted">
          Это тот же путь кандидата RecruitSmart: статус, подготовка и поддержка остаются в одном экране, без лишних развилок.
        </p>
        {materialCards.length ? (
          <div className="max-grid max-grid--cards">
            {materialCards.map((item) => (
              <article
                key={`help-${item.key}-${item.card.title}`}
                className={`max-card max-card--compact max-inline-card max-inline-card--${item.tone}`}
              >
                <p className="max-card__eyebrow">{item.eyebrow}</p>
                <h3>{item.card.title}</h3>
                <p>{item.card.body}</p>
              </article>
            ))}
          </div>
        ) : (
          <div className="max-banner" role="status">
            <p className="max-banner__eyebrow">Поддержка</p>
            <p className="max-banner__body">Материалы появятся здесь, когда сервер обновит шаг кандидата.</p>
          </div>
        )}
        <div className="max-actions">
          <button type="button" className="max-btn max-btn--primary" disabled={busy} onClick={() => replacePanel('home')}>
            На главный экран
          </button>
        </div>
      </section>
    )
  }

  return (
    <div className={`max-miniapp max-miniapp--panel-${activePanel}`}>
      <div className="max-miniapp__backdrop" />
      <div className="max-miniapp__content">
        {error ? (
          <div className="max-banner max-banner--error" role="alert">
            <p className="max-banner__eyebrow">Не удалось обновить экран</p>
            <p className="max-banner__body">{error}</p>
          </div>
        ) : null}
        {renderLoadingState()}
        {renderPrebind()}
        {renderHome()}
        {renderTest1()}
        {renderTest2()}
        {renderBookingPanel()}
        {renderManualAvailabilityPanel()}
        {renderBookedPanel()}
        {renderIntroDayPanel()}
        {renderHelpPanel()}

        {busy && (binding || accessSessionId) ? (
          <div className="max-banner max-banner--progress" role="status" aria-live="polite">
            <p className="max-banner__eyebrow">Синхронизация</p>
            <p className="max-banner__body">{busyMessage(activePanel, Boolean(accessSessionId))}</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}

export default MaxMiniAppPage
