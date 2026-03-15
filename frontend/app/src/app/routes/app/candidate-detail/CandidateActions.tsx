import type { Ref } from 'react'
import type { CandidateAction, CandidateDetail, TestSection } from '@/api/services/candidates'
import { getHhSyncBadge } from './candidate-detail.constants'
import { normalizeConferenceUrl, normalizeTelegramUsername } from '@/shared/utils/normalizers'

type CandidateActionsProps = {
  candidate: CandidateDetail
  statusSlug: string | null
  test2Section?: TestSection
  actionPending: boolean
  actionsRef?: Ref<HTMLDivElement>
  onOpenChat: () => void
  onScheduleSlot: () => void
  onScheduleIntroDay: () => void
  onActionClick: (action: CandidateAction) => void
}

export function CandidateActions({
  candidate,
  statusSlug,
  test2Section,
  actionPending,
  actionsRef,
  onOpenChat,
  onScheduleSlot,
  onScheduleIntroDay,
  onActionClick,
}: CandidateActionsProps) {
  const slots = candidate.slots || []
  const telegramUsername = normalizeTelegramUsername(candidate.telegram_username)
  const telegramLink = telegramUsername
    ? `https://t.me/${telegramUsername}`
    : candidate.telegram_id
      ? `tg://user?id=${candidate.telegram_id}`
      : null
  const hhLink = candidate.hh_profile_url || null
  const hhBadge = getHhSyncBadge(candidate.hh_sync_status)
  const conferenceLink = normalizeConferenceUrl(candidate.telemost_url)
  const conferenceSourceLabel =
    candidate.telemost_source === 'upcoming'
      ? 'Источник: ближайший слот'
      : candidate.telemost_source === 'recent'
        ? 'Источник: последний слот'
        : null

  const hasUpcomingSlot = slots.some((slot) => {
    const status = String(slot.status || '').toUpperCase()
    return ['BOOKED', 'PENDING', 'CONFIRMED', 'CONFIRMED_BY_CANDIDATE'].includes(status)
  })
  const hasIntroDay = slots.some((slot) => slot.purpose === 'intro_day')

  const actions = candidate.candidate_actions || []
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
  const canScheduleIntroDay = Boolean(candidate.telegram_id) && !hasIntroDay && test2Passed && isWaitingIntroDay
  const canScheduleInterview = Boolean(candidate.telegram_id) && Boolean(scheduleAction)
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
  const resolveRailTone = (variant?: CandidateAction['variant']) => {
    if (variant === 'primary') return 'cd-rail-btn--primary'
    if (variant === 'danger') return 'cd-rail-btn--danger'
    return 'cd-rail-btn--secondary'
  }

  return (
    <div className="cd-actions">
      <div className="cd-actions__meta">
        {hhBadge && (
          <span
            className={`cd-chip ${
              hhBadge.tone === 'success' ? 'cd-chip--success'
              : hhBadge.tone === 'danger' ? 'cd-chip--danger'
              : hhBadge.tone === 'warning' ? 'cd-chip--warning'
              : ''
            }`}
            title={candidate.hh_sync_error || hhBadge.label}
          >
            {hhBadge.label}
          </span>
        )}
        {candidate.messenger_platform && candidate.messenger_platform !== 'telegram' && (
          <span
            className="cd-chip"
            title={`Мессенджер: ${candidate.messenger_platform}${candidate.max_user_id ? ` (ID: ${candidate.max_user_id})` : ''}`}
          >
            {candidate.messenger_platform === 'max' ? 'Max' : candidate.messenger_platform}
          </span>
        )}
        {conferenceSourceLabel && (
          <span className="cd-chip cd-chip--small">{conferenceSourceLabel}</span>
        )}
      </div>

      <div className="cd-action-rail" data-testid="candidate-actions" ref={actionsRef}>
        <div className="cd-action-rail__scroll">
          {telegramLink ? (
            <a
              href={telegramLink}
              className="cd-rail-btn cd-rail-btn--icon cd-rail-btn--secondary"
              target="_blank"
              rel="noopener"
              title={telegramUsername ? `Открыть Telegram @${telegramUsername}` : 'Открыть Telegram'}
              aria-label={telegramUsername ? `Открыть Telegram @${telegramUsername}` : 'Открыть Telegram'}
            >
              <span className="cd-rail-btn__icon">TG</span>
            </a>
          ) : (
            <span className="cd-rail-btn cd-rail-btn--icon cd-rail-btn--disabled" title="Telegram не привязан">
              <span className="cd-rail-btn__icon">TG</span>
            </span>
          )}
          {hhLink ? (
            <a
              href={hhLink}
              className="cd-rail-btn cd-rail-btn--icon cd-rail-btn--secondary"
              target="_blank"
              rel="noopener"
              title="Открыть HH-профиль"
              aria-label="Открыть HH-профиль"
            >
              <span className="cd-rail-btn__icon">HH</span>
            </a>
          ) : (
            <span className="cd-rail-btn cd-rail-btn--icon cd-rail-btn--disabled" title="HH-профиль не привязан">
              <span className="cd-rail-btn__icon">HH</span>
            </span>
          )}
          {conferenceLink ? (
            <a
              href={conferenceLink}
              className="cd-rail-btn cd-rail-btn--icon cd-rail-btn--secondary"
              target="_blank"
              rel="noopener noreferrer"
              title={conferenceSourceLabel || 'Ссылка на конференцию'}
              aria-label="Открыть конференцию"
            >
              <span className="cd-rail-btn__icon">VC</span>
            </a>
          ) : (
            <span className="cd-rail-btn cd-rail-btn--icon cd-rail-btn--disabled" title="У рекрутера не заполнена ссылка на конференцию">
              <span className="cd-rail-btn__icon">VC</span>
            </span>
          )}
          <button
            type="button"
            className="cd-rail-btn cd-rail-btn--secondary"
            onClick={onOpenChat}
            disabled={!candidate.telegram_id}
          >
            Чат
          </button>
          {canScheduleInterview && (
            <button className="cd-rail-btn cd-rail-btn--primary" onClick={onScheduleSlot}>
              {scheduleLabel}
            </button>
          )}
          {canScheduleIntroDay && (
            <button className="cd-rail-btn cd-rail-btn--primary" onClick={onScheduleIntroDay}>
              Назначить ОД
            </button>
          )}
          {test2Action && (
            <button
              className={`cd-rail-btn ${canSendTest2 ? 'cd-rail-btn--primary' : 'cd-rail-btn--secondary'}`}
              onClick={() => canSendTest2 && onActionClick(test2Action)}
              disabled={!canSendTest2 || actionPending}
            >
              Отправить Тест 2
            </button>
          )}
          {inlineActions.map((action) => (
            <button
              key={action.key}
              className={`cd-rail-btn ${resolveRailTone(action.variant)}`}
              onClick={() => onActionClick(action)}
              disabled={actionPending}
            >
              {action.label}
            </button>
          ))}
          {overflowActions.length > 0 && (
            <details className="ui-disclosure cd-actions-overflow" data-testid="candidate-actions-overflow">
              <summary className="cd-rail-btn cd-rail-btn--secondary">Ещё</summary>
              <div className="ui-disclosure__content cd-actions-overflow__content">
                {overflowActions.map((action) => (
                  <button
                    key={action.key}
                    className={`cd-rail-btn ${resolveRailTone(action.variant)}`}
                    onClick={() => onActionClick(action)}
                    disabled={actionPending}
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </details>
          )}
          {rejectAction && (
            <button
              className="cd-rail-btn cd-rail-btn--danger"
              onClick={() => onActionClick(rejectAction)}
              disabled={actionPending}
            >
              {rejectAction.label}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
