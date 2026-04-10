import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import {
  fetchCandidatePortalJourney,
  parseCandidatePortalError,
  type CandidateEntryChannel,
  type CandidateEntryGatewayOption,
  type CandidatePortalJourneyResponse,
} from '@/api/candidate'
import {
  persistCandidatePortalEntryTokenFromUrl,
  readCandidatePortalEntryToken,
} from '@/shared/candidate-portal-session'
import { ensureCandidateWebAppBridge, markCandidateWebAppReady } from './webapp'
import '../candidate-portal.css'

const JOURNEY_QUERY_KEY = ['candidate-portal-journey']

const MESSENGER_SURFACE_STYLES = `
  .candidate-portal__messenger-grid,
  .candidate-portal__messenger-steps,
  .candidate-portal__messenger-channels,
  .candidate-portal__messenger-facts {
    display: grid;
    gap: 14px;
  }

  .candidate-portal__messenger-grid {
    grid-template-columns: minmax(0, 1.15fr) minmax(280px, 0.85fr);
  }

  .candidate-portal__messenger-steps {
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  }

  .candidate-portal__messenger-channels {
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }

  .candidate-portal__messenger-card {
    position: relative;
    display: grid;
    gap: 10px;
    padding: 18px;
    border: 1px solid color-mix(in srgb, var(--border) 78%, transparent);
    border-radius: 22px;
    background: color-mix(in srgb, var(--surface-elevated) 78%, transparent);
  }

  .candidate-portal__messenger-card--accent {
    border-color: color-mix(in srgb, var(--accent) 46%, var(--border));
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--accent) 12%, var(--surface-elevated)),
      color-mix(in srgb, var(--surface-elevated) 90%, transparent)
    );
  }

  .candidate-portal__messenger-channel {
    display: grid;
    gap: 12px;
    padding: 18px;
    border: 1px solid color-mix(in srgb, var(--border) 78%, transparent);
    border-radius: 22px;
    background: color-mix(in srgb, var(--surface-elevated) 82%, transparent);
  }

  .candidate-portal__messenger-channel.is-disabled {
    opacity: 0.72;
  }

  .candidate-portal__messenger-channel-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .candidate-portal__messenger-status {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 0.84rem;
    font-weight: 700;
    background: color-mix(in srgb, var(--surface) 90%, white);
    color: var(--muted);
  }

  .candidate-portal__messenger-status.is-ready {
    background: color-mix(in srgb, var(--success) 14%, transparent);
    color: color-mix(in srgb, var(--success) 72%, var(--text));
  }

  .candidate-portal__messenger-status.is-blocked {
    background: color-mix(in srgb, var(--danger) 12%, transparent);
    color: color-mix(in srgb, var(--danger) 72%, var(--text));
  }

  .candidate-portal__messenger-note-list {
    display: grid;
    gap: 10px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .candidate-portal__messenger-note-list li {
    position: relative;
    padding-left: 18px;
    color: var(--muted);
  }

  .candidate-portal__messenger-note-list li::before {
    content: '';
    position: absolute;
    top: 0.55rem;
    left: 0;
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 76%, white);
  }

  @media (max-width: 959px) {
    .candidate-portal__messenger-grid {
      grid-template-columns: 1fr;
    }
  }
`

type JourneyViewStep = {
  key: string
  label: string
  status: 'pending' | 'in_progress' | 'completed'
}

type JourneyViewChannel = {
  channel: 'max' | 'telegram'
  label: string
  description: string
  launchUrl: string | null
  enabled: boolean
  reason: string | null
  requiresBotStart: boolean
}

type JourneyViewBrowserFallback = {
  label: string
  description: string
  launchUrl: string | null
  enabled: boolean
  reason: string | null
}

type JourneyViewModel = {
  mode: 'live' | 'preview'
  badge: string
  title: string
  subtitle: string
  candidateName: string
  city: string
  vacancy: string
  company: string
  currentStepLabel: string
  currentStatusLabel: string
  nextAction: string
  nextUpdate: string
  currentChannel: string
  highlights: string[]
  notes: string[]
  steps: JourneyViewStep[]
  channels: JourneyViewChannel[]
  browserFallback: JourneyViewBrowserFallback | null
  alerts: Array<{
    level: 'info' | 'success' | 'warning' | 'danger'
    title: string
    body: string
  }>
  history: Array<{
    kind: string
    title: string
    body: string
    createdAt: string
    statusLabel: string | null
  }>
}

type PreviewScenarioKey = 'waiting' | 'scheduled' | 'action_needed'

const CHANNEL_ORDER: Array<'max' | 'telegram'> = ['max', 'telegram']

const formatDateTime = (value?: string | null, timeZone?: string | null) => {
  if (!value) return 'Время уточняется'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: timeZone || undefined,
  }).format(date)
}

const channelMeta = (channel: 'max' | 'telegram') => (
  channel === 'max'
    ? {
      label: 'MAX',
      description: 'Здесь кандидат проходит Test 1, получает слот и видит ответы рекрутера.',
    }
    : {
      label: 'Telegram',
      description: 'Тот же flow: Test 1, подтверждение слота и обратная связь в одном messenger channel.',
    }
)

const stepNarrative = (
  currentStep: string,
  activeSlot?: CandidatePortalJourneyResponse['journey']['slots']['active'] | null,
) => {
  switch (currentStep) {
    case 'profile':
      return 'Подтвердите базовые данные в мессенджере. После этого CRM закрепит профиль кандидата и откроет следующий этап.'
    case 'screening':
      return 'Кандидату приходит Test 1 в MAX или Telegram. После завершения ответы и детали анкеты сразу появляются у рекрутера в системе.'
    case 'slot_selection':
      return 'Если кандидат проходит по критериям, рекрутер назначает слот. Предложение времени и подтверждение прилетают в мессенджер сразу.'
    case 'status':
      if (activeSlot?.start_utc) {
        return `Слот уже назначен на ${formatDateTime(activeSlot.start_utc, activeSlot.tz_name || activeSlot.candidate_tz)}. Любое изменение по встрече или статусу придёт в мессенджер в том же канале общения.`
      }
      return 'Рекрутер продолжает вести кандидата через MAX или Telegram: статусы, уточнения и следующая обратная связь приходят туда же.'
    default:
      return 'Весь путь кандидата ведётся через MAX или Telegram: Test 1, назначение слота и следующая обратная связь.'
  }
}

const normalizeAlertLevel = (value?: string | null): 'info' | 'success' | 'warning' | 'danger' => {
  if (value === 'success' || value === 'warning' || value === 'danger') return value
  return 'info'
}

const toJourneyChannels = (
  options?: Partial<Record<CandidateEntryChannel, CandidateEntryGatewayOption>>,
) => CHANNEL_ORDER.map((channel) => {
  const option = options?.[channel]
  const meta = channelMeta(channel)
  return {
    channel,
    label: meta.label,
    description: meta.description,
    launchUrl: String(option?.launch_url || '').trim() || null,
    enabled: Boolean(option?.enabled),
    reason: option?.reason_if_blocked || null,
    requiresBotStart: Boolean(option?.requires_bot_start),
  }
})

const toBrowserFallback = (
  options?: Partial<Record<CandidateEntryChannel, CandidateEntryGatewayOption>>,
): JourneyViewBrowserFallback | null => {
  const option = options?.web
  if (!option) return null
  return {
    label: 'Браузер',
    description: 'Резервный путь на том же shared candidate flow. Используйте его, если MAX или Telegram не открываются на этом устройстве.',
    launchUrl: String(option.launch_url || '').trim() || null,
    enabled: Boolean(option.enabled),
    reason: option.reason_if_blocked || null,
  }
}

function createLiveJourneyViewModel(payload: CandidatePortalJourneyResponse): JourneyViewModel {
  const activeSlot = payload.journey.slots.active || null
  const hasActiveStage = payload.journey.current_step === 'slot_selection' || payload.journey.current_step === 'status'
  const highlights = [
    payload.journey.current_step_label,
    payload.candidate.status_label || 'Статус обновляется',
    payload.journey.entry_channel === 'max' ? 'MAX' : payload.journey.entry_channel === 'telegram' ? 'Telegram' : 'Messenger',
  ].filter(Boolean)

  const alerts = [
    ...(payload.dashboard?.alerts || []).map((item) => ({
      level: normalizeAlertLevel(item.level),
      title: item.title || 'Обновление',
      body: item.body || '',
    })),
  ]

  if (alerts.length === 0) {
    alerts.push({
      level: 'info',
      title: 'Как работает путь кандидата',
      body: stepNarrative(payload.journey.current_step, activeSlot),
    })
  }

  const notes = [
    'Test 1 приходит кандидату в MAX или Telegram и сохраняется в CRM без ручного переноса.',
    'После прохождения по критериям рекрутер назначает слот в системе, а уведомление уходит в мессенджер сразу.',
    'Чат и следующая обратная связь остаются в том же мессенджере, где кандидат уже ведёт диалог.',
  ]

  if (activeSlot?.start_utc) {
    notes.unshift(`Ближайший слот: ${formatDateTime(activeSlot.start_utc, activeSlot.tz_name || activeSlot.candidate_tz)}.`)
  }

  const history = (payload.history?.items || []).map((item) => ({
    kind: item.kind || 'journey',
    title: item.title || 'Обновление',
    body: item.body || '',
    createdAt: formatDateTime(item.created_at, payload.journey.next_step_timezone || activeSlot?.tz_name || activeSlot?.candidate_tz),
    statusLabel: item.status_label || null,
  }))

  return {
    mode: 'live',
    badge: payload.journey.entry_channel === 'max' ? 'MAX flow' : payload.journey.entry_channel === 'telegram' ? 'Telegram flow' : 'Messenger flow',
    title: hasActiveStage ? 'У вас уже есть активный этап' : 'Путь кандидата в мессенджере',
    subtitle: hasActiveStage
      ? payload.journey.next_action || stepNarrative(payload.journey.current_step, activeSlot)
      : stepNarrative(payload.journey.current_step, activeSlot),
    candidateName: payload.candidate.fio || 'Кандидат',
    city: payload.candidate.city || payload.journey.profile.city_name || 'Город уточняется',
    vacancy: payload.candidate.vacancy_label || payload.candidate.vacancy_position || 'Вакансия уточняется',
    company: payload.company?.name || 'Команда подбора',
    currentStepLabel: payload.journey.current_step_label || 'В работе',
    currentStatusLabel: payload.candidate.status_label || 'Статус обновляется',
    nextAction: payload.journey.next_action || 'Следующее действие придёт в мессенджер.',
    nextUpdate: activeSlot?.start_utc
      ? formatDateTime(activeSlot.start_utc, activeSlot.tz_name || activeSlot.candidate_tz)
      : formatDateTime(payload.journey.next_step_at, payload.journey.next_step_timezone),
    currentChannel: payload.journey.entry_channel === 'max'
      ? 'MAX'
      : payload.journey.entry_channel === 'telegram'
        ? 'Telegram'
        : 'Messenger',
    highlights,
    notes,
    steps: (payload.journey.steps || []).map((step) => ({
      key: step.key,
      label: step.label,
      status: step.status === 'completed' ? 'completed' : step.status === 'in_progress' ? 'in_progress' : 'pending',
    })),
    channels: toJourneyChannels(payload.journey.channel_options),
    browserFallback: toBrowserFallback(payload.journey.channel_options),
    alerts,
    history,
  }
}

function createPreviewJourneyViewModel(scenario: PreviewScenarioKey): JourneyViewModel {
  const scenarios: Record<PreviewScenarioKey, JourneyViewModel> = {
    waiting: {
      mode: 'preview',
      badge: 'Preview',
      title: 'Messenger-first candidate flow',
      subtitle: 'Кандидат проходит Test 1 в MAX. После завершения детали анкеты сразу появляются в CRM и остаются частью одного messenger flow.',
      candidateName: 'Иван Петров',
      city: 'Москва',
      vacancy: 'Менеджер по работе с клиентами',
      company: 'SMART SERVICE',
      currentStepLabel: 'Тест 1',
      currentStatusLabel: 'Ожидаем завершение',
      nextAction: 'Пройти Test 1 в MAX и отправить ответы.',
      nextUpdate: 'После завершения рекрутер увидит анкету в CRM.',
      currentChannel: 'MAX',
      highlights: ['MAX', 'Test 1', 'CRM sync'],
      notes: [
        'Кандидат отвечает в MAX, а профиль и результаты теста появляются в карточке кандидата.',
        'Telegram работает по той же схеме: сообщения и статусы зеркалятся в CRM.',
        'MAX и Telegram остаются основными поверхностями для кандидата.',
      ],
      steps: [
        { key: 'screening', label: 'Test 1', status: 'in_progress' },
        { key: 'profile', label: 'Профиль в CRM', status: 'pending' },
        { key: 'slot', label: 'Назначение слота', status: 'pending' },
        { key: 'feedback', label: 'Обратная связь', status: 'pending' },
      ],
      channels: [
        {
          channel: 'max',
          label: 'MAX',
          description: 'Кандидат уже в диалоге с ботом и проходит текущий этап здесь.',
          launchUrl: 'https://max.ru/id1_bot?startapp=preview',
          enabled: true,
          reason: null,
          requiresBotStart: false,
        },
        {
          channel: 'telegram',
          label: 'Telegram',
          description: 'Тот же сценарий можно продолжить через Telegram, если этот канал уже связан.',
          launchUrl: 'https://t.me/test_bot?start=preview',
          enabled: true,
          reason: null,
          requiresBotStart: true,
        },
      ],
      browserFallback: {
        label: 'Браузер',
        description: 'Резервный путь на том же candidate flow, если MAX недоступен на устройстве кандидата.',
        launchUrl: '/candidate/start?entry=preview',
        enabled: true,
        reason: null,
      },
      alerts: [
        {
          level: 'info',
          title: 'Синхронизация с CRM',
          body: 'После завершения Test 1 анкета кандидата и ответы сразу видны рекрутеру в системе.',
        },
      ],
      history: [],
    },
    scheduled: {
      mode: 'preview',
      badge: 'Preview',
      title: 'Messenger-first candidate flow',
      subtitle: 'Кандидат прошёл отбор по критериям. Рекрутер назначил слот, а уведомление прилетело в MAX сразу.',
      candidateName: 'Иван Петров',
      city: 'Москва',
      vacancy: 'Менеджер по работе с клиентами',
      company: 'SMART SERVICE',
      currentStepLabel: 'Слот назначен',
      currentStatusLabel: 'Ждём подтверждение',
      nextAction: 'Подтвердить участие во встрече 05 апреля в 11:00.',
      nextUpdate: '05 апр. 2026 г., 11:00',
      currentChannel: 'MAX',
      highlights: ['MAX', 'slot pending', 'instant feedback'],
      notes: [
        'Рекрутер назначает слот в CRM, а уведомление мгновенно уходит в мессенджер.',
        'Подтверждение, перенос или отказ также возвращаются в CRM без ручной синхронизации.',
        'Telegram использует тот же outbox и тот же статусный контур.',
      ],
      steps: [
        { key: 'screening', label: 'Test 1', status: 'completed' },
        { key: 'profile', label: 'Профиль в CRM', status: 'completed' },
        { key: 'slot', label: 'Назначение слота', status: 'in_progress' },
        { key: 'feedback', label: 'Обратная связь', status: 'pending' },
      ],
      channels: [
        {
          channel: 'max',
          label: 'MAX',
          description: 'Подтверждение встречи и следующий статус приходят прямо в MAX.',
          launchUrl: 'https://max.ru/id1_bot?startapp=preview',
          enabled: true,
          reason: null,
          requiresBotStart: false,
        },
        {
          channel: 'telegram',
          label: 'Telegram',
          description: 'Если кандидат связан с Telegram, событие уйдёт туда тем же каналом уведомлений.',
          launchUrl: 'https://t.me/test_bot?start=preview',
          enabled: true,
          reason: null,
          requiresBotStart: true,
        },
      ],
      browserFallback: {
        label: 'Браузер',
        description: 'Открывает тот же этап в browser fallback без сброса прогресса.',
        launchUrl: '/candidate/start?entry=preview',
        enabled: true,
        reason: null,
      },
      alerts: [
        {
          level: 'success',
          title: 'Слот назначен',
          body: 'Кандидат получил сообщение о встрече, а CRM ждёт ответ на подтверждение.',
        },
      ],
      history: [],
    },
    action_needed: {
      mode: 'preview',
      badge: 'Preview',
      title: 'Messenger-first candidate flow',
      subtitle: 'Рекрутер вернул кандидату следующий шаг. Весь диалог и дальнейшая обратная связь остаются в том же мессенджере.',
      candidateName: 'Иван Петров',
      city: 'Москва',
      vacancy: 'Менеджер по работе с клиентами',
      company: 'SMART SERVICE',
      currentStepLabel: 'Нужно действие кандидата',
      currentStatusLabel: 'Ожидаем ответ',
      nextAction: 'Ответить рекрутеру и подтвердить готовность к следующему этапу.',
      nextUpdate: 'Сообщение уже отправлено в мессенджер.',
      currentChannel: 'Telegram',
      highlights: ['Telegram', 'feedback', 'CRM synced'],
      notes: [
        'Рекрутер пишет из CRM, а кандидат получает сообщение в своём мессенджере сразу.',
        'Ответ кандидата возвращается в recruiter inbox в том же messenger flow.',
        'MAX работает по той же схеме, если канал кандидата привязан там.',
      ],
      steps: [
        { key: 'screening', label: 'Test 1', status: 'completed' },
        { key: 'profile', label: 'Профиль в CRM', status: 'completed' },
        { key: 'slot', label: 'Назначение слота', status: 'completed' },
        { key: 'feedback', label: 'Обратная связь', status: 'in_progress' },
      ],
      channels: [
        {
          channel: 'max',
          label: 'MAX',
          description: 'Канал доступен как резервный messenger entry, если кандидат уже связан с MAX.',
          launchUrl: 'https://max.ru/id1_bot?startapp=preview',
          enabled: true,
          reason: null,
          requiresBotStart: false,
        },
        {
          channel: 'telegram',
          label: 'Telegram',
          description: 'Кандидат уже ведёт диалог в Telegram и получает новую обратную связь без задержки.',
          launchUrl: 'https://t.me/test_bot?start=preview',
          enabled: true,
          reason: null,
          requiresBotStart: false,
        },
      ],
      browserFallback: {
        label: 'Браузер',
        description: 'Резервный путь, если Telegram или MAX не открываются на этом устройстве.',
        launchUrl: '/candidate/start?entry=preview',
        enabled: true,
        reason: null,
      },
      alerts: [
        {
          level: 'warning',
          title: 'Ждём ответ кандидата',
          body: 'Следующее сообщение уже ушло в Telegram и одновременно осталось в CRM для рекрутера.',
        },
      ],
      history: [],
    },
  }

  return scenarios[scenario]
}

function readPreviewMode() {
  if (typeof window === 'undefined') return false
  return new URLSearchParams(window.location.search).get('preview') === '1'
}

function readPreviewScenario(): PreviewScenarioKey {
  if (typeof window === 'undefined') return 'waiting'
  const value = new URLSearchParams(window.location.search).get('scenario')
  return value === 'scheduled' || value === 'action_needed' ? value : 'waiting'
}

function CandidateJourneyStatusScreen({
  title,
  subtitle,
  recoveryHref,
}: {
  title: string
  subtitle: string
  recoveryHref: string
}) {
  return (
    <div className="candidate-portal">
      <style>{MESSENGER_SURFACE_STYLES}</style>
      <div className="candidate-portal__loader">
        <div className="glass glass--elevated candidate-portal__card">
          <div className="candidate-portal__eyebrow">Candidate Messaging</div>
          <h1 className="candidate-portal__title">{title}</h1>
          <p className="candidate-portal__subtitle">{subtitle}</p>
          <div className="candidate-portal__actions" style={{ justifyContent: 'center' }}>
            <button className="ui-btn ui-btn--primary" onClick={() => window.location.reload()}>
              Повторить
            </button>
            <a className="ui-btn ui-btn--ghost" href={recoveryHref}>
              Вернуться на старт
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}

function CandidateJourneySurface({ viewModel }: { viewModel: JourneyViewModel }) {
  return (
    <div className="candidate-portal">
      <style>{MESSENGER_SURFACE_STYLES}</style>
      <div className="candidate-portal__shell">
        <section className="candidate-portal__hero glass glass--elevated">
          <div className="candidate-portal__eyebrow">Candidate Messaging</div>
          <div className="candidate-portal__summary-tags">
            <span className="candidate-portal__summary-tag">{viewModel.badge}</span>
            {viewModel.highlights.map((item) => (
              <span key={item} className="candidate-portal__summary-tag">{item}</span>
            ))}
          </div>
          <h1 className="candidate-portal__title">{viewModel.title}</h1>
          <p className="candidate-portal__subtitle">{viewModel.subtitle}</p>
          <div className="candidate-portal__summary-grid">
            <article className="candidate-portal__summary-card candidate-portal__summary-card--company">
              <div className="candidate-portal__summary-label">Кандидат</div>
              <div className="candidate-portal__summary-value">{viewModel.candidateName}</div>
              <div className="candidate-portal__summary-meta">{viewModel.city}</div>
            </article>
            <article className="candidate-portal__summary-card">
              <div className="candidate-portal__summary-label">Вакансия</div>
              <div className="candidate-portal__summary-value">{viewModel.vacancy}</div>
              <div className="candidate-portal__summary-meta">{viewModel.company}</div>
            </article>
            <article className="candidate-portal__summary-card">
              <div className="candidate-portal__summary-label">Текущий этап</div>
              <div className="candidate-portal__summary-value">{viewModel.currentStepLabel}</div>
              <div className="candidate-portal__summary-meta">{viewModel.currentStatusLabel}</div>
            </article>
            <article className="candidate-portal__summary-card">
              <div className="candidate-portal__summary-label">Активный канал</div>
              <div className="candidate-portal__summary-value">{viewModel.currentChannel}</div>
              <div className="candidate-portal__summary-meta">{viewModel.nextUpdate}</div>
            </article>
          </div>
        </section>

        <div className="candidate-portal__messenger-grid">
          <div className="candidate-portal__section-stack">
            <article className="candidate-portal__messenger-card candidate-portal__messenger-card--accent">
              <div className="candidate-portal__card-head">
                <span className="candidate-portal__summary-label">Что происходит дальше</span>
                <strong>{viewModel.currentStepLabel}</strong>
              </div>
              <p className="candidate-portal__card-copy">{viewModel.nextAction}</p>
              <ul className="candidate-portal__messenger-note-list">
                {viewModel.notes.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>

            <article className="candidate-portal__card glass glass--elevated">
              <div className="candidate-portal__card-head">
                <span className="candidate-portal__summary-label">Этапы</span>
                <strong>CRM ↔ Messenger</strong>
              </div>
              <div className="candidate-portal__messenger-steps">
                {viewModel.steps.map((step) => (
                  <div key={step.key} className="candidate-portal__step" data-state={step.status}>
                    <div className="candidate-portal__summary-label">{step.status === 'completed' ? 'Завершено' : step.status === 'in_progress' ? 'Текущий этап' : 'Далее'}</div>
                    <div className="candidate-portal__step-label">{step.label}</div>
                  </div>
                ))}
              </div>
            </article>

            <article className="candidate-portal__card">
              <div className="candidate-portal__card-head">
                <span className="candidate-portal__summary-label">Обновления</span>
                <strong>Сигналы для кандидата</strong>
              </div>
              <div className="candidate-portal__section-stack">
                {viewModel.alerts.map((alert) => (
                  <div key={`${alert.level}-${alert.title}`} className="candidate-portal__alert-card" data-level={alert.level}>
                    <strong>{alert.title}</strong>
                    <p>{alert.body}</p>
                  </div>
                ))}
              </div>
            </article>

            <article className="candidate-portal__card glass glass--elevated">
              <div className="candidate-portal__card-head">
                <span className="candidate-portal__summary-label">История пути</span>
                <strong>Что уже произошло</strong>
              </div>
              <div className="candidate-portal__section-stack">
                {viewModel.history.length > 0 ? viewModel.history.map((item, index) => (
                  <div key={`${item.kind}-${item.title}-${index}`} className="candidate-portal__messenger-card">
                    <div className="candidate-portal__card-head">
                      <span className="candidate-portal__summary-label">{item.createdAt}</span>
                      {item.statusLabel ? <strong>{item.statusLabel}</strong> : null}
                    </div>
                    <strong>{item.title}</strong>
                    <p className="candidate-portal__card-copy">{item.body}</p>
                  </div>
                )) : (
                  <p className="candidate-portal__helper">История обновится автоматически, как только появятся новые действия по вашему этапу.</p>
                )}
              </div>
            </article>
          </div>

          <aside className="candidate-portal__section-stack">
            <article className="candidate-portal__card">
              <div className="candidate-portal__card-head">
                <span className="candidate-portal__summary-label">Продолжить в мессенджере</span>
                <strong>MAX и Telegram</strong>
              </div>
              <div className="candidate-portal__messenger-channels">
                {viewModel.channels.map((channel) => (
                  <div
                    key={channel.channel}
                    className={`candidate-portal__messenger-channel ${channel.enabled ? '' : 'is-disabled'}`}
                  >
                    <div className="candidate-portal__messenger-channel-head">
                      <div>
                        <div className="candidate-portal__summary-label">{channel.label}</div>
                        <strong>{channel.description}</strong>
                      </div>
                      <span className={`candidate-portal__messenger-status ${channel.enabled ? 'is-ready' : 'is-blocked'}`}>
                        {channel.enabled ? 'Готово' : 'Недоступно'}
                      </span>
                    </div>
                    {channel.reason ? <p className="candidate-portal__helper">{channel.reason}</p> : null}
                    {channel.requiresBotStart ? (
                      <p className="candidate-portal__helper">Если бот ещё не активирован, сначала откройте диалог в мессенджере.</p>
                    ) : null}
                    <div className="candidate-portal__actions">
                      {channel.launchUrl ? (
                        <a
                          className={`ui-btn ${channel.enabled ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
                          href={channel.launchUrl}
                          aria-disabled={!channel.enabled}
                          onClick={(event) => {
                            if (!channel.enabled) event.preventDefault()
                          }}
                        >
                          Открыть {channel.label}
                        </a>
                      ) : (
                        <button type="button" className="ui-btn ui-btn--ghost" disabled>
                          Ссылка не готова
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </article>

            {viewModel.browserFallback ? (
              <article className="candidate-portal__resource-card">
                <strong>Резервный вход в браузере</strong>
                <p>{viewModel.browserFallback.description}</p>
                {viewModel.browserFallback.reason ? (
                  <p className="candidate-portal__helper">{viewModel.browserFallback.reason}</p>
                ) : null}
                <div className="candidate-portal__actions">
                  {viewModel.browserFallback.launchUrl ? (
                    <a
                      className={`ui-btn ${viewModel.browserFallback.enabled ? 'ui-btn--ghost' : 'ui-btn--ghost'}`}
                      href={viewModel.browserFallback.launchUrl}
                      aria-disabled={!viewModel.browserFallback.enabled}
                      onClick={(event) => {
                        if (!viewModel.browserFallback?.enabled) event.preventDefault()
                      }}
                    >
                      Открыть в браузере
                    </a>
                  ) : (
                    <button type="button" className="ui-btn ui-btn--ghost" disabled>
                      Браузерный вход не готов
                    </button>
                  )}
                </div>
              </article>
            ) : null}

            <article className="candidate-portal__resource-card">
              <strong>Как это работает с Telegram</strong>
              <p>
                Telegram использует тот же контур, что и MAX: кандидат получает Test 1, завершает его в чате, CRM сохраняет профиль и результаты,
                а назначение слота и обратная связь отправляются через тот же outbox в том же канале общения.
              </p>
            </article>
          </aside>
        </div>
      </div>
    </div>
  )
}

function CandidateJourneyLivePage() {
  const journeyQuery = useQuery<CandidatePortalJourneyResponse>({
    queryKey: JOURNEY_QUERY_KEY,
    queryFn: () => fetchCandidatePortalJourney(),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  useEffect(() => {
    if (!journeyQuery.data) return
    persistCandidatePortalEntryTokenFromUrl(journeyQuery.data.candidate.entry_url)
  }, [journeyQuery.data])

  if (journeyQuery.isLoading) {
    return (
      <CandidateJourneyStatusScreen
        title="Подтягиваю состояние кандидата"
        subtitle="Проверяю этап подбора и доступные мессенджеры."
        recoveryHref="/candidate/start"
      />
    )
  }

  if (journeyQuery.isError || !journeyQuery.data) {
    const info = parseCandidatePortalError(journeyQuery.error)
    const entryToken = readCandidatePortalEntryToken()
    const recoveryHref = entryToken
      ? `/candidate/start?entry=${encodeURIComponent(entryToken)}`
      : '/candidate/start'

    return (
      <CandidateJourneyStatusScreen
        title={info?.state === 'needs_new_link' ? 'Нужно открыть новую ссылку' : 'Не удалось восстановить путь кандидата'}
        subtitle={info?.message || 'Текущий вход недоступен. Вернитесь на старт и продолжите через MAX или Telegram.'}
        recoveryHref={recoveryHref}
      />
    )
  }

  return <CandidateJourneySurface viewModel={createLiveJourneyViewModel(journeyQuery.data)} />
}

function CandidateJourneyPreviewPage() {
  const [scenario, setScenario] = useState<PreviewScenarioKey>(readPreviewScenario())
  const viewModel = useMemo(() => createPreviewJourneyViewModel(scenario), [scenario])

  return (
    <>
      <CandidateJourneySurface viewModel={viewModel} />
      <div
        style={{
          position: 'fixed',
          right: 16,
          bottom: 16,
          display: 'flex',
          gap: 8,
          flexWrap: 'wrap',
          zIndex: 20,
        }}
      >
        <button type="button" className={`ui-btn ui-btn--sm ${scenario === 'waiting' ? 'ui-btn--primary' : 'ui-btn--ghost'}`} onClick={() => setScenario('waiting')}>
          Test 1
        </button>
        <button type="button" className={`ui-btn ui-btn--sm ${scenario === 'scheduled' ? 'ui-btn--primary' : 'ui-btn--ghost'}`} onClick={() => setScenario('scheduled')}>
          Слот назначен
        </button>
        <button type="button" className={`ui-btn ui-btn--sm ${scenario === 'action_needed' ? 'ui-btn--primary' : 'ui-btn--ghost'}`} onClick={() => setScenario('action_needed')}>
          Обратная связь
        </button>
      </div>
    </>
  )
}

export function CandidateJourneyPage() {
  useEffect(() => {
    markCandidateWebAppReady()
    void ensureCandidateWebAppBridge().finally(() => {
      markCandidateWebAppReady()
    })
  }, [])

  if (readPreviewMode()) {
    return <CandidateJourneyPreviewPage />
  }

  return <CandidateJourneyLivePage />
}
