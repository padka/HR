import type { CSSProperties } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'

type CandidateInfo = {
  user_id: number
  full_name: string
  candidate_id?: number | null
  city_id?: number | null
  city_name?: string | null
  status?: string | null
}

type CandidateSession = {
  session_id: string
  journey_session_id: number
  status: string
  surface: string
  auth_method: string
  launch_channel: string
  expires_at: string
  reused: boolean
}

type BootstrapResponse = {
  ok: boolean
  candidate: {
    id: number
    candidate_id: string
    application_id?: number | null
  }
  session: CandidateSession
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

type CandidateDecision = {
  outcome: string
  explanation: string
  required_next_action: string
}

type Test1Response = {
  journey_step: string
  questions: TestQuestion[]
  draft_answers: Record<string, string>
  is_completed: boolean
  screening_decision?: CandidateDecision | null
  required_next_action?: string | null
}

type JourneyTimelineStep = {
  key: string
  label: string
  state: string
  state_label: string
  detail?: string | null
}

type JourneyResponse = {
  candidate: CandidateInfo
  active_booking?: Booking | null
  timeline: JourneyTimelineStep[]
  primary_action?: {
    key: string
    label: string
    kind: string
    detail?: string | null
  } | null
  status_card?: {
    title: string
    body: string
    tone: string
  } | null
  screening_decision?: CandidateDecision | null
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
  available_slots: number
  available_recruiters: number
  has_available_recruiters: boolean
}

type RecruiterInfo = {
  recruiter_id: number
  recruiter_name: string
  city_id: number
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
  slot_id: number
  candidate_id: number
  recruiter_name: string
  start_utc: string
  end_utc: string
  status: string
}

type Test2Response = {
  questions: Array<{
    id: string
    prompt: string
    question_index: number
    options: TestQuestionOption[]
  }>
  current_question_index?: number | null
  is_completed: boolean
  result_message?: string | null
}

type VerificationChannelInfo = {
  available: boolean
  verified: boolean
  status: string
  label: string
  url?: string | null
  start_param?: string | null
  expires_at?: string | null
  reason?: string | null
  local_confirm_available?: boolean
}

type VerificationStatus = {
  verified: boolean
  booking_ready?: boolean
  required_before: string[]
  available_channels: string[]
  telegram: VerificationChannelInfo
  max: VerificationChannelInfo
  hh: VerificationChannelInfo
  hh_resume?: {
    resume_id?: string | null
    url?: string | null
    title?: string | null
    city?: string | null
    synced_at?: string | null
    import_status?: string | null
    contact_available?: boolean
  } | null
}

type PublicCampaign = {
  slug: string
  title: string
  status: string
  available: boolean
  allowed_providers: Array<'telegram' | 'max' | 'hh' | string>
  city_label?: string | null
  source_label?: string | null
  copy?: {
    title?: string
    subtitle?: string
  }
  availability_flags?: {
    telegram?: boolean
    max?: boolean
    hh?: boolean
    local_confirm?: boolean
  }
}

type PublicVerificationStart = {
  provider: 'telegram' | 'max' | 'hh' | string
  available: boolean
  url?: string | null
  poll_token?: string | null
  start_param?: string | null
  expires_at?: string | null
  reason?: string | null
  local_confirm_available?: boolean
}

type PublicVerificationStatus = {
  status: string
  provider?: string | null
  verified: boolean
  handoff_available: boolean
  handoff_code?: string | null
  reason?: string | null
  expires_at?: string | null
}

type ApiError = Error & {
  code?: string | null
  status?: number
}

const SESSION_STORAGE_KEY = 'rs:candidate-web-session'
const PUBLIC_POLL_STORAGE_PREFIX = 'rs:candidate-web-public-poll:'
const TOKEN_QUERY_KEYS = ['token', 't', 'invite', 'resume']
const CANDIDATE_FLOW_CSS = `
.candidate-flow{--cf-ink:#20251d;--cf-muted:#5d6458;--cf-card:#fffdf5e8;--cf-line:#20251d24;--cf-accent:#b96a37;--cf-accent-soft:#b96a371f;min-height:100vh;padding:20px;background:radial-gradient(circle at 12% 5%,#fff6d8 0,#fff6d800 28%),linear-gradient(135deg,#f7ecdb,#dfead8);color:var(--cf-ink)}.candidate-flow__shell{max-width:1080px;margin:auto}.candidate-flow__hero,.candidate-flow__card,.candidate-flow__banner,.candidate-flow__progress-strip{border:1px solid var(--cf-line);border-radius:24px;background:var(--cf-card);box-shadow:0 16px 50px #2823191f}.candidate-flow__hero{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:22px 26px;margin-bottom:16px}.candidate-flow__hero h1{margin:0;font-size:clamp(2.25rem,6vw,4.4rem);line-height:.9;letter-spacing:-.045em}.candidate-flow__hero p{max-width:600px;margin:12px 0 0;color:var(--cf-muted);font-size:1.02rem}.candidate-flow__account-button{display:inline-flex;align-items:center;gap:10px;min-height:48px;padding:0 18px;border:1px solid var(--cf-line);border-radius:999px;background:#fffaf0;color:var(--cf-ink);font:inherit;font-weight:850;white-space:nowrap;cursor:pointer;box-shadow:0 10px 24px #28231914}.candidate-flow__account-button:hover,.candidate-flow__account-button:focus-visible{transform:translateY(-1px);border-color:#20251d66;outline:0}.candidate-flow__account-icon{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:var(--cf-ink);color:#fff8eb;font-size:.9rem}.candidate-flow__grid{display:grid;grid-template-columns:1fr}.candidate-flow__main,.candidate-flow__questions,.candidate-flow__booking,.candidate-flow__timeline,.candidate-flow__question{display:grid;gap:14px}.candidate-flow__card{padding:24px}.candidate-flow__eyebrow{width:fit-content;padding:7px 10px;border-radius:999px;background:var(--cf-accent-soft);color:var(--cf-accent);font-size:.78rem;font-weight:800;text-transform:uppercase}.candidate-flow__progress-strip{display:grid;gap:12px;margin-bottom:16px;padding:16px}.candidate-flow__progress-title{display:flex;align-items:center;justify-content:space-between;gap:12px}.candidate-flow__progress-title strong{font-size:1.05rem}.candidate-flow__progress-items{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:10px}.candidate-flow__timeline-step{display:flex;justify-content:space-between;gap:10px;padding:11px;border:1px solid var(--cf-line);border-radius:16px;background:#ffffffb8;color:var(--cf-ink);font:inherit;text-align:left;cursor:pointer;transition:transform .18s ease,border-color .18s ease,background .18s ease,box-shadow .18s ease}.candidate-flow__timeline-step:hover,.candidate-flow__timeline-step:focus-visible{transform:translateY(-2px);border-color:#20251d66;outline:0;box-shadow:0 12px 26px #2823191a}.candidate-flow__timeline-step[data-state="current"]{background:#fff1dc;border-color:#b96a3766;animation:cf-progress-pulse 1.8s ease-in-out infinite}.candidate-flow__timeline-step[data-state="done"]{background:#eef6e8}.candidate-flow__timeline-step span{color:var(--cf-muted)}.candidate-flow__question,.candidate-flow__choice-card,.candidate-flow__slot,.candidate-flow__option,.candidate-flow__free-answer input{border:1px solid var(--cf-line);border-radius:16px;background:#ffffffd9}.candidate-flow__options,.candidate-flow__choice-grid,.candidate-flow__slot-list,.candidate-flow__free-answer{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.candidate-flow__question{padding:14px}.candidate-flow__question strong{line-height:1.25}.candidate-flow__question p{margin:.5rem 0 0;color:var(--cf-muted)}.candidate-flow__option,.candidate-flow__choice-card,.candidate-flow__slot{min-height:46px;padding:14px;color:var(--cf-ink);font:inherit;font-weight:800;text-align:left;cursor:pointer;transition:transform .16s ease,border-color .16s ease,background .16s ease,color .16s ease,box-shadow .16s ease}.candidate-flow__option:hover,.candidate-flow__choice-card:hover,.candidate-flow__slot:hover,.candidate-flow__option:focus-visible,.candidate-flow__choice-card:focus-visible,.candidate-flow__slot:focus-visible{transform:translateY(-1px);border-color:#20251d66;outline:0;box-shadow:0 10px 22px #28231914}.candidate-flow__option[data-selected="true"],.candidate-flow__slot[data-selected="true"]{background:var(--cf-ink);border-color:var(--cf-ink);color:#fff8eb}.candidate-flow__choice-card{display:grid;gap:4px}.candidate-flow__choice-card span,.candidate-flow__slot span{color:var(--cf-muted);font-weight:650}.candidate-flow__free-answer input{min-height:46px;padding:0 14px;color:var(--cf-ink);font:inherit}.candidate-flow__button{min-height:46px;padding:0 18px;border:0;border-radius:999px;font-weight:850;background:var(--cf-ink);color:#fff8eb;cursor:pointer}.candidate-flow__button--secondary{border:1px solid var(--cf-line);background:#fff;color:var(--cf-ink)}.candidate-flow button:disabled{cursor:not-allowed;opacity:.52}.candidate-flow__banner{padding:14px 16px;font-weight:750}.candidate-flow__state{place-items:center;min-height:300px;text-align:center}.candidate-flow__banner--error,.candidate-flow__state--error{color:#a33b38}.candidate-flow__account-backdrop{position:fixed;inset:0;z-index:40;display:grid;justify-items:end;background:#10140f66;backdrop-filter:blur(5px)}.candidate-flow__account-panel{width:min(420px,100%);height:100%;padding:24px;background:#fffdf5;color:var(--cf-ink);box-shadow:-24px 0 60px #11170f33;overflow:auto;animation:cf-panel-in .22s ease-out}.candidate-flow__account-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}.candidate-flow__account-head h2{margin:0}.candidate-flow__account-close{width:42px;height:42px;border:1px solid var(--cf-line);border-radius:50%;background:#fff;color:var(--cf-ink);font-size:1.2rem;cursor:pointer}.candidate-flow__profile-card{display:grid;gap:8px;margin-bottom:16px;padding:16px;border:1px solid var(--cf-line);border-radius:20px;background:#fffaf0}.candidate-flow__profile-card h3{margin:0;font-size:1.45rem}.candidate-flow__profile-card p{margin:0;color:var(--cf-muted)}.candidate-flow__account-booking{margin-bottom:16px;padding:14px;border-radius:18px;background:#eef6e8}.candidate-flow__verification{display:grid;gap:14px;position:relative;overflow:hidden}.candidate-flow__verification:before{content:"";position:absolute;inset:-40% auto auto 55%;width:240px;height:240px;border-radius:50%;background:radial-gradient(circle,#b96a3733,#b96a3700 68%);animation:cf-orbit 5s ease-in-out infinite;pointer-events:none}.candidate-flow__verification h2,.candidate-flow__verification h3{margin:.2rem 0}.candidate-flow__verification p{margin:0;color:var(--cf-muted)}.candidate-flow__verification--compact{margin-bottom:16px;padding:14px;border:1px solid var(--cf-line);border-radius:20px;background:#fffaf0}.candidate-flow__verification-badges,.candidate-flow__verification-actions{display:flex;flex-wrap:wrap;gap:10px}.candidate-flow__status-pill{position:relative;z-index:1;padding:9px 12px;border-radius:999px;background:#fff;border:1px solid var(--cf-line);font-weight:800}.candidate-flow__status-pill[data-state="verified"]{background:#eef6e8;border-color:#6f9f5b66}.candidate-flow__verification-actions{position:relative;z-index:1}.candidate-flow__empty{display:grid;gap:4px;color:var(--cf-muted)}@keyframes cf-progress-pulse{0%,100%{box-shadow:0 0 0 0 #b96a3726}50%{box-shadow:0 0 0 8px #b96a3700}}@keyframes cf-orbit{0%,100%{transform:translate3d(0,0,0) scale(1)}50%{transform:translate3d(-18px,14px,0) scale(1.08)}}@keyframes cf-panel-in{from{transform:translateX(24px);opacity:.7}to{transform:translateX(0);opacity:1}}@media(max-width:860px){.candidate-flow{padding:12px}.candidate-flow__hero{align-items:flex-start;flex-direction:column;padding:18px}.candidate-flow__account-button{width:100%;justify-content:center}.candidate-flow__options,.candidate-flow__choice-grid,.candidate-flow__free-answer{grid-template-columns:1fr}.candidate-flow__progress-items{grid-template-columns:1fr}.candidate-flow__verification-actions{display:grid}}
`
const CANDIDATE_FLOW_BOOKING_CSS = `
.candidate-flow__booking-stage{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:18px;align-items:stretch}.candidate-flow__booking-copy{display:grid;gap:12px}.candidate-flow__booking-copy h2{margin:0;font-size:clamp(1.7rem,4vw,2.65rem);line-height:.95;letter-spacing:-.03em}.candidate-flow__booking-copy p{margin:0;color:var(--cf-muted)}.candidate-flow__booking-calendar{display:grid;gap:10px}.candidate-flow__calendar-days{display:flex;gap:8px;overflow:auto;padding-bottom:4px}.candidate-flow__calendar-day{min-width:104px;padding:12px;border:1px solid var(--cf-line);border-radius:18px;background:#fffaf0;color:var(--cf-ink);font:inherit;text-align:left}.candidate-flow__calendar-day[data-selected="true"]{background:var(--cf-ink);color:#fff8eb}.candidate-flow__calendar-day strong{display:block;font-size:1.2rem}.candidate-flow__calendar-day span{display:block;color:inherit;opacity:.75}.candidate-flow__recruiter-orbit{position:relative;min-height:250px;border:1px solid var(--cf-line);border-radius:24px;background:radial-gradient(circle at 50% 45%,#fff8e9,#efe4cf);overflow:hidden;perspective:900px}.candidate-flow__recruiter-orbit:before,.candidate-flow__recruiter-orbit:after{content:"";position:absolute;inset:32px;border:1px dashed #20251d2e;border-radius:50%;transform:rotateX(68deg);box-shadow:0 0 34px #b96a3724}.candidate-flow__recruiter-orbit:after{inset:54px;border-style:solid;opacity:.35;animation:cf-ring-glow 3.6s ease-in-out infinite}.candidate-flow__orbit-core{position:absolute;left:50%;top:50%;width:96px;height:96px;margin:-48px;border-radius:50%;display:grid;place-items:center;background:linear-gradient(145deg,#20251d,#384231);color:#fff8eb;font-weight:950;box-shadow:0 18px 40px #20251d33;z-index:2}.candidate-flow__orbit-core small{display:block;color:#f1cfaa;font-size:.62rem;letter-spacing:.08em;text-transform:uppercase}.candidate-flow__avatar-orbit{position:absolute;inset:34px;transform-style:preserve-3d;animation:cf-avatar-orbit 9s linear infinite}.candidate-flow__recruiter-avatar{position:absolute;left:50%;top:50%;width:82px;height:92px;margin:-41px;border:1px solid #ffffff99;border-radius:26px;background:linear-gradient(145deg,#ffe0b7,#b96a37);color:#20251d;font-weight:950;box-shadow:0 18px 32px #20251d26;display:grid;gap:4px;place-items:center;padding:8px;transform:rotateY(calc(var(--i)*72deg)) translateZ(116px);transform-style:preserve-3d}.candidate-flow__recruiter-avatar span{display:grid;place-items:center;width:42px;height:42px;border-radius:50%;background:#fff8eb}.candidate-flow__recruiter-avatar small{font-size:.62rem;line-height:1;text-align:center;color:#402b1b}.candidate-flow__orbit-status{position:absolute;left:14px;right:14px;bottom:12px;display:flex;justify-content:space-between;gap:8px;font-size:.72rem;font-weight:850;color:#5d6458}.candidate-flow__orbit-status span{padding:7px 9px;border-radius:999px;background:#fffaf0cc;border:1px solid #20251d1a}.candidate-flow__slot-list{grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}.candidate-flow__slot small{display:block;margin-top:6px;color:inherit;opacity:.65}.candidate-flow__verification-inline{border:1px dashed #b96a3780;border-radius:20px;padding:14px;background:#fff6e8}.candidate-flow__verification-inline h3{margin:.2rem 0}.candidate-flow__verification-inline p{margin:0 0 12px;color:var(--cf-muted)}@keyframes cf-avatar-orbit{from{transform:rotateY(0deg) rotateX(8deg)}to{transform:rotateY(360deg) rotateX(8deg)}}@keyframes cf-ring-glow{0%,100%{opacity:.25;transform:rotateX(68deg) scale(.96)}50%{opacity:.55;transform:rotateX(68deg) scale(1.03)}}@media(max-width:860px){.candidate-flow__booking-stage{grid-template-columns:1fr}.candidate-flow__recruiter-orbit{min-height:210px}.candidate-flow__recruiter-avatar{transform:rotateY(calc(var(--i)*72deg)) translateZ(88px)}}@media(prefers-reduced-motion:reduce){.candidate-flow__avatar-orbit,.candidate-flow__recruiter-orbit:after{animation:none}}
`

function readStoredSession() {
  try {
    return window.sessionStorage.getItem(SESSION_STORAGE_KEY)
  } catch {
    return null
  }
}

function storeSession(sessionId: string) {
  try {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId)
  } catch {
    // Session recovery is best effort; API auth remains server-side.
  }
}

function clearStoredSession() {
  try {
    window.sessionStorage.removeItem(SESSION_STORAGE_KEY)
  } catch {
    // Ignore storage cleanup failures.
  }
}

function publicPollStorageKey(slug: string) {
  return `${PUBLIC_POLL_STORAGE_PREFIX}${slug}`
}

function storePublicPollToken(slug: string, pollToken: string) {
  try {
    window.sessionStorage.setItem(publicPollStorageKey(slug), pollToken)
  } catch {
    // Public intake polling is best effort; the provider token remains server-side.
  }
}

function readPublicPollToken(slug: string) {
  try {
    return window.sessionStorage.getItem(publicPollStorageKey(slug))
  } catch {
    return null
  }
}

function clearPublicPollToken(slug: string) {
  try {
    window.sessionStorage.removeItem(publicPollStorageKey(slug))
  } catch {
    // Ignore cleanup failures.
  }
}

function detectTokenFromUrl() {
  if (typeof window === 'undefined') return ''
  const query = new URLSearchParams(window.location.search)
  for (const key of TOKEN_QUERY_KEYS) {
    const value = query.get(key)
    if (value?.trim()) return value.trim()
  }
  return ''
}

function detectCampaignSlugFromUrl() {
  if (typeof window === 'undefined') return ''
  const query = new URLSearchParams(window.location.search)
  const campaign = query.get('campaign')?.trim().toLowerCase()
  if (campaign) return campaign
  const applyMatch = window.location.pathname.match(/^\/apply\/([a-z0-9_-]+)/i)
  if (applyMatch?.[1]) return applyMatch[1].toLowerCase()
  return ''
}

function collectUtm() {
  if (typeof window === 'undefined') return {}
  const query = new URLSearchParams(window.location.search)
  const utm: Record<string, string> = {}
  for (const key of ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'ref']) {
    const value = query.get(key)
    if (value?.trim()) utm[key] = value.trim()
  }
  return utm
}

function detectHhMarker() {
  if (typeof window === 'undefined') return ''
  return new URLSearchParams(window.location.search).get('hh')?.trim().toLowerCase() || ''
}

function hhMarkerNotice(marker: string) {
  if (marker === 'connected') return 'HH подтверждён, резюме импортировано.'
  if (marker === 'no_resume') return 'HH подтверждён, но резюме не найдено. Можно продолжить анкету.'
  if (marker === 'conflict') return 'Это HH-резюме уже связано с другим кандидатом. Рекрутер проверит вручную.'
  if (marker === 'disabled') return 'HH OAuth недоступен в локальном окружении.'
  if (marker === 'error') return 'Не удалось подтвердить HH. Можно выбрать Telegram или MAX.'
  return null
}

function extractApiError(payload: unknown, fallback: string): { code?: string | null; message: string } {
  if (!payload || typeof payload !== 'object') return { message: fallback }
  const typedPayload = payload as { detail?: unknown; message?: unknown; code?: unknown }
  const detail = typedPayload.detail
  if (detail && typeof detail === 'object') {
    const typedDetail = detail as { code?: unknown; message?: unknown }
    return {
      code: typeof typedDetail.code === 'string' ? typedDetail.code : null,
      message: typeof typedDetail.message === 'string' ? typedDetail.message : fallback,
    }
  }
  if (typeof detail === 'string') return { message: detail }
  if (typeof typedPayload.message === 'string') return { message: typedPayload.message }
  return { message: fallback }
}

async function candidateWebApi<T>(
  path: string,
  {
    method = 'GET',
    body,
    sessionId,
  }: {
    method?: string
    body?: unknown
    sessionId?: string | null
  } = {},
): Promise<T> {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  if (sessionId) headers.set('X-Candidate-Access-Session', sessionId)
  const response = await fetch(`/api/candidate-web${path}`, {
    method,
    headers,
    body: body == null ? undefined : JSON.stringify(body),
    credentials: 'same-origin',
  })

  if (!response.ok) {
    let errorInfo: { code?: string | null; message: string } = { message: response.statusText }
    try {
      errorInfo = extractApiError(await response.json(), response.statusText)
    } catch {
      // Keep generic status text; browser link errors must not leak internals.
    }
    const error = new Error(errorInfo.message || 'Request failed') as ApiError
    error.code = errorInfo.code
    error.status = response.status
    throw error
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

async function exchangePublicHandoff(
  handoffCode: string,
  utm: Record<string, string>,
) {
  const bootstrap = await candidateWebApi<BootstrapResponse>('/public/session/exchange', {
    method: 'POST',
    body: {
      handoff_code: handoffCode,
      source: 'web',
      utm,
    },
  })
  const nextSessionId = bootstrap.session.session_id
  storeSession(nextSessionId)
  if (typeof window !== 'undefined') {
    window.history.replaceState(null, '', '/candidate-flow')
  }
  return nextSessionId
}

function formatDateTime(value?: string | null) {
  if (!value) return 'Время уточняется'
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric',
      month: 'long',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))
  } catch {
    return value
  }
}

function normalizeBookingStatus(status?: string | null) {
  const value = String(status || '').trim().toLowerCase()
  if (value === 'confirmed' || value === 'confirmed_by_candidate') return 'Подтверждено'
  if (value === 'booked' || value === 'pending') return 'Ожидает подтверждения'
  return status || 'Назначено'
}

function cleanQuestionText(value?: string | null) {
  return String(value || '')
    .replace(/<\/?(b|i|strong|em)>/gi, '')
    .replace(/^\s*\d+\s*[‰%.\-:]?\s*/u, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function isBookingActionable(test1: Test1Response | null, journey: JourneyResponse | null) {
  if (!test1?.is_completed) return false
  if (test1.required_next_action === 'select_interview_slot') return true
  if (journey?.active_booking) return true
  if (journey?.primary_action?.kind === 'booking') return true
  return !test1.screening_decision && test1.required_next_action === 'recruiter_review'
}

function dateKey(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 10)
  return date.toISOString().slice(0, 10)
}

function formatDayLabel(value: string) {
  try {
    return new Intl.DateTimeFormat('ru-RU', { weekday: 'short', day: 'numeric', month: 'short' }).format(new Date(value))
  } catch {
    return value
  }
}

function recruiterInitials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'HR'
}

function uniqueRecruiters(recruiters: RecruiterInfo[], slots: SlotInfo[]) {
  const map = new Map<number, { id: number; name: string; availableSlots: number }>()
  for (const recruiter of recruiters) {
    map.set(recruiter.recruiter_id, {
      id: recruiter.recruiter_id,
      name: recruiter.recruiter_name,
      availableSlots: recruiter.available_slots,
    })
  }
  for (const slot of slots) {
    if (!map.has(slot.recruiter_id)) {
      map.set(slot.recruiter_id, {
        id: slot.recruiter_id,
        name: slot.recruiter_name,
        availableSlots: slots.filter((item) => item.recruiter_id === slot.recruiter_id).length,
      })
    }
  }
  return Array.from(map.values()).slice(0, 5)
}

function currentTest2Question(test2: Test2Response | null) {
  if (!test2 || test2.is_completed || test2.current_question_index == null) return null
  return test2.questions.find((question) => question.question_index === test2.current_question_index) || null
}

export function CandidateFlowPage() {
  const didBootstrapRef = useRef(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [candidate, setCandidate] = useState<CandidateInfo | null>(null)
  const [journey, setJourney] = useState<JourneyResponse | null>(null)
  const [test1, setTest1] = useState<Test1Response | null>(null)
  const [test2, setTest2] = useState<Test2Response | null>(null)
  const [verification, setVerification] = useState<VerificationStatus | null>(null)
  const [bookingContext, setBookingContext] = useState<BookingContext | null>(null)
  const [cities, setCities] = useState<CityInfo[]>([])
  const [recruiters, setRecruiters] = useState<RecruiterInfo[]>([])
  const [slots, setSlots] = useState<SlotInfo[]>([])
  const [selectedSlotId, setSelectedSlotId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [accountOpen, setAccountOpen] = useState(false)
  const [freeTextDrafts, setFreeTextDrafts] = useState<Record<string, string>>({})
  const [publicCampaignSlug, setPublicCampaignSlug] = useState<string>('')
  const [publicCampaign, setPublicCampaign] = useState<PublicCampaign | null>(null)
  const [publicPollToken, setPublicPollToken] = useState<string | null>(null)
  const [publicVerification, setPublicVerification] = useState<PublicVerificationStatus | null>(null)

  useEffect(() => {
    if (!test1) return
    setFreeTextDrafts((previous) => {
      const next = { ...previous }
      for (const question of test1.questions) {
        if (question.options.length > 0) continue
        const saved = test1.draft_answers[question.id]
        if (saved) next[question.id] = saved
      }
      return next
    })
  }, [test1])

  const effectiveAnswers = useMemo(() => {
    if (!test1) return {}
    const answers: Record<string, string> = { ...test1.draft_answers }
    for (const question of test1.questions) {
      if (question.options.length > 0) continue
      const draft = freeTextDrafts[question.id]?.trim()
      if (draft) answers[question.id] = draft
    }
    return answers
  }, [freeTextDrafts, test1])

  const pendingQuestions = useMemo(() => {
    if (!test1 || test1.is_completed) return []
    return test1.questions.filter((question) => !effectiveAnswers[question.id]?.trim())
  }, [effectiveAnswers, test1])

  const isIdentityVerified = Boolean(verification?.verified)
  const isBookingReady = Boolean(verification?.booking_ready ?? verification?.verified)
  const needsIdentityVerification = Boolean(verification && !verification.verified)
  const bookingActionable = isBookingActionable(test1, journey)
  const activeTest2Question = currentTest2Question(test2)

  async function loadJourneyState(nextSessionId: string) {
    const journeyResponse = await candidateWebApi<JourneyResponse>('/journey', { sessionId: nextSessionId })
    setJourney(journeyResponse)
    setCandidate(journeyResponse.candidate)
    return journeyResponse
  }

  async function loadVerification(nextSessionId: string) {
    const response = await candidateWebApi<VerificationStatus>('/verification', { sessionId: nextSessionId })
    setVerification(response)
    return response
  }

  async function loadBookingState(nextSessionId: string, nextTest1 = test1, nextJourney = journey) {
    const context = await candidateWebApi<BookingContext>('/booking-context', { sessionId: nextSessionId })
    setBookingContext(context)
    if (!isBookingActionable(nextTest1, nextJourney)) {
      setCities([])
      setRecruiters([])
      setSlots([])
      return
    }
    const cityList = await candidateWebApi<CityInfo[]>('/cities', { sessionId: nextSessionId })
    setCities(cityList)
    if (!context.city_id) {
      setRecruiters([])
      setSlots([])
      return
    }
    const recruiterList = await candidateWebApi<RecruiterInfo[]>(
      `/recruiters?city_id=${context.city_id}`,
      { sessionId: nextSessionId },
    )
    setRecruiters(recruiterList)
    if (!context.recruiter_id) {
      setSlots([])
      return
    }
    const slotList = await candidateWebApi<SlotInfo[]>(
      `/slots?city_id=${context.city_id}&recruiter_id=${context.recruiter_id}`,
      { sessionId: nextSessionId },
    )
    setSlots(slotList)
    setSelectedSlotId((previous) => previous && slotList.some((slot) => slot.slot_id === previous) ? previous : slotList[0]?.slot_id || null)
  }

  async function refresh(nextSessionId = sessionId) {
    if (!nextSessionId) return
    const journeyResponse = await loadJourneyState(nextSessionId)
    const verificationResponse = await loadVerification(nextSessionId)
    if (!verificationResponse.verified) {
      setTest1(null)
      setTest2(null)
      setBookingContext(null)
      setCities([])
      setRecruiters([])
      setSlots([])
      setSelectedSlotId(null)
      return
    }
    const test1Response = await candidateWebApi<Test1Response>('/test1', { sessionId: nextSessionId })
    setTest1(test1Response)
    await loadBookingState(nextSessionId, test1Response, journeyResponse)
    if (journeyResponse.primary_action?.kind === 'test2') {
      const nextTest2 = await candidateWebApi<Test2Response>('/test2', { sessionId: nextSessionId })
      setTest2(nextTest2)
    }
  }

  useEffect(() => {
    if (didBootstrapRef.current) return
    didBootstrapRef.current = true
    let cancelled = false

    async function run() {
      setBusy(true)
      setError(null)
      const token = detectTokenFromUrl()
      const campaignSlug = detectCampaignSlugFromUrl()
      const storedSession = readStoredSession()
      try {
        if (!token && campaignSlug) {
          setPublicCampaignSlug(campaignSlug)
          const campaign = await candidateWebApi<PublicCampaign>(`/public/campaigns/${campaignSlug}`)
          if (cancelled) return
          setPublicCampaign(campaign)
          const storedPoll = readPublicPollToken(campaignSlug)
          if (storedPoll) {
            setPublicPollToken(storedPoll)
            try {
              const publicStatus = await candidateWebApi<PublicVerificationStatus>(
                `/public/verification/status?poll_token=${encodeURIComponent(storedPoll)}`,
              )
              if (!cancelled) setPublicVerification(publicStatus)
            } catch {
              clearPublicPollToken(campaignSlug)
              if (!cancelled) setPublicPollToken(null)
            }
          }
          const markerNotice = hhMarkerNotice(detectHhMarker())
          if (markerNotice) setNotice(markerNotice)
          return
        }
        let nextSessionId = storedSession
        if (token) {
          const bootstrap = await candidateWebApi<BootstrapResponse>('/bootstrap', {
            method: 'POST',
            body: {
              token,
              source: 'web',
              utm: collectUtm(),
            },
          })
          nextSessionId = bootstrap.session.session_id
          storeSession(nextSessionId)
        }
        if (!nextSessionId) {
          throw Object.assign(new Error('Ссылка недействительна или уже не содержит код доступа.'), {
            code: 'missing_link',
            status: 400,
          })
        }
        if (cancelled) return
        setSessionId(nextSessionId)
        await refresh(nextSessionId)
        const markerNotice = hhMarkerNotice(detectHhMarker())
        if (markerNotice) setNotice(markerNotice)
      } catch (err) {
        if (cancelled) return
        const apiError = err as ApiError
        if (apiError.status === 401 || apiError.status === 403 || apiError.status === 410) {
          clearStoredSession()
        }
        setError(apiError)
      } finally {
        if (!cancelled) setBusy(false)
      }
    }

    void run()
    return () => {
      cancelled = true
    }
    // Bootstrap must run once per page load; duplicate calls would re-consume invite links in StrictMode.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function saveAnswer(question: TestQuestion, value: string) {
    if (!sessionId || busyAction || !value.trim()) return
    setBusyAction(`answer:${question.id}`)
    setError(null)
    try {
      const response = await candidateWebApi<Test1Response>('/test1/answers', {
        method: 'POST',
        sessionId,
        body: { answers: { [question.id]: value.trim() } },
      })
      setTest1(response)
      await refresh(sessionId)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusyAction(null)
    }
  }

  async function completeTest1() {
    if (!sessionId || busyAction || !test1) return
    setBusyAction('complete-test1')
    setError(null)
    try {
      const unsavedFreeTextAnswers: Record<string, string> = {}
      for (const question of test1.questions) {
        if (question.options.length > 0) continue
        const value = freeTextDrafts[question.id]?.trim()
        if (value && test1.draft_answers[question.id] !== value) {
          unsavedFreeTextAnswers[question.id] = value
        }
      }
      if (Object.keys(unsavedFreeTextAnswers).length > 0) {
        await candidateWebApi<Test1Response>('/test1/answers', {
          method: 'POST',
          sessionId,
          body: { answers: unsavedFreeTextAnswers },
        })
      }
      const response = await candidateWebApi<Test1Response>('/test1/complete', {
        method: 'POST',
        sessionId,
      })
      setTest1(response)
      await refresh(sessionId)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusyAction(null)
    }
  }

  async function selectCity(cityId: number) {
    if (!sessionId || busyAction) return
    setBusyAction(`city:${cityId}`)
    setError(null)
    try {
      await candidateWebApi<BookingContext>('/booking-context', {
        method: 'POST',
        sessionId,
        body: { city_id: cityId, recruiter_id: null },
      })
      await refresh(sessionId)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusyAction(null)
    }
  }

  async function selectRecruiter(recruiterId: number) {
    if (!sessionId || busyAction || !bookingContext?.city_id) return
    setBusyAction(`recruiter:${recruiterId}`)
    setError(null)
    try {
      await candidateWebApi<BookingContext>('/booking-context', {
        method: 'POST',
        sessionId,
        body: { city_id: bookingContext.city_id, recruiter_id: recruiterId },
      })
      await refresh(sessionId)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusyAction(null)
    }
  }

  async function createBooking() {
    if (!sessionId || busyAction || !selectedSlotId) return
    setBusyAction('booking')
    setError(null)
    setNotice(null)
    try {
      const booking = await candidateWebApi<Booking>('/bookings', {
        method: 'POST',
        sessionId,
        body: { slot_id: selectedSlotId },
      })
      setNotice(`Собеседование назначено: ${formatDateTime(booking.start_utc)}.`)
      await refresh(sessionId)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusyAction(null)
    }
  }

  async function startVerification(channel: 'telegram' | 'max' | 'hh') {
    if (!sessionId || busyAction) return
    setBusyAction(`verification:${channel}`)
    setError(null)
    setNotice(null)
    try {
      const response = await candidateWebApi<VerificationStatus>(`/verification/${channel}/start`, {
        method: 'POST',
        sessionId,
      })
      setVerification(response)
      const channelInfo = response[channel]
      if (!channelInfo.available && channel === 'hh') {
        setNotice(channelInfo.local_confirm_available
          ? 'HH OAuth недоступен в локальном окружении, но можно импортировать тестовое резюме ниже.'
          : 'HH недоступен в локальном окружении. Используйте Telegram или MAX.')
        return
      }
      if (!channelInfo.available && channel === 'max') {
        setNotice(channelInfo.local_confirm_available
          ? 'MAX недоступен как внешний бот, но локальная проверка доступна ниже.'
          : 'MAX недоступен в локальном окружении. Для MVP можно проверить Telegram.')
        return
      }
      if (channelInfo.url) {
        if (channel === 'hh') {
          window.location.href = channelInfo.url
        } else {
          window.open(channelInfo.url, '_blank', 'noopener,noreferrer')
        }
        setNotice('После подтверждения вернитесь сюда и обновите статус.')
        return
      }
      if (channelInfo.start_param) {
        setNotice(`Отправьте боту команду /start ${channelInfo.start_param}, затем обновите статус. В локальном режиме можно нажать локальное подтверждение.`)
        return
      }
      setNotice('Канал верификации сейчас недоступен.')
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusyAction(null)
    }
  }

  async function refreshVerification() {
    if (!sessionId || busyAction) return
    setBusyAction('verification:refresh')
    setError(null)
    try {
      const response = await loadVerification(sessionId)
      setNotice(response.verified
        ? (response.booking_ready ? 'Профиль подтверждён. Запись открыта.' : 'Профиль подтверждён. Для записи нужен контакт через Telegram/MAX или HH.')
        : 'Подтверждение пока не найдено.')
      await refresh(sessionId)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusyAction(null)
    }
  }

  async function localConfirmVerification(channel: 'telegram' | 'max' | 'hh') {
    if (!sessionId || busyAction) return
    setBusyAction(`verification:${channel}:local`)
    setError(null)
    setNotice(null)
    try {
      const response = await candidateWebApi<VerificationStatus>(`/verification/${channel}/local-confirm`, {
        method: 'POST',
        sessionId,
      })
      setVerification(response)
      setNotice(response.verified ? 'Локальная верификация выполнена. Анкета открыта.' : 'Не удалось подтвердить профиль локально.')
      await refresh(sessionId)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusyAction(null)
    }
  }

  async function startPublicVerification(channel: 'telegram' | 'max' | 'hh') {
    if (!publicCampaignSlug || busyAction) return
    setBusyAction(`public-verification:${channel}`)
    setError(null)
    setNotice(null)
    try {
      const response = await candidateWebApi<PublicVerificationStart>(
        `/public/campaigns/${publicCampaignSlug}/verification/${channel}/start`,
        {
          method: 'POST',
          body: { utm: collectUtm() },
        },
      )
      if (response.poll_token) {
        setPublicPollToken(response.poll_token)
        storePublicPollToken(publicCampaignSlug, response.poll_token)
      }
      if (!response.available && channel === 'hh') {
        setNotice(response.local_confirm_available
          ? 'HH OAuth недоступен локально. Для MVP можно импортировать тестовое резюме.'
          : 'HH сейчас недоступен. Выберите Telegram или MAX.')
        return
      }
      if (!response.available && channel === 'max') {
        setNotice(response.local_confirm_available
          ? 'MAX недоступен как внешний бот. Для MVP доступно локальное подтверждение.'
          : 'MAX сейчас недоступен. Выберите Telegram или HH.')
        return
      }
      if (response.url) {
        if (channel === 'hh') {
          window.location.href = response.url
        } else {
          window.open(response.url, '_blank', 'noopener,noreferrer')
          setNotice('После подтверждения вернитесь сюда и нажмите “Обновить статус”.')
        }
        return
      }
      if (response.start_param) {
        setNotice(`Отправьте боту команду /start ${response.start_param}, затем обновите статус.`)
      }
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusyAction(null)
    }
  }

  async function refreshPublicVerification() {
    if (!publicCampaignSlug || !publicPollToken || busyAction) return
    setBusyAction('public-verification:refresh')
    setError(null)
    try {
      const response = await candidateWebApi<PublicVerificationStatus>(
        `/public/verification/status?poll_token=${encodeURIComponent(publicPollToken)}`,
      )
      setPublicVerification(response)
      if (response.handoff_available && response.handoff_code) {
        const nextSessionId = await exchangePublicHandoff(response.handoff_code, collectUtm())
        clearPublicPollToken(publicCampaignSlug)
        setPublicPollToken(null)
        setPublicCampaign(null)
        setPublicCampaignSlug('')
        setPublicVerification(null)
        setSessionId(nextSessionId)
        setNotice('Профиль подтверждён. Анкета открыта.')
        await refresh(nextSessionId)
        return
      }
      if (response.status === 'conflict') {
        setNotice('Профиль требует ручной проверки рекрутером. Мы не объединяем кандидатов автоматически.')
      } else if (response.status === 'expired') {
        setNotice('Подтверждение устарело. Начните заново.')
      } else {
        setNotice(response.verified ? 'Профиль подтверждён. Готовим анкету.' : 'Подтверждение пока не найдено.')
      }
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusyAction(null)
    }
  }

  async function localConfirmPublicVerification(channel: 'telegram' | 'max' | 'hh') {
    if (!publicCampaignSlug || !publicPollToken || busyAction) return
    setBusyAction(`public-verification:${channel}:local`)
    setError(null)
    setNotice(null)
    try {
      const response = await candidateWebApi<PublicVerificationStatus>('/public/verification/local-confirm', {
        method: 'POST',
        body: {
          poll_token: publicPollToken,
          provider: channel,
        },
      })
      setPublicVerification(response)
      if (response.handoff_available && response.handoff_code) {
        const nextSessionId = await exchangePublicHandoff(response.handoff_code, collectUtm())
        clearPublicPollToken(publicCampaignSlug)
        setPublicPollToken(null)
        setPublicCampaign(null)
        setPublicCampaignSlug('')
        setPublicVerification(null)
        setSessionId(nextSessionId)
        setNotice('Локальная верификация выполнена. Анкета открыта.')
        await refresh(nextSessionId)
      }
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusyAction(null)
    }
  }

  async function confirmBooking(bookingId: number) {
    if (!sessionId || busyAction) return
    setBusyAction('confirm-booking')
    setError(null)
    try {
      await candidateWebApi<Booking>(`/bookings/${bookingId}/confirm`, {
        method: 'POST',
        sessionId,
      })
      setNotice('Встреча подтверждена. Мы закрепили выбранное время.')
      await refresh(sessionId)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusyAction(null)
    }
  }

  async function submitTest2Answer(questionIndex: number, answerIndex: number) {
    if (!sessionId || busyAction) return
    setBusyAction(`test2:${questionIndex}:${answerIndex}`)
    setError(null)
    try {
      const response = await candidateWebApi<Test2Response>('/test2/answers', {
        method: 'POST',
        sessionId,
        body: { question_index: questionIndex, answer_index: answerIndex },
      })
      setTest2(response)
      await refresh(sessionId)
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setBusyAction(null)
    }
  }

  const activeBooking = journey?.active_booking || null
  const statusTitle = needsIdentityVerification
    ? 'Подтвердите профиль для анкеты'
    : bookingActionable && !activeBooking
    ? (isBookingReady ? 'Выберите время собеседования' : 'Добавьте контакт для записи')
    : journey?.status_card?.title || (test1?.is_completed ? 'Анкета принята' : 'Продолжите анкету')
  const statusBody = needsIdentityVerification
    ? 'Перед Test1 подтвердите профиль через Telegram, MAX или hh.ru, чтобы мы точно связали ответы с вашим профилем.'
    : bookingActionable && !activeBooking
    ? (isBookingReady
        ? 'Откройте календарь ниже, выберите рекрутера и удобный слот.'
        : 'Анкета сохранена. Для записи добавьте Telegram/MAX или контакт из hh.ru.')
    : journey?.status_card?.body || 'Ответьте на вопросы и выберите удобное время, если система откроет запись.'

  function handleProgressStepClick(step: JourneyTimelineStep) {
    const targetSelector = step.key.includes('booking') || step.key.includes('slot')
      ? '[data-testid="candidate-flow-booking"], [data-testid="candidate-flow-booked"]'
      : step.key.includes('test2')
        ? '[data-testid="candidate-flow-test2"]'
        : step.key.includes('test1')
          ? '[data-testid="candidate-flow-test1"]'
          : '.candidate-flow__status'
    document.querySelector(targetSelector)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <main className="candidate-flow" data-testid="candidate-flow">
      <style>{CANDIDATE_FLOW_CSS}</style>
      <style>{CANDIDATE_FLOW_BOOKING_CSS}</style>
      <style>{`.candidate-flow__hint{margin:0;color:var(--cf-muted);font-size:.92rem;line-height:1.35}.candidate-flow__hh-resume{display:grid;gap:8px;margin-bottom:16px;padding:14px;border:1px solid var(--cf-line);border-radius:18px;background:#eef6e8}.candidate-flow__hh-resume h3,.candidate-flow__hh-resume p{margin:0}.candidate-flow__hh-resume a{color:var(--cf-accent);font-weight:850}`}</style>
      <div className="candidate-flow__orb candidate-flow__orb--one" aria-hidden="true" />
      <div className="candidate-flow__orb candidate-flow__orb--two" aria-hidden="true" />
      <section className="candidate-flow__shell">
        <header className="candidate-flow__hero">
          <div className="candidate-flow__hero-copy">
            <h1>Кандидатский маршрут</h1>
            <p>
              Пройдите анкету и выберите время собеседования. Прогресс сохраняется автоматически.
            </p>
          </div>
          {journey ? (
            <button
              type="button"
              className="candidate-flow__account-button"
              onClick={() => setAccountOpen(true)}
              aria-haspopup="dialog"
              aria-expanded={accountOpen}
            >
              <span className="candidate-flow__account-icon" aria-hidden="true">ЛК</span>
              <span>Личный кабинет</span>
            </button>
          ) : null}
        </header>

        {busy && !journey ? (
          <section className="candidate-flow__card candidate-flow__state" data-testid="candidate-flow-loading">
            <span className="candidate-flow__spinner" aria-hidden="true" />
            <h2>Проверяем ссылку</h2>
            <p>Это занимает несколько секунд.</p>
          </section>
        ) : null}

        {error && !journey && !publicCampaign ? (
          <section className="candidate-flow__card candidate-flow__state candidate-flow__state--error" data-testid="candidate-flow-error">
            <span className="candidate-flow__eyebrow">{error.code || 'candidate_flow_error'}</span>
            <h2>{error.status === 410 ? 'Ссылка устарела' : 'Не удалось открыть маршрут'}</h2>
            <p>{error.message || 'Попросите рекрутера отправить новую ссылку.'}</p>
          </section>
        ) : null}

        {publicCampaign && !journey ? (
          <>
            {notice ? (
              <div className="candidate-flow__banner candidate-flow__banner--success" role="status">
                {notice}
              </div>
            ) : null}
            {error ? (
              <div className="candidate-flow__banner candidate-flow__banner--error" role="alert">
                {error.message || 'Не удалось выполнить действие.'}
              </div>
            ) : null}
            <PublicCampaignLanding
              campaign={publicCampaign}
              status={publicVerification}
              pollToken={publicPollToken}
              busyAction={busyAction}
              onStartVerification={startPublicVerification}
              onRefreshVerification={refreshPublicVerification}
              onLocalConfirmVerification={localConfirmPublicVerification}
            />
          </>
        ) : null}

        {journey ? (
          <>
          <AccountPanel
            open={accountOpen}
            candidate={candidate}
            journey={journey}
            activeBooking={activeBooking}
            verification={verification}
            onClose={() => setAccountOpen(false)}
            onStepClick={handleProgressStepClick}
            onStartVerification={startVerification}
            onRefreshVerification={refreshVerification}
            onLocalConfirmVerification={localConfirmVerification}
            busyAction={busyAction}
          />
          <section className="candidate-flow__progress-strip" aria-label="Прогресс кандидата">
            <div className="candidate-flow__progress-title">
              <strong>Прогресс</strong>
              <span>{journey.primary_action?.label || statusTitle}</span>
            </div>
            <div className="candidate-flow__progress-items">
              {journey.timeline.map((step) => (
                <button
                  key={step.key}
                  type="button"
                  className="candidate-flow__timeline-step"
                  data-state={step.state}
                  onClick={() => handleProgressStepClick(step)}
                >
                  <strong>{step.label}</strong>
                  <span>{step.state_label}</span>
                </button>
              ))}
            </div>
          </section>
          <div className="candidate-flow__grid">
            <div className="candidate-flow__main">
              {notice ? (
                <div className="candidate-flow__banner candidate-flow__banner--success" role="status">
                  {notice}
                </div>
              ) : null}
              {error ? (
                <div className="candidate-flow__banner candidate-flow__banner--error" role="alert">
                  {error.message || 'Не удалось выполнить действие.'}
                </div>
              ) : null}

              <section className="candidate-flow__card candidate-flow__status">
                <span className="candidate-flow__eyebrow">Текущий шаг</span>
                <h2>{statusTitle}</h2>
                <p>{statusBody}</p>
              </section>

              {needsIdentityVerification ? (
                <VerificationEntry
                  verification={verification}
                  busyAction={busyAction}
                  onStartVerification={startVerification}
                  onRefreshVerification={refreshVerification}
                  onLocalConfirmVerification={localConfirmVerification}
                />
              ) : null}

              {isIdentityVerified && test1 && !test1.is_completed ? (
                <section className="candidate-flow__card candidate-flow__questions" data-testid="candidate-flow-test1">
                  <div className="candidate-flow__section-head">
                    <div>
                      <span className="candidate-flow__eyebrow">Test1</span>
                      <h2>Ответьте на вопросы</h2>
                    </div>
                    <span className="candidate-flow__counter">
                      {test1.questions.length - pendingQuestions.length}/{test1.questions.length}
                    </span>
                  </div>
                  {test1.questions.map((question) => {
                    const savedAnswer = test1.draft_answers[question.id]
                    return (
                      <article key={question.id} className="candidate-flow__question" data-complete={Boolean(savedAnswer)}>
                        <div>
                          <strong>{cleanQuestionText(question.prompt)}</strong>
                          {question.helper ? <p>{cleanQuestionText(question.helper)}</p> : null}
                        </div>
                        {question.options.length > 0 ? (
                          <div className="candidate-flow__options">
                            {question.options.map((option) => (
                              <button
                                key={option.value}
                                type="button"
                                className="candidate-flow__option"
                                data-selected={savedAnswer === option.value}
                                onClick={() => { void saveAnswer(question, option.value) }}
                                disabled={Boolean(busyAction)}
                              >
                                {option.label}
                              </button>
                            ))}
                          </div>
                        ) : (
                          <FreeTextAnswer
                            question={question}
                            value={freeTextDrafts[question.id] ?? savedAnswer ?? ''}
                            disabled={Boolean(busyAction)}
                            onChange={(value) => {
                              setFreeTextDrafts((previous) => ({ ...previous, [question.id]: value }))
                            }}
                            onSave={saveAnswer}
                          />
                        )}
                      </article>
                    )
                  })}
                  <button
                    type="button"
                    className="candidate-flow__button candidate-flow__button--primary"
                    onClick={() => { void completeTest1() }}
                    disabled={Boolean(busyAction) || pendingQuestions.length > 0}
                  >
                    {busyAction === 'complete-test1' ? 'Сохраняем и завершаем...' : 'Завершить анкету'}
                  </button>
                  {pendingQuestions.length > 0 ? (
                    <p className="candidate-flow__hint">
                      Осталось ответить: {pendingQuestions.map((question) => cleanQuestionText(question.prompt)).join(', ')}.
                    </p>
                  ) : null}
                </section>
              ) : null}

              {isIdentityVerified && test2 && (activeTest2Question || test2.is_completed) ? (
                <section className="candidate-flow__card candidate-flow__questions" data-testid="candidate-flow-test2">
                  <span className="candidate-flow__eyebrow">Test2</span>
                  <h2>{test2.is_completed ? 'Тест 2 завершён' : cleanQuestionText(activeTest2Question?.prompt)}</h2>
                  {test2.is_completed ? (
                    <p>{test2.result_message || 'Ответы сохранены. Следующий шаг появится здесь.'}</p>
                  ) : (
                    <div className="candidate-flow__options">
                      {activeTest2Question?.options.map((option, index) => (
                        <button
                          key={option.value}
                          type="button"
                          className="candidate-flow__option"
                          onClick={() => { void submitTest2Answer(activeTest2Question.question_index, index) }}
                          disabled={Boolean(busyAction)}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  )}
                </section>
              ) : null}

              {activeBooking ? (
                <section className="candidate-flow__card candidate-flow__booking" data-testid="candidate-flow-booked">
                  <span className="candidate-flow__eyebrow">Запись</span>
                  <h2>{normalizeBookingStatus(activeBooking.status)}</h2>
                  <p>{activeBooking.recruiter_name} · {formatDateTime(activeBooking.start_utc)}</p>
                  <button
                    type="button"
                    className="candidate-flow__button candidate-flow__button--primary"
                    onClick={() => { void confirmBooking(activeBooking.booking_id) }}
                    disabled={Boolean(busyAction) || normalizeBookingStatus(activeBooking.status) === 'Подтверждено'}
                  >
                    {busyAction === 'confirm-booking' ? 'Подтверждаем...' : 'Подтвердить встречу'}
                  </button>
                </section>
              ) : null}

              {bookingActionable && isIdentityVerified && !activeBooking ? (
                <BookingPanel
                  bookingContext={bookingContext}
                  cities={cities}
                  recruiters={recruiters}
                  slots={slots}
                  selectedSlotId={selectedSlotId}
                  isSocialVerified={isBookingReady}
                  verification={verification}
                  busyAction={busyAction}
                  onSelectCity={selectCity}
                  onSelectRecruiter={selectRecruiter}
                  onSelectSlot={setSelectedSlotId}
                  onCreateBooking={createBooking}
                  onStartVerification={startVerification}
                  onRefreshVerification={refreshVerification}
                  onLocalConfirmVerification={localConfirmVerification}
                />
              ) : null}
            </div>
          </div>
          </>
        ) : null}
      </section>
    </main>
  )
}

function PublicCampaignLanding({
  campaign,
  status,
  pollToken,
  busyAction,
  onStartVerification,
  onRefreshVerification,
  onLocalConfirmVerification,
}: {
  campaign: PublicCampaign
  status: PublicVerificationStatus | null
  pollToken: string | null
  busyAction: string | null
  onStartVerification: (channel: 'telegram' | 'max' | 'hh') => Promise<void>
  onRefreshVerification: () => Promise<void>
  onLocalConfirmVerification: (channel: 'telegram' | 'max' | 'hh') => Promise<void>
}) {
  const allowed = new Set(campaign.allowed_providers)
  const localConfirm = Boolean(campaign.availability_flags?.local_confirm)
  const providerLabel = status?.provider ? status.provider.toUpperCase() : 'не выбран'
  const isPending = Boolean(pollToken && status?.status !== 'verified')
  return (
    <section className="candidate-flow__card candidate-flow__verification" data-testid="candidate-flow-public-start">
      <div>
        <span className="candidate-flow__eyebrow">Массовый вход</span>
        <h2>{campaign.copy?.title || campaign.title}</h2>
        <p>{campaign.copy?.subtitle || 'Подтвердите профиль, затем система откроет анкету Test1.'}</p>
        {campaign.city_label ? <p>Город потока: {campaign.city_label}</p> : null}
      </div>
      <div className="candidate-flow__verification-badges">
        <span className="candidate-flow__status-pill" data-state={campaign.available ? 'verified' : 'pending'}>
          Кампания: {campaign.available ? 'активна' : 'недоступна'}
        </span>
        <span className="candidate-flow__status-pill" data-state={status?.verified ? 'verified' : 'pending'}>
          Проверка: {status?.verified ? 'подтверждена' : isPending ? `ожидаем ${providerLabel}` : 'не начата'}
        </span>
      </div>
      <div className="candidate-flow__verification-actions">
        {allowed.has('telegram') ? (
          <button
            type="button"
            className="candidate-flow__button candidate-flow__button--primary"
            onClick={() => { void onStartVerification('telegram') }}
            disabled={Boolean(busyAction) || !campaign.available}
          >
            {busyAction === 'public-verification:telegram' ? 'Открываем...' : 'Подтвердить Telegram'}
          </button>
        ) : null}
        {allowed.has('max') ? (
          <button
            type="button"
            className="candidate-flow__button candidate-flow__button--secondary"
            onClick={() => { void onStartVerification('max') }}
            disabled={Boolean(busyAction) || !campaign.available}
          >
            {busyAction === 'public-verification:max' ? 'Открываем...' : 'Подтвердить MAX'}
          </button>
        ) : null}
        {allowed.has('hh') ? (
          <button
            type="button"
            className="candidate-flow__button candidate-flow__button--secondary"
            onClick={() => { void onStartVerification('hh') }}
            disabled={Boolean(busyAction) || !campaign.available}
          >
            {busyAction === 'public-verification:hh' ? 'Открываем...' : 'Подтвердить hh.ru'}
          </button>
        ) : null}
        <button
          type="button"
          className="candidate-flow__button candidate-flow__button--secondary"
          onClick={() => { void onRefreshVerification() }}
          disabled={Boolean(busyAction) || !pollToken}
        >
          {busyAction === 'public-verification:refresh' ? 'Проверяем...' : 'Я подтвердил, обновить статус'}
        </button>
        {localConfirm && pollToken ? (
          <>
            {allowed.has('telegram') ? (
              <button
                type="button"
                className="candidate-flow__button candidate-flow__button--secondary"
                onClick={() => { void onLocalConfirmVerification('telegram') }}
                disabled={Boolean(busyAction)}
              >
                Локально Telegram
              </button>
            ) : null}
            {allowed.has('hh') ? (
              <button
                type="button"
                className="candidate-flow__button candidate-flow__button--secondary"
                onClick={() => { void onLocalConfirmVerification('hh') }}
                disabled={Boolean(busyAction)}
              >
                Локально HH
              </button>
            ) : null}
            {allowed.has('max') ? (
              <button
                type="button"
                className="candidate-flow__button candidate-flow__button--secondary"
                onClick={() => { void onLocalConfirmVerification('max') }}
                disabled={Boolean(busyAction)}
              >
                Локально MAX
              </button>
            ) : null}
          </>
        ) : null}
      </div>
      <p className="candidate-flow__hint">
        Глобальная ссылка не содержит персональный токен. Анкета откроется только после подтверждения личности.
      </p>
    </section>
  )
}

function BookingPanel({
  bookingContext,
  cities,
  recruiters,
  slots,
  selectedSlotId,
  isSocialVerified,
  verification,
  busyAction,
  onSelectCity,
  onSelectRecruiter,
  onSelectSlot,
  onCreateBooking,
  onStartVerification,
  onRefreshVerification,
  onLocalConfirmVerification,
}: {
  bookingContext: BookingContext | null
  cities: CityInfo[]
  recruiters: RecruiterInfo[]
  slots: SlotInfo[]
  selectedSlotId: number | null
  isSocialVerified: boolean
  verification: VerificationStatus | null
  busyAction: string | null
  onSelectCity: (cityId: number) => Promise<void>
  onSelectRecruiter: (recruiterId: number) => Promise<void>
  onSelectSlot: (slotId: number) => void
  onCreateBooking: () => Promise<void>
  onStartVerification: (channel: 'telegram' | 'max' | 'hh') => Promise<void>
  onRefreshVerification: () => Promise<void>
  onLocalConfirmVerification: (channel: 'telegram' | 'max' | 'hh') => Promise<void>
}) {
  const visibleRecruiters = uniqueRecruiters(recruiters, slots)
  const selectedDay = selectedSlotId
    ? dateKey(slots.find((slot) => slot.slot_id === selectedSlotId)?.start_utc || slots[0]?.start_utc || '')
    : dateKey(slots[0]?.start_utc || '')
  const dayKeys = Array.from(new Set(slots.map((slot) => dateKey(slot.start_utc))))
  const visibleSlots = selectedDay ? slots.filter((slot) => dateKey(slot.start_utc) === selectedDay) : slots

  return (
    <section className="candidate-flow__card candidate-flow__booking" data-testid="candidate-flow-booking">
      <div className="candidate-flow__booking-stage">
        <div className="candidate-flow__booking-copy">
          <span className="candidate-flow__eyebrow">Выбор времени</span>
          <h2>Выберите слот в календаре</h2>
            <p>
              {isSocialVerified
                ? 'Выберите город, рекрутера и удобное время интервью.'
                : 'Для записи нужен Telegram/MAX или контакт из импортированного HH-резюме.'}
            </p>
          {!isSocialVerified ? (
            <div className="candidate-flow__verification-inline" data-testid="candidate-flow-verification-gate">
              <h3>Подтвердите профиль</h3>
              <p>Запись на слот откроется после Telegram/MAX или HH с доступным контактом.</p>
              <VerificationBadges verification={verification} />
              <VerificationActions
                verification={verification}
                busyAction={busyAction}
                onStartVerification={onStartVerification}
                onRefreshVerification={onRefreshVerification}
                onLocalConfirmVerification={onLocalConfirmVerification}
              />
            </div>
          ) : null}
        </div>
        <div className="candidate-flow__recruiter-orbit" aria-label="Рекрутеры">
          <div className="candidate-flow__orbit-core">
            <div>
              HR
              <small>online</small>
            </div>
          </div>
          <div className="candidate-flow__avatar-orbit">
            {(visibleRecruiters.length > 0 ? visibleRecruiters : [{ id: 0, name: 'Рекрутер', availableSlots: 0 }]).map((recruiter, index) => (
              <div
                key={recruiter.id || recruiter.name}
                className="candidate-flow__recruiter-avatar"
                style={{ '--i': index } as CSSProperties}
                title={recruiter.name}
              >
                <span>{recruiterInitials(recruiter.name)}</span>
                <small>{recruiter.availableSlots} сл.</small>
              </div>
            ))}
          </div>
          <div className="candidate-flow__orbit-status" aria-hidden="true">
            <span>{visibleRecruiters.length || recruiters.length || 1} рекрутер</span>
            <span>{slots.length || cities.reduce((total, city) => total + city.available_slots, 0)} слотов</span>
          </div>
        </div>
      </div>

      {!bookingContext?.city_id ? (
        <div className="candidate-flow__choice-grid">
          {cities.map((city) => (
            <button
              key={city.city_id}
              type="button"
              className="candidate-flow__choice-card"
              onClick={() => { void onSelectCity(city.city_id) }}
              disabled={Boolean(busyAction) || !city.has_available_recruiters || !isSocialVerified}
            >
              <strong>{city.city_name}</strong>
              <span>{city.available_slots} слотов · {city.available_recruiters} рекрутеров</span>
            </button>
          ))}
        </div>
      ) : !bookingContext.recruiter_id ? (
        <div className="candidate-flow__choice-grid">
          {recruiters.map((recruiter) => (
            <button
              key={recruiter.recruiter_id}
              type="button"
              className="candidate-flow__choice-card"
              onClick={() => { void onSelectRecruiter(recruiter.recruiter_id) }}
              disabled={Boolean(busyAction) || recruiter.available_slots <= 0 || !isSocialVerified}
            >
              <strong>{recruiter.recruiter_name}</strong>
              <span>{recruiter.available_slots} слотов</span>
            </button>
          ))}
        </div>
      ) : slots.length > 0 ? (
        <>
          <div className="candidate-flow__booking-calendar" aria-label="Календарь доступных дней">
            <div className="candidate-flow__calendar-days">
              {dayKeys.map((key) => (
                <button
                  key={key}
                  type="button"
                  className="candidate-flow__calendar-day"
                  data-selected={key === selectedDay}
                  onClick={() => {
                    const firstSlot = slots.find((slot) => dateKey(slot.start_utc) === key)
                    if (firstSlot) onSelectSlot(firstSlot.slot_id)
                  }}
                >
                  <strong>{formatDayLabel(key)}</strong>
                  <span>{slots.filter((slot) => dateKey(slot.start_utc) === key).length} слота</span>
                </button>
              ))}
            </div>
          </div>
          <div className="candidate-flow__slot-list">
            {visibleSlots.map((slot) => (
              <button
                key={slot.slot_id}
                type="button"
                className="candidate-flow__slot"
                data-selected={selectedSlotId === slot.slot_id}
                onClick={() => onSelectSlot(slot.slot_id)}
              >
                <strong>{formatDateTime(slot.start_utc)}</strong>
                <span>{slot.recruiter_name}</span>
                <small>{slot.duration_minutes} минут</small>
              </button>
            ))}
          </div>
          <button
            type="button"
            className="candidate-flow__button candidate-flow__button--primary"
            onClick={() => { void onCreateBooking() }}
            disabled={Boolean(busyAction) || !selectedSlotId || !isSocialVerified}
          >
            {busyAction === 'booking' ? 'Бронируем...' : 'Забронировать слот'}
          </button>
        </>
      ) : (
        <div className="candidate-flow__empty" data-testid="candidate-flow-no-slots">
          <strong>Свободных слотов нет</strong>
          <span>Попробуйте выбрать другой город или дождитесь сообщения рекрутера.</span>
        </div>
      )}
    </section>
  )
}

function VerificationEntry({
  verification,
  busyAction,
  onStartVerification,
  onRefreshVerification,
  onLocalConfirmVerification,
}: {
  verification: VerificationStatus | null
  busyAction: string | null
  onStartVerification: (channel: 'telegram' | 'max' | 'hh') => Promise<void>
  onRefreshVerification: () => Promise<void>
  onLocalConfirmVerification: (channel: 'telegram' | 'max' | 'hh') => Promise<void>
}) {
  return (
    <section className="candidate-flow__card candidate-flow__verification" data-testid="candidate-flow-verification-gate">
      <div>
        <span className="candidate-flow__eyebrow">Верификация</span>
        <h2>Подтвердите профиль перед анкетой</h2>
        <p>Так мы сразу свяжем Test1, запись на слот и профиль в CRM с Telegram, MAX или hh.ru.</p>
      </div>
      <VerificationBadges verification={verification} />
      <VerificationActions
        verification={verification}
        busyAction={busyAction}
        onStartVerification={onStartVerification}
        onRefreshVerification={onRefreshVerification}
        onLocalConfirmVerification={onLocalConfirmVerification}
      />
    </section>
  )
}

function AccountPanel({
  open,
  candidate,
  journey,
  activeBooking,
  verification,
  onClose,
  onStepClick,
  onStartVerification,
  onRefreshVerification,
  onLocalConfirmVerification,
  busyAction,
}: {
  open: boolean
  candidate: CandidateInfo | null
  journey: JourneyResponse
  activeBooking: Booking | null
  verification: VerificationStatus | null
  onClose: () => void
  onStepClick: (step: JourneyTimelineStep) => void
  onStartVerification: (channel: 'telegram' | 'max' | 'hh') => Promise<void>
  onRefreshVerification: () => Promise<void>
  onLocalConfirmVerification: (channel: 'telegram' | 'max' | 'hh') => Promise<void>
  busyAction: string | null
}) {
  if (!open) return null

  return (
    <div className="candidate-flow__account-backdrop" role="presentation" onClick={onClose}>
      <section
        className="candidate-flow__account-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="candidate-flow-account-title"
        data-testid="candidate-flow-account"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="candidate-flow__account-head">
          <h2 id="candidate-flow-account-title">Личный кабинет</h2>
          <button type="button" className="candidate-flow__account-close" onClick={onClose} aria-label="Закрыть личный кабинет">
            ×
          </button>
        </div>
        <section className="candidate-flow__profile-card">
          <span className="candidate-flow__eyebrow">Кандидат</span>
          <h3>{candidate?.full_name || 'Кандидат'}</h3>
          <p>{candidate?.city_name || candidate?.status || 'Город будет уточнён в анкете'}</p>
        </section>
        {activeBooking ? (
          <section className="candidate-flow__account-booking">
            <strong>{normalizeBookingStatus(activeBooking.status)}</strong>
            <p>{activeBooking.recruiter_name} · {formatDateTime(activeBooking.start_utc)}</p>
          </section>
        ) : null}
        <section className="candidate-flow__verification candidate-flow__verification--compact">
          <div>
            <span className="candidate-flow__eyebrow">Верификация</span>
            <h3>{verification?.verified ? 'Профиль подтверждён' : 'Нужно подтвердить профиль'}</h3>
            <p>Для анкеты нужен Telegram, MAX или hh.ru. Для записи нужен контакт для рекрутера.</p>
          </div>
          <VerificationBadges verification={verification} />
          {!verification?.verified ? (
            <VerificationActions
              verification={verification}
              busyAction={busyAction}
              onStartVerification={onStartVerification}
              onRefreshVerification={onRefreshVerification}
              onLocalConfirmVerification={onLocalConfirmVerification}
            />
          ) : null}
        </section>
        {verification?.hh_resume ? (
          <section className="candidate-flow__hh-resume">
            <span className="candidate-flow__eyebrow">HH-резюме</span>
            <h3>{verification.hh_resume.title || 'Резюме импортировано'}</h3>
            <p>{verification.hh_resume.city || 'Город не указан'} · {verification.hh_resume.import_status || 'synced'}</p>
            {verification.hh_resume.synced_at ? <p>Импорт: {formatDateTime(verification.hh_resume.synced_at)}</p> : null}
            {verification.hh_resume.url ? (
              <a href={verification.hh_resume.url} target="_blank" rel="noopener noreferrer">Открыть резюме на hh.ru</a>
            ) : null}
          </section>
        ) : null}
        <section className="candidate-flow__timeline" aria-label="Прогресс">
          {journey.timeline.map((step) => (
            <button
              key={step.key}
              type="button"
              className="candidate-flow__timeline-step"
              data-state={step.state}
              onClick={() => {
                onStepClick(step)
                onClose()
              }}
            >
              <strong>{step.label}</strong>
              <span>{step.state_label}</span>
            </button>
          ))}
        </section>
      </section>
    </div>
  )
}

function VerificationBadges({ verification }: { verification: VerificationStatus | null }) {
  return (
    <div className="candidate-flow__verification-badges" aria-label="Статус верификации">
      <span className="candidate-flow__status-pill" data-state={verification?.telegram.verified ? 'verified' : 'pending'}>
        Telegram: {verification?.telegram.verified ? 'подтверждён' : 'ожидает'}
      </span>
      <span className="candidate-flow__status-pill" data-state={verification?.max.verified ? 'verified' : 'pending'}>
        MAX: {verification?.max.verified ? 'подтверждён' : verification?.max.available ? 'доступен' : 'недоступен локально'}
      </span>
      <span className="candidate-flow__status-pill" data-state={verification?.hh?.verified ? 'verified' : 'pending'}>
        HH: {verification?.hh?.verified ? 'подтверждён' : verification?.hh?.available ? 'доступен' : 'недоступен локально'}
      </span>
    </div>
  )
}

function VerificationActions({
  verification,
  busyAction,
  onStartVerification,
  onRefreshVerification,
  onLocalConfirmVerification,
}: {
  verification: VerificationStatus | null
  busyAction: string | null
  onStartVerification: (channel: 'telegram' | 'max' | 'hh') => Promise<void>
  onRefreshVerification: () => Promise<void>
  onLocalConfirmVerification: (channel: 'telegram' | 'max' | 'hh') => Promise<void>
}) {
  const telegramLocal = Boolean(verification?.telegram.local_confirm_available && !verification.telegram.verified)
  const maxLocal = Boolean(verification?.max.local_confirm_available && !verification.max.verified)
  const hhLocal = Boolean(verification?.hh?.local_confirm_available && !verification.hh.verified)
  return (
    <div className="candidate-flow__verification-actions">
      <button
        type="button"
        className="candidate-flow__button candidate-flow__button--primary"
        onClick={() => { void onStartVerification('telegram') }}
        disabled={Boolean(busyAction)}
      >
        {busyAction === 'verification:telegram' ? 'Открываем...' : 'Подтвердить Telegram'}
      </button>
      <button
        type="button"
        className="candidate-flow__button candidate-flow__button--secondary"
        onClick={() => { void onStartVerification('max') }}
        disabled={Boolean(busyAction) || verification?.max.available === false}
      >
        {busyAction === 'verification:max' ? 'Открываем...' : 'Подтвердить MAX'}
      </button>
      <button
        type="button"
        className="candidate-flow__button candidate-flow__button--secondary"
        onClick={() => { void onStartVerification('hh') }}
        disabled={Boolean(busyAction) || verification?.hh?.available === false}
      >
        {busyAction === 'verification:hh' ? 'Открываем...' : 'Подтвердить hh.ru'}
      </button>
      {telegramLocal ? (
        <button
          type="button"
          className="candidate-flow__button candidate-flow__button--secondary"
          onClick={() => { void onLocalConfirmVerification('telegram') }}
          disabled={Boolean(busyAction)}
        >
          {busyAction === 'verification:telegram:local' ? 'Подтверждаем...' : 'Локально подтвердить Telegram'}
        </button>
      ) : null}
      {maxLocal ? (
        <button
          type="button"
          className="candidate-flow__button candidate-flow__button--secondary"
          onClick={() => { void onLocalConfirmVerification('max') }}
          disabled={Boolean(busyAction)}
        >
          {busyAction === 'verification:max:local' ? 'Подтверждаем...' : 'Локально подтвердить MAX'}
        </button>
      ) : null}
      {hhLocal ? (
        <button
          type="button"
          className="candidate-flow__button candidate-flow__button--secondary"
          onClick={() => { void onLocalConfirmVerification('hh') }}
          disabled={Boolean(busyAction)}
        >
          {busyAction === 'verification:hh:local' ? 'Импортируем...' : 'Локально импортировать HH'}
        </button>
      ) : null}
      <button
        type="button"
        className="candidate-flow__button candidate-flow__button--secondary"
        onClick={() => { void onRefreshVerification() }}
        disabled={Boolean(busyAction)}
      >
        {busyAction === 'verification:refresh' ? 'Проверяем...' : 'Я подтвердил, обновить статус'}
      </button>
    </div>
  )
}

function FreeTextAnswer({
  question,
  value,
  disabled,
  onChange,
  onSave,
}: {
  question: TestQuestion
  value: string
  disabled: boolean
  onChange: (value: string) => void
  onSave: (question: TestQuestion, value: string) => Promise<void>
}) {
  return (
    <div className="candidate-flow__free-answer">
      <input
        type="text"
        value={value}
        placeholder={question.placeholder || 'Введите ответ'}
        onChange={(event) => onChange(event.currentTarget.value)}
        disabled={disabled}
      />
      <button
        type="button"
        className="candidate-flow__button candidate-flow__button--secondary"
        onClick={() => { void onSave(question, value) }}
        disabled={disabled || !value.trim()}
      >
        Сохранить
      </button>
    </div>
  )
}
