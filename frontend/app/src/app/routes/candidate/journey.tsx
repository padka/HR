import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'

import {
  cancelCandidatePortalSlot,
  completeCandidatePortalScreening,
  confirmCandidatePortalSlot,
  fetchCandidatePortalJourney,
  logoutCandidatePortalSession,
  reserveCandidatePortalSlot,
  rescheduleCandidatePortalSlot,
  saveCandidatePortalProfile,
  saveCandidatePortalScreeningDraft,
  sendCandidatePortalMessage,
  type CandidatePortalJourneyResponse,
  type CandidatePortalQuestion,
  type CandidatePortalSlot,
} from '@/api/candidate'
import '../candidate-portal.css'

const JOURNEY_QUERY_KEY = ['candidate-portal-journey']

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
  const journeyQuery = useQuery({
    queryKey: JOURNEY_QUERY_KEY,
    queryFn: fetchCandidatePortalJourney,
  })

  const payload = journeyQuery.data
  const currentStep = payload?.journey.current_step
  const activeSlot = payload?.journey.slots.active
  const availableSlots = payload?.journey.slots.available || []

  const [profileForm, setProfileForm] = useState({
    fio: '',
    phone: '',
    city_id: '',
  })
  const [screeningAnswers, setScreeningAnswers] = useState<Record<string, string>>({})
  const [messageText, setMessageText] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const [pendingSlotId, setPendingSlotId] = useState<number | null>(null)

  useEffect(() => {
    if (!payload) return
    setProfileForm({
      fio: payload.journey.profile.fio || '',
      phone: payload.journey.profile.phone || '',
      city_id: payload.journey.profile.city_id ? String(payload.journey.profile.city_id) : '',
    })
    setScreeningAnswers(payload.journey.screening.draft_answers || {})
  }, [payload])

  const setMutationError = (error: unknown) => {
    setLocalError(error instanceof Error ? error.message : 'Не удалось выполнить действие.')
  }

  const profileMutation = useMutation({
    mutationFn: saveCandidatePortalProfile,
    onSuccess: (nextPayload) => {
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
    },
    onError: setMutationError,
  })

  const saveDraftMutation = useMutation({
    mutationFn: saveCandidatePortalScreeningDraft,
    onSuccess: (nextPayload) => {
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
    },
    onError: setMutationError,
  })

  const completeScreeningMutation = useMutation({
    mutationFn: completeCandidatePortalScreening,
    onSuccess: (nextPayload) => {
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
    },
    onError: setMutationError,
  })

  const reserveSlotMutation = useMutation({
    mutationFn: reserveCandidatePortalSlot,
    onSuccess: (nextPayload) => {
      setPendingSlotId(null)
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
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
    },
    onError: setMutationError,
  })

  const cancelSlotMutation = useMutation({
    mutationFn: cancelCandidatePortalSlot,
    onSuccess: (nextPayload) => {
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
    },
    onError: setMutationError,
  })

  const rescheduleSlotMutation = useMutation({
    mutationFn: rescheduleCandidatePortalSlot,
    onSuccess: (nextPayload) => {
      setPendingSlotId(null)
      setLocalError(null)
      applyJourneyPayload(queryClient, nextPayload)
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
    },
    onError: setMutationError,
  })

  const logoutMutation = useMutation({
    mutationFn: logoutCandidatePortalSession,
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: JOURNEY_QUERY_KEY })
      window.location.reload()
    },
  })

  const screeningQuestions = payload?.journey.screening.questions || []
  const screeningCompleted = Boolean(payload?.journey.screening.completed)
  const messages = payload?.journey.messages || []

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

  if (journeyQuery.isLoading) {
    return (
      <div className="candidate-portal">
        <div className="candidate-portal__loader">
          <div className="glass glass--elevated candidate-portal__card">
            <div className="candidate-portal__eyebrow">Candidate Portal</div>
            <h1 className="candidate-portal__title">Загружаю ваш статус</h1>
            <p className="candidate-portal__subtitle">Подтягиваю прогресс анкеты, слот и переписку с рекрутером.</p>
          </div>
        </div>
      </div>
    )
  }

  if (journeyQuery.isError || !payload) {
    const error = journeyQuery.error as Error & { status?: number }
    const isExpired = error?.status === 401
    return (
      <div className="candidate-portal">
        <div className="candidate-portal__loader">
          <div className="glass glass--elevated candidate-portal__card">
            <div className="candidate-portal__eyebrow">Candidate Portal</div>
            <h1 className="candidate-portal__title">{isExpired ? 'Ссылка истекла' : 'Не удалось загрузить портал'}</h1>
            <p className="candidate-portal__subtitle">
              {error?.message || 'Попробуйте открыть последнюю ссылку из сообщения или запросите новую у рекрутера.'}
            </p>
            <div className="candidate-portal__actions">
              <Link className="ui-btn ui-btn--ghost" to="/candidate/journey">
                Повторить
              </Link>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="candidate-portal">
      <div className="candidate-portal__shell">
        <section className="glass glass--elevated candidate-portal__hero">
          <div className="candidate-portal__eyebrow">Candidate Portal</div>
          <h1 className="candidate-portal__title">
            {payload.candidate.fio || 'Ваш путь кандидата'}
          </h1>
          <p className="candidate-portal__subtitle">{payload.journey.next_action}</p>
          <div className="candidate-portal__status-meta">
            {payload.candidate.status_label ? <span className="candidate-portal__chip">{payload.candidate.status_label}</span> : null}
            {payload.journey.entry_channel ? <span className="candidate-portal__chip">Вход: {payload.journey.entry_channel}</span> : null}
            {statusSummary ? <span className="candidate-portal__chip">{statusSummary}</span> : null}
          </div>
        </section>

        <div className="candidate-portal__grid">
          <aside className="candidate-portal__steps">
            <div className="glass candidate-portal__card">
              <div className="candidate-portal__card-head">
                <h2 className="candidate-portal__card-title">Прогресс</h2>
                <p className="candidate-portal__card-copy">Возвращайтесь по этой же ссылке. Система продолжит с последнего шага.</p>
              </div>
              <div className="candidate-portal__steps-list">
                {payload.journey.steps.map((step) => (
                  <div key={step.key} className="candidate-portal__step" data-state={step.status}>
                    <small>{step.status === 'completed' ? 'Готово' : step.status === 'in_progress' ? 'Сейчас' : 'Далее'}</small>
                    <span className="candidate-portal__step-label">{step.label}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass candidate-portal__card">
              <div className="candidate-portal__card-head">
                <h2 className="candidate-portal__card-title">Контакты</h2>
              </div>
              <div className="candidate-portal__section-stack">
                <div className="candidate-portal__chip">{payload.candidate.phone || 'Телефон не указан'}</div>
                <div className="candidate-portal__chip">{payload.candidate.city || 'Город не указан'}</div>
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
            {localError ? <p className="candidate-portal__error">{localError}</p> : null}

            {currentStep === 'profile' ? (
              <section className="glass glass--elevated candidate-portal__card">
                <div className="candidate-portal__card-head">
                  <h2 className="candidate-portal__card-title">Шаг 1. Профиль кандидата</h2>
                  <p className="candidate-portal__card-copy">Сохраняем контакт и город, чтобы не потерять вас между каналами.</p>
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
                        {payload.journey.cities.map((city) => (
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
            ) : null}

            {currentStep === 'screening' ? (
              <section className="glass glass--elevated candidate-portal__card">
                <div className="candidate-portal__card-head">
                  <h2 className="candidate-portal__card-title">Шаг 2. Короткая анкета</h2>
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
            ) : null}

            {currentStep === 'slot_selection' ? (
              <section className="glass glass--elevated candidate-portal__card">
                <div className="candidate-portal__card-head">
                  <h2 className="candidate-portal__card-title">Шаг 3. Выберите слот</h2>
                  <p className="candidate-portal__card-copy">После выбора слот уйдет рекрутеру на подтверждение, а вы увидите обновление статуса здесь.</p>
                </div>
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
              </section>
            ) : null}

            <div className="candidate-portal__split">
              <section className="glass glass--elevated candidate-portal__card">
                <div className="candidate-portal__card-head">
                  <h2 className="candidate-portal__card-title">Мой статус</h2>
                  <p className="candidate-portal__card-copy">{payload.journey.next_action}</p>
                </div>

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
                ) : (
                  <div className="candidate-portal__status-card">
                    <strong>{screeningCompleted ? 'Анкета завершена' : 'Анкета в процессе'}</strong>
                    <div className="candidate-portal__status-meta">
                      {payload.candidate.status_label ? (
                        <span className="candidate-portal__chip">{payload.candidate.status_label}</span>
                      ) : null}
                    </div>
                    <p className="candidate-portal__empty">
                      {screeningCompleted
                        ? availableSlots.length > 0
                          ? 'Свободные слоты доступны выше. Выберите удобное время.'
                          : 'Слотов пока нет. Мы сохранили ваш прогресс и вернем вас в этот же статус.'
                        : 'Заполните профиль и анкету, чтобы перейти к выбору слота.'}
                    </p>
                  </div>
                )}
              </section>

              <section className="glass candidate-portal__card">
                <div className="candidate-portal__card-head">
                  <h2 className="candidate-portal__card-title">Связь с рекрутером</h2>
                  <p className="candidate-portal__card-copy">Сообщения сохраняются в единой карточке кандидата. Рекрутер увидит их в CRM.</p>
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
                        <div>{message.text || 'Сообщение без текста'}</div>
                        <div className="candidate-portal__message-meta">
                          {message.author_label || (message.direction === 'outbound' ? 'Рекрутер' : 'Кандидат')}
                          {message.created_at ? ` • ${formatDateTime(message.created_at)}` : ''}
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
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}

