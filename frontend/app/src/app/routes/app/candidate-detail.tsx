import { Link, useParams } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, useMemo, useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
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
    stats?: {
      total_questions?: number
      correct_answers?: number
      overtime_questions?: number
      raw_score?: number
      final_score?: number
      total_time?: number
    }
  }
  history?: Array<{
    id: number
    completed_at?: string | null
    raw_score?: number
    final_score?: number
    source?: string
  }>
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
  slot_pending: { label: 'Ожидает подтверждения времени', tone: 'info' },
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

function normalizeTelegramUsername(username?: string | null): string | null {
  if (!username) return null
  const cleaned = username.trim().replace(/^@/, '')
  return cleaned || null
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

type AISummary = {
  tldr: string
  fit?: AIFit | null
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

type AIDraftsResponse = {
  ok: boolean
  cached: boolean
  input_hash: string
  analysis?: string | null
  drafts: AIDraftItem[]
  used_context?: Record<string, any>
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
    BOOKED: { label: 'Забронирован', cls: 'cd-slot-badge--booked' },
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
      <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal">
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Отчёт · {title}</h2>
              <p className="modal__subtitle">{isPdf ? 'PDF-документ' : 'Текстовый отчёт'}</p>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <a href={url} className="ui-btn ui-btn--ghost" target="_blank" rel="noopener">
                Скачать
              </a>
              <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
            </div>
          </div>

          <div className="modal__body">
            {status === 'loading' && <p className="subtitle">Загрузка отчёта...</p>}
            {status === 'error' && (
              <div className="glass panel--tight" style={{ borderColor: 'rgba(240, 115, 115, 0.3)' }}>
                <p style={{ color: '#f07373', margin: 0 }}>{error}</p>
              </div>
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

    queryFn: () => apiFetch('/cities'),

  })



  const cities = citiesQuery.data || []



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



  const mutation = useMutation({

    mutationFn: async () => {

      return apiFetch(`/candidates/${candidateId}/schedule-slot`, {

        method: 'POST',

        body: JSON.stringify({

          city_id: resolvedCityId,

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



          {error && (

            <div className="glass panel--tight" style={{ borderColor: 'rgba(240, 115, 115, 0.3)' }}>

              <p style={{ color: '#f07373', margin: 0 }}>{error}</p>

            </div>

          )}



          <div className="modal__body">

            <p className="text-muted text-sm" style={{ marginTop: 0 }}>
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

                  <span className="form-group__label">Время</span>

                  <input

                    type="time"

                    value={form.time}

                    onChange={(e) => setForm({ ...form, time: e.target.value })}

                  />

                </label>

              </div>



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
  const [template, setTemplate] = useState<string>('')

  // Helper to generate message
  const generateMessage = (tmpl: string, dateStr: string, timeStr: string) => {
    if (!tmpl) return ''
    let msg = tmpl.replace(/\[Имя\]/g, candidateFio.split(' ')[1] || candidateFio.split(' ')[0] || 'Кандидат') // Try to get first name
    
    // Format date: YYYY-MM-DD -> dd.mm
    let formattedDate = dateStr
    try {
        const [y, m, d] = dateStr.split('-')
        if (y && m && d) formattedDate = `${d}.${m}`
    } catch (e) {}

    msg = msg.replace(/\[Дата\]/g, formattedDate)
    msg = msg.replace(/\[Время\]/g, timeStr)
    return msg
  }

  useEffect(() => {
    if (introDayTemplate) {
      setTemplate(introDayTemplate)
      setForm(prev => ({ ...prev, customMessage: generateMessage(introDayTemplate, prev.date, prev.time) }))
    } else {
      apiFetch('/templates?key=intro_day_invitation')
        .then((data: any) => {
          if (data && data.text) {
            setTemplate(data.text)
            setForm(prev => ({ ...prev, customMessage: generateMessage(data.text, prev.date, prev.time) }))
          }
        })
        .catch(() => {
          // Ignore template fetch errors
        })
    }
  }, [introDayTemplate])

  // Update message when date/time changes
  useEffect(() => {
      if (template) {
          setForm(prev => ({ ...prev, customMessage: generateMessage(template, prev.date, prev.time) }))
      }
  }, [form.date, form.time, template])

  const mutation = useMutation({
    mutationFn: async () => {
      return apiFetch(`/candidates/${candidateId}/schedule-intro-day`, {
        method: 'POST',
        body: JSON.stringify({
          date: form.date,
          time: form.time,
          custom_message: form.customMessage,
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

          {error && (
            <div className="glass panel--tight" style={{ borderColor: 'rgba(240, 115, 115, 0.3)' }}>
              <p style={{ color: '#f07373', margin: 0 }}>{error}</p>
            </div>
          )}

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
                <span className="form-group__label">Время</span>
                <input
                  type="time"
                  value={form.time}
                  onChange={(e) => setForm({ ...form, time: e.target.value })}
                />
              </label>
            </div>
            
            <label className="form-group" style={{ marginTop: 12 }}>
              <span className="form-group__label">Сообщение кандидату</span>
              <textarea
                rows={6}
                value={form.customMessage}
                onChange={(e) => setForm({ ...form, customMessage: e.target.value })}
                placeholder="Текст приглашения..."
                className="ui-input"
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.2)', color: 'inherit' }}
              />
            </label>

            <p className="subtitle" style={{ marginTop: 12 }}>
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
      return apiFetch(`/candidates/${candidateId}/actions/${actionKey}`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
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

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal modal--sm">
          <div className="modal__header">
            <h2 className="modal__title">{title || 'Укажите причину отказа'}</h2>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
          </div>
          <div className="modal__body">
            {error && <p style={{ color: '#f07373', marginBottom: 12 }}>{error}</p>}
            <textarea
              rows={4}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Причина отказа..."
              className="ui-input"
              autoFocus
              style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.2)', color: 'inherit' }}
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

export function CandidateDetailPage() {
  const queryClient = useQueryClient()
  const params = useParams({ from: '/app/candidates/$candidateId' })
  const candidateId = Number(params.candidateId)
  const [chatText, setChatText] = useState('')
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [showScheduleSlotModal, setShowScheduleSlotModal] = useState(false)
  const [showScheduleIntroDayModal, setShowScheduleIntroDayModal] = useState(false)
  const [showRejectModal, setShowRejectModal] = useState<{ actionKey: string; title?: string } | null>(null)
  const [reportPreview, setReportPreview] = useState<ReportPreviewState | null>(null)
  const [isChatOpen, setIsChatOpen] = useState(false)
  const chatMessagesRef = useRef<HTMLDivElement | null>(null)
  const chatTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const [aiDraftsOpen, setAiDraftsOpen] = useState(false)
  const [aiDraftMode, setAiDraftMode] = useState<'short' | 'neutral' | 'supportive'>('neutral')

  const detailQuery = useQuery<CandidateDetail>({
    queryKey: ['candidate-detail', candidateId],
    queryFn: () => apiFetch(`/candidates/${candidateId}`),
  })

  const chatQuery = useQuery<ChatPayload>({
    queryKey: ['candidate-chat', candidateId],
    queryFn: () => apiFetch(`/candidates/${candidateId}/chat?limit=50`),
    enabled: isChatOpen,
    refetchInterval: isChatOpen ? 3000 : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: isChatOpen,
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

  const aiSummaryQuery = useQuery<AISummaryResponse>({
    queryKey: ['ai-summary', candidateId],
    queryFn: () => apiFetch(`/ai/candidates/${candidateId}/summary`),
    enabled: false,
    retry: false,
  })

  const aiRefreshMutation = useMutation({
    mutationFn: async () => apiFetch<AISummaryResponse>(`/ai/candidates/${candidateId}/summary/refresh`, { method: 'POST' }),
    onSuccess: (data) => {
      queryClient.setQueryData(['ai-summary', candidateId], data)
    },
  })

  const aiDraftsMutation = useMutation({
    mutationFn: async (mode: 'short' | 'neutral' | 'supportive') => {
      return apiFetch<AIDraftsResponse>(`/ai/candidates/${candidateId}/chat/drafts`, {
        method: 'POST',
        body: JSON.stringify({ mode }),
      })
    },
  })

  const actionMutation = useMutation({
    mutationFn: async ({ actionKey, payload }: { actionKey: string; payload?: any }) => {
      return apiFetch(`/candidates/${candidateId}/actions/${actionKey}`, {
        method: 'POST',
        body: payload ? JSON.stringify(payload) : undefined,
      })
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
  const rawTestSections = detail?.test_sections || []
  const testResultsMap = detail?.test_results || {}
  const testSections = useMemo(() => {
    if (rawTestSections.length > 0) return rawTestSections
    const entries = Object.entries(testResultsMap)
    if (entries.length === 0) return []
    return entries.map(([key, value]) => ({
      ...value,
      key,
      title: key === 'test1' ? 'Тест 1' : key === 'test2' ? 'Тест 2' : (value.title || key),
    }))
  }, [rawTestSections, testResultsMap])
  const test1Section = testSections.find((section) => section.key === 'test1')
  const test2Section = testSections.find((section) => section.key === 'test2')
  const chatMessages = (chatQuery.data?.messages || []).slice().reverse()
  const pipelineStages = detail?.pipeline_stages || []
  const lastChatMessage = chatMessages.length > 0 ? chatMessages[chatMessages.length - 1] : null

  const aiSummaryData = aiSummaryQuery.data?.summary || null
  const aiRisks = aiSummaryData?.risks || []
  const aiNextActions = aiSummaryData?.next_actions || []
  const aiFit = aiSummaryData?.fit || null
  const aiStrengths = aiSummaryData?.strengths || []
  const aiWeaknesses = aiSummaryData?.weaknesses || []
  const aiCriteriaChecklist = (aiSummaryData?.criteria_checklist || []).filter((c) => Boolean(c?.label || c?.evidence))
  const aiTestInsights = aiSummaryData?.test_insights || null
  const aiSummaryError = (aiSummaryQuery.error as Error | null) || (aiRefreshMutation.error as Error | null)

  useEffect(() => {
    if (!isChatOpen) return
    chatQuery.refetch()
  }, [isChatOpen, chatQuery.refetch])

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
        window.location.href = action.url
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

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className="page">
        {detailQuery.isLoading && <div className="glass panel" style={{ textAlign: 'center', padding: 48 }}><p className="subtitle">Загрузка...</p></div>}
        {detailQuery.isError && <div className="glass panel"><p style={{ color: '#f07373' }}>Ошибка: {(detailQuery.error as Error).message}</p></div>}

        {detail && (<>
        {/* ── Header Card ── */}
        <div className="glass panel cd-header">
          <div className="cd-header__top">
            <div className="cd-header__avatar">
              {(detail.fio || '?').charAt(0).toUpperCase()}
            </div>
            <div className="cd-header__info">
              <div className="cd-header__name-row">
                <h1 className="cd-header__name">{detail.fio || `Кандидат #${candidateId}`}</h1>
                {statusDisplay && (
                  <span className={`status-pill status-pill--${statusDisplay.tone}`}>
                    <span className={`cd-status-dot cd-status-dot--${statusDisplay.tone}`} />
                    {statusDisplay.label}
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
            <button className="cd-contact-btn" onClick={() => setIsChatOpen(true)} disabled={!detail.telegram_id}>
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
            {detail.telegram_id && (
              <span className="cd-contact-btn cd-contact-btn--disabled" style={{ marginLeft: 'auto' }}>
                <span className="cd-contact-btn__icon" style={{ fontSize: 10 }}>ID</span>
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

        {/* ── Pipeline & Status Center (Funnel) ── */}
        <div className="glass panel cd-pipeline">
          <div className="cd-section-header">
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

          <div className="cd-pipeline__actions" style={{ marginTop: 24, display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
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
                {test2Action.label}
              </button>
            )}

            {canScheduleIntroDay && (
              <button className="ui-btn ui-btn--primary" onClick={() => setShowScheduleIntroDayModal(true)}>
                Назначить ознакомительный день
              </button>
            )}

            {filteredActions.map((action) => (
              <button
                key={action.key}
                className={`ui-btn ${action.variant === 'primary' ? 'ui-btn--primary' : action.variant === 'danger' ? 'ui-btn--danger' : 'ui-btn--ghost'}`}
                onClick={() => onActionClick(action)}
                disabled={actionMutation.isPending}
              >
                {action.label}
              </button>
            ))}

            {rejectAction && (
              <button
                className="ui-btn ui-btn--danger"
                onClick={() => onActionClick(rejectAction)}
                disabled={actionMutation.isPending}
              >
                {rejectAction.label}
              </button>
            )}

            {actionMessage && <p className="subtitle" style={{ width: '100%', textAlign: 'center', marginTop: 8 }}>{actionMessage}</p>}
          </div>
        </div>

        {/* ── AI Copilot ── */}
        <div className="glass panel cd-ai">
          <div className="cd-section-header">
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
            </div>
          </div>

          {aiSummaryError && (
            <p className="subtitle" style={{ color: '#f07373' }}>
              AI: {aiSummaryError.message}
            </p>
          )}

          {!aiSummaryData && !aiSummaryQuery.isFetching && !aiRefreshMutation.isPending && (
            <p className="subtitle">
              Сгенерируйте краткую сводку и рекомендации по следующему шагу.
            </p>
          )}

          {aiSummaryData && (
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
          )}
        </div>

        {/* ── Slots Table ── */}
        <div className="glass panel">
          <div className="cd-section-header">
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

        {/* ── Tests ── */}
        <div className="glass panel">
          <div className="cd-section-header">
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
                          <div key={h.id} className="cd-test-card__history-item">
                            <span>{h.completed_at ? new Date(h.completed_at).toLocaleDateString('ru-RU') : '—'}</span>
                            <span>{typeof h.final_score === 'number' ? h.final_score.toFixed(1) : '—'}</span>
                            {h.source && <span className="cd-chip cd-chip--small">{h.source}</span>}
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        </>)}
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
                {chatQuery.isError && <p style={{ color: '#f07373' }}>Ошибка: {(chatQuery.error as Error).message}</p>}
                {chatMessages.length === 0 && !chatQuery.isLoading && (
                  <p className="subtitle">Сообщений пока нет.</p>
                )}
                {chatMessages.length > 0 && (
                  <div className="candidate-chat-drawer__messages" ref={chatMessagesRef}>
                    {chatMessages.map((msg) => (
                      <div
                        key={msg.id}
                        className={`candidate-chat-message ${msg.direction === 'outbound' ? 'candidate-chat-message--outbound' : 'candidate-chat-message--inbound'}`}
                      >
                        <div className="candidate-chat-message__text">{msg.text}</div>
                        <div className="candidate-chat-message__meta">
                          {new Date(msg.created_at).toLocaleString('ru-RU', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}
                        </div>
                      </div>
                    ))}
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
                      <p className="subtitle" style={{ color: '#f07373' }}>
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
