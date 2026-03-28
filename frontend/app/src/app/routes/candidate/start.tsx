import { useNavigate, useParams } from '@tanstack/react-router'
import { startTransition, useEffect, useMemo, useState } from 'react'

import {
  exchangeCandidatePortalToken,
  fetchCandidatePortalJourney,
  parseCandidatePortalError,
  resolveCandidateEntryGateway,
  selectCandidateEntryChannel,
  startCandidateSharedAccessChallenge,
  switchCandidateEntryChannel,
  type CandidatePortalJourneyResponse,
  type CandidateEntryChannel,
  type CandidateEntryGatewayResponse,
  verifyCandidateSharedAccessCode,
} from '@/api/candidate'
import { queryClient } from '@/api/client'
import {
  clearCandidatePortalAccessToken,
  readCandidatePortalAccessToken,
  persistCandidatePortalEntryTokenFromUrl,
  readCandidatePortalEntryToken,
  writeCandidatePortalEntryToken,
} from '@/shared/candidate-portal-session'
import {
  ensureCandidateWebAppBridge,
  hasCandidatePortalLocationToken,
  markCandidateWebAppReady,
  persistCandidatePortalAccessToken,
  resolveCandidatePortalToken,
} from './webapp'
import '../candidate-portal.css'

const ENTRY_CHOOSER_STYLES = `
  .candidate-portal__entry-stack,
  .candidate-portal__entry-copy,
  .candidate-portal__entry-side,
  .candidate-portal__entry-channels,
  .candidate-portal__entry-option,
  .candidate-portal__entry-option-head,
  .candidate-portal__entry-feature-list,
  .candidate-portal__entry-illustration,
  .candidate-portal__entry-avatar,
  .candidate-portal__entry-timeline {
    display: grid;
  }

  .candidate-portal__entry-stack,
  .candidate-portal__entry-copy,
  .candidate-portal__entry-side,
  .candidate-portal__entry-option,
  .candidate-portal__entry-channels {
    gap: 14px;
  }

  .candidate-portal__entry-grid,
  .candidate-portal__entry-badges {
    display: grid;
    gap: 18px;
  }

  .candidate-portal__entry-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }

  .candidate-portal__entry-hero {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(260px, 0.9fr);
    gap: 18px;
    align-items: stretch;
    padding: 22px;
    position: relative;
    overflow: hidden;
    background:
      radial-gradient(circle at top left, color-mix(in srgb, var(--accent) 22%, transparent), transparent 42%),
      linear-gradient(160deg, color-mix(in srgb, var(--surface-elevated) 84%, #121a27), color-mix(in srgb, var(--surface) 84%, #0d1420));
  }

  .candidate-portal__entry-hero::after {
    content: '';
    position: absolute;
    inset: auto -10% -35% 40%;
    height: 220px;
    background: radial-gradient(circle, color-mix(in srgb, var(--accent) 18%, transparent), transparent 68%);
    pointer-events: none;
  }

  .candidate-portal__summary-card--spotlight {
    background: linear-gradient(180deg, color-mix(in srgb, var(--accent) 12%, var(--surface-elevated)), color-mix(in srgb, var(--surface-elevated) 82%, transparent));
    border-color: color-mix(in srgb, var(--accent) 48%, var(--border));
  }

  .candidate-portal__entry-grid {
    grid-template-columns: minmax(280px, 0.82fr) minmax(0, 1.18fr);
  }

  .candidate-portal__entry-timeline {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
  }

  .candidate-portal__entry-timeline-step {
    position: relative;
    display: grid;
    gap: 10px;
    padding: 12px 14px;
    min-height: 86px;
    border-radius: 18px;
    border: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
    background: color-mix(in srgb, var(--surface) 82%, transparent);
    color: var(--muted);
    font-weight: 600;
  }

  .candidate-portal__entry-timeline-step::after {
    content: '';
    position: absolute;
    top: 26px;
    left: calc(100% - 4px);
    width: 18px;
    height: 2px;
    background: color-mix(in srgb, var(--border) 78%, transparent);
  }

  .candidate-portal__entry-timeline-step:last-child::after {
    display: none;
  }

  .candidate-portal__entry-timeline-step.is-completed {
    border-color: color-mix(in srgb, var(--success) 44%, var(--border));
    background: color-mix(in srgb, var(--success) 12%, var(--surface-elevated));
    color: var(--text);
  }

  .candidate-portal__entry-timeline-step.is-current {
    border-color: color-mix(in srgb, var(--accent) 54%, var(--border));
    background: color-mix(in srgb, var(--accent) 12%, var(--surface-elevated));
    color: var(--text);
    box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 18%, transparent), 0 24px 50px color-mix(in srgb, var(--accent) 12%, transparent);
  }

  .candidate-portal__entry-timeline-dot {
    width: 14px;
    height: 14px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--surface-elevated) 86%, white);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--border) 70%, transparent);
  }

  .candidate-portal__entry-timeline-step.is-completed .candidate-portal__entry-timeline-dot {
    background: color-mix(in srgb, var(--success) 75%, white);
  }

  .candidate-portal__entry-timeline-step.is-current .candidate-portal__entry-timeline-dot {
    background: color-mix(in srgb, var(--accent) 76%, white);
    box-shadow: 0 0 0 8px color-mix(in srgb, var(--accent) 14%, transparent);
  }

  .candidate-portal__entry-illustration {
    position: relative;
    place-items: center;
    min-height: 330px;
    isolation: isolate;
  }

  .candidate-portal__entry-orbit,
  .candidate-portal__entry-path,
  .candidate-portal__entry-briefcase,
  .candidate-portal__entry-avatar {
    position: absolute;
  }

  .candidate-portal__entry-orbit {
    width: 280px;
    height: 280px;
    border-radius: 999px;
    border: 1px dashed color-mix(in srgb, var(--accent) 34%, transparent);
    opacity: 0.48;
    animation: candidate-entry-orbit 14s linear infinite;
  }

  .candidate-portal__entry-orbit--inner {
    width: 210px;
    height: 210px;
    opacity: 0.6;
    animation-direction: reverse;
    animation-duration: 10s;
  }

  .candidate-portal__entry-path {
    inset: 50% auto auto 50%;
    width: 220px;
    display: flex;
    justify-content: space-between;
    transform: translate(-50%, -50%);
  }

  .candidate-portal__entry-path span {
    width: 10px;
    height: 10px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 76%, white);
    box-shadow: 0 0 0 10px color-mix(in srgb, var(--accent) 10%, transparent);
    animation: candidate-entry-pulse 2.8s ease-in-out infinite;
  }

  .candidate-portal__entry-path span:nth-child(2) { animation-delay: 0.35s; }
  .candidate-portal__entry-path span:nth-child(3) { animation-delay: 0.7s; }

  .candidate-portal__entry-avatar {
    width: 104px;
    gap: 8px;
    justify-items: center;
    animation: candidate-entry-float 4.4s ease-in-out infinite;
  }

  .candidate-portal__entry-avatar--candidate {
    left: 10%;
    bottom: 14%;
  }

  .candidate-portal__entry-avatar--recruiter {
    right: 10%;
    top: 16%;
    animation-delay: 0.6s;
  }

  .candidate-portal__entry-avatar-head {
    width: 40px;
    height: 40px;
    border-radius: 999px;
    background: linear-gradient(180deg, color-mix(in srgb, #ffd8b2 84%, white), #f0b884);
  }

  .candidate-portal__entry-avatar-body {
    width: 72px;
    height: 72px;
    border-radius: 26px;
    background: linear-gradient(180deg, color-mix(in srgb, var(--surface-elevated) 20%, var(--accent)), color-mix(in srgb, var(--surface) 34%, #101722));
    box-shadow: 0 18px 34px rgba(0, 0, 0, 0.16);
  }

  .candidate-portal__entry-avatar--recruiter .candidate-portal__entry-avatar-body {
    background: linear-gradient(180deg, color-mix(in srgb, var(--warning) 32%, var(--surface-elevated)), color-mix(in srgb, var(--surface) 24%, #1a2231));
  }

  .candidate-portal__entry-avatar em {
    font-style: normal;
    font-size: 0.86rem;
    color: var(--muted);
  }

  .candidate-portal__entry-briefcase {
    inset: 50% auto auto 50%;
    width: 76px;
    height: 58px;
    border-radius: 18px;
    background: linear-gradient(180deg, color-mix(in srgb, var(--surface-elevated) 60%, white), color-mix(in srgb, var(--surface) 74%, #151b25));
    box-shadow: 0 18px 34px rgba(0, 0, 0, 0.18);
    transform: translate(-50%, -50%);
    animation: candidate-entry-float 3.6s ease-in-out infinite;
  }

  .candidate-portal__entry-briefcase span {
    position: absolute;
    inset: 10px 16px auto;
    height: 8px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 62%, white);
  }

  .candidate-portal__entry-feature-list {
    gap: 10px;
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .candidate-portal__entry-feature-list li {
    position: relative;
    padding-left: 18px;
    color: var(--muted);
  }

  .candidate-portal__entry-feature-list li::before {
    content: '';
    position: absolute;
    top: 0.55rem;
    left: 0;
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 76%, white);
  }

  .candidate-portal__entry-option {
    position: relative;
    padding: 20px;
    border-radius: 22px;
    border: 1px solid color-mix(in srgb, var(--border) 74%, transparent);
    background: linear-gradient(180deg, color-mix(in srgb, var(--surface-elevated) 82%, transparent), color-mix(in srgb, var(--surface) 86%, #0d1420));
    overflow: hidden;
    transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
  }

  .candidate-portal__entry-option:hover {
    transform: translateY(-3px);
    border-color: color-mix(in srgb, var(--accent) 46%, var(--border));
    box-shadow: 0 18px 34px rgba(0, 0, 0, 0.14);
  }

  .candidate-portal__entry-option.is-featured {
    border-color: color-mix(in srgb, var(--accent) 56%, var(--border));
    box-shadow: 0 22px 42px color-mix(in srgb, var(--accent) 14%, transparent);
  }

  .candidate-portal__entry-option-head {
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: 14px;
  }

  .candidate-portal__entry-option-kicker {
    margin-bottom: 6px;
    color: var(--muted);
    font-size: 0.84rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .candidate-portal__entry-option-note {
    padding: 10px 12px;
    border-radius: 14px;
    background: color-mix(in srgb, var(--surface) 88%, transparent);
    color: var(--muted);
    font-size: 0.95rem;
  }

  .candidate-portal__entry-status {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 7px 12px;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 700;
  }

  .candidate-portal__entry-status.is-ready {
    background: color-mix(in srgb, var(--success) 14%, transparent);
    color: color-mix(in srgb, var(--success) 70%, var(--text));
  }

  .candidate-portal__entry-status.is-blocked {
    background: color-mix(in srgb, var(--danger) 14%, transparent);
    color: color-mix(in srgb, var(--danger) 72%, var(--text));
  }

  @keyframes candidate-entry-float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
  }

  @keyframes candidate-entry-pulse {
    0%, 100% { transform: scale(1); opacity: 0.72; }
    50% { transform: scale(1.16); opacity: 1; }
  }

  @keyframes candidate-entry-orbit {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  @media (max-width: 959px) {
    .candidate-portal__entry-hero,
    .candidate-portal__entry-grid {
      grid-template-columns: 1fr;
    }

    .candidate-portal__entry-illustration {
      min-height: 260px;
      order: -1;
    }

    .candidate-portal__entry-timeline {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 640px) {
    .candidate-portal__entry-hero,
    .candidate-portal__entry-option {
      padding: 16px;
    }

    .candidate-portal__entry-illustration {
      min-height: 210px;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .candidate-portal__entry-avatar,
    .candidate-portal__entry-briefcase,
    .candidate-portal__entry-orbit,
    .candidate-portal__entry-path span,
    .candidate-portal__entry-option {
      animation: none !important;
      transition: none !important;
    }
  }
`

function gatewayFromJourney(payload: CandidatePortalJourneyResponse): CandidateEntryGatewayResponse {
  return {
    candidate: {
      id: payload.candidate.id,
      candidate_id: payload.candidate.candidate_id,
      fio: payload.candidate.fio,
      city: payload.candidate.city,
      vacancy_label: payload.candidate.vacancy_label,
      company: payload.company?.name,
    },
    journey: {
      session_id: payload.journey.session_id,
      current_step: payload.journey.current_step,
      current_step_label: payload.journey.current_step_label,
      status: payload.candidate.status,
      status_label: payload.candidate.status_label,
      next_action: payload.journey.next_action,
      last_entry_channel: payload.journey.last_entry_channel,
      available_channels: payload.journey.available_channels,
    },
    options: {
      web: payload.journey.channel_options?.web || { channel: 'web', enabled: true, type: 'cabinet' },
      max: payload.journey.channel_options?.max || { channel: 'max', enabled: false, reason_if_blocked: 'MAX сейчас недоступен.' },
      telegram: payload.journey.channel_options?.telegram || { channel: 'telegram', enabled: false, reason_if_blocked: 'Telegram сейчас недоступен.' },
    },
    company_preview: {
      summary: payload.company?.summary,
      highlights: payload.company?.highlights || [],
    },
    suggested_channel: 'web',
    fallback_policy: 'web_always_available_when_portal_public_ready',
  }
}

export function CandidateStartPage() {
  const { token } = useParams({ strict: false }) as { token?: string }
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [errorState, setErrorState] = useState<string | null>(null)
  const [entryGateway, setEntryGateway] = useState<CandidateEntryGatewayResponse | null>(null)
  const [entryLaunchMode, setEntryLaunchMode] = useState<'entry' | 'session'>('entry')
  const [entryPendingChannel, setEntryPendingChannel] = useState<CandidateEntryChannel | null>(null)
  const [showGenericLanding, setShowGenericLanding] = useState(false)
  const [genericNotice, setGenericNotice] = useState<string | null>(null)
  const [resumeNonce, setResumeNonce] = useState(0)
  const [sharedPhone, setSharedPhone] = useState('')
  const [sharedCode, setSharedCode] = useState('')
  const [sharedChallengeToken, setSharedChallengeToken] = useState('')
  const [sharedChallengePending, setSharedChallengePending] = useState(false)
  const [sharedVerifyPending, setSharedVerifyPending] = useState(false)
  const [sharedAccessMessage, setSharedAccessMessage] = useState<string | null>(null)

  const entryToken = useMemo(() => {
    if (typeof window === 'undefined') return ''
    return new URLSearchParams(window.location.search).get('entry')?.trim() || ''
  }, [])
  const locationHasPortalToken = useMemo(() => hasCandidatePortalLocationToken(token), [token])
  const storedAccessToken = readCandidatePortalAccessToken()
  const storedEntryToken = readCandidatePortalEntryToken()
  const hasRecoverableLocalState = Boolean(storedAccessToken || storedEntryToken)
  const recoveryEntryToken = entryToken || (locationHasPortalToken ? storedEntryToken : '')
  const recoveryEntryUrl = useMemo(
    () => (recoveryEntryToken ? `/candidate/start?entry=${encodeURIComponent(recoveryEntryToken)}` : '/candidate/start'),
    [recoveryEntryToken],
  )
  const entryJourneyPreview = useMemo(() => {
    if (!entryGateway) return []
    const currentStep = String(entryGateway.journey.current_step || '').trim()
    const order = ['profile', 'screening', 'slot_selection', 'status'] as const
    const labels: Record<string, string> = {
      profile: 'Анкета',
      screening: 'Тест 1',
      slot_selection: 'Слот',
      status: 'Диалог',
    }
    const currentIndex = Math.max(order.indexOf(currentStep as (typeof order)[number]), 0)
    return order.map((key, index) => ({
      key,
      label: labels[key] || key,
      state:
        index < currentIndex ? 'completed' : index === currentIndex ? 'current' : 'pending',
    }))
  }, [entryGateway])
  const entryChannelCards = useMemo(() => {
    if (!entryGateway) return []
    return (['web', 'max', 'telegram'] as CandidateEntryChannel[]).map((channel) => {
      const option = entryGateway.options[channel]
      return {
        channel,
        option,
        title:
          channel === 'web'
            ? 'Веб-кабинет'
            : channel === 'max'
              ? 'MAX Messenger'
              : 'Telegram',
        kicker:
          channel === 'web'
            ? 'Рекомендуем для прохождения этапов'
            : channel === 'max'
              ? 'Продолжение через MAX'
              : 'Продолжение через Telegram',
        body:
          channel === 'web'
            ? 'Пройти Test 1, записаться на слот, читать информацию о компании и общаться с рекрутером в одном кабинете.'
            : 'Запускает тот же путь через бот и возвращает вас в тот же кабинет без потери прогресса.',
        note:
          channel === 'web'
            ? 'Самый устойчивый путь для анкеты, теста и записи на собеседование.'
            : 'Подходит, если удобнее получать напоминания и продолжать диалог в мессенджере.',
        accent:
          channel === 'web'
            ? 'web'
            : channel === 'max'
              ? 'max'
              : 'telegram',
        cta:
          channel === 'web'
            ? 'Открыть кабинет'
            : channel === 'max'
              ? 'Продолжить в MAX'
              : 'Продолжить в Telegram',
        statusLabel: option?.enabled ? 'Готово' : 'Недоступно',
      }
    })
  }, [entryGateway])

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      setError(null)
      setErrorState(null)
      setEntryGateway(null)
      setEntryPendingChannel(null)
      setShowGenericLanding(false)
      setGenericNotice(null)

      const showNeutralLanding = (notice?: string | null) => {
        if (cancelled) return
        clearCandidatePortalAccessToken()
        setEntryGateway(null)
        setEntryLaunchMode('entry')
        setError(null)
        setErrorState(null)
        setShowGenericLanding(true)
        setGenericNotice(notice || null)
      }

      const recoverWithEntryToken = async (allowStoredEntryToken = false) => {
        const fallbackEntryToken = entryToken || (allowStoredEntryToken ? readCandidatePortalEntryToken() : '')
        if (!fallbackEntryToken) return false
        try {
          const payload = await resolveCandidateEntryGateway(fallbackEntryToken)
          if (cancelled) return true
          writeCandidatePortalEntryToken(fallbackEntryToken)
          setEntryGateway(payload)
          setEntryLaunchMode('entry')
          setError(null)
          setErrorState(null)
          return true
        } catch {
          return false
        }
      }

      if (entryToken) {
        try {
          const payload = await resolveCandidateEntryGateway(entryToken)
          if (cancelled) return
          writeCandidatePortalEntryToken(entryToken)
          setEntryGateway(payload)
          setEntryLaunchMode('entry')
          return
        } catch (gatewayError) {
          if (cancelled) return
          const info = parseCandidatePortalError(gatewayError)
          setError(info?.message || 'Не удалось подготовить варианты входа. Попробуйте открыть кабинет на этом устройстве ещё раз.')
          setErrorState(info?.state || null)
          return
        }
      }
      if (!locationHasPortalToken) {
        await ensureCandidateWebAppBridge()
      }
      markCandidateWebAppReady()
      const resolvedToken = resolveCandidatePortalToken(token)
      if (!resolvedToken.token) {
        if (resumeNonce > 0 && (await recoverWithEntryToken(true))) {
          return
        }
        showNeutralLanding()
        return
      }
      try {
        const payload = await exchangeCandidatePortalToken(resolvedToken.token)
        if (cancelled) return
        persistCandidatePortalEntryTokenFromUrl(payload.candidate?.entry_url)
        persistCandidatePortalAccessToken(resolvedToken.token)
        queryClient.setQueryData(['candidate-portal-journey'], payload)
        startTransition(() => {
          void navigate({ to: '/candidate/journey' })
        })
      } catch (err) {
        if (cancelled) return
        const status = err instanceof Error && 'status' in err ? Number((err as { status?: number }).status) : undefined
        if (status === 401 || status === 422) {
          const initialError = parseCandidatePortalError(err)
          const shouldSkipStoredToken = resolvedToken.direct
          const allowStoredEntryRecovery = shouldSkipStoredToken || resumeNonce > 0
          if (shouldSkipStoredToken) {
            clearCandidatePortalAccessToken()
          }
          try {
            const payload = await fetchCandidatePortalJourney({
              skipStoredPortalToken: shouldSkipStoredToken,
            })
            if (cancelled) return
            persistCandidatePortalEntryTokenFromUrl(payload.candidate?.entry_url)
            queryClient.setQueryData(['candidate-portal-journey'], payload)
            startTransition(() => {
              void navigate({ to: '/candidate/journey' })
            })
            return
          } catch (fallbackError) {
            if (cancelled) return
            if (await recoverWithEntryToken(allowStoredEntryRecovery)) {
              return
            }
            if (resolvedToken.source === 'storage') {
              showNeutralLanding(
                resumeNonce > 0
                  ? 'На этом устройстве не найден активный кабинет. Запросите новый код на стартовой странице и продолжите через удобный канал.'
                  : null,
              )
              return
            }
            const info = shouldSkipStoredToken ? initialError : parseCandidatePortalError(fallbackError)
            setError(info?.message || 'Не удалось восстановить кабинет автоматически.')
            setErrorState(info?.state || null)
            return
          }
        }
        const info = parseCandidatePortalError(err)
        setError(info?.message || 'Не удалось открыть ссылку.')
        setErrorState(info?.state || null)
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [entryToken, locationHasPortalToken, navigate, resumeNonce, token])

  const handleSelectEntryChannel = async (channel: CandidateEntryChannel) => {
    setEntryPendingChannel(channel)
    setError(null)
    try {
      const payload =
        entryLaunchMode === 'session'
          ? await switchCandidateEntryChannel(channel)
          : await selectCandidateEntryChannel(entryToken || readCandidatePortalEntryToken(), channel)
      const launchUrl = String(payload.launch?.url || payload.cabinet_url || '').trim()
      if (!launchUrl) {
        setError('Ссылка для запуска канала пока не подготовлена. Продолжайте через веб-кабинет.')
        setEntryPendingChannel(null)
        return
      }
      window.location.assign(launchUrl)
    } catch (selectError) {
      const info = parseCandidatePortalError(selectError)
      setError(info?.message || 'Не удалось запустить выбранный канал. Попробуйте ещё раз или продолжайте через веб-кабинет.')
      setErrorState(info?.state || null)
      setEntryPendingChannel(null)
    }
  }

  const handleResumeOnThisDevice = () => {
    setResumeNonce((current) => current + 1)
  }

  const handleRequestSharedAccessCode = async () => {
    setSharedChallengePending(true)
    setError(null)
    setErrorState(null)
    setSharedAccessMessage(null)
    try {
      const payload = await startCandidateSharedAccessChallenge(sharedPhone)
      setSharedChallengeToken(payload.challenge_token)
      setSharedCode('')
      setSharedAccessMessage(
        payload.delivery_hint || payload.message || 'Если номер найден, код отправлен в связанный канал кандидата.',
      )
    } catch (challengeError) {
      const info = parseCandidatePortalError(challengeError)
      setError(info?.message || 'Не удалось отправить код. Проверьте номер и попробуйте ещё раз.')
      setErrorState(info?.state || null)
    } finally {
      setSharedChallengePending(false)
    }
  }

  const handleVerifySharedAccessCode = async () => {
    setSharedVerifyPending(true)
    setError(null)
    setErrorState(null)
    try {
      const payload = await verifyCandidateSharedAccessCode(sharedChallengeToken, sharedCode)
      clearCandidatePortalAccessToken()
      writeCandidatePortalEntryToken('')
      queryClient.setQueryData(['candidate-portal-journey'], payload)
      setEntryGateway(gatewayFromJourney(payload))
      setEntryLaunchMode('session')
      setShowGenericLanding(false)
      setSharedChallengeToken('')
      setSharedCode('')
      setSharedAccessMessage(null)
      setGenericNotice(null)
    } catch (verifyError) {
      const info = parseCandidatePortalError(verifyError)
      setError(info?.message || 'Не удалось подтвердить код входа.')
      setErrorState(info?.state || null)
    } finally {
      setSharedVerifyPending(false)
    }
  }

  return (
    <div className="candidate-portal">
      <style>{ENTRY_CHOOSER_STYLES}</style>
      <div className="candidate-portal__loader">
        <div className="glass glass--elevated candidate-portal__card">
          <div className="candidate-portal__eyebrow">Candidate Portal</div>
          <h1 className="candidate-portal__title">
            {entryGateway
              ? 'Выберите, где продолжить общение'
              : showGenericLanding
                ? 'Начните путь в компании'
              : error
                ? errorState === 'blocked'
                  ? 'Доступ к кабинету недоступен'
                  : errorState === 'recoverable'
                    ? 'Восстанавливаю доступ'
                    : errorState === 'needs_new_link'
                      ? 'Продолжим через выбор канала'
                      : 'Не удалось восстановить кабинет'
                : 'Открываю ваш кабинет'}
          </h1>
          <p className="candidate-portal__subtitle">
            {entryGateway
              ? entryGateway.journey.next_action || 'Можно продолжить в браузере, MAX или Telegram без потери прогресса.'
              : showGenericLanding
                ? 'Введите телефон из отклика, получите код в HH, Telegram или MAX и выберите удобный способ продолжения.'
                : error
                ? errorState === 'blocked'
                  ? 'Кабинет сейчас недоступен в текущем режиме. Попробуйте вернуться к выбору способа входа.'
                  : errorState === 'recoverable'
                    ? 'Пробую вернуть вас в кабинет на этом устройстве без потери прогресса.'
                    : errorState === 'needs_new_link'
                      ? 'Текущий вход устарел, поэтому вернёмся к выбору Web, MAX или Telegram.'
                      : 'Сейчас попробую открыть кабинет заново на этом устройстве.'
                : 'Проверяю ссылку, поднимаю кабинет и восстанавливаю прогресс прохождения.'}
          </p>
          {error ? <p className="candidate-portal__error">{error}</p> : null}
          {showGenericLanding ? (
            <div className="candidate-portal__section-stack candidate-portal__entry-stack" style={{ marginTop: 18, textAlign: 'left' }}>
              <section className="glass candidate-portal__entry-hero">
                <div className="candidate-portal__entry-copy">
                  <div className="candidate-portal__entry-badges">
                    <span className="candidate-portal__summary-tag">Одна ссылка для всех кандидатов</span>
                    <span className="candidate-portal__summary-tag">Код придёт в связанный канал</span>
                    <span className="candidate-portal__summary-tag">Web, MAX и Telegram на выбор</span>
                  </div>
                  <div className="candidate-portal__summary-grid" aria-label="Как устроен путь кандидата">
                    <article className="glass candidate-portal__summary-card candidate-portal__summary-card--spotlight">
                      <div className="candidate-portal__summary-label">Шаг 1</div>
                      <div className="candidate-portal__summary-value">Откройте единый портал</div>
                      <div className="candidate-portal__summary-meta">Эту ссылку рекрутер отправляет всем кандидатам массово.</div>
                    </article>
                    <article className="glass candidate-portal__summary-card">
                      <div className="candidate-portal__summary-label">Шаг 2</div>
                      <div className="candidate-portal__summary-value">Подтвердите номер</div>
                      <div className="candidate-portal__summary-meta">Код придёт в уже связанный HH, Telegram или MAX без ручной ссылки.</div>
                    </article>
                    <article className="glass candidate-portal__summary-card">
                      <div className="candidate-portal__summary-label">Шаг 3</div>
                      <div className="candidate-portal__summary-value">Выберите Web, MAX или Telegram</div>
                      <div className="candidate-portal__summary-meta">Анкета, Test 1, слот и чат с рекрутером живут в одном кабинете.</div>
                    </article>
                  </div>

                  <div className="candidate-portal__entry-timeline" aria-label="Основные действия">
                    {[
                      'Единый портал',
                      'Код входа',
                      'Выбор слота',
                      'Диалог с рекрутером',
                    ].map((label, index) => (
                      <div
                        key={label}
                        className={`candidate-portal__entry-timeline-step ${index === 0 ? 'is-current' : ''}`}
                      >
                        <span className="candidate-portal__entry-timeline-dot" />
                        <span>{label}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="candidate-portal__entry-illustration" aria-hidden="true">
                  <div className="candidate-portal__entry-orbit candidate-portal__entry-orbit--outer" />
                  <div className="candidate-portal__entry-orbit candidate-portal__entry-orbit--inner" />
                  <div className="candidate-portal__entry-path">
                    <span />
                    <span />
                    <span />
                  </div>
                  <div className="candidate-portal__entry-avatar candidate-portal__entry-avatar--candidate">
                    <span className="candidate-portal__entry-avatar-head" />
                    <span className="candidate-portal__entry-avatar-body" />
                    <em>Кандидат</em>
                  </div>
                  <div className="candidate-portal__entry-briefcase">
                    <span />
                  </div>
                  <div className="candidate-portal__entry-avatar candidate-portal__entry-avatar--recruiter">
                    <span className="candidate-portal__entry-avatar-head" />
                    <span className="candidate-portal__entry-avatar-body" />
                    <em>Рекрутер</em>
                  </div>
                </div>
              </section>

              <div className="candidate-portal__entry-grid">
                <aside className="candidate-portal__entry-side">
                  <div className="candidate-portal__resource-card candidate-portal__entry-sidecard">
                    <strong>Что будет доступно после входа</strong>
                    <ul className="candidate-portal__entry-feature-list">
                      <li>Пройти анкету и Test 1 в одном потоке</li>
                      <li>Записаться на свободный слот собеседования</li>
                      <li>Получать ответы рекрутера и писать в ответ</li>
                      <li>Проверять этап найма и информацию о компании</li>
                    </ul>
                  </div>
                  <div className="candidate-portal__resource-card candidate-portal__entry-sidecard">
                    <strong>Подтверждение входа</strong>
                    <p>
                      Введите телефон, который вы использовали при отклике. Если кандидат найден,
                      система отправит одноразовый код в HH, Telegram или MAX и откроет ваш кабинет без участия рекрутера.
                    </p>
                    {sharedAccessMessage ? (
                      <p className="candidate-portal__helper">{sharedAccessMessage}</p>
                    ) : null}
                  </div>
                </aside>

                <div className="candidate-portal__entry-channels">
                  <div className="candidate-portal__entry-option is-featured">
                    <div className="candidate-portal__entry-option-head">
                      <div>
                        <div className="candidate-portal__entry-option-kicker">Шаг 1. Подтвердите себя</div>
                        <strong>Телефон из вашего отклика</strong>
                      </div>
                      <span className="candidate-portal__entry-status is-ready">Shared portal</span>
                    </div>
                    <p>Никаких персональных ссылок. Один и тот же портал подходит для всех кандидатов.</p>
                    <label className="candidate-portal__field">
                      <span className="candidate-portal__field-label">Телефон</span>
                      <input
                        className="candidate-portal__input"
                        placeholder="+7 900 000 00 00"
                        value={sharedPhone}
                        onChange={(event) => setSharedPhone(event.target.value)}
                        autoComplete="tel"
                        inputMode="tel"
                      />
                    </label>
                    <div className="candidate-portal__actions">
                      <button
                        type="button"
                        className="ui-btn ui-btn--primary"
                        disabled={sharedChallengePending || sharedPhone.trim().length < 10}
                        onClick={handleRequestSharedAccessCode}
                      >
                        {sharedChallengePending ? 'Отправляю код…' : 'Получить код входа'}
                      </button>
                    </div>
                  </div>
                  <div className="candidate-portal__entry-option">
                    <div className="candidate-portal__entry-option-head">
                      <div>
                        <div className="candidate-portal__entry-option-kicker">Шаг 2. Введите код</div>
                        <strong>Код подтверждения</strong>
                      </div>
                      <span className={`candidate-portal__entry-status ${sharedChallengeToken ? 'is-ready' : 'is-blocked'}`}>
                        {sharedChallengeToken ? 'Код отправлен' : 'Ожидает телефон'}
                      </span>
                    </div>
                    <p>Если номер найден, код придёт в доступный канал, уже связанный с вашим откликом.</p>
                    <label className="candidate-portal__field">
                      <span className="candidate-portal__field-label">Код</span>
                      <input
                        className="candidate-portal__input"
                        placeholder="123456"
                        value={sharedCode}
                        onChange={(event) => setSharedCode(event.target.value.replace(/[^\d]/g, '').slice(0, 6))}
                        inputMode="numeric"
                        autoComplete="one-time-code"
                      />
                    </label>
                    <div className="candidate-portal__actions">
                      <button
                        type="button"
                        className="ui-btn ui-btn--ghost"
                        disabled={!sharedChallengeToken || sharedVerifyPending || sharedCode.trim().length < 4}
                        onClick={handleVerifySharedAccessCode}
                      >
                        {sharedVerifyPending ? 'Проверяю…' : 'Подтвердить код'}
                      </button>
                    </div>
                  </div>
                  {[
                    {
                      title: 'Веб-кабинет',
                      kicker: 'После кода откроется основная рабочая зона',
                      note: 'Здесь кандидат проходит тесты, выбирает слот, читает информацию о компании и пишет рекрутеру.',
                    },
                    {
                      title: 'MAX и Telegram',
                      kicker: 'После кода можно продолжить в мессенджере',
                      note: 'Мессенджеры остаются launcher-слоем, а весь прогресс хранится в одном кабинете кандидата.',
                    },
                  ].map((item) => (
                    <div key={item.title} className="candidate-portal__entry-option">
                      <div className="candidate-portal__entry-option-head">
                        <div>
                          <div className="candidate-portal__entry-option-kicker">{item.kicker}</div>
                          <strong>{item.title}</strong>
                        </div>
                        <span className="candidate-portal__entry-status is-ready">После подтверждения</span>
                      </div>
                      <p>{item.note}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
          {entryGateway ? (
            <div className="candidate-portal__section-stack candidate-portal__entry-stack" style={{ marginTop: 18, textAlign: 'left' }}>
              <section className="glass candidate-portal__entry-hero">
                <div className="candidate-portal__entry-copy">
                  <div className="candidate-portal__entry-badges">
                    <span className="candidate-portal__summary-tag">Новый шаг найма</span>
                    <span className="candidate-portal__summary-tag">Прогресс сохранится автоматически</span>
                    <span className="candidate-portal__summary-tag">Можно переключать канал позже</span>
                  </div>
                  <div className="candidate-portal__summary-grid" aria-label="Входной контекст">
                    <article className="glass candidate-portal__summary-card candidate-portal__summary-card--spotlight">
                      <div className="candidate-portal__summary-label">Кандидат</div>
                      <div className="candidate-portal__summary-value">{entryGateway.candidate.fio || 'Кандидат'}</div>
                      <div className="candidate-portal__summary-meta">{entryGateway.candidate.city || 'Город уточняется'}</div>
                    </article>
                    <article className="glass candidate-portal__summary-card">
                      <div className="candidate-portal__summary-label">Вакансия</div>
                      <div className="candidate-portal__summary-value">{entryGateway.candidate.vacancy_label || 'Вакансия уточняется'}</div>
                      <div className="candidate-portal__summary-meta">{entryGateway.candidate.company || 'Компания'}</div>
                    </article>
                    <article className="glass candidate-portal__summary-card">
                      <div className="candidate-portal__summary-label">Текущий этап</div>
                      <div className="candidate-portal__summary-value">{entryGateway.journey.current_step_label || 'В обработке'}</div>
                      <div className="candidate-portal__summary-meta">{entryGateway.journey.status_label || 'Статус обновляется автоматически'}</div>
                    </article>
                  </div>

                  <div className="candidate-portal__entry-timeline" aria-label="Путь кандидата">
                    {entryJourneyPreview.map((item) => (
                      <div key={item.key} className={`candidate-portal__entry-timeline-step is-${item.state}`}>
                        <span className="candidate-portal__entry-timeline-dot" />
                        <span>{item.label}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="candidate-portal__entry-illustration" aria-hidden="true">
                  <div className="candidate-portal__entry-orbit candidate-portal__entry-orbit--outer" />
                  <div className="candidate-portal__entry-orbit candidate-portal__entry-orbit--inner" />
                  <div className="candidate-portal__entry-path">
                    <span />
                    <span />
                    <span />
                  </div>
                  <div className="candidate-portal__entry-avatar candidate-portal__entry-avatar--candidate">
                    <span className="candidate-portal__entry-avatar-head" />
                    <span className="candidate-portal__entry-avatar-body" />
                    <em>Вы</em>
                  </div>
                  <div className="candidate-portal__entry-briefcase">
                    <span />
                  </div>
                  <div className="candidate-portal__entry-avatar candidate-portal__entry-avatar--recruiter">
                    <span className="candidate-portal__entry-avatar-head" />
                    <span className="candidate-portal__entry-avatar-body" />
                    <em>Команда</em>
                  </div>
                </div>
              </section>

              <div className="candidate-portal__entry-grid">
                <aside className="candidate-portal__entry-side">
                  <div className="candidate-portal__resource-card candidate-portal__entry-sidecard">
                    <strong>Что будет доступно в кабинете</strong>
                    <ul className="candidate-portal__entry-feature-list">
                      <li>Пройти анкету и Test 1 без потери прогресса</li>
                      <li>Выбрать свободный слот и подтвердить собеседование</li>
                      <li>Написать рекрутеру и увидеть ответ в одном месте</li>
                      <li>Проверить этап найма и прочитать информацию о компании</li>
                    </ul>
                  </div>
                  {entryGateway.company_preview?.summary ? (
                    <div className="candidate-portal__resource-card candidate-portal__entry-sidecard">
                      <strong>Что дальше</strong>
                      <p>{entryGateway.company_preview.summary}</p>
                      <div className="candidate-portal__summary-tags">
                        {(entryGateway.company_preview.highlights || []).map((item) => (
                          <span key={item} className="candidate-portal__summary-tag">{item}</span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </aside>

                <div className="candidate-portal__entry-channels">
                  {entryChannelCards.map(({ channel, option, title, kicker, body, note, accent, cta, statusLabel }) => (
                    <div
                      key={channel}
                      className={`candidate-portal__entry-option candidate-portal__entry-option--${accent} ${channel === 'web' ? 'is-featured' : ''}`}
                    >
                      <div className="candidate-portal__entry-option-head">
                        <div>
                          <div className="candidate-portal__entry-option-kicker">{kicker}</div>
                          <strong>{title}</strong>
                        </div>
                        <span className={`candidate-portal__entry-status ${option?.enabled ? 'is-ready' : 'is-blocked'}`}>
                          {statusLabel}
                        </span>
                      </div>
                      <p>{body}</p>
                      <div className="candidate-portal__entry-option-note">{note}</div>
                      {option?.reason_if_blocked ? (
                        <p className="candidate-portal__helper">{option.reason_if_blocked}</p>
                      ) : null}
                      <div className="candidate-portal__actions">
                        <button
                          type="button"
                          className={`ui-btn ${channel === 'web' ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
                          disabled={!option?.enabled || entryPendingChannel !== null}
                          onClick={() => handleSelectEntryChannel(channel)}
                        >
                          {entryPendingChannel === channel ? 'Открываю…' : cta}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
          {showGenericLanding ? (
            <div className="candidate-portal__actions" style={{ justifyContent: 'center' }}>
              {hasRecoverableLocalState ? (
                <button className="ui-btn ui-btn--primary" onClick={handleResumeOnThisDevice}>
                  Продолжить на этом устройстве
                </button>
              ) : null}
              <a className="ui-btn ui-btn--ghost" href="/app/login">
                Войти для рекрутера
              </a>
            </div>
          ) : null}
          {showGenericLanding && genericNotice ? (
            <p className="candidate-portal__helper" style={{ textAlign: 'center', marginTop: 12 }}>
              {genericNotice}
            </p>
          ) : null}
          {error ? (
            <div className="candidate-portal__actions" style={{ justifyContent: 'center' }}>
              <button className="ui-btn ui-btn--primary" onClick={() => window.location.reload()}>
                Повторить
              </button>
              <a className="ui-btn ui-btn--ghost" href={recoveryEntryUrl}>
                Вернуться к выбору способа входа
              </a>
            </div>
          ) : null}
          {error ? (
            <p className="candidate-portal__helper" style={{ textAlign: 'center', marginTop: 12 }}>
              {recoveryEntryToken
                ? 'Использую сохранённый вход на этом устройстве, чтобы вернуть вас к выбору Web, MAX или Telegram.'
                : 'Если автоматическое восстановление не сработало, вернитесь на стартовую страницу и продолжите через удобный канал.'}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
