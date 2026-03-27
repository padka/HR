import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'

import {
  cancelCandidatePortalSlot,
  completeCandidatePortalScreening,
  confirmCandidatePortalSlot,
  parseCandidatePortalError,
  fetchCandidatePortalJourney,
  logoutCandidatePortalSession,
  reserveCandidatePortalSlot,
  rescheduleCandidatePortalSlot,
  saveCandidatePortalProfile,
  saveCandidatePortalScreeningDraft,
  sendCandidatePortalMessage,
  switchCandidateEntryChannel,
  type CandidateEntryChannel,
  type CandidatePortalJourneyResponse,
  type CandidatePortalQuestion,
  type CandidatePortalSlot,
} from '@/api/candidate'
import { clearCandidatePortalAccessToken } from '@/shared/candidate-portal-session'
import { ensureCandidateWebAppBridge, markCandidateWebAppReady } from './webapp'
import { navigateToCandidateLaunch } from './launch'
import '../candidate-portal.css'

const JOURNEY_QUERY_KEY = ['candidate-portal-journey']

type CandidateCabinetTab =
  | 'home'
  | 'workflow'
  | 'tests'
  | 'schedule'
  | 'messages'
  | 'company'
  | 'feedback'

const CABINET_TABS: Array<{ key: CandidateCabinetTab; label: string }> = [
  { key: 'home', label: 'Главная' },
  { key: 'workflow', label: 'Мой путь' },
  { key: 'tests', label: 'Тесты и анкеты' },
  { key: 'schedule', label: 'Собеседования' },
  { key: 'messages', label: 'Сообщения' },
  { key: 'company', label: 'О компании' },
  { key: 'feedback', label: 'Обратная связь' },
]

const formatDateTime = (value?: string | null, timeZone?: string | null) => {
  if (!value) return 'Дата уточняется'
  const date = new Date(value)
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: timeZone || undefined,
  }).format(date)
}

const slotStatusLabel = (status?: string | null) => {
  switch ((status || '').toLowerCase()) {
    case 'pending':
      return 'На подтверждении'
    case 'booked':
      return 'Подтвержден рекрутером'
    case 'confirmed':
    case 'confirmed_by_candidate':
      return 'Подтверждено'
    default:
      return 'Ожидает действия'
  }
}

const isSlotConfirmable = (slot?: CandidatePortalSlot | null) =>
  ['pending', 'booked'].includes(String(slot?.status || '').toLowerCase())

const isSlotAlreadyConfirmed = (slot?: CandidatePortalSlot | null) =>
  ['confirmed', 'confirmed_by_candidate'].includes(String(slot?.status || '').toLowerCase())

const resolveCabinetTab = (value?: string | null): CandidateCabinetTab => {
  if (!value) return 'home'
  if (CABINET_TABS.some((tab) => tab.key === value)) return value as CandidateCabinetTab
  return 'home'
}

function SlotCard({
  slot,
  actionLabel,
  busy,
  onAction,
}: {
  slot: CandidatePortalSlot
  actionLabel: string
  busy?: boolean
  onAction: () => void
}) {
  return (
    <div className="candidate-portal__slot-card">
      <div>
        <strong>{formatDateTime(slot.start_utc, slot.tz_name || slot.candidate_tz)}</strong>
      </div>
      <div className="candidate-portal__slot-meta">
        {slot.city_name ? <span className="candidate-portal__chip">{slot.city_name}</span> : null}
        {slot.recruiter_name ? <span className="candidate-portal__chip">Рекрутер: {slot.recruiter_name}</span> : null}
        {slot.duration_min ? <span className="candidate-portal__chip">{slot.duration_min} мин</span> : null}
      </div>
      <div className="candidate-portal__slot-actions">
        <button className="ui-btn ui-btn--primary" onClick={onAction} disabled={busy}>
          {busy ? 'Сохраняю…' : actionLabel}
        </button>
      </div>
    </div>
  )
}

function ScreeningQuestion({
  question,
  value,
  onChange,
}: {
  question: CandidatePortalQuestion
  value: string
  onChange: (next: string) => void
}) {
  return (
    <div className="candidate-portal__question">
      <label className="candidate-portal__label">{question.prompt}</label>
      {question.helper ? <p className="candidate-portal__helper">{question.helper}</p> : null}
      {question.options && question.options.length > 0 ? (
        <div className="candidate-portal__question-options">
          {question.options.map((option) => (
            <label key={option} className="candidate-portal__option">
              <input
                type="radio"
                name={question.id}
                checked={value === option}
                onChange={() => onChange(option)}
              />
              <span>{option}</span>
            </label>
          ))}
        </div>
      ) : question.input_type === 'number' ? (
        <input
          className="candidate-portal__input"
          inputMode="numeric"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={question.placeholder || ''}
        />
      ) : (
        <textarea
          className="candidate-portal__textarea"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={question.placeholder || ''}
        />
      )}
    </div>
  )
}

function applyJourneyPayload(
  queryClient: ReturnType<typeof useQueryClient>,
  payload: CandidatePortalJourneyResponse,
) {
  queryClient.setQueryData(JOURNEY_QUERY_KEY, payload)
}

export function CandidateJourneyPage() {
  const queryClient = useQueryClient()
  const journeyQuery = useQuery<CandidatePortalJourneyResponse>({
    queryKey: JOURNEY_QUERY_KEY,
    queryFn: () => fetchCandidatePortalJourney(),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const payload = journeyQuery.data
  const currentStep = payload?.journey.current_step
  const activeSlot = payload?.journey.slots.active
  const availableSlots = payload?.journey.slots.available || []

  const [activeTab, setActiveTab] = useState<CandidateCabinetTab>('home')
  const [profileForm, setProfileForm] = useState({
    fio: '',
    phone: '',
    city_id: '',
  })
  const [screeningAnswers, setScreeningAnswers] = useState<Record<string, string>>({})
  const [messageText, setMessageText] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const [pendingSlotId, setPendingSlotId] = useState<number | null>(null)
  const [pendingChannel, setPendingChannel] = useState<CandidateEntryChannel | null>(null)
  const [supportMessage, setSupportMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!payload) return
    setProfileForm({
      fio: payload.journey.profile.fio || '',
      phone: payload.journey.profile.phone || '',
      city_id: payload.journey.profile.city_id ? String(payload.journey.profile.city_id) : '',
    })
    setScreeningAnswers(payload.journey.screening.draft_answers || {})
  }, [payload])

  useEffect(() => {
    markCandidateWebAppReady()
    void ensureCandidateWebAppBridge().finally(() => {
      markCandidateWebAppReady()
    })
  }, [])

  useEffect(() => {
    if (!payload?.dashboard?.primary_action?.target) return
    if (activeTab !== 'home') return
    setActiveTab('home')
  }, [activeTab, payload?.dashboard?.primary_action?.target])

  const handleCopySupportMessage = async () => {
    const requestText = 'Здравствуйте! Пришлите, пожалуйста, новую ссылку для входа в кабинет кандидата.'
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(requestText)
        setSupportMessage('Текст для рекрутера скопирован.')
        return
      }
    } catch {
      // Fall through to inline fallback.
    }
    setSupportMessage(requestText)
  }

  const setMutationError = (error: unknown) => {
    setLocalError(error instanceof Error ? error.message : 'Не удалось выполнить действие.')
  }

  const profileMutation = useMutation({
    mutationFn: saveCandidatePortalProfile,
    onSuccess: (nextPayload) => {
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
      setActiveTab('workflow')
    },
    onError: setMutationError,
  })

  const saveDraftMutation = useMutation({
    mutationFn: saveCandidatePortalScreeningDraft,
    onSuccess: (nextPayload) => {
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
      setActiveTab('tests')
    },
    onError: setMutationError,
  })

  const completeScreeningMutation = useMutation({
    mutationFn: completeCandidatePortalScreening,
    onSuccess: (nextPayload) => {
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
      setActiveTab('schedule')
    },
    onError: setMutationError,
  })

  const reserveSlotMutation = useMutation({
    mutationFn: reserveCandidatePortalSlot,
    onSuccess: (nextPayload) => {
      setPendingSlotId(null)
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
      setActiveTab('schedule')
    },
    onError: (error) => {
      setPendingSlotId(null)
      setMutationError(error)
    },
  })

  const confirmSlotMutation = useMutation({
    mutationFn: confirmCandidatePortalSlot,
    onSuccess: (nextPayload) => {
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
      setActiveTab('feedback')
    },
    onError: setMutationError,
  })

  const cancelSlotMutation = useMutation({
    mutationFn: cancelCandidatePortalSlot,
    onSuccess: (nextPayload) => {
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
      setActiveTab('schedule')
    },
    onError: setMutationError,
  })

  const rescheduleSlotMutation = useMutation({
    mutationFn: rescheduleCandidatePortalSlot,
    onSuccess: (nextPayload) => {
      setPendingSlotId(null)
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
      setActiveTab('schedule')
    },
    onError: (error) => {
      setPendingSlotId(null)
      setMutationError(error)
    },
  })

  const sendMessageMutation = useMutation({
    mutationFn: sendCandidatePortalMessage,
    onSuccess: (nextPayload) => {
      setMessageText('')
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
      setActiveTab('messages')
    },
    onError: setMutationError,
  })

  const switchChannelMutation = useMutation({
    mutationFn: switchCandidateEntryChannel,
    onSuccess: (_, channel) => {
      setLocalError(null)
      queryClient.setQueryData(
        JOURNEY_QUERY_KEY,
        (current: CandidatePortalJourneyResponse | undefined) =>
          current
            ? {
                ...current,
                journey: {
                  ...current.journey,
                  entry_channel: channel,
                  last_entry_channel: channel,
                },
              }
            : current,
      )
    },
    onError: setMutationError,
  })

  const logoutMutation = useMutation({
    mutationFn: logoutCandidatePortalSession,
    onSuccess: async () => {
      clearCandidatePortalAccessToken()
      queryClient.removeQueries({ queryKey: JOURNEY_QUERY_KEY })
      window.location.reload()
    },
  })

  const screeningQuestions = payload?.journey.screening.questions || []
  const screeningCompleted = Boolean(payload?.journey.screening.completed)
  const messages = payload?.journey.messages || []
  const companyName = payload?.company?.name || 'SMART SERVICE'
  const companySummary =
    payload?.company?.summary
    || `Вы проходите отбор в ${companyName}. В кабинете доступны анкета, текущий этап и запись на следующий шаг.`
  const companyHighlights =
    payload?.company?.highlights?.length
      ? payload.company.highlights
      : [
          'Анкета и прогресс сохраняются автоматически',
          'Статус и следующий шаг видны в одном месте',
          'Запись на собеседование доступна из кабинета',
        ]
  const faqItems = payload?.resources?.faq || payload?.company?.faq || []
  const resourceDocuments = payload?.resources?.documents || payload?.company?.documents || []
  const contactItems = payload?.resources?.contacts || payload?.company?.contacts || []
  const feedbackItems = payload?.feedback?.items || []
  const testsItems = payload?.tests?.items || []
  const inboxMeta = payload?.journey.inbox || null
  const latestInboxMessage = inboxMeta?.latest_message || null
  const cabinetAlerts = payload?.dashboard?.alerts || []
  const primaryAction = payload?.dashboard?.primary_action || null
  const dashboardUpcoming = payload?.dashboard?.upcoming_items || []
  const channelOptions = payload?.journey.channel_options || {}

  const canReschedule = Boolean(activeSlot) && availableSlots.length > 0
  const canConfirm = isSlotConfirmable(activeSlot)

  const statusSummary = useMemo(() => {
    if (!payload) return ''
    if (activeSlot) {
      return slotStatusLabel(activeSlot.status)
    }
    if (payload.candidate.status_label) return payload.candidate.status_label
    return 'В обработке'
  }, [activeSlot, payload])

  const vacancyLabel = payload?.candidate.vacancy_label || 'Вакансия уточняется'
  const vacancyMeta =
    payload?.candidate.vacancy_position || payload?.candidate.vacancy_reference || 'Информация о вакансии подтянется из CRM'
  const nextStepLabel = payload?.journey.next_step_at
    ? formatDateTime(payload.journey.next_step_at, payload.journey.next_step_timezone)
    : 'Следующий шаг пока не назначен'
  const nextStepMeta = payload?.journey.next_step_timezone
    ? `Часовой пояс: ${payload.journey.next_step_timezone}`
    : 'Данные обновляются автоматически'
  const portalError = parseCandidatePortalError(journeyQuery.error)

  const openPrimaryActionTarget = () => {
    setActiveTab(resolveCabinetTab(primaryAction?.target))
  }

  const handleOpenChannel = async (channel: CandidateEntryChannel) => {
    const option = channelOptions[channel]
    const launchUrl = String(option?.launch_url || '').trim()
    if (!launchUrl) {
      setLocalError(option?.reason_if_blocked || 'Новый канал пока недоступен. Попросите рекрутера переотправить доступ.')
      return
    }
    setLocalError(null)
    setPendingChannel(channel)
    try {
      const result = await switchChannelMutation.mutateAsync(channel)
      const nextUrl = String(result?.launch?.url || launchUrl).trim()
      if (!nextUrl) {
        setLocalError('Не удалось открыть новый канал. Попросите рекрутера переотправить доступ.')
        return
      }
      navigateToCandidateLaunch(nextUrl)
    } catch {
      // Error is normalized in onError.
    } finally {
      setPendingChannel(null)
    }
  }

  const renderProfileForm = () => (
    <section className="glass glass--elevated candidate-portal__card">
      <div className="candidate-portal__card-head">
        <h2 className="candidate-portal__card-title">Профиль кандидата</h2>
        <p className="candidate-portal__card-copy">Сохраняем контакты, чтобы кабинет и переписка оставались доступными без привязки к одному мессенджеру.</p>
      </div>
      <form
        className="candidate-portal__form"
        onSubmit={(event) => {
          event.preventDefault()
          setLocalError(null)
          profileMutation.mutate({
            fio: profileForm.fio,
            phone: profileForm.phone,
            city_id: Number(profileForm.city_id),
          })
        }}
      >
        <div className="candidate-portal__form-grid">
          <div className="candidate-portal__field">
            <label className="candidate-portal__label">ФИО</label>
            <input
              className="candidate-portal__input"
              value={profileForm.fio}
              onChange={(event) => setProfileForm((current) => ({ ...current, fio: event.target.value }))}
              placeholder="Иванов Иван Иванович"
            />
          </div>
          <div className="candidate-portal__field">
            <label className="candidate-portal__label">Телефон</label>
            <input
              className="candidate-portal__input"
              value={profileForm.phone}
              onChange={(event) => setProfileForm((current) => ({ ...current, phone: event.target.value }))}
              placeholder="+7 999 123-45-67"
            />
          </div>
          <div className="candidate-portal__field">
            <label className="candidate-portal__label">Город</label>
            <select
              className="candidate-portal__select"
              value={profileForm.city_id}
              onChange={(event) => setProfileForm((current) => ({ ...current, city_id: event.target.value }))}
            >
              <option value="">Выберите город</option>
              {payload?.journey.cities.map((city) => (
                <option key={city.id} value={city.id}>{city.name}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="candidate-portal__actions">
          <button className="ui-btn ui-btn--primary" type="submit" disabled={profileMutation.isPending}>
            {profileMutation.isPending ? 'Сохраняю…' : 'Сохранить и продолжить'}
          </button>
        </div>
      </form>
    </section>
  )

  const renderScreeningForm = () => (
    <section className="glass glass--elevated candidate-portal__card">
      <div className="candidate-portal__card-head">
        <h2 className="candidate-portal__card-title">Короткая анкета</h2>
        <p className="candidate-portal__card-copy">Ответы сохраняются как черновик. Можно вернуться позже и продолжить с того же места.</p>
      </div>
      <div className="candidate-portal__form">
        {screeningQuestions.map((question) => (
          <ScreeningQuestion
            key={question.id}
            question={question}
            value={screeningAnswers[question.id] || ''}
            onChange={(nextValue) => setScreeningAnswers((current) => ({ ...current, [question.id]: nextValue }))}
          />
        ))}
        <div className="candidate-portal__actions">
          <button
            className="ui-btn ui-btn--ghost"
            type="button"
            onClick={() => {
              setLocalError(null)
              saveDraftMutation.mutate(screeningAnswers)
            }}
            disabled={saveDraftMutation.isPending}
          >
            {saveDraftMutation.isPending ? 'Сохраняю…' : 'Сохранить черновик'}
          </button>
          <button
            className="ui-btn ui-btn--primary"
            type="button"
            onClick={() => {
              setLocalError(null)
              completeScreeningMutation.mutate(screeningAnswers)
            }}
            disabled={completeScreeningMutation.isPending}
          >
            {completeScreeningMutation.isPending ? 'Отправляю…' : 'Завершить анкету'}
          </button>
        </div>
      </div>
    </section>
  )

  const renderSchedulePanel = () => (
    <section className="glass glass--elevated candidate-portal__card">
      <div className="candidate-portal__card-head">
        <h2 className="candidate-portal__card-title">Собеседования и расписание</h2>
        <p className="candidate-portal__card-copy">
          {activeSlot
            ? 'Вы можете подтвердить встречу, отменить её или сразу запросить перенос на другой слот.'
            : 'Когда слот появится, кабинет покажет его здесь. Запись на собеседование всегда остается внутри кабинета.'}
        </p>
      </div>

      {currentStep === 'slot_selection' ? (
        <div className="candidate-portal__slots">
          {availableSlots.length === 0 ? (
            <p className="candidate-portal__empty">Свободных слотов пока нет. Мы сохранили ваш прогресс и покажем новый слот, как только он появится.</p>
          ) : (
            availableSlots.map((slot) => (
              <SlotCard
                key={slot.id}
                slot={slot}
                actionLabel="Выбрать слот"
                busy={reserveSlotMutation.isPending && pendingSlotId === slot.id}
                onAction={() => {
                  setPendingSlotId(slot.id)
                  setLocalError(null)
                  reserveSlotMutation.mutate(slot.id)
                }}
              />
            ))
          )}
        </div>
      ) : null}

      {activeSlot ? (
        <div className="candidate-portal__status-card">
          <strong>{formatDateTime(activeSlot.start_utc, activeSlot.tz_name || activeSlot.candidate_tz)}</strong>
          <div className="candidate-portal__status-meta">
            <span className="candidate-portal__chip">{slotStatusLabel(activeSlot.status)}</span>
            {activeSlot.city_name ? <span className="candidate-portal__chip">{activeSlot.city_name}</span> : null}
            {activeSlot.recruiter_name ? <span className="candidate-portal__chip">Рекрутер: {activeSlot.recruiter_name}</span> : null}
          </div>
          <div className="candidate-portal__status-actions">
            {canConfirm ? (
              <button
                className="ui-btn ui-btn--primary"
                type="button"
                onClick={() => {
                  setLocalError(null)
                  confirmSlotMutation.mutate()
                }}
                disabled={confirmSlotMutation.isPending}
              >
                {confirmSlotMutation.isPending ? 'Подтверждаю…' : 'Подтвердить участие'}
              </button>
            ) : null}
            {!isSlotAlreadyConfirmed(activeSlot) ? (
              <button
                className="ui-btn ui-btn--ghost"
                type="button"
                onClick={() => {
                  setLocalError(null)
                  cancelSlotMutation.mutate()
                }}
                disabled={cancelSlotMutation.isPending}
              >
                {cancelSlotMutation.isPending ? 'Отменяю…' : 'Отменить'}
              </button>
            ) : null}
          </div>
          {canReschedule ? (
            <div className="candidate-portal__slots">
              <p className="candidate-portal__helper">Нужно перенести? Выберите новый слот ниже.</p>
              {availableSlots.map((slot) => (
                <SlotCard
                  key={slot.id}
                  slot={slot}
                  actionLabel="Перенести сюда"
                  busy={rescheduleSlotMutation.isPending && pendingSlotId === slot.id}
                  onAction={() => {
                    setPendingSlotId(slot.id)
                    setLocalError(null)
                    rescheduleSlotMutation.mutate(slot.id)
                  }}
                />
              ))}
            </div>
          ) : null}
        </div>
      ) : currentStep !== 'slot_selection' ? (
        <div className="candidate-portal__status-card">
          <strong>{screeningCompleted ? 'Анкета завершена' : 'Анкета в процессе'}</strong>
          <div className="candidate-portal__status-meta">
            {payload?.candidate.status_label ? (
              <span className="candidate-portal__chip">{payload.candidate.status_label}</span>
            ) : null}
          </div>
          <p className="candidate-portal__empty">
            {screeningCompleted
              ? availableSlots.length > 0
                ? 'Свободные слоты уже доступны. Перейдите к выбору времени и завершите запись.'
                : 'Слотов пока нет. Мы сохранили ваш прогресс и вернем вас в этот же статус.'
              : 'Сначала завершите профиль и анкету, чтобы перейти к выбору слота.'}
          </p>
        </div>
      ) : null}
    </section>
  )

  const renderMessagesPanel = () => (
    <section className="glass glass--elevated candidate-portal__card">
      <div className="candidate-portal__card-head">
        <h2 className="candidate-portal__card-title">Сообщения</h2>
        <p className="candidate-portal__card-copy">
          Это основной inbox кабинета. Ответы рекрутера появляются здесь вне зависимости от того, каким каналом было отправлено уведомление.
        </p>
      </div>
      <div className="candidate-portal__status-meta">
        <span className="candidate-portal__chip">Диалог: {inboxMeta?.conversation_id || 'candidate inbox'}</span>
        {(inboxMeta?.available_channels || ['web']).map((channel) => (
          <span key={channel} className="candidate-portal__chip">
            {channel === 'web' ? 'Web cabinet' : channel.toUpperCase()}
          </span>
        ))}
      </div>
      <div className="candidate-portal__messages">
        {messages.length === 0 ? (
          <p className="candidate-portal__empty">Пока сообщений нет.</p>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className="candidate-portal__message"
              data-direction={message.direction}
            >
              <div className="candidate-portal__message-head">
                <strong>{message.author_label || (message.direction === 'outbound' ? 'Рекрутер' : 'Кандидат')}</strong>
                <span className="candidate-portal__message-channel">
                  {message.origin_channel || message.channel || 'web'}
                </span>
              </div>
              <div>{message.text || 'Сообщение без текста'}</div>
              <div className="candidate-portal__message-meta">
                {message.created_at ? formatDateTime(message.created_at) : 'Время уточняется'}
                {message.delivery_state ? ` • ${message.delivery_state}` : ''}
              </div>
            </div>
          ))
        )}
      </div>
      <div className="candidate-portal__field">
        <label className="candidate-portal__label">Новое сообщение</label>
        <textarea
          className="candidate-portal__textarea"
          value={messageText}
          onChange={(event) => setMessageText(event.target.value)}
          placeholder="Например: мне нужен перенос на вечерний слот"
        />
      </div>
      <div className="candidate-portal__actions">
        <button
          className="ui-btn ui-btn--primary"
          type="button"
          disabled={sendMessageMutation.isPending || !messageText.trim()}
          onClick={() => {
            setLocalError(null)
            sendMessageMutation.mutate(messageText)
          }}
        >
          {sendMessageMutation.isPending ? 'Отправляю…' : 'Отправить рекрутеру'}
        </button>
      </div>
    </section>
  )

  const renderCompanyPanel = () => (
    <section className="candidate-portal__section-stack">
      <section className="glass glass--elevated candidate-portal__card">
        <div className="candidate-portal__card-head">
          <h2 className="candidate-portal__card-title">О компании</h2>
          <p className="candidate-portal__card-copy">{companySummary}</p>
        </div>
        <div className="candidate-portal__summary-tags">
          {companyHighlights.map((highlight) => (
            <span key={highlight} className="candidate-portal__summary-tag">{highlight}</span>
          ))}
        </div>
      </section>

      <section className="candidate-portal__split">
        <article className="glass candidate-portal__card">
          <div className="candidate-portal__card-head">
            <h2 className="candidate-portal__card-title">FAQ</h2>
          </div>
          <div className="candidate-portal__resource-list">
            {faqItems.length === 0 ? (
              <p className="candidate-portal__empty">Ответы и подсказки появятся здесь по мере движения по воронке.</p>
            ) : (
              faqItems.map((item) => (
                <div key={item.question} className="candidate-portal__resource-card">
                  <strong>{item.question}</strong>
                  <p>{item.answer}</p>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="glass candidate-portal__card">
          <div className="candidate-portal__card-head">
            <h2 className="candidate-portal__card-title">Материалы и контакты</h2>
          </div>
          <div className="candidate-portal__resource-list">
            {resourceDocuments.map((item) => (
              <div key={item.key} className="candidate-portal__resource-card">
                <strong>{item.title}</strong>
                <p>{item.summary}</p>
              </div>
            ))}
            {contactItems.map((item) => (
              <div key={`${item.label}-${item.value}`} className="candidate-portal__resource-card">
                <strong>{item.label}</strong>
                <p>{item.value}</p>
              </div>
            ))}
          </div>
        </article>
      </section>
    </section>
  )

  const renderFeedbackPanel = () => (
    <section className="candidate-portal__section-stack">
      <section className="glass glass--elevated candidate-portal__card">
        <div className="candidate-portal__card-head">
          <h2 className="candidate-portal__card-title">Обратная связь и обновления</h2>
          <p className="candidate-portal__card-copy">Здесь собраны системные статусы, сообщения рекрутера и последние итоги по вашему пути.</p>
        </div>
        <div className="candidate-portal__resource-list">
          {feedbackItems.length === 0 ? (
            <p className="candidate-portal__empty">Обновления появятся здесь, как только рекрутер или система зафиксируют следующий шаг.</p>
          ) : (
            feedbackItems.map((item, index) => (
              <div key={`${item.kind || 'feedback'}-${item.title || index}`} className="candidate-portal__resource-card">
                <div className="candidate-portal__message-head">
                  <strong>{item.title || 'Обновление'}</strong>
                  <span className="candidate-portal__message-channel">{item.author_role || 'system'}</span>
                </div>
                <p>{item.body || 'Детали появятся позже.'}</p>
                {item.created_at ? (
                  <div className="candidate-portal__message-meta">{formatDateTime(item.created_at)}</div>
                ) : null}
              </div>
            ))
          )}
        </div>
      </section>

      <section className="candidate-portal__split">
        <article className="glass candidate-portal__card">
          <div className="candidate-portal__card-head">
            <h2 className="candidate-portal__card-title">Текущий статус</h2>
            <p className="candidate-portal__card-copy">{payload?.journey.next_action}</p>
          </div>
          <div className="candidate-portal__status-meta">
            {payload?.candidate.status_label ? <span className="candidate-portal__chip">{payload.candidate.status_label}</span> : null}
            {payload?.journey.current_step_label ? <span className="candidate-portal__chip">{payload.journey.current_step_label}</span> : null}
            {payload?.feedback?.last_feedback_sent_at ? (
              <span className="candidate-portal__chip">
                Последнее обновление: {formatDateTime(payload.feedback.last_feedback_sent_at)}
              </span>
            ) : null}
          </div>
        </article>
        <article className="glass candidate-portal__card">
          <div className="candidate-portal__card-head">
            <h2 className="candidate-portal__card-title">Следующий шаг</h2>
          </div>
          <div className="candidate-portal__summary-value">{nextStepLabel}</div>
          <div className="candidate-portal__summary-meta">{nextStepMeta}</div>
        </article>
      </section>
    </section>
  )

  const renderWorkflowPanel = () => (
    <div className="candidate-portal__grid">
      <aside className="candidate-portal__steps">
        <div className="glass candidate-portal__card">
          <div className="candidate-portal__card-head">
            <h2 className="candidate-portal__card-title">Мой путь</h2>
            <p className="candidate-portal__card-copy">Кабинет запоминает ваше место в процессе и не требует заново проходить уже завершённые этапы.</p>
          </div>
          <div className="candidate-portal__steps-list">
            {payload?.journey.steps.map((step) => (
              <div key={step.key} className="candidate-portal__step" data-state={step.status}>
                <small>{step.status === 'completed' ? 'Готово' : step.status === 'in_progress' ? 'Сейчас' : 'Далее'}</small>
                <span className="candidate-portal__step-label">{step.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="glass candidate-portal__card">
          <div className="candidate-portal__card-head">
            <h2 className="candidate-portal__card-title">Контакты и вход</h2>
          </div>
          <div className="candidate-portal__section-stack">
            <div className="candidate-portal__chip">{payload?.candidate.phone || 'Телефон не указан'}</div>
            <div className="candidate-portal__chip">{payload?.candidate.city || 'Город не указан'}</div>
            <div className="candidate-portal__chip">Вход: {payload?.journey.entry_channel || 'web'}</div>
          </div>
          <div className="candidate-portal__actions">
            <button
              type="button"
              className="ui-btn ui-btn--ghost"
              onClick={() => logoutMutation.mutate()}
              disabled={logoutMutation.isPending}
            >
              {logoutMutation.isPending ? 'Закрываю…' : 'Выйти'}
            </button>
          </div>
        </div>
      </aside>

      <main className="candidate-portal__section-stack">
        {currentStep === 'profile' ? renderProfileForm() : null}
        {currentStep === 'screening' ? renderScreeningForm() : null}
        {currentStep === 'slot_selection' ? renderSchedulePanel() : null}
        {currentStep === 'status' ? renderSchedulePanel() : null}
      </main>
    </div>
  )

  const renderTestsPanel = () => (
    <section className="candidate-portal__section-stack">
      <section className="candidate-portal__summary-grid" aria-label="Тесты и анкеты">
        {testsItems.map((item) => (
          <article key={item.key} className="glass candidate-portal__summary-card">
            <div className="candidate-portal__summary-label">{item.title}</div>
            <div className="candidate-portal__summary-value">{item.status_label || 'Статус уточняется'}</div>
            <div className="candidate-portal__summary-meta">{item.summary || 'Данные обновляются автоматически.'}</div>
            <div className="candidate-portal__summary-tags">
              {item.question_count ? <span className="candidate-portal__summary-tag">Вопросов: {item.question_count}</span> : null}
              {item.final_score != null ? <span className="candidate-portal__summary-tag">Скор: {item.final_score}</span> : null}
              {item.completed_at ? <span className="candidate-portal__summary-tag">{formatDateTime(item.completed_at)}</span> : null}
            </div>
          </article>
        ))}
      </section>
      {currentStep === 'screening' ? renderScreeningForm() : null}
    </section>
  )

  const renderHomePanel = () => (
    <section className="candidate-portal__section-stack">
      <section className="candidate-portal__dashboard-grid" aria-label="Главная кабинета кандидата">
        <article className="glass glass--elevated candidate-portal__dashboard-primary">
          <div className="candidate-portal__card-head">
            <h2 className="candidate-portal__card-title">Что нужно сделать сейчас</h2>
            <p className="candidate-portal__card-copy">{primaryAction?.description || payload?.journey.next_action}</p>
          </div>
          <div className="candidate-portal__summary-value">{primaryAction?.label || 'Открыть следующий шаг'}</div>
          <div className="candidate-portal__actions">
            <button type="button" className="ui-btn ui-btn--primary" onClick={openPrimaryActionTarget}>
              {primaryAction?.label || 'Продолжить'}
            </button>
            <button type="button" className="ui-btn ui-btn--ghost" onClick={() => setActiveTab('messages')}>
              Открыть inbox
            </button>
          </div>
        </article>

        <article className="glass candidate-portal__dashboard-card">
          <div className="candidate-portal__summary-label">Где я нахожусь</div>
          <div className="candidate-portal__summary-value">{payload?.journey.current_step_label}</div>
          <div className="candidate-portal__summary-meta">{statusSummary}</div>
        </article>

        <article className="glass candidate-portal__dashboard-card">
          <div className="candidate-portal__summary-label">Следующее событие</div>
          <div className="candidate-portal__summary-value">{nextStepLabel}</div>
          <div className="candidate-portal__summary-meta">{nextStepMeta}</div>
        </article>

        <article className="glass candidate-portal__dashboard-card">
          <div className="candidate-portal__summary-label">Последнее сообщение</div>
          <div className="candidate-portal__summary-value">
            {latestInboxMessage?.author_label || 'Переписка ещё не началась'}
          </div>
          <div className="candidate-portal__summary-meta">
            {latestInboxMessage?.text || 'Рекрутер сможет ответить вам прямо в этом кабинете.'}
          </div>
        </article>
      </section>

      {cabinetAlerts.length > 0 ? (
        <section className="candidate-portal__alerts">
          {cabinetAlerts.map((alert, index) => (
            <article key={`${alert.title || 'alert'}-${index}`} className="glass candidate-portal__alert-card" data-level={alert.level || 'info'}>
              <strong>{alert.title}</strong>
              <p>{alert.body}</p>
            </article>
          ))}
        </section>
      ) : null}

      <section className="candidate-portal__split">
        <article className="glass candidate-portal__card">
          <div className="candidate-portal__card-head">
            <h2 className="candidate-portal__card-title">Запланированное</h2>
            <p className="candidate-portal__card-copy">Все важные точки процесса видны в одном месте.</p>
          </div>
          <div className="candidate-portal__resource-list">
            {dashboardUpcoming.length === 0 ? (
              <p className="candidate-portal__empty">Следующее событие пока не назначено. Мы обновим кабинет автоматически.</p>
            ) : (
              dashboardUpcoming.map((item, index) => (
                <div key={`${item.kind || 'item'}-${index}`} className="candidate-portal__resource-card">
                  <strong>{item.title || 'Событие'}</strong>
                  <p>{item.scheduled_at ? formatDateTime(item.scheduled_at, item.timezone) : 'Время уточняется'}</p>
                  {item.state ? <span className="candidate-portal__chip">{item.state}</span> : null}
                </div>
              ))
            )}
          </div>
        </article>

        <article className="glass candidate-portal__card">
          <div className="candidate-portal__card-head">
            <h2 className="candidate-portal__card-title">Последние обновления</h2>
            <p className="candidate-portal__card-copy">Важные изменения и решения публикуются прямо в кабинете.</p>
          </div>
          <div className="candidate-portal__resource-list">
            {feedbackItems.length === 0 ? (
              <p className="candidate-portal__empty">Обновления появятся здесь по мере прохождения отбора.</p>
            ) : (
              feedbackItems.slice(0, 3).map((item, index) => (
                <div key={`${item.kind || 'update'}-${index}`} className="candidate-portal__resource-card">
                  <strong>{item.title || 'Обновление'}</strong>
                  <p>{item.body || 'Подробности появятся позже.'}</p>
                </div>
              ))
            )}
          </div>
        </article>
      </section>
    </section>
  )

  if (journeyQuery.isLoading) {
    return (
      <div className="candidate-portal">
        <div className="candidate-portal__loader">
          <div className="glass glass--elevated candidate-portal__card">
            <div className="candidate-portal__eyebrow">Candidate Cabinet</div>
            <h1 className="candidate-portal__title">Загружаю ваш кабинет</h1>
            <p className="candidate-portal__subtitle">Подтягиваю прогресс, сообщения, расписание и материалы компании.</p>
          </div>
        </div>
      </div>
    )
  }

  if (journeyQuery.isError || !payload) {
    const recoveryState = portalError?.state || (portalError?.status === 401 ? 'recoverable' : null)
    const errorTitle =
      recoveryState === 'blocked'
        ? 'Доступ к кабинету недоступен'
        : recoveryState === 'needs_new_link'
          ? 'Нужна новая ссылка'
          : recoveryState === 'recoverable'
            ? 'Сессия кабинета истекла'
            : 'Не удалось восстановить кабинет'
    const errorSubtitle =
      recoveryState === 'blocked'
        ? 'Сессия отозвана или кабинет не найден. Попросите рекрутера восстановить доступ.'
        : recoveryState === 'needs_new_link'
          ? 'Старая ссылка устарела. Откройте свежую ссылку из сообщения или письма от рекрутера.'
          : 'Откройте кабинет заново по свежей ссылке. Если resume-cookie ещё жив, доступ поднимется автоматически.'
    return (
      <div className="candidate-portal">
        <div className="candidate-portal__loader">
          <div className="glass glass--elevated candidate-portal__card">
            <div className="candidate-portal__eyebrow">Candidate Cabinet</div>
            <h1 className="candidate-portal__title">{errorTitle}</h1>
            <p className="candidate-portal__subtitle">
              {errorSubtitle}
            </p>
            {portalError?.message ? <p className="candidate-portal__error">{portalError.message}</p> : null}
            <div className="candidate-portal__actions" style={{ justifyContent: 'center' }}>
              <button className="ui-btn ui-btn--primary" onClick={() => journeyQuery.refetch()}>
                Повторить
              </button>
              <Link className="ui-btn ui-btn--ghost" to="/candidate/start">
                Открыть новую ссылку
              </Link>
              <button className="ui-btn ui-btn--ghost" onClick={handleCopySupportMessage}>
                Запросить новую ссылку у рекрутера
              </button>
            </div>
            <p className="candidate-portal__helper" style={{ textAlign: 'center', marginTop: 12 }}>
              {supportMessage || 'Если проблема повторяется, попросите рекрутера переотправить доступ или открыть кабинет заново.'}
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="candidate-portal">
      <div className="candidate-portal__shell">
        <section className="glass glass--elevated candidate-portal__hero">
          <div className="candidate-portal__eyebrow">Candidate Cabinet</div>
          <h1 className="candidate-portal__title">{payload.candidate.fio || 'Ваш кабинет кандидата'}</h1>
          <p className="candidate-portal__subtitle">{payload.journey.next_action}</p>
          <div className="candidate-portal__status-meta">
            {payload.journey.current_step_label ? <span className="candidate-portal__chip">Этап: {payload.journey.current_step_label}</span> : null}
            {payload.candidate.status_label ? <span className="candidate-portal__chip">{payload.candidate.status_label}</span> : null}
            {payload.journey.entry_channel ? <span className="candidate-portal__chip">Вход: {payload.journey.entry_channel}</span> : null}
            {statusSummary ? <span className="candidate-portal__chip">{statusSummary}</span> : null}
          </div>
        </section>

        <section className="candidate-portal__summary-card" style={{ marginBottom: 20 }}>
          <div className="candidate-portal__card-head">
            <h2 className="candidate-portal__card-title">Кабинет работает как главный интерфейс кандидата</h2>
            <p className="candidate-portal__card-copy">
              Ссылки из MAX, Telegram или письма от рекрутера только открывают доступ. Весь прогресс, сообщения и запись на собеседование живут здесь.
            </p>
          </div>
          <div className="candidate-portal__summary-tags" aria-label="Преимущества кабинета кандидата">
            <span className="candidate-portal__summary-tag">Magic link + resume-cookie</span>
            <span className="candidate-portal__summary-tag">Web inbox вместо привязки к одному мессенджеру</span>
            <span className="candidate-portal__summary-tag">Следующий шаг и статус в одном месте</span>
          </div>
        </section>

        <section className="candidate-portal__summary-card" style={{ marginBottom: 20 }}>
          <div className="candidate-portal__card-head">
            <h2 className="candidate-portal__card-title">Продолжить в другом канале</h2>
            <p className="candidate-portal__card-copy">
              Можно открыть тот же процесс в Web, MAX или Telegram. Прогресс, сообщения и запись на слот останутся общими.
            </p>
          </div>
          <div className="candidate-portal__actions">
            {(['web', 'max', 'telegram'] as CandidateEntryChannel[]).map((channel) => {
              const option = channelOptions[channel]
              const label =
                channel === 'web' ? 'Web cabinet' : channel === 'max' ? 'Открыть в MAX' : 'Открыть в Telegram'
              return (
                <button
                  key={channel}
                  type="button"
                  className={`ui-btn ${channel === 'web' ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
                  disabled={!option?.enabled || Boolean(pendingChannel && pendingChannel !== channel)}
                  onClick={() => {
                    void handleOpenChannel(channel)
                  }}
                  title={option?.reason_if_blocked || undefined}
                >
                  {pendingChannel === channel ? 'Открываю…' : label}
                </button>
              )
            })}
          </div>
          <div className="candidate-portal__summary-tags">
            <span className="candidate-portal__summary-tag">
              Текущий вход: {payload.journey.last_entry_channel || payload.journey.entry_channel || 'web'}
            </span>
            {(payload.journey.available_channels || []).map((channel) => (
              <span key={channel} className="candidate-portal__summary-tag">
                {channel === 'web' ? 'web ready' : `${channel} ready`}
              </span>
            ))}
          </div>
        </section>

        <section className="candidate-portal__summary-grid" aria-label="Краткая сводка">
          <article className="glass candidate-portal__summary-card">
            <div className="candidate-portal__summary-label">Вакансия</div>
            <div className="candidate-portal__summary-value">{vacancyLabel}</div>
            <div className="candidate-portal__summary-meta">{vacancyMeta}</div>
          </article>
          <article className="glass candidate-portal__summary-card candidate-portal__summary-card--company">
            <div className="candidate-portal__summary-label">Компания</div>
            <div className="candidate-portal__summary-value">{companyName}</div>
            <div className="candidate-portal__summary-meta">{companySummary}</div>
            <div className="candidate-portal__summary-tags" aria-label="Преимущества кабинета">
              {companyHighlights.map((highlight) => (
                <span key={highlight} className="candidate-portal__summary-tag">
                  {highlight}
                </span>
              ))}
            </div>
          </article>
          <article className="glass candidate-portal__summary-card">
            <div className="candidate-portal__summary-label">Текущий этап</div>
            <div className="candidate-portal__summary-value">{payload.journey.current_step_label}</div>
            <div className="candidate-portal__summary-meta">{payload.journey.next_action}</div>
          </article>
          <article className="glass candidate-portal__summary-card">
            <div className="candidate-portal__summary-label">Следующий шаг</div>
            <div className="candidate-portal__summary-value">{nextStepLabel}</div>
            <div className="candidate-portal__summary-meta">{nextStepMeta}</div>
          </article>
        </section>

        <nav className="candidate-portal__tabs" aria-label="Разделы кабинета кандидата">
          {CABINET_TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={`candidate-portal__tab ${activeTab === tab.key ? 'is-active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {localError ? <p className="candidate-portal__error">{localError}</p> : null}

        {activeTab === 'home' ? renderHomePanel() : null}
        {activeTab === 'workflow' ? renderWorkflowPanel() : null}
        {activeTab === 'tests' ? renderTestsPanel() : null}
        {activeTab === 'schedule' ? renderSchedulePanel() : null}
        {activeTab === 'messages' ? renderMessagesPanel() : null}
        {activeTab === 'company' ? renderCompanyPanel() : null}
        {activeTab === 'feedback' ? renderFeedbackPanel() : null}
      </div>
    </div>
  )
}
