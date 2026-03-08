import { Link, useParams } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, useMemo, useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import {
  applyCandidateAction,
  fetchCandidateAiCoach,
  fetchCandidateAiSummary,
  fetchCandidateChat,
  fetchCandidateChatDrafts,
  fetchCandidateCoachDrafts,
  fetchCandidateDetail,
  fetchCandidateHHSummary,
  fetchCandidateInterviewScript,
  fetchCities,
  fetchTemplateByKey,
  markCandidateChatRead,
  refreshCandidateAiCoach,
  refreshCandidateAiSummary,
  refreshCandidateInterviewScript,
  scheduleCandidateInterview,
  scheduleCandidateIntroDay,
  sendCandidateChatMessage,
  submitCandidateInterviewScriptFeedback,
  type CandidateHHSummary,
} from '@/api/services/candidates'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useIsMobile } from '@/app/hooks/useIsMobile'
import { browserTimeZone, buildSlotTimePreview } from '@/app/lib/timezonePreview'

type City = {
  id: number
  name: string
  tz?: string | null
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
  requires_test2_passed?: boolean
  requires_slot?: boolean
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

type TestQuestionAnswer = {
  question_index?: number
  question_text?: string | null
  user_answer?: string | null
  correct_answer?: string | null
  attempts_count?: number | null
  time_spent?: number | null
  is_correct?: boolean | null
  overtime?: boolean | null
}

type TestStats = {
  total_questions?: number
  correct_answers?: number
  overtime_questions?: number
  raw_score?: number
  final_score?: number
  total_time?: number
}

type TestAttempt = {
  id: number
  completed_at?: string | null
  raw_score?: number
  final_score?: number
  source?: string
  details?: {
    stats?: TestStats
    questions?: TestQuestionAnswer[]
  }
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
  details?: {
    stats?: TestStats
    questions?: TestQuestionAnswer[]
  }
  history?: TestAttempt[]
}

type ReportPreviewState = {
  title: string
  url: string
}

type CandidateDetail = {
  id: number
  fio?: string | null
  city?: string | null
  telegram_id?: number | null
  telegram_username?: string | null
  hh_profile_url?: string | null
  hh_resume_id?: string | null
  hh_negotiation_id?: string | null
  hh_vacancy_id?: string | null
  hh_sync_status?: string | null
  hh_sync_error?: string | null
  messenger_platform?: string | null
  max_user_id?: string | null
  phone?: string | null
  is_active?: boolean
  stage?: string | null
  workflow_status_label?: string | null
  workflow_status_color?: string | null
  candidate_status_slug?: string | null
  candidate_status_color?: string | null
  candidate_status_display?: string | null
  telemost_url?: string | null
  telemost_source?: string | null
  responsible_recruiter?: { id?: number | null; name?: string | null } | null
  reschedule_request?: {
    requested_at?: string | null
    requested_start_utc?: string | null
    requested_end_utc?: string | null
    requested_tz?: string | null
    candidate_comment?: string | null
    source?: string | null
  } | null
  candidate_actions?: CandidateAction[]
  allowed_next_statuses?: Array<{ slug: string; label: string; color?: string; is_terminal?: boolean }>
  pipeline_stages?: Array<{ key: string; label: string; state?: string }>
  status_is_terminal?: boolean
  candidate_status_options?: Array<{ slug: string; label: string }>
  legacy_status_enabled?: boolean
  slots?: CandidateSlot[]
  test_sections?: TestSection[]
  test_results?: Record<string, TestSection>
  stats?: { tests_total?: number; average_score?: number | null }
  intro_day_template?: string | null
}

const STATUS_LABELS: Record<string, { label: string; tone: string }> = {
  lead: { label: 'Лид', tone: 'muted' },
  contacted: { label: 'Контакт установлен', tone: 'info' },
  invited: { label: 'Приглашён', tone: 'info' },
  test1_completed: { label: 'Тест 1 пройден', tone: 'success' },
  waiting_slot: { label: 'Ожидает слот', tone: 'warning' },
  stalled_waiting_slot: { label: 'Застрял (ожидание слота)', tone: 'warning' },
  slot_pending: { label: 'На согласовании', tone: 'info' },
  interview_scheduled: { label: 'Собеседование назначено', tone: 'info' },
  interview_confirmed: { label: 'Собеседование подтверждено', tone: 'info' },
  interview_declined: { label: 'Отказ на собеседовании', tone: 'danger' },
  test2_sent: { label: 'Тест 2 отправлен', tone: 'info' },
  test2_completed: { label: 'Тест 2 пройден', tone: 'success' },
  test2_failed: { label: 'Тест 2 не пройден', tone: 'danger' },
  intro_day_scheduled: { label: 'Ознакомительный день назначен', tone: 'info' },
  intro_day_confirmed_preliminary: { label: 'ОД предварительно подтверждён', tone: 'info' },
  intro_day_declined_invitation: { label: 'ОД отклонён (приглашение)', tone: 'danger' },
  intro_day_confirmed_day_of: { label: 'ОД подтверждён (день)', tone: 'success' },
  intro_day_declined_day_of: { label: 'ОД отклонён (день)', tone: 'danger' },
  hired: { label: 'Закреплён на обучение', tone: 'success' },
  not_hired: { label: 'Не закреплён', tone: 'danger' },
}

function getStatusDisplay(slug: string | null | undefined) {
  if (!slug) return { label: 'Нет статуса', tone: 'muted' }
  return STATUS_LABELS[slug] || { label: slug, tone: 'muted' }
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

function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return '—'
  return dt.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatRescheduleRequest(
  request?: CandidateDetail['reschedule_request'],
): { summary: string; comment?: string | null } | null {
  if (!request) return null
  if (request.requested_start_utc && request.requested_end_utc) {
    const start = new Date(request.requested_start_utc)
    const end = new Date(request.requested_end_utc)
    const sameDay = start.toDateString() === end.toDateString()
    const startLabel = new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(start)
    const endLabel = new Intl.DateTimeFormat('ru-RU', {
      ...(sameDay ? {} : { day: '2-digit', month: '2-digit' }),
      hour: '2-digit',
      minute: '2-digit',
    }).format(end)
    return {
      summary: `Окно: ${startLabel}–${endLabel}`,
      comment: request.candidate_comment,
    }
  }
  if (request.requested_start_utc) {
    return {
      summary: `Хочет время: ${formatDateTime(request.requested_start_utc)}`,
      comment: request.candidate_comment,
    }
  }
  if (request.candidate_comment) {
    return {
      summary: `Пожелание: ${request.candidate_comment}`,
      comment: null,
    }
  }
  return null
}

function getHhSyncBadge(status?: string | null) {
  if (status === 'synced') return { label: 'HH синхр.', tone: 'success' }
  if (status === 'failed_sync' || status === 'error') return { label: 'HH ошибка', tone: 'danger' }
  if (status === 'pending_sync' || status === 'pending') return { label: 'HH ожидание', tone: 'warning' }
  if (status === 'conflicted') return { label: 'HH конфликт', tone: 'warning' }
  if (status === 'stale') return { label: 'HH устарело', tone: 'warning' }
  if (status === 'skipped') return { label: 'HH не найден', tone: 'muted' }
  if (!status) return null
  return { label: `HH: ${status}`, tone: 'muted' }
}

function formatSecondsToMinutes(value?: number | null): string {
  if (typeof value !== 'number' || value <= 0) return '—'
  return `${Math.max(1, Math.round(value / 60))} мин`
}

function normalizeTelegramUsername(username?: string | null): string | null {
  if (!username) return null
  const cleaned = username.trim().replace(/^@/, '')
  return cleaned || null
}

function normalizeConferenceUrl(url?: string | null): string | null {
  if (!url) return null
  const raw = url.trim()
  if (!raw) return null
  try {
    const prepared = raw.includes('://') ? raw : `https://${raw}`
    const parsed = new URL(prepared)
    if (!['http:', 'https:'].includes(parsed.protocol)) return null
    return parsed.toString()
  } catch {
    return null
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

type AIRiskItem = {
  key: string
  severity: 'low' | 'medium' | 'high'
  label: string
  explanation: string
}

type AINextActionItem = {
  key: string
  label: string
  rationale: string
  cta?: string | null
}

type AIFit = {
  score?: number | null
  level?: 'high' | 'medium' | 'low' | 'unknown'
  rationale?: string
  criteria_used?: boolean
}

type AIEvidenceItem = {
  key: string
  label: string
  evidence: string
}

type AICriterionChecklistItem = {
  key: string
  status: 'met' | 'not_met' | 'unknown'
  label: string
  evidence: string
}

type AIVacancyFitEvidence = {
  factor: string
  assessment: 'positive' | 'negative' | 'neutral' | 'unknown'
  detail: string
}

type AIVacancyFit = {
  score?: number | null
  level: 'high' | 'medium' | 'low' | 'unknown'
  summary: string
  evidence?: AIVacancyFitEvidence[]
  criteria_source?: string
}

type AISummary = {
  tldr: string
  fit?: AIFit | null
  vacancy_fit?: AIVacancyFit | null
  strengths?: AIEvidenceItem[]
  weaknesses?: AIEvidenceItem[]
  criteria_checklist?: AICriterionChecklistItem[]
  test_insights?: string | null
  risks?: AIRiskItem[]
  next_actions?: AINextActionItem[]
  notes?: string | null
}

type AISummaryResponse = {
  ok: boolean
  cached: boolean
  input_hash: string
  summary: AISummary
}

type AIDraftItem = {
  text: string
  reason: string
}

type AICoach = {
  relevance_score?: number | null
  relevance_level?: 'high' | 'medium' | 'low' | 'unknown'
  rationale?: string
  criteria_used?: boolean
  strengths?: AIEvidenceItem[]
  risks?: AIRiskItem[]
  interview_questions?: string[]
  next_best_action?: string
  message_drafts?: AIDraftItem[]
}

type AICoachResponse = {
  ok: boolean
  cached: boolean
  input_hash: string
  coach: AICoach
}

type InterviewRiskFlag = {
  code: string
  severity: 'low' | 'medium' | 'high'
  reason: string
  question: string
  recommended_phrase: string
}

type InterviewScriptIfAnswer = {
  pattern: string
  hint: string
}

type InterviewScriptBlock = {
  id: string
  title: string
  goal: string
  recruiter_text: string
  candidate_questions: string[]
  if_answers: InterviewScriptIfAnswer[]
}

type InterviewObjection = {
  topic: string
  candidate_says: string
  recruiter_answer: string
}

type InterviewCtaTemplate = {
  type: string
  text: string
}

type InterviewScriptPayload = {
  risk_flags: InterviewRiskFlag[]
  highlights: string[]
  checks: string[]
  objections: InterviewObjection[]
  script_blocks: InterviewScriptBlock[]
  cta_templates: InterviewCtaTemplate[]
}

type InterviewScriptResponse = {
  ok: boolean
  cached: boolean
  input_hash: string
  generated_at?: string | null
  model?: string | null
  prompt_version?: string | null
  script: InterviewScriptPayload
}

type InterviewScriptFeedbackPayload = {
  helped?: boolean | null
  edited: boolean
  quick_reasons: string[]
  final_script?: InterviewScriptPayload | null
  outcome: 'od_assigned' | 'showed_up' | 'no_show' | 'decline' | 'unknown'
  outcome_reason?: string | null
  idempotency_key: string
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

function TestScoreBar({ correct, total, score }: { correct: number; total: number; score?: number | null }) {
  const pct = total > 0 ? Math.round((correct / total) * 100) : 0
  const barColor = pct >= 70 ? 'var(--success, #5BE1A5)' : pct >= 40 ? 'var(--warning, #F6C16B)' : 'var(--danger, #F07373)'
  return (
    <div className="cd-score">
      <div className="cd-score__bar">
        <div className="cd-score__fill" style={{ width: `${pct}%`, background: barColor }} />
      </div>
      <div className="cd-score__text">
        {correct}/{total}
        {typeof score === 'number' && <span className="cd-score__final"> ({score.toFixed(1)})</span>}
      </div>
    </div>
  )
}

function SlotStatusBadge({ status }: { status?: string | null }) {
  const map: Record<string, { label: string; cls: string }> = {
    FREE: { label: 'Свободен', cls: 'cd-slot-badge--free' },
    PENDING: { label: 'Ожидание', cls: 'cd-slot-badge--pending' },
    BOOKED: { label: 'Согласован слот', cls: 'cd-slot-badge--booked' },
    CONFIRMED: { label: 'Подтверждён', cls: 'cd-slot-badge--confirmed' },
    CONFIRMED_BY_CANDIDATE: { label: 'Подтверждён кандидатом', cls: 'cd-slot-badge--confirmed' },
    CANCELED: { label: 'Отменён', cls: 'cd-slot-badge--canceled' },
    COMPLETED: { label: 'Завершён', cls: 'cd-slot-badge--completed' },
  }
  const info = status ? map[status] || { label: status, cls: '' } : { label: '—', cls: '' }
  return <span className={`cd-slot-badge ${info.cls}`}>{info.label}</span>
}

function ModalPortal({ children }: { children: ReactNode }) {
  if (typeof document === 'undefined') return null
  return createPortal(children, document.body)
}

type ReportPreviewModalProps = {
  title: string
  url: string
  onClose: () => void
}

function ReportPreviewModal({ title, url, onClose }: ReportPreviewModalProps) {
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [contentType, setContentType] = useState<string>('')
  const [text, setText] = useState<string>('')
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    setStatus('loading')
    setError(null)
    setText('')
    setContentType('')
    setBlobUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })

    fetch(url, { credentials: 'include', signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) {
          const msg = await res.text().catch(() => '')
          throw new Error(msg || res.statusText)
        }
        const ct = res.headers.get('content-type') || ''
        if (!active) return
        setContentType(ct)
        if (ct.includes('application/pdf')) {
          const blob = await res.blob()
          if (!active) return
          const objectUrl = URL.createObjectURL(blob)
          setBlobUrl(objectUrl)
          setStatus('ready')
          return
        }
        const bodyText = await res.text()
        if (!active) return
        setText(bodyText)
        setStatus('ready')
      })
      .catch((err: unknown) => {
        if (!active) return
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'Не удалось загрузить отчёт')
        setStatus('error')
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [url])

  useEffect(() => {
    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl)
    }
  }, [blobUrl])

  const isPdf = contentType.includes('application/pdf')

  return (
    <ModalPortal>
      <div
        className="modal-overlay"
        onClick={(e) => e.target === e.currentTarget && onClose()}
        role="dialog"
        aria-modal="true"
      >
        <div className="glass glass--elevated modal">
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Отчёт · {title}</h2>
              <p className="modal__subtitle">{isPdf ? 'PDF-документ' : 'Текстовый отчёт'}</p>
            </div>
            <div className="report-preview__actions">
              <a href={url} className="ui-btn ui-btn--ghost" target="_blank" rel="noopener">
                Скачать
              </a>
              <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
            </div>
          </div>

          <div className="modal__body">
            {status === 'loading' && <p className="subtitle">Загрузка отчёта...</p>}
            {status === 'error' && (
              <div className="ui-alert ui-alert--error">{error}</div>
            )}
            {status === 'ready' && (
              <div className="report-preview__frame">
                {isPdf && blobUrl ? (
                  <iframe className="report-preview__pdf" title={title} src={blobUrl} />
                ) : (
                  <pre className="report-preview__text">{text || 'Отчёт пустой.'}</pre>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}

type TestAttemptModalProps = {
  testTitle: string
  attempt: TestAttempt
  onClose: () => void
}

function TestAttemptModal({ testTitle, attempt, onClose }: TestAttemptModalProps) {
  const stats = attempt.details?.stats
  const questions = attempt.details?.questions || []
  const totalQuestions = stats?.total_questions ?? questions.length
  const correctAnswers = stats?.correct_answers ?? questions.filter((q) => q.is_correct).length

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal">
          <div className="modal__header">
            <div>
              <h2 className="modal__title">
                {testTitle} · попытка #{attempt.id}
              </h2>
              <p className="modal__subtitle">
                {formatDateTime(attempt.completed_at)}
                {attempt.source ? ` · ${attempt.source}` : ''}
              </p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
          </div>

          <div className="modal__body">
            <div className="cd-test-attempt-modal__summary">
              <TestScoreBar
                correct={correctAnswers}
                total={totalQuestions}
                score={stats?.final_score ?? attempt.final_score}
              />
              <div className="cd-test-card__extra">
                <span>Сырые: {typeof (stats?.raw_score ?? attempt.raw_score) === 'number' ? (stats?.raw_score ?? attempt.raw_score) : '—'}</span>
                <span>Время: {formatSecondsToMinutes(stats?.total_time)}</span>
                <span>Просрочено: {stats?.overtime_questions ?? 0}</span>
              </div>
            </div>

            {questions.length === 0 ? (
              <p className="subtitle">Для этой попытки нет подробных ответов.</p>
            ) : (
              <div className="cd-test-attempt-modal__questions">
                {questions.map((question, index) => (
                  <div key={`${attempt.id}-${question.question_index ?? index}`} className="glass cd-test-attempt-question">
                    <div className="cd-test-attempt-question__header">
                      <span>Вопрос {question.question_index ?? index + 1}</span>
                      <span className={`cd-chip cd-chip--small ${question.is_correct ? 'cd-chip--success' : 'cd-chip--danger'}`}>
                        {question.is_correct ? 'Верно' : 'Неверно'}
                      </span>
                    </div>
                    <div className="cd-test-attempt-question__text">{question.question_text || '—'}</div>
                    <div className="cd-test-attempt-question__answer">
                      <strong>Ответ кандидата:</strong> {question.user_answer || '—'}
                    </div>
                    {question.correct_answer && (
                      <div className="cd-test-attempt-question__answer">
                        <strong>Эталон:</strong> {question.correct_answer}
                      </div>
                    )}
                    <div className="cd-test-attempt-question__meta">
                      <span>Попыток: {question.attempts_count ?? 1}</span>
                      <span>Время: {formatSecondsToMinutes(question.time_spent)}</span>
                      {question.overtime ? <span>Просрочено</span> : null}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </ModalPortal>
  )
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

    date: getTomorrowDate(),

    time: '10:00',

    custom_message: '',

  })

  const [resolvedCityId, setResolvedCityId] = useState<number | null>(null)

  const [error, setError] = useState<string | null>(null)



  const citiesQuery = useQuery<City[]> ({

    queryKey: ['cities'],

    queryFn: fetchCities,

  })

  const cities = useMemo(() => citiesQuery.data ?? [], [citiesQuery.data])



  // Auto-resolve city based on candidate's city

  useEffect(() => {

    if (candidateCity && cities.length > 0 && resolvedCityId === null) {

      const match = cities.find((c) => c.name.toLowerCase() === candidateCity.toLowerCase())

      if (match) {

        setResolvedCityId(match.id)

      }

    }

  }, [candidateCity, cities, resolvedCityId])



  const selectedCity = useMemo(() => cities.find((c) => c.id === resolvedCityId), [cities, resolvedCityId])

  const cityTz = selectedCity?.tz || 'Europe/Moscow'
  const recruiterTz = browserTimeZone()
  const slotPreview = useMemo(
    () => buildSlotTimePreview(form.date, form.time, recruiterTz, cityTz),
    [form.date, form.time, recruiterTz, cityTz],
  )



  const mutation = useMutation({

    mutationFn: async () => {

      return scheduleCandidateInterview(candidateId, {
        city_id: resolvedCityId,
        date: form.date,
        time: form.time,
        custom_message: form.custom_message || null,
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



  const canSubmit = resolvedCityId && form.date && form.time



  return (

    <ModalPortal>

      <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()} role="dialog" aria-modal="true">

        <div className="glass glass--elevated modal modal--md">

          <div className="modal__header">

            <div>

              <h2 className="modal__title">Предложить время собеседования</h2>

              <p className="modal__subtitle">

                Кандидат: <strong>{candidateFio}</strong>

              </p>

            </div>

            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>

          </div>



          {error && <div className="ui-alert ui-alert--error">{error}</div>}



          <div className="modal__body">

            <p className="text-muted text-sm subtitle--mt-0">
              Кандидату придёт предложение времени. После подтверждения отправится приглашение на собеседование.
            </p>

            <div className="form-grid">

              {selectedCity && (

                <div className="form-group">

                  <span className="form-group__label">Город</span>

                  <span>{selectedCity.name} — {cityTz} ({formatTzOffset(cityTz)})</span>

                </div>

              )}



              <div className="form-row">

                <label className="form-group">

                  <span className="form-group__label">Дата</span>

                  <input

                    type="date"

                    value={form.date}

                    onChange={(e) => setForm({ ...form, date: e.target.value })}

                  />

                </label>

                <label className="form-group">

                  <span className="form-group__label">Время ({recruiterTz})</span>

                  <input

                    type="time"

                    value={form.time}

                    onChange={(e) => setForm({ ...form, time: e.target.value })}

                  />

                </label>

              </div>

              {slotPreview && (
                <div className="glass slot-preview">
                  <div>
                    <div className="slot-preview__label">Вы вводите (ваша TZ)</div>
                    <div className="slot-preview__value">{slotPreview.recruiterLabel}</div>
                    <div className="slot-preview__hint">{slotPreview.recruiterTz}</div>
                  </div>
                  <div>
                    <div className="slot-preview__label">Кандидат увидит</div>
                    <div className="slot-preview__value">{slotPreview.candidateLabel}</div>
                    <div className="slot-preview__hint">{slotPreview.candidateTz}</div>
                  </div>
                </div>
              )}



              <label className="form-group">

                <span className="form-group__label">Сообщение кандидату (опционально)</span>

                <textarea

                  rows={3}

                  value={form.custom_message}

                  onChange={(e) => setForm({ ...form, custom_message: e.target.value })}

                  placeholder="Например: Мы предлагаем собеседование в это время. Подойдёт ли вам?"

                />

              </label>

            </div>

          </div>



          <div className="modal__footer">

            <button

              className="ui-btn ui-btn--primary"

              onClick={() => mutation.mutate()}

              disabled={!canSubmit || mutation.isPending}

            >

              {mutation.isPending ? 'Отправляем...' : 'Отправить предложение'}

            </button>

            <button className="ui-btn ui-btn--ghost" onClick={onClose}>

              Отмена

            </button>

          </div>

        </div>

      </div>

    </ModalPortal>

  )

}

type ScheduleIntroDayModalProps = {
  candidateId: number
  candidateFio: string
  candidateCity?: string | null
  introDayTemplate?: string | null
  onClose: () => void
  onSuccess: () => void
}

function ScheduleIntroDayModal({ candidateId, candidateFio, candidateCity, introDayTemplate, onClose, onSuccess }: ScheduleIntroDayModalProps) {
  const [form, setForm] = useState({
    date: getTomorrowDate(),
    time: '10:00',
    customMessage: '',
  })
  const [error, setError] = useState<string | null>(null)
  const recruiterTz = browserTimeZone()
  const citiesQuery = useQuery<City[]>({
    queryKey: ['cities'],
    queryFn: fetchCities,
  })
  const introCityTz = useMemo(() => {
    const cities = citiesQuery.data || []
    if (!candidateCity) return 'Europe/Moscow'
    const match = cities.find((c) => c.name.toLowerCase() === candidateCity.toLowerCase())
    return match?.tz || 'Europe/Moscow'
  }, [citiesQuery.data, candidateCity])
  const [template, setTemplate] = useState<string>('')

  // Helper to generate message
  const generateMessage = useMemo(() => {
    return (tmpl: string, dateStr: string, timeStr: string) => {
    if (!tmpl) return ''
    let msg = tmpl.replace(/\[Имя\]/g, candidateFio.split(' ')[1] || candidateFio.split(' ')[0] || 'Кандидат') // Try to get first name
    
    // Format date: YYYY-MM-DD -> dd.mm
    let formattedDate = dateStr
    try {
        const [y, m, d] = dateStr.split('-')
        if (y && m && d) formattedDate = `${d}.${m}`
    } catch {}

    msg = msg.replace(/\[Дата\]/g, formattedDate)
    msg = msg.replace(/\[Время\]/g, timeStr)
    return msg
    }
  }, [candidateFio])

  useEffect(() => {
    if (introDayTemplate) {
      setTemplate(introDayTemplate)
      setForm(prev => ({ ...prev, customMessage: generateMessage(introDayTemplate, prev.date, prev.time) }))
    } else {
      fetchTemplateByKey('intro_day_invitation')
        .then((data) => {
          const text = Array.isArray(data) ? data[0]?.text : data?.text
          if (text) {
            setTemplate(text)
            setForm(prev => ({ ...prev, customMessage: generateMessage(text, prev.date, prev.time) }))
          }
        })
        .catch(() => {
          // Ignore template fetch errors
        })
    }
  }, [generateMessage, introDayTemplate])

  // Update message when date/time changes
  useEffect(() => {
      if (template) {
          setForm(prev => ({ ...prev, customMessage: generateMessage(template, prev.date, prev.time) }))
      }
  }, [form.date, form.time, generateMessage, template])

  const mutation = useMutation({
    mutationFn: async () => {
      return scheduleCandidateIntroDay(candidateId, {
        date: form.date,
        time: form.time,
        custom_message: form.customMessage,
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
  const introPreview = useMemo(
    () => buildSlotTimePreview(form.date, form.time, recruiterTz, introCityTz),
    [form.date, form.time, recruiterTz, introCityTz],
  )

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal modal--sm">
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Назначить ознакомительный день</h2>
              <p className="modal__subtitle">
                Кандидат: <strong>{candidateFio}</strong>
                {candidateCity && <><br />Город: {candidateCity}</>}
              </p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
          </div>

          {error && <div className="ui-alert ui-alert--error">{error}</div>}

          <div className="modal__body">
            <div className="form-row">
              <label className="form-group">
                <span className="form-group__label">Дата</span>
                <input
                  type="date"
                  value={form.date}
                  onChange={(e) => setForm({ ...form, date: e.target.value })}
                />
              </label>
              <label className="form-group">
                <span className="form-group__label">Время ({recruiterTz})</span>
                <input
                  type="time"
                  value={form.time}
                  onChange={(e) => setForm({ ...form, time: e.target.value })}
                />
              </label>
            </div>

            {introPreview && (
              <div className="glass slot-preview">
                <div>
                  <div className="slot-preview__label">Вы вводите (ваша TZ)</div>
                  <div className="slot-preview__value">{introPreview.recruiterLabel}</div>
                  <div className="slot-preview__hint">{introPreview.recruiterTz}</div>
                </div>
                <div>
                  <div className="slot-preview__label">Кандидат увидит</div>
                  <div className="slot-preview__value">{introPreview.candidateLabel}</div>
                  <div className="slot-preview__hint">{introPreview.candidateTz}</div>
                </div>
              </div>
            )}
            
            <label className="form-group form-group--mt">
              <span className="form-group__label">Сообщение кандидату</span>
              <textarea
                rows={6}
                value={form.customMessage}
                onChange={(e) => setForm({ ...form, customMessage: e.target.value })}
                placeholder="Текст приглашения..."
                className="ui-input ui-input--multiline"
              />
            </label>

            <p className="subtitle subtitle--mt-sm">
              Адрес и контакт руководителя будут взяты из шаблона города.
            </p>
          </div>

          <div className="modal__footer">
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
    </ModalPortal>
  )
}

type RejectModalProps = {
  candidateId: number
  onClose: () => void
  onSuccess: () => void
  title?: string
  actionKey: string
}

function RejectModal({ candidateId, onClose, onSuccess, title, actionKey }: RejectModalProps) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      return applyCandidateAction(candidateId, actionKey, { reason })
    },
    onSuccess: () => {
      onSuccess()
      onClose()
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal modal--sm">
          <div className="modal__header">
            <h2 className="modal__title">{title || 'Укажите причину отказа'}</h2>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
          </div>
          <div className="modal__body">
            {error && <p className="subtitle subtitle--danger">{error}</p>}
            <textarea
              rows={4}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Причина отказа..."
              className="ui-input ui-input--multiline"
              autoFocus
            />
          </div>
          <div className="modal__footer">
            <button
              className="ui-btn ui-btn--danger"
              onClick={() => mutation.mutate()}
              disabled={!reason.trim() || mutation.isPending}
            >
              Подтвердить отказ
            </button>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Отмена</button>
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}

type InterviewScriptModalProps = {
  candidateId: number
  onClose: () => void
}

const INTERVIEW_FEEDBACK_REASONS = [
  'слишком длинно',
  'не тот тон',
  'не учёл опыт',
  'не закрыл логистику',
] as const

function InterviewScriptModal({ candidateId, onClose }: InterviewScriptModalProps) {
  const queryClient = useQueryClient()
  const [helped, setHelped] = useState<boolean | null>(null)
  const [edited, setEdited] = useState(false)
  const [quickReasons, setQuickReasons] = useState<string[]>([])
  const [outcome, setOutcome] = useState<'od_assigned' | 'showed_up' | 'no_show' | 'decline' | 'unknown'>('unknown')
  const [outcomeReason, setOutcomeReason] = useState('')
  const [scriptEditor, setScriptEditor] = useState('')
  const [feedbackSaved, setFeedbackSaved] = useState(false)

  const scriptQuery = useQuery<InterviewScriptResponse>({
    queryKey: ['ai-interview-script', candidateId],
    queryFn: () => fetchCandidateInterviewScript(candidateId),
    retry: false,
  })

  const refreshMutation = useMutation({
    mutationFn: () => refreshCandidateInterviewScript(candidateId),
    onSuccess: (data) => {
      queryClient.setQueryData(['ai-interview-script', candidateId], data)
      setScriptEditor(JSON.stringify(data.script, null, 2))
    },
  })

  const feedbackMutation = useMutation({
    mutationFn: (payload: InterviewScriptFeedbackPayload) =>
      submitCandidateInterviewScriptFeedback(candidateId, payload),
    onSuccess: () => {
      setFeedbackSaved(true)
    },
  })

  useEffect(() => {
    if (!scriptQuery.data?.script) return
    setScriptEditor(JSON.stringify(scriptQuery.data.script, null, 2))
  }, [scriptQuery.data?.script])

  const script = scriptQuery.data?.script

  const copyText = async (value: string) => {
    const text = value.trim()
    if (!text) return
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      }
    } catch {
      // Clipboard may be unavailable in some environments.
    }
  }

  const toggleReason = (value: string) => {
    setQuickReasons((prev) => (prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value]))
  }

  const submitFeedback = () => {
    let finalScript: InterviewScriptPayload | null = null
    if (edited) {
      try {
        finalScript = JSON.parse(scriptEditor) as InterviewScriptPayload
      } catch {
        window.alert('JSON в поле "Отредактировал" невалидный')
        return
      }
    }
    feedbackMutation.mutate({
      helped,
      edited,
      quick_reasons: quickReasons,
      final_script: finalScript,
      outcome,
      outcome_reason: outcomeReason.trim() || null,
      idempotency_key: `isf-${candidateId}-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`,
    })
  }

  return (
    <ModalPortal>
      <div
        className="modal-overlay"
        onClick={(e) => e.target === e.currentTarget && onClose()}
        role="dialog"
        aria-modal="true"
        data-testid="interview-script-modal"
      >
        <div className="glass glass--elevated modal cd-interview-script-modal" onClick={(e) => e.stopPropagation()}>
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Скрипт интервью</h2>
              <p className="modal__subtitle">Персонализированный сценарий звонка и фидбек для дообучения</p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
          </div>

          <div className="modal__body">
            <div className="cd-interview-script__toolbar">
              <button
                className="ui-btn ui-btn--ghost"
                onClick={() => refreshMutation.mutate()}
                disabled={refreshMutation.isPending || scriptQuery.isFetching}
              >
                {refreshMutation.isPending ? 'Обновление…' : 'Обновить'}
              </button>
              <button
                className="ui-btn ui-btn--ghost"
                onClick={() => copyText(JSON.stringify(script || {}, null, 2))}
                disabled={!script}
              >
                Скопировать всё
              </button>
              {scriptQuery.data && (
                <>
                  <span className={`cd-chip cd-chip--small ${scriptQuery.data.cached ? '' : 'cd-chip--accent'}`}>
                    {scriptQuery.data.cached ? 'Кэш' : 'Новый'}
                  </span>
                  {scriptQuery.data.model && <span className="cd-chip cd-chip--small">{scriptQuery.data.model}</span>}
                  {scriptQuery.data.prompt_version && <span className="cd-chip cd-chip--small">{scriptQuery.data.prompt_version}</span>}
                </>
              )}
            </div>

            {scriptQuery.isLoading && <div className="subtitle">Генерация скрипта…</div>}
            {scriptQuery.error && (
              <ApiErrorBanner
                error={scriptQuery.error}
                title="Не удалось сгенерировать скрипт интервью"
                onRetry={() => scriptQuery.refetch()}
                className="glass panel"
              />
            )}

            {script && (
              <div className="cd-interview-script__sections">
                <section className="cd-interview-script__section">
                  <h3>Highlights</h3>
                  <ul className="cd-ai__list">
                    {script.highlights.map((item, idx) => (
                      <li key={`highlight-${idx}`} className="cd-ai__point">
                        <div className="cd-ai__point-text">{item}</div>
                      </li>
                    ))}
                  </ul>
                </section>

                <section className="cd-interview-script__section">
                  <h3>Checks</h3>
                  <ul className="cd-ai__list">
                    {script.checks.map((item, idx) => (
                      <li key={`check-${idx}`} className="cd-ai__point">
                        <div className="cd-ai__point-text">{item}</div>
                      </li>
                    ))}
                  </ul>
                </section>

                <section className="cd-interview-script__section">
                  <details className="ui-disclosure" open>
                    <summary className="ui-disclosure__trigger" data-testid="cd-ai-section-toggle-risks">Риски</summary>
                    <div className="ui-disclosure__content">
                      <div className="cd-interview-script__risk-grid">
                        {script.risk_flags.map((risk) => (
                          <div key={risk.code} className={`cd-ai__risk cd-ai__risk--${risk.severity}`}>
                            <div className="cd-ai__risk-title">
                              <span>{risk.code}</span>
                              <span className="cd-chip cd-chip--small">{risk.severity}</span>
                            </div>
                            <div className="cd-ai__risk-text">{risk.reason}</div>
                            <div className="cd-ai__point-text"><strong>Вопрос:</strong> {risk.question}</div>
                            <div className="cd-ai__point-text"><strong>Фраза:</strong> {risk.recommended_phrase}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </details>
                </section>

                <section className="cd-interview-script__section">
                  <h3>Блоки скрипта</h3>
                  <div className="cd-interview-script__blocks">
                    {script.script_blocks.map((block) => (
                      <details key={block.id} className="cd-test-card__history">
                        <summary>{block.title}</summary>
                        <div className="cd-interview-script__block">
                          <div className="cd-ai__point-text"><strong>Цель:</strong> {block.goal}</div>
                          <div className="cd-ai__point-text">{block.recruiter_text}</div>
                          {block.candidate_questions.length > 0 && (
                            <ul className="cd-ai__list">
                              {block.candidate_questions.map((q, idx) => (
                                <li key={`${block.id}-q-${idx}`} className="cd-ai__action">
                                  <div className="cd-ai__action-text">{q}</div>
                                </li>
                              ))}
                            </ul>
                          )}
                          {block.if_answers.length > 0 && (
                            <ul className="cd-ai__list">
                              {block.if_answers.map((rule, idx) => (
                                <li key={`${block.id}-if-${idx}`} className="cd-ai__point">
                                  <div className="cd-ai__point-title">{rule.pattern}</div>
                                  <div className="cd-ai__point-text">{rule.hint}</div>
                                </li>
                              ))}
                            </ul>
                          )}
                          <button
                            type="button"
                            className="ui-btn ui-btn--ghost"
                            onClick={() => copyText(`${block.title}\n${block.recruiter_text}`)}
                          >
                            Скопировать блок
                          </button>
                        </div>
                      </details>
                    ))}
                  </div>
                </section>

                <section className="cd-interview-script__section">
                  <details className="ui-disclosure">
                    <summary className="ui-disclosure__trigger" data-testid="cd-ai-section-toggle-objections">Возражения</summary>
                    <div className="ui-disclosure__content">
                      <div className="cd-interview-script__objections">
                        {script.objections.map((obj, idx) => (
                          <div key={`obj-${idx}`} className="cd-ai__point">
                            <div className="cd-ai__point-title">{obj.topic}</div>
                            <div className="cd-ai__point-text"><strong>Кандидат:</strong> {obj.candidate_says}</div>
                            <div className="cd-ai__point-text"><strong>Ответ:</strong> {obj.recruiter_answer}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </details>
                </section>

                <section className="cd-interview-script__section">
                  <details className="ui-disclosure">
                    <summary className="ui-disclosure__trigger" data-testid="cd-ai-section-toggle-cta">CTA шаблоны</summary>
                    <div className="ui-disclosure__content">
                      <div className="cd-interview-script__objections">
                        {script.cta_templates.map((item, idx) => (
                          <div key={`cta-${idx}`} className="cd-ai__action">
                            <div className="cd-ai__action-title">{item.type}</div>
                            <div className="cd-ai__action-text">{item.text}</div>
                            <button className="ui-btn ui-btn--ghost" onClick={() => copyText(item.text)}>Скопировать</button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </details>
                </section>

                <section className="cd-interview-script__section cd-interview-script__section--feedback">
                  <h3>Feedback</h3>
                  <div className="cd-interview-script__feedback-row">
                    <button
                      type="button"
                      className={`ui-btn ${helped === true ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
                      onClick={() => setHelped(true)}
                    >
                      Скрипт помог
                    </button>
                    <button
                      type="button"
                      className={`ui-btn ${helped === false ? 'ui-btn--danger' : 'ui-btn--ghost'}`}
                      onClick={() => setHelped(false)}
                    >
                      Не помог
                    </button>
                    <label className="cd-interview-script__edited">
                      <input
                        type="checkbox"
                        checked={edited}
                        onChange={(e) => setEdited(e.target.checked)}
                      />
                      Отредактировал
                    </label>
                  </div>

                  <div className="cd-interview-script__feedback-row">
                    {INTERVIEW_FEEDBACK_REASONS.map((reason) => (
                      <label key={reason} className="cd-interview-script__reason">
                        <input
                          type="checkbox"
                          checked={quickReasons.includes(reason)}
                          onChange={() => toggleReason(reason)}
                        />
                        {reason}
                      </label>
                    ))}
                  </div>

                  {edited && (
                    <textarea
                      className="ui-input"
                      rows={8}
                      value={scriptEditor}
                      onChange={(e) => setScriptEditor(e.target.value)}
                      placeholder="Вставьте итоговый JSON-скрипт"
                    />
                  )}

                  <div className="cd-interview-script__feedback-row">
                    <select
                      className="ui-input"
                      value={outcome}
                      onChange={(e) => setOutcome(e.target.value as 'od_assigned' | 'showed_up' | 'no_show' | 'decline' | 'unknown')}
                    >
                      <option value="unknown">Исход: неизвестно</option>
                      <option value="od_assigned">ОД назначен</option>
                      <option value="showed_up">Пришёл</option>
                      <option value="no_show">Не пришёл</option>
                      <option value="decline">Отказ</option>
                    </select>
                    <input
                      className="ui-input"
                      value={outcomeReason}
                      onChange={(e) => setOutcomeReason(e.target.value)}
                      placeholder="Причина/комментарий (опционально)"
                    />
                  </div>

                  {feedbackMutation.error && (
                    <div className="ui-alert ui-alert--error">
                      Ошибка feedback: {(feedbackMutation.error as Error).message}
                    </div>
                  )}
                  {feedbackSaved && <div className="ui-alert ui-alert--success">Feedback сохранён</div>}

                  <div className="modal__footer modal__footer--flat">
                    <button
                      className="ui-btn ui-btn--primary"
                      onClick={submitFeedback}
                      disabled={feedbackMutation.isPending}
                    >
                      {feedbackMutation.isPending ? 'Сохранение…' : 'Сохранить feedback'}
                    </button>
                  </div>
                </section>
              </div>
            )}
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}

export function CandidateDetailPage() {
  const queryClient = useQueryClient()
  const params = useParams({ from: '/app/candidates/$candidateId' })
  const isMobile = useIsMobile()
  const candidateId = Number(params.candidateId)
  const [mobileTab, setMobileTab] = useState<'profile' | 'tests' | 'timeline' | 'chat'>('profile')
  const [chatText, setChatText] = useState('')
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [showScheduleSlotModal, setShowScheduleSlotModal] = useState(false)
  const [showScheduleIntroDayModal, setShowScheduleIntroDayModal] = useState(false)
  const [showRejectModal, setShowRejectModal] = useState<{ actionKey: string; title?: string } | null>(null)
  const [reportPreview, setReportPreview] = useState<ReportPreviewState | null>(null)
  const [attemptPreview, setAttemptPreview] = useState<{ testTitle: string; attempt: TestAttempt } | null>(null)
  const [isChatOpen, setIsChatOpen] = useState(false)
  const pipelineActionsRef = useRef<HTMLDivElement | null>(null)
  const chatMessagesRef = useRef<HTMLDivElement | null>(null)
  const chatTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const testsSectionRef = useRef<HTMLDivElement | null>(null)
  const [aiDraftsOpen, setAiDraftsOpen] = useState(false)
  const [aiDraftMode, setAiDraftMode] = useState<'short' | 'neutral' | 'supportive'>('neutral')
  const [aiCoachDrafts, setAiCoachDrafts] = useState<AIDraftItem[] | null>(null)
  const [showInterviewScriptModal, setShowInterviewScriptModal] = useState(false)

  const detailQuery = useQuery<CandidateDetail>({
    queryKey: ['candidate-detail', candidateId],
    queryFn: () => fetchCandidateDetail(candidateId),
  })

  const hhSummaryQuery = useQuery<CandidateHHSummary>({
    queryKey: ['candidate-hh-summary', candidateId],
    queryFn: () => fetchCandidateHHSummary(candidateId),
    retry: false,
  })

  const chatQuery = useQuery<ChatPayload>({
    queryKey: ['candidate-chat', candidateId],
    queryFn: () => fetchCandidateChat(candidateId, 50),
    enabled: isChatOpen,
    refetchInterval: isChatOpen ? 3000 : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: isChatOpen,
  })

  const markChatReadMutation = useMutation({
    mutationFn: markCandidateChatRead,
    onSuccess: (_data, readCandidateId) => {
      queryClient.setQueryData<{ threads?: Array<{ candidate_id: number; unread_count?: number }> }>(
        ['candidate-chat-threads'],
        (prev) => {
          if (!prev?.threads) return prev
          return {
            ...prev,
            threads: prev.threads.map((thread) =>
              thread.candidate_id === readCandidateId ? { ...thread, unread_count: 0 } : thread,
            ),
          }
        },
      )
    },
  })
  const markChatRead = markChatReadMutation.mutate

  const sendMutation = useMutation({
    mutationFn: async (text: string) => {
      return sendCandidateChatMessage(candidateId, text, String(Date.now()))
    },
    onSuccess: () => {
      setChatText('')
      chatQuery.refetch()
    },
  })

  const aiSummaryQuery = useQuery<AISummaryResponse>({
    queryKey: ['ai-summary', candidateId],
    queryFn: () => fetchCandidateAiSummary(candidateId),
    enabled: false,
    retry: false,
  })

  const aiCoachQuery = useQuery<AICoachResponse>({
    queryKey: ['ai-coach', candidateId],
    queryFn: () => fetchCandidateAiCoach(candidateId),
    enabled: false,
    retry: false,
  })

  const aiRefreshMutation = useMutation({
    mutationFn: () => refreshCandidateAiSummary(candidateId),
    onSuccess: (data) => {
      queryClient.setQueryData(['ai-summary', candidateId], data)
    },
  })

  const aiCoachRefreshMutation = useMutation({
    mutationFn: () => refreshCandidateAiCoach(candidateId),
    onSuccess: (data) => {
      queryClient.setQueryData(['ai-coach', candidateId], data)
      setAiCoachDrafts(null)
    },
  })

  const aiDraftsMutation = useMutation({
    mutationFn: (mode: 'short' | 'neutral' | 'supportive') => fetchCandidateChatDrafts(candidateId, mode),
  })

  const aiCoachDraftsMutation = useMutation({
    mutationFn: (mode: 'short' | 'neutral' | 'supportive') => fetchCandidateCoachDrafts(candidateId, mode),
    onSuccess: (data) => {
      setAiCoachDrafts(data.drafts || [])
    },
  })

  const actionMutation = useMutation({
    mutationFn: ({ actionKey, payload }: { actionKey: string; payload?: any }) =>
      applyCandidateAction(candidateId, actionKey, payload),
    onSuccess: () => {
      setActionMessage('Действие выполнено')
      detailQuery.refetch()
      queryClient.invalidateQueries({ queryKey: ['candidates'] })
    },
    onError: (err: unknown) => {
      setActionMessage((err as Error).message)
    },
  })

  const detail = detailQuery.data
  const hhSummary = hhSummaryQuery.data
  const actions = detail?.candidate_actions || []
  const slots = detail?.slots || []
  const testSections = useMemo(() => {
    const raw = detail?.test_sections ?? []
    if (raw.length > 0) return raw
    const map = detail?.test_results ?? {}
    const entries = Object.entries(map)
    if (entries.length === 0) return []
    return entries.map(([key, value]) => ({
      ...value,
      key,
      title: key === 'test1' ? 'Тест 1' : key === 'test2' ? 'Тест 2' : (value.title || key),
    }))
  }, [detail?.test_results, detail?.test_sections])
  const test1Section = testSections.find((section) => section.key === 'test1')
  const test2Section = testSections.find((section) => section.key === 'test2')
  const chatMessages = (chatQuery.data?.messages || []).slice().reverse()
  const rescheduleRequest = formatRescheduleRequest(detail?.reschedule_request)
  const pipelineStages = detail?.pipeline_stages || []
  const refetchChat = chatQuery.refetch

  const aiSummaryData = aiSummaryQuery.data?.summary || null
  const aiRisks = aiSummaryData?.risks || []
  const aiNextActions = aiSummaryData?.next_actions || []
  const aiFit = aiSummaryData?.fit || null
  const aiStrengths = aiSummaryData?.strengths || []
  const aiWeaknesses = aiSummaryData?.weaknesses || []
  const aiCriteriaChecklist = (aiSummaryData?.criteria_checklist || []).filter((c) => Boolean(c?.label || c?.evidence))
  const aiTestInsights = aiSummaryData?.test_insights || null
  const aiSummaryError = (aiSummaryQuery.error as Error | null) || (aiRefreshMutation.error as Error | null)
  const aiCoachData = aiCoachQuery.data?.coach || null
  const aiCoachStrengths = aiCoachData?.strengths || []
  const aiCoachRisks = aiCoachData?.risks || []
  const aiCoachQuestions = aiCoachData?.interview_questions || []
  const aiCoachDraftItems = aiCoachDrafts || aiCoachData?.message_drafts || []
  const aiCoachError = (aiCoachQuery.error as Error | null) || (aiCoachRefreshMutation.error as Error | null)

  useEffect(() => {
    if (!isChatOpen) return
    refetchChat()
  }, [isChatOpen, refetchChat])

  useEffect(() => {
    if (!isChatOpen) return
    markChatRead(candidateId)
  }, [candidateId, isChatOpen, markChatRead])

  useEffect(() => {
    if (!isChatOpen || chatMessages.length === 0) return
    markChatRead(candidateId)
  }, [candidateId, chatMessages.length, isChatOpen, markChatRead])

  useEffect(() => {
    setAiCoachDrafts(null)
  }, [candidateId])

  useEffect(() => {
    if (!isChatOpen) return
    const container = chatMessagesRef.current
    if (!container) return
    requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight
    })
  }, [isChatOpen, chatMessages.length])

  const onActionClick = (action: CandidateAction) => {
    const isRejection =
      action.key === 'reject' ||
      action.key === 'interview_outcome_failed' ||
      action.key === 'interview_declined' ||
      action.key === 'mark_not_hired' ||
      action.key === 'decline_after_intro' ||
      action.variant === 'danger'

    if (isRejection) {
      setShowRejectModal({ actionKey: action.key, title: action.label })
      return
    }

    if ((action.method || 'GET').toUpperCase() === 'GET') {
      if (action.url) {
        // Prevent open redirect: only allow same-origin or relative URLs
        try {
          const target = new URL(action.url, window.location.origin)
          if (target.origin !== window.location.origin) {
            console.warn('Blocked redirect to external origin:', action.url)
            return
          }
          window.location.href = target.href
        } catch {
          // Invalid URL — treat as relative path
          window.location.href = action.url
        }
      }
      return
    }
    if (action.confirmation && !window.confirm(action.confirmation)) {
      return
    }
    actionMutation.mutate({ actionKey: action.key })
  }

  const statusSlug = detail?.candidate_status_slug || null
  const statusDisplay = detail ? getStatusDisplay(statusSlug) : null
  const statusTone = detail?.candidate_status_color || statusDisplay?.tone || 'muted'
  const statusLabel = detail?.candidate_status_display || statusDisplay?.label || 'Нет статуса'
  const hasUpcomingSlot = slots.some((s) => {
    const status = String(s.status || '').toUpperCase()
    return ['BOOKED', 'PENDING', 'CONFIRMED', 'CONFIRMED_BY_CANDIDATE'].includes(status)
  })
  const hasIntroDay = slots.some((s) => s.purpose === 'intro_day')
  const telegramUsername = normalizeTelegramUsername(detail?.telegram_username)
  const telegramLink = telegramUsername
    ? `https://t.me/${telegramUsername}`
    : detail?.telegram_id
      ? `tg://user?id=${detail.telegram_id}`
      : null
  const hhLink = detail?.hh_profile_url || null
  const hhBadge = getHhSyncBadge(hhSummary?.sync_status ?? detail?.hh_sync_status)
  const hhAvailableActions = (hhSummary?.available_actions || []).filter((item) => item.enabled !== false)
  const shouldShowHhPanel = Boolean(
    hhSummaryQuery.isPending
      || hhSummary?.linked
      || hhSummaryQuery.isError
      || detail?.hh_resume_id
      || detail?.hh_negotiation_id
      || detail?.hh_sync_status,
  )
  const conferenceLink = normalizeConferenceUrl(detail?.telemost_url)
  const conferenceSourceLabel =
    detail?.telemost_source === 'upcoming'
      ? 'Источник: ближайший слот'
      : detail?.telemost_source === 'recent'
        ? 'Источник: последний слот'
        : null

  const test2Action = actions.find((action) => {
    const key = action.key?.toLowerCase?.() || ''
    const label = action.label?.toLowerCase?.() || ''
    return action.target_status === 'test2_sent' || key.includes('test2') || label.includes('тест 2')
  })
  const scheduleAction = actions.find((action) =>
    ['schedule_interview', 'reschedule_interview'].includes(action.key)
  )
  const rejectAction = actions.find((action) => action.key === 'reject' || action.target_status === 'interview_declined')
  const canSendTest2 = Boolean(test2Action)
  const test2Passed = test2Section?.status === 'passed' || statusSlug === 'test2_completed'
  const isWaitingIntroDay = statusSlug === 'test2_completed'
  const canScheduleIntroDay = Boolean(detail?.telegram_id) && !hasIntroDay && test2Passed && isWaitingIntroDay
  const canScheduleInterview = Boolean(detail?.telegram_id) && Boolean(scheduleAction)
    && (scheduleAction?.key === 'reschedule_interview' || !hasUpcomingSlot)
  const scheduleLabel = scheduleAction?.key === 'reschedule_interview' || statusSlug === 'slot_pending'
    ? 'Предложить другое время'
    : 'Предложить время'
  const filteredActions = actions.filter((action) => {
    if (action === test2Action || action === rejectAction) return false
    if (['schedule_interview', 'reschedule_interview', 'schedule_intro_day'].includes(action.key)) return false
    return true
  })
  const inlineActions = filteredActions.slice(0, 2)
  const overflowActions = filteredActions.slice(2)

  useEffect(() => {
    setMobileTab('profile')
  }, [candidateId])

  useEffect(() => {
    if (!isMobile) return
    if (mobileTab === 'chat') {
      setIsChatOpen(true)
      return
    }
    setIsChatOpen(false)
  }, [isMobile, mobileTab])

  useEffect(() => {
    if (!isMobile) return
    if (!isChatOpen && mobileTab === 'chat') setMobileTab('profile')
  }, [isMobile, isChatOpen, mobileTab])

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (window.location.hash !== '#tests') return
    if (isMobile && mobileTab !== 'tests') {
      setMobileTab('tests')
    }
  }, [candidateId, isMobile, mobileTab])

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (window.location.hash !== '#tests') return
    const frame = window.requestAnimationFrame(() => {
      const testsSection = testsSectionRef.current
      if (testsSection && typeof testsSection.scrollIntoView === 'function') {
        testsSection.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    })
    return () => window.cancelAnimationFrame(frame)
  }, [candidateId, detail?.id, mobileTab, testSections.length])

  const showProfileSection = !isMobile || mobileTab === 'profile'
  const showTimelineSection = !isMobile || mobileTab === 'timeline'
  const showTestsSection = !isMobile || mobileTab === 'tests'

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className="page app-page app-page--ops candidate-detail-page">
        {detailQuery.isLoading && <div className="glass panel cd-loading-panel app-page__section"><p className="subtitle">Загрузка...</p></div>}
        {detailQuery.isError && (
          <ApiErrorBanner
            error={detailQuery.error}
            title="Не удалось загрузить профиль кандидата"
            onRetry={() => detailQuery.refetch()}
          />
        )}

        {detail && (<>
        {isMobile && (
          <div className="cd-mobile-tabs glass">
            <button
              type="button"
              className={`ui-btn ui-btn--sm ${mobileTab === 'profile' ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
              onClick={() => setMobileTab('profile')}
            >
              Профиль
            </button>
            <button
              type="button"
              className={`ui-btn ui-btn--sm ${mobileTab === 'tests' ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
              onClick={() => setMobileTab('tests')}
            >
              Тесты
            </button>
            <button
              type="button"
              className={`ui-btn ui-btn--sm ${mobileTab === 'timeline' ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
              onClick={() => setMobileTab('timeline')}
            >
              Таймлайн
            </button>
            <button
              type="button"
              className={`ui-btn ui-btn--sm ${mobileTab === 'chat' ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
              onClick={() => setMobileTab('chat')}
            >
              Чат
            </button>
          </div>
        )}
        {showProfileSection && (<>
        {/* ── Header Card ── */}
        <div className="glass panel cd-header app-page__hero" data-testid="candidate-header">
          <div className="cd-header__top">
            <div className="cd-header__avatar">
              {(detail.fio || '?').charAt(0).toUpperCase()}
            </div>
            <div className="cd-header__info">
              <div className="cd-header__name-row">
                <h1 className="cd-header__name">{detail.fio || `Кандидат #${candidateId}`}</h1>
                {statusDisplay && (
                  <span className={`status-pill status-pill--${statusTone}`}>
                    <span className={`cd-status-dot cd-status-dot--${statusTone}`} />
                    {statusLabel}
                  </span>
                )}
                {detail.status_is_terminal && (
                  <span className="cd-badge cd-badge--terminal">Финальный</span>
                )}
              </div>
              <div className="cd-header__meta">
                {detail.city && <span className="cd-chip">{detail.city}</span>}
                {detail.responsible_recruiter?.name && (
                  <span className="cd-chip cd-chip--accent">{detail.responsible_recruiter.name}</span>
                )}
                {detail.is_active === false && (
                  <span className="cd-chip cd-chip--danger">Неактивен</span>
                )}
              </div>
            </div>
            <div className="cd-header__actions">
              <Link to="/app/candidates" className="ui-btn ui-btn--ghost">К списку</Link>
            </div>
          </div>

          {/* Contacts row */}
          <div className="cd-contacts">
            {telegramLink ? (
              <a href={telegramLink} className="cd-contact-btn" target="_blank" rel="noopener">
                <span className="cd-contact-btn__icon">TG</span>
                <span>{telegramUsername ? `@${telegramUsername}` : 'Telegram'}</span>
              </a>
            ) : (
              <span className="cd-contact-btn cd-contact-btn--disabled">
                <span className="cd-contact-btn__icon">TG</span>
                <span>Telegram</span>
              </span>
            )}
            <button
              className="cd-contact-btn"
              onClick={() => {
                if (isMobile) setMobileTab('chat')
                setIsChatOpen(true)
              }}
              disabled={!detail.telegram_id}
            >
              <span className="cd-contact-btn__icon">CH</span>
              <span>Чат</span>
            </button>
            {hhLink ? (
              <a href={hhLink} className="cd-contact-btn" target="_blank" rel="noopener">
                <span className="cd-contact-btn__icon">HH</span>
                <span>Профиль</span>
              </a>
            ) : (
              <span className="cd-contact-btn cd-contact-btn--disabled">
                <span className="cd-contact-btn__icon">HH</span>
                <span>Профиль</span>
              </span>
            )}
            {hhBadge && (
              <span
                className={`cd-chip ${
                  hhBadge.tone === 'success' ? 'cd-chip--success'
                  : hhBadge.tone === 'danger' ? 'cd-chip--danger'
                  : hhBadge.tone === 'warning' ? 'cd-chip--warning'
                  : ''
                }`}
                title={hhSummary?.sync_error || detail.hh_sync_error || hhBadge.label}
              >
                {hhBadge.label}
              </span>
            )}
            {detail.messenger_platform && detail.messenger_platform !== 'telegram' && (
              <span
                className="cd-chip cd-chip--info"
                title={`Мессенджер: ${detail.messenger_platform}${detail.max_user_id ? ` (ID: ${detail.max_user_id})` : ''}`}
              >
                {detail.messenger_platform === 'max' ? '💬 Max' : detail.messenger_platform}
              </span>
            )}
            {conferenceLink ? (
              <a
                href={conferenceLink}
                className="cd-contact-btn"
                target="_blank"
                rel="noopener noreferrer"
                title={conferenceSourceLabel || 'Ссылка на конференцию'}
              >
                <span className="cd-contact-btn__icon">VC</span>
                <span>В конференцию</span>
              </a>
            ) : (
              <span className="cd-contact-btn cd-contact-btn--disabled" title="У рекрутера не заполнена ссылка на конференцию">
                <span className="cd-contact-btn__icon">VC</span>
                <span>В конференцию</span>
              </span>
            )}
            {detail.telegram_id && (
              <span className="cd-contact-btn cd-contact-btn--disabled cd-contact-btn--id">
                <span className="cd-contact-btn__icon cd-contact-btn__icon--small">ID</span>
                <span>{detail.telegram_id}</span>
              </span>
            )}
          </div>
        </div>

        {/* ── Stat Cards ── */}
        <div className="cd-stats-grid">
          <div className="glass cd-stat">
            <div className="cd-stat__label">Стадия</div>
            <div className="cd-stat__value">{detail.stage || detail.workflow_status_label || '—'}</div>
          </div>
          <div className="glass cd-stat">
            <div className="cd-stat__label">Тесты пройдено</div>
            <div className="cd-stat__value">{detail.stats?.tests_total ?? 0}</div>
            <div className="cd-stat__sub">Средний балл: <strong>{detail.stats?.average_score != null ? String(detail.stats.average_score) : '—'}</strong></div>
          </div>
          <div className="glass cd-stat">
            <div className="cd-stat__label">Тест 1</div>
            <div className="cd-stat__value">{test1Section?.status_label || '—'}</div>
            {test1Section?.details?.stats && (
              <TestScoreBar
                correct={test1Section.details.stats.correct_answers ?? 0}
                total={test1Section.details.stats.total_questions ?? 0}
                score={test1Section.details.stats.final_score}
              />
            )}
            {!test1Section?.details?.stats && <div className="cd-stat__sub">{test1Section?.summary || 'Нет данных'}</div>}
          </div>
          <div className="glass cd-stat">
            <div className="cd-stat__label">Тест 2</div>
            <div className="cd-stat__value">{test2Section?.status_label || '—'}</div>
            {test2Section?.details?.stats && (
              <TestScoreBar
                correct={test2Section.details.stats.correct_answers ?? 0}
                total={test2Section.details.stats.total_questions ?? 0}
                score={test2Section.details.stats.final_score}
              />
            )}
            {!test2Section?.details?.stats && <div className="cd-stat__sub">{test2Section?.summary || 'Нет данных'}</div>}
          </div>
          </div>

          {shouldShowHhPanel && (
            <div className="glass panel cd-hh-panel app-page__section">
              <div className="cd-section-header app-page__section-head">
                <div>
                  <h2 className="cd-section-title">HH.ru</h2>
                  <p className="ui-message ui-message--muted">Внешняя связка резюме, вакансии и negotiation lifecycle.</p>
                </div>
                <div className="ui-section-header__actions">
                  {hhSummary?.resume?.url ? (
                    <a href={hhSummary.resume.url} className="ui-btn ui-btn--ghost ui-btn--sm" target="_blank" rel="noopener">
                      Открыть в HH
                    </a>
                  ) : null}
                </div>
              </div>

              {hhSummaryQuery.isPending ? (
                <div className="ui-state ui-state--loading">
                  <p className="ui-state__text">Загружаю HH metadata…</p>
                </div>
              ) : hhSummaryQuery.isError ? (
                <ApiErrorBanner
                  title="Не удалось загрузить HH metadata"
                  error={hhSummaryQuery.error}
                  onRetry={() => hhSummaryQuery.refetch()}
                />
              ) : hhSummary?.linked ? (
                <div className="cd-hh-panel__grid">
                  <div className="cd-hh-card">
                    <div className="cd-hh-card__label">Resume</div>
                    <div className="cd-hh-card__value">{hhSummary.resume?.title || hhSummary.resume?.id || '—'}</div>
                    <div className="cd-hh-card__meta">
                      {hhSummary.resume?.id ? <span className="cd-chip">resume {hhSummary.resume.id}</span> : null}
                      {hhSummary.resume?.source_updated_at ? (
                        <span className="cd-chip">обновлено {formatDateTime(hhSummary.resume.source_updated_at)}</span>
                      ) : null}
                    </div>
                  </div>

                  <div className="cd-hh-card">
                    <div className="cd-hh-card__label">Negotiation</div>
                    <div className="cd-hh-card__value">{hhSummary.negotiation?.employer_state || '—'}</div>
                    <div className="cd-hh-card__meta">
                      {hhSummary.negotiation?.collection_name ? (
                        <span className="cd-chip">{hhSummary.negotiation.collection_name}</span>
                      ) : null}
                      {hhSummary.negotiation?.id ? (
                        <span className="cd-chip">negotiation {hhSummary.negotiation.id}</span>
                      ) : null}
                    </div>
                  </div>

                  <div className="cd-hh-card">
                    <div className="cd-hh-card__label">Vacancy</div>
                    <div className="cd-hh-card__value">{hhSummary.vacancy?.title || hhSummary.vacancy?.id || '—'}</div>
                    <div className="cd-hh-card__meta">
                      {hhSummary.vacancy?.id ? <span className="cd-chip">vacancy {hhSummary.vacancy.id}</span> : null}
                      {hhSummary.vacancy?.area_name ? <span className="cd-chip">{hhSummary.vacancy.area_name}</span> : null}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="ui-state ui-state--empty">
                  <p className="ui-state__text">Прямая HH-связка для этого кандидата ещё не сформирована.</p>
                </div>
              )}

              {hhSummary?.linked ? (
                <>
                  <div className="cd-hh-panel__meta">
                    {hhBadge ? (
                      <span className={`cd-chip ${hhBadge.tone === 'success' ? 'cd-chip--success' : hhBadge.tone === 'danger' ? 'cd-chip--danger' : hhBadge.tone === 'warning' ? 'cd-chip--warning' : ''}`}>
                        {hhBadge.label}
                      </span>
                    ) : null}
                    {hhSummary.last_hh_sync_at ? (
                      <span className="cd-chip">sync {formatDateTime(hhSummary.last_hh_sync_at)}</span>
                    ) : null}
                    {hhSummary.sync_error ? (
                      <span className="cd-chip cd-chip--danger" title={hhSummary.sync_error}>есть ошибка sync</span>
                    ) : null}
                  </div>

                  {hhAvailableActions.length > 0 ? (
                    <div className="cd-hh-panel__actions">
                      {hhAvailableActions.slice(0, 8).map((action) => (
                        <span key={action.id || action.name} className="cd-chip cd-chip--accent" title={action.resulting_employer_state?.name || undefined}>
                          {action.name || action.id}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  {hhSummary.recent_jobs && hhSummary.recent_jobs.length > 0 ? (
                    <div className="cd-hh-panel__jobs">
                      <div className="cd-hh-card__label">Последние HH sync jobs</div>
                      <div className="cd-hh-panel__job-list">
                        {hhSummary.recent_jobs.slice(0, 3).map((job) => (
                          <div key={job.id} className="cd-hh-job">
                            <span className="cd-hh-job__title">{job.job_type}</span>
                            <span className={`cd-chip ${job.status === 'done' ? 'cd-chip--success' : job.status === 'dead' ? 'cd-chip--danger' : job.status === 'running' ? 'cd-chip--warning' : ''}`}>
                              {job.status}
                            </span>
                            <span className="cd-hh-job__meta">
                              #{job.id}
                              {job.finished_at ? ` · ${formatDateTime(job.finished_at)}` : ''}
                              {job.attempts ? ` · попыток ${job.attempts}` : ''}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </>
              ) : null}
            </div>
          )}

        {/* ── Pipeline & Status Center (Funnel) ── */}
        <div className="glass panel cd-pipeline app-page__section">
          <div className="cd-section-header app-page__section-head">
            <h2 className="cd-section-title">Воронка</h2>
          </div>

          {pipelineStages.length > 0 && (
            <div className="cd-pipeline__stages">
              {pipelineStages.map((stage, idx) => {
                const state = stage.state || 'pending'
                return (
                  <div key={stage.key || idx} className={`cd-pipeline__stage cd-pipeline__stage--${state}`}>
                    <div className="cd-pipeline__stage-dot" />
                    <div className="cd-pipeline__stage-label">{stage.label}</div>
                    {idx < pipelineStages.length - 1 && <div className="cd-pipeline__connector" />}
                  </div>
                )
              })}
            </div>
          )}

          <div className="cd-pipeline__actions" data-testid="candidate-actions" ref={pipelineActionsRef}>
            {canScheduleInterview && (
              <button className="ui-btn ui-btn--primary" onClick={() => setShowScheduleSlotModal(true)}>
                {scheduleLabel}
              </button>
            )}

            {test2Action && (
              <button
                className={`ui-btn ${canSendTest2 ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
                onClick={() => canSendTest2 && onActionClick(test2Action)}
                disabled={!canSendTest2 || actionMutation.isPending}
              >
                Отправить Тест 2
              </button>
            )}

            {canScheduleIntroDay && (
              <button className="ui-btn ui-btn--primary" onClick={() => setShowScheduleIntroDayModal(true)}>
                Назначить ознакомительный день
              </button>
            )}

            {inlineActions.map((action) => (
              <button
                key={action.key}
                className={`ui-btn ${action.variant === 'primary' ? 'ui-btn--primary' : action.variant === 'danger' ? 'ui-btn--danger' : 'ui-btn--ghost'}`}
                onClick={() => onActionClick(action)}
                disabled={actionMutation.isPending}
              >
                {action.label}
              </button>
            ))}
            {overflowActions.length > 0 && (
              <details className="ui-disclosure cd-actions-overflow" data-testid="candidate-actions-overflow">
                <summary className="ui-disclosure__trigger">Ещё действия</summary>
                <div className="ui-disclosure__content cd-actions-overflow__content">
                  {overflowActions.map((action) => (
                    <button
                      key={action.key}
                      className={`ui-btn ${action.variant === 'primary' ? 'ui-btn--primary' : action.variant === 'danger' ? 'ui-btn--danger' : 'ui-btn--ghost'}`}
                      onClick={() => onActionClick(action)}
                      disabled={actionMutation.isPending}
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              </details>
            )}

            {rejectAction && (
              <button
                className="ui-btn ui-btn--danger"
                onClick={() => onActionClick(rejectAction)}
                disabled={actionMutation.isPending}
              >
                {rejectAction.label}
              </button>
            )}

            {actionMessage && <p className="subtitle subtitle--center cd-action-message">{actionMessage}</p>}
          </div>

          {detail.reschedule_request && rescheduleRequest && (
            <div className="cd-slot-card glass">
              <div className="cd-slot-card__type">Перенос</div>
              <div className="cd-slot-card__main">
                <div className="cd-slot-card__time">{rescheduleRequest.summary}</div>
                <div className="cd-slot-card__details">
                  <span>Запрос от {formatDateTime(detail.reschedule_request.requested_at)}</span>
                  {rescheduleRequest.comment ? <span>{rescheduleRequest.comment}</span> : null}
                </div>
              </div>
              <button
                className="ui-btn ui-btn--ghost ui-btn--sm"
                onClick={() => setShowScheduleSlotModal(true)}
                disabled={!canScheduleInterview}
              >
                Предложить другое время
              </button>
            </div>
          )}
        </div>

        {/* ── AI Copilot ── */}
        <div className="glass panel cd-ai app-page__section">
          <div className="cd-section-header app-page__section-head">
            <h2 className="cd-section-title">AI Copilot</h2>
            <div className="cd-ai__actions">
              {aiSummaryQuery.data && (
                <span className={`cd-chip cd-chip--small ${aiSummaryQuery.data.cached ? '' : 'cd-chip--accent'}`}>
                  {aiSummaryQuery.data.cached ? 'Кэш' : 'Новый'}
                </span>
              )}
              {!aiSummaryQuery.data ? (
                <button
                  className="ui-btn ui-btn--ghost"
                  onClick={() => aiSummaryQuery.refetch()}
                  disabled={aiSummaryQuery.isFetching}
                >
                  {aiSummaryQuery.isFetching ? 'Генерация…' : 'Сгенерировать'}
                </button>
              ) : (
                <button
                  className="ui-btn ui-btn--ghost"
                  onClick={() => aiRefreshMutation.mutate()}
                  disabled={aiRefreshMutation.isPending}
                  title="Форс-обновление сводки"
                >
                  {aiRefreshMutation.isPending ? 'Обновление…' : 'Обновить'}
                </button>
              )}
              <button
                className="ui-btn ui-btn--ghost"
                onClick={() => setShowInterviewScriptModal(true)}
              >
                Скрипт интервью
              </button>
            </div>
          </div>

          <details className="ui-disclosure cd-ai__disclosure">
            <summary className="ui-disclosure__trigger" data-testid="cd-ai-section-toggle-coach">Recruiter Coach</summary>
            <div className="ui-disclosure__content">
              <div className="cd-ai-coach__toolbar">
              {!aiCoachData ? (
                <button
                  className="ui-btn ui-btn--ghost"
                  onClick={() => aiCoachQuery.refetch()}
                  disabled={aiCoachQuery.isFetching}
                >
                  {aiCoachQuery.isFetching ? 'Генерация…' : 'Сгенерировать Coach'}
                </button>
              ) : (
                <button
                  className="ui-btn ui-btn--ghost"
                  onClick={() => aiCoachRefreshMutation.mutate()}
                  disabled={aiCoachRefreshMutation.isPending}
                >
                  {aiCoachRefreshMutation.isPending ? 'Обновление…' : 'Обновить Coach'}
                </button>
              )}
              <div className="cd-ai-drafts__modes">
                {(['short', 'neutral', 'supportive'] as const).map((mode) => (
                  <button
                    key={`coach-${mode}`}
                    type="button"
                    className={`cd-ai-drafts__mode ${aiDraftMode === mode ? 'cd-ai-drafts__mode--active' : ''}`}
                    onClick={() => {
                      setAiDraftMode(mode)
                      aiCoachDraftsMutation.mutate(mode)
                    }}
                    disabled={aiCoachDraftsMutation.isPending || !aiCoachData}
                  >
                    {mode === 'short' ? 'Коротко' : mode === 'neutral' ? 'Нейтр.' : 'Поддерж.'}
                  </button>
                ))}
              </div>
              </div>

              {aiCoachError && (
                <p className="subtitle subtitle--danger">
                  AI Coach: {aiCoachError.message}
                </p>
              )}
              {aiCoachDraftsMutation.error && (
                <p className="subtitle subtitle--danger">
                  AI Coach drafts: {(aiCoachDraftsMutation.error as Error).message}
                </p>
              )}
              {!aiCoachData && !aiCoachQuery.isFetching && !aiCoachRefreshMutation.isPending && (
                <p className="subtitle">Сгенерируйте рекомендации по релевантности, рискам и вопросам интервью.</p>
              )}

              {aiCoachData && (
                <div className="cd-ai-coach__grid">
                <div className="cd-ai__card">
                  <div className="cd-ai__label">Релевантность</div>
                  <div className="cd-ai-fit">
                    <div className="cd-ai-fit__score">
                      {aiCoachData.relevance_score != null ? `${aiCoachData.relevance_score}/100` : '—'}
                    </div>
                    <div className={`cd-ai-fit__badge cd-ai-fit__badge--${aiCoachData.relevance_level || 'unknown'}`}>
                      {aiCoachData.relevance_level === 'high'
                        ? 'Высокая'
                        : aiCoachData.relevance_level === 'medium'
                          ? 'Средняя'
                          : aiCoachData.relevance_level === 'low'
                            ? 'Низкая'
                            : 'Неизвестно'}
                    </div>
                  </div>
                  {aiCoachData.rationale && <div className="cd-ai__text">{aiCoachData.rationale}</div>}
                </div>

                <div className="cd-ai__card">
                  <div className="cd-ai__label">Следующий шаг</div>
                  <div className="cd-ai__text">{aiCoachData.next_best_action || '—'}</div>
                </div>

                <div className="cd-ai__card">
                  <div className="cd-ai__label">Сильные стороны</div>
                  {aiCoachStrengths.length === 0 ? (
                    <div className="subtitle">Нет данных</div>
                  ) : (
                    <ul className="cd-ai__list">
                      {aiCoachStrengths.slice(0, 5).map((s) => (
                        <li key={`coach-strength-${s.key}`} className="cd-ai__point cd-ai__point--strength">
                          <div className="cd-ai__point-title">{s.label}</div>
                          <div className="cd-ai__point-text">{s.evidence}</div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="cd-ai__card">
                  <div className="cd-ai__label">Риски</div>
                  {aiCoachRisks.length === 0 ? (
                    <div className="subtitle">Нет рисков</div>
                  ) : (
                    <ul className="cd-ai__list">
                      {aiCoachRisks.slice(0, 5).map((r) => (
                        <li key={`coach-risk-${r.key}`} className={`cd-ai__risk cd-ai__risk--${r.severity}`}>
                          <div className="cd-ai__risk-title">{r.label}</div>
                          <div className="cd-ai__risk-text">{r.explanation}</div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="cd-ai__card">
                  <div className="cd-ai__label">Вопросы интервью</div>
                  {aiCoachQuestions.length === 0 ? (
                    <div className="subtitle">Нет предложенных вопросов</div>
                  ) : (
                    <ol className="cd-ai__list cd-ai__list--ordered">
                      {aiCoachQuestions.slice(0, 6).map((q, idx) => (
                        <li key={`coach-question-${idx}`} className="cd-ai__action">
                          <div className="cd-ai__action-text">{q}</div>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>

                <div className="cd-ai__card cd-ai__card--span">
                  <div className="cd-ai__label">Черновики сообщений</div>
                  {aiCoachDraftsMutation.isPending && <div className="subtitle">Генерация черновиков…</div>}
                  {aiCoachDraftItems.length === 0 ? (
                    <div className="subtitle">Нет черновиков. Нажмите один из режимов выше.</div>
                  ) : (
                    <div className="cd-ai-drafts__list">
                      {aiCoachDraftItems.map((d, idx) => (
                        <div key={`coach-draft-${idx}-${d.reason}`} className="cd-ai-drafts__item">
                          <div className="cd-ai-drafts__text">{d.text}</div>
                          <div className="cd-ai-drafts__actions">
                            <span className="cd-ai-drafts__reason">{d.reason}</span>
                            <button
                              type="button"
                              className="ui-btn ui-btn--primary"
                              onClick={() => {
                                setChatText(d.text)
                                setIsChatOpen(true)
                                requestAnimationFrame(() => chatTextareaRef.current?.focus())
                              }}
                            >
                              Вставить в чат
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                </div>
              )}
            </div>
          </details>

          {aiSummaryError && (
            <p className="subtitle subtitle--danger">
              AI: {aiSummaryError.message}
            </p>
          )}

          {!aiSummaryData && !aiSummaryQuery.isFetching && !aiRefreshMutation.isPending && (
            <p className="subtitle">
              Сгенерируйте краткую сводку и рекомендации по следующему шагу.
            </p>
          )}

          {aiSummaryData && (
            <>
              <div className="cd-ai__grid">
                <div className="cd-ai__card">
                  <div className="cd-ai__label">TL;DR</div>
                  <div className="cd-ai__text">{aiSummaryData.tldr}</div>
                </div>

                <div className="cd-ai__card">
                  <div className="cd-ai__label">Релевантность</div>
                  <div className="cd-ai-fit">
                    <div className="cd-ai-fit__score">{aiFit?.score != null ? `${aiFit.score}/100` : '—'}</div>
                    <div className={`cd-ai-fit__badge cd-ai-fit__badge--${aiFit?.level || 'unknown'}`}>
                      {aiFit?.level === 'high' ? 'Высокая' : aiFit?.level === 'medium' ? 'Средняя' : aiFit?.level === 'low' ? 'Низкая' : 'Неизвестно'}
                    </div>
                  </div>
                  {aiFit?.criteria_used === false && (
                    <div className="subtitle">Критерии города не заданы, оценка ограничена.</div>
                  )}
                  {aiFit?.rationale && <div className="cd-ai__text">{aiFit.rationale}</div>}
                </div>
              </div>
              <details className="ui-disclosure cd-ai__disclosure">
                <summary className="ui-disclosure__trigger" data-testid="cd-ai-section-toggle-analysis">Развернуть полный AI анализ</summary>
                <div className="ui-disclosure__content">
                  <div className="cd-ai__grid">
              {aiSummaryData.vacancy_fit && (
                <div className="cd-ai__card cd-ai__card--span">
                  <div className="cd-ai__label">Оценка релевантности вакансии</div>
                  <div className="cd-ai-fit cd-ai-fit--spaced">
                    <div className="cd-ai-fit__score">{aiSummaryData.vacancy_fit.score != null ? `${aiSummaryData.vacancy_fit.score}/100` : '—'}</div>
                    <div className={`cd-ai-fit__badge cd-ai-fit__badge--${aiSummaryData.vacancy_fit.level || 'unknown'}`}>
                      {aiSummaryData.vacancy_fit.level === 'high' ? 'Высокая' : aiSummaryData.vacancy_fit.level === 'medium' ? 'Средняя' : aiSummaryData.vacancy_fit.level === 'low' ? 'Низкая' : 'Неизвестно'}
                    </div>
                    {aiSummaryData.vacancy_fit.criteria_source && aiSummaryData.vacancy_fit.criteria_source !== 'none' && (
                      <span className="cd-chip cd-chip--small">
                        {aiSummaryData.vacancy_fit.criteria_source === 'both' ? 'критерии + регламент' : aiSummaryData.vacancy_fit.criteria_source === 'city_criteria' ? 'критерии города' : 'регламент'}
                      </span>
                    )}
                  </div>
                  {aiSummaryData.vacancy_fit.summary && <div className="cd-ai__text cd-ai__text--spaced">{aiSummaryData.vacancy_fit.summary}</div>}
                  {(aiSummaryData.vacancy_fit.evidence || []).length > 0 && (
                    <ul className="cd-ai__list">
                      {(aiSummaryData.vacancy_fit.evidence || []).map((e, i) => (
                        <li key={i} className={`cd-ai__point cd-ai__point--${e.assessment === 'positive' ? 'strength' : e.assessment === 'negative' ? 'weakness' : 'neutral'}`}>
                          <div className="cd-ai__point-title">{e.factor}</div>
                          <div className="cd-ai__point-text">{e.detail}</div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {aiCriteriaChecklist.length > 0 && (
                <div className="cd-ai__card cd-ai__card--span">
                  <div className="cd-ai__label">Чек-лист критериев</div>
                  <ul className="cd-ai__list">
                    {aiCriteriaChecklist.map((c) => (
                      <li key={c.key} className={`cd-ai-crit cd-ai-crit--${c.status || 'unknown'}`}>
                        <div className="cd-ai-crit__top">
                          <span className={`cd-ai-crit__badge cd-ai-crit__badge--${c.status || 'unknown'}`}>
                            {c.status === 'met' ? 'ОК' : c.status === 'not_met' ? 'Не ок' : 'Неясно'}
                          </span>
                          <div className="cd-ai-crit__title">{c.label}</div>
                        </div>
                        <div className="cd-ai-crit__text">{c.evidence}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="cd-ai__card">
                <div className="cd-ai__label">Сильные стороны</div>
                {aiStrengths.length === 0 ? (
                  <div className="subtitle">Нет явных сильных сторон по текущим данным.</div>
                ) : (
                  <ul className="cd-ai__list">
                    {aiStrengths.map((s) => (
                      <li key={s.key} className="cd-ai__point cd-ai__point--strength">
                        <div className="cd-ai__point-title">{s.label}</div>
                        <div className="cd-ai__point-text">{s.evidence}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="cd-ai__card">
                <div className="cd-ai__label">Зоны роста</div>
                {aiWeaknesses.length === 0 ? (
                  <div className="subtitle">Критичных зон роста не выявлено.</div>
                ) : (
                  <ul className="cd-ai__list">
                    {aiWeaknesses.map((w) => (
                      <li key={w.key} className="cd-ai__point cd-ai__point--weakness">
                        <div className="cd-ai__point-title">{w.label}</div>
                        <div className="cd-ai__point-text">{w.evidence}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="cd-ai__card">
                <div className="cd-ai__label">Риски</div>
                {aiRisks.length === 0 ? (
                  <div className="subtitle">Явных рисков не найдено.</div>
                ) : (
                  <ul className="cd-ai__list">
                    {aiRisks.map((r) => (
                      <li key={r.key} className={`cd-ai__risk cd-ai__risk--${r.severity}`}>
                        <div className="cd-ai__risk-title">{r.label}</div>
                        <div className="cd-ai__risk-text">{r.explanation}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="cd-ai__card">
                <div className="cd-ai__label">Следующие шаги</div>
                {aiNextActions.length === 0 ? (
                  <div className="subtitle">Нет рекомендаций.</div>
                ) : (
                  <ol className="cd-ai__list cd-ai__list--ordered">
                    {aiNextActions.map((a) => (
                      <li key={a.key} className="cd-ai__action">
                        <div className="cd-ai__action-title">{a.label}</div>
                        <div className="cd-ai__action-text">{a.rationale}</div>
                      </li>
                    ))}
                  </ol>
                )}
              </div>

              {aiTestInsights && (
                <div className="cd-ai__card cd-ai__card--span">
                  <div className="cd-ai__label">Анализ тестов</div>
                  <div className="cd-ai__text">{aiTestInsights}</div>
                </div>
              )}

              {aiSummaryData.notes && (
                <div className="cd-ai__card cd-ai__card--span">
                  <div className="cd-ai__label">Заметки</div>
                  <div className="cd-ai__text">{aiSummaryData.notes}</div>
                </div>
              )}
                  </div>
                </div>
              </details>
            </>
          )}
        </div>
        </>)}

        {/* ── Slots Table ── */}
        {showTimelineSection && (
        <div className="glass panel app-page__section">
          <div className="cd-section-header app-page__section-head">
            <h2 className="cd-section-title">Слоты и интервью</h2>
            {detail.telegram_id && !hasUpcomingSlot && (
              <button className="ui-btn ui-btn--ghost" onClick={() => setShowScheduleSlotModal(true)}>
                + Предложить время
              </button>
            )}
          </div>
          {slots.length === 0 && <p className="subtitle">Слоты не найдены</p>}
          {slots.length > 0 && (
            <div className="cd-slots-list">
              {slots.map((slot) => (
                <div key={slot.id} className="cd-slot-card glass">
                  <div className="cd-slot-card__type">
                    {slot.purpose === 'intro_day' ? 'ОД' : 'Интервью'}
                  </div>
                  <div className="cd-slot-card__main">
                    <div className="cd-slot-card__time">{formatSlotTime(slot.start_utc, slot.candidate_tz)}</div>
                    <div className="cd-slot-card__details">
                      {slot.recruiter_name && <span>{slot.recruiter_name}</span>}
                      {slot.city_name && <span>{slot.city_name}</span>}
                    </div>
                  </div>
                  <SlotStatusBadge status={slot.status} />
                </div>
              ))}
            </div>
          )}
        </div>
        )}

        {/* ── Tests ── */}
        {showTestsSection && (
        <div
          id="tests"
          ref={testsSectionRef}
          className="glass panel app-page__section"
          data-testid="candidate-tests-section"
        >
          <div className="cd-section-header app-page__section-head">
            <h2 className="cd-section-title">Тесты</h2>
          </div>
          {testSections.length === 0 && <p className="subtitle">Данные по тестам отсутствуют.</p>}
          {testSections.length > 0 && (
            <div className="cd-tests-grid">
              {testSections.map((section) => (
                <div key={section.key} className="cd-test-card glass">
                  <div className="cd-test-card__header">
                    <span className="cd-test-card__title">{section.title}</span>
                    <span className={`cd-test-status cd-test-status--${section.status || 'unknown'}`}>
                      {section.status_label || section.status || '—'}
                    </span>
                  </div>
                  {section.summary && <div className="cd-test-card__summary">{section.summary}</div>}
                  {section.details?.stats && (
                    <TestScoreBar
                      correct={section.details.stats.correct_answers ?? 0}
                      total={section.details.stats.total_questions ?? 0}
                      score={section.details.stats.final_score}
                    />
                  )}
                  {section.details?.stats && (
                    <div className="cd-test-card__extra">
                      {typeof section.details.stats.total_time === 'number' && (
                        <span>Время: {Math.round(section.details.stats.total_time / 60)} мин</span>
                      )}
                      {typeof section.details.stats.overtime_questions === 'number' && section.details.stats.overtime_questions > 0 && (
                        <span>Просрочено: {section.details.stats.overtime_questions}</span>
                      )}
                    </div>
                  )}
                  {section.report_url && (
                    <button
                      type="button"
                      className="cd-test-card__report"
                      onClick={() => setReportPreview({ title: section.title || 'Отчёт', url: section.report_url || '' })}
                    >
                      Подробный отчёт
                    </button>
                  )}
                  {section.history && section.history.length > 1 && (
                    <details className="cd-test-card__history">
                      <summary>История попыток ({section.history.length})</summary>
                      <div className="cd-test-card__history-list">
                        {section.history.map((h) => (
                          <button
                            key={h.id}
                            type="button"
                            className="cd-test-card__history-item cd-test-card__history-item--button"
                            onClick={() => setAttemptPreview({ testTitle: section.title, attempt: h })}
                          >
                            <span>{formatDateTime(h.completed_at)}</span>
                            <span>{typeof h.final_score === 'number' ? h.final_score.toFixed(1) : '—'}</span>
                            {h.source && <span className="cd-chip cd-chip--small">{h.source}</span>}
                            <span className="cd-test-card__history-link">Открыть</span>
                          </button>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        )}
        </>)}
        {detail && isMobile && (
          <div className="cd-mobile-actions glass">
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={() => {
                setMobileTab('profile')
                requestAnimationFrame(() =>
                  pipelineActionsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }),
                )
              }}
            >
              Сменить статус
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--primary ui-btn--sm"
              onClick={() => {
                setMobileTab('chat')
                setIsChatOpen(true)
              }}
            >
              Написать
            </button>
          </div>
        )}
      </div>

      {/* Modals */}
      {showInterviewScriptModal && (
        <InterviewScriptModal
          candidateId={candidateId}
          onClose={() => setShowInterviewScriptModal(false)}
        />
      )}

      {showScheduleSlotModal && detail && (
        <ScheduleSlotModal
          candidateId={candidateId}
          candidateFio={detail.fio || `Кандидат #${candidateId}`}
          candidateCity={detail.city}
          onClose={() => setShowScheduleSlotModal(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['candidate-detail', candidateId] })
            queryClient.invalidateQueries({ queryKey: ['candidates'] })
            setActionMessage('Предложение отправлено кандидату')
          }}
        />
      )}

      {showScheduleIntroDayModal && (
        <ScheduleIntroDayModal
          candidateId={candidateId}
          candidateFio={detailQuery.data?.fio || 'Кандидат'}
          candidateCity={detailQuery.data?.city}
          introDayTemplate={detailQuery.data?.intro_day_template}
          onClose={() => setShowScheduleIntroDayModal(false)}
          onSuccess={() => {
            detailQuery.refetch()
            queryClient.invalidateQueries({ queryKey: ['candidates'] })
            setActionMessage('Ознакомительный день назначен')
          }}
        />
      )}

      {showRejectModal && (
        <RejectModal
          candidateId={candidateId}
          actionKey={showRejectModal.actionKey}
          title={showRejectModal.title}
          onClose={() => setShowRejectModal(null)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['candidate-detail', candidateId] })
            queryClient.invalidateQueries({ queryKey: ['candidates'] })
          }}
        />
      )}

      {reportPreview && (
        <ReportPreviewModal
          title={reportPreview.title}
          url={reportPreview.url}
          onClose={() => setReportPreview(null)}
        />
      )}

      {attemptPreview && (
        <TestAttemptModal
          testTitle={attemptPreview.testTitle}
          attempt={attemptPreview.attempt}
          onClose={() => setAttemptPreview(null)}
        />
      )}

      {isChatOpen && (
        <ModalPortal>
          <div className="drawer-overlay" onClick={(e) => e.target === e.currentTarget && setIsChatOpen(false)}>
            <aside className="candidate-chat-drawer glass" onClick={(e) => e.stopPropagation()}>
              <header className="candidate-chat-drawer__header">
                <div>
                  <h3 className="candidate-chat-drawer__title">Чат с кандидатом</h3>
                  <p className="subtitle">Ответ будет отправлен через Telegram</p>
                </div>
                <button className="ui-btn ui-btn--ghost" onClick={() => setIsChatOpen(false)}>Закрыть</button>
              </header>

              <div className="candidate-chat-drawer__body">
                {chatQuery.isLoading && <p className="subtitle">Загрузка сообщений…</p>}
                {chatQuery.isError && (
                  <ApiErrorBanner
                    error={chatQuery.error}
                    title="Не удалось загрузить сообщения"
                    onRetry={() => chatQuery.refetch()}
                    className="glass panel"
                  />
                )}
                {chatMessages.length === 0 && !chatQuery.isLoading && (
                  <p className="subtitle">Сообщений пока нет.</p>
                )}
                {chatMessages.length > 0 && (
                  <div className="candidate-chat-drawer__messages" ref={chatMessagesRef}>
                    {chatMessages.map((msg) => {
                      const isOutbound = msg.direction === 'outbound'
                      const isBot = isOutbound && (msg.author || '').trim().toLowerCase() === 'bot'
                      const authorLabel = isBot
                        ? 'Бот'
                        : isOutbound
                          ? (msg.author || 'Вы')
                          : (msg.author || 'Кандидат')

                      return (
                        <div
                          key={msg.id}
                          className={`candidate-chat-message ${isOutbound ? 'candidate-chat-message--outbound' : 'candidate-chat-message--inbound'} ${isBot ? 'candidate-chat-message--bot' : ''}`}
                        >
                          <div className="candidate-chat-message__text">{msg.text}</div>
                          <div className="candidate-chat-message__meta">
                            <span className="candidate-chat-message__author">{authorLabel}</span>
                            <span> · </span>
                            <span>{new Date(msg.created_at).toLocaleString('ru-RU', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}</span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              <div className="candidate-chat-drawer__footer">
                {aiDraftsOpen && (
                  <div className="cd-ai-drafts glass">
                    <div className="cd-ai-drafts__header">
                      <div className="cd-ai-drafts__title">Черновики ответа</div>
                      <div className="cd-ai-drafts__modes">
                        {(['short', 'neutral', 'supportive'] as const).map((mode) => (
                          <button
                            key={mode}
                            type="button"
                            className={`cd-ai-drafts__mode ${aiDraftMode === mode ? 'cd-ai-drafts__mode--active' : ''}`}
                            onClick={() => {
                              setAiDraftMode(mode)
                              aiDraftsMutation.mutate(mode)
                            }}
                            disabled={aiDraftsMutation.isPending}
                          >
                            {mode === 'short' ? 'Коротко' : mode === 'neutral' ? 'Нейтр.' : 'Поддерж.'}
                          </button>
                        ))}
                      </div>
                      <button type="button" className="ui-btn ui-btn--ghost" onClick={() => setAiDraftsOpen(false)}>
                        Закрыть
                      </button>
                    </div>

                    {aiDraftsMutation.isPending && <p className="subtitle">Генерация…</p>}
                    {aiDraftsMutation.error && (
                      <p className="subtitle subtitle--danger">
                        AI: {(aiDraftsMutation.error as Error).message}
                      </p>
                    )}
                    {aiDraftsMutation.data?.analysis && (
                      <div className="cd-ai-drafts__analysis">
                        <div className="cd-ai-drafts__analysis-label">Анализ переписки</div>
                        <div className="cd-ai-drafts__analysis-text">{aiDraftsMutation.data.analysis}</div>
                      </div>
                    )}
                    {aiDraftsMutation.data?.drafts?.length ? (
                      <div className="cd-ai-drafts__list">
                        {aiDraftsMutation.data.drafts.map((d, idx) => (
                          <div key={`${idx}-${d.reason}`} className="cd-ai-drafts__item">
                            <div className="cd-ai-drafts__text">{d.text}</div>
                            <div className="cd-ai-drafts__actions">
                              <span className="cd-ai-drafts__reason">{d.reason}</span>
                              <button
                                type="button"
                                className="ui-btn ui-btn--primary"
                                onClick={() => {
                                  setChatText(d.text)
                                  setAiDraftsOpen(false)
                                  requestAnimationFrame(() => chatTextareaRef.current?.focus())
                                }}
                              >
                                Вставить
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )}
                <textarea
                  ref={chatTextareaRef}
                  rows={3}
                  value={chatText}
                  onChange={(e) => setChatText(e.target.value)}
                  placeholder="Написать сообщение…"
                  data-testid="chat-textarea"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      const text = chatText.trim()
                      if (text) sendMutation.mutate(text)
                    }
                  }}
                />
                <div className="candidate-chat-drawer__actions">
                  <button
                    type="button"
                    className="ui-btn ui-btn--ghost"
                    onClick={() => {
                      const next = !aiDraftsOpen
                      setAiDraftsOpen(next)
                      if (next) aiDraftsMutation.mutate(aiDraftMode)
                    }}
                    disabled={aiDraftsMutation.isPending}
                  >
                    Черновики ответа
                  </button>
                  <button
                    className="ui-btn ui-btn--primary"
                    onClick={() => chatText.trim() && sendMutation.mutate(chatText.trim())}
                    disabled={sendMutation.isPending}
                  >
                    {sendMutation.isPending ? 'Отправка…' : 'Отправить'}
                  </button>
                </div>
              </div>
            </aside>
          </div>
        </ModalPortal>
      )}
    </RoleGuard>
  )
}
