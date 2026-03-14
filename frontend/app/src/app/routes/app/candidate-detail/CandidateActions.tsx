import type { Ref } from 'react'
import type { CandidateAction, CandidateDetail, TestSection } from '@/api/services/candidates'
import { getHhSyncBadge } from './candidate-detail.constants'
import { normalizeConferenceUrl, normalizeTelegramUsername } from '@/shared/utils/normalizers'

type CandidateActionsProps = {
  candidate: CandidateDetail
  statusSlug: string | null
  test2Section?: TestSection
  isInsightsOpen: boolean
  isInterviewScriptOpen: boolean
  actionPending: boolean
  actionsRef?: Ref<HTMLDivElement>
  onOpenDetails: () => void
  onOpenChat: () => void
  onToggleScript: () => void
  onScheduleSlot: () => void
  onScheduleIntroDay: () => void
  onActionClick: (action: CandidateAction) => void
}

export function CandidateActions({
  candidate,
  statusSlug,
  test2Section,
  isInsightsOpen,
  isInterviewScriptOpen,
  actionPending,
  actionsRef,
  onOpenDetails,
  onOpenChat,
  onToggleScript,
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

  return (
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
      <button className="cd-contact-btn" onClick={onOpenChat} disabled={!candidate.telegram_id}>
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
          title={candidate.hh_sync_error || hhBadge.label}
        >
          {hhBadge.label}
        </span>
      )}
      {candidate.messenger_platform && candidate.messenger_platform !== 'telegram' && (
        <span
          className="cd-chip cd-chip--info"
          title={`Мессенджер: ${candidate.messenger_platform}${candidate.max_user_id ? ` (ID: ${candidate.max_user_id})` : ''}`}
        >
          {candidate.messenger_platform === 'max' ? '💬 Max' : candidate.messenger_platform}
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
      <div className="cd-contact-actions" data-testid="candidate-actions" ref={actionsRef}>
        <button
          type="button"
          className={`ui-btn ui-btn--sm ${isInsightsOpen ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
          onClick={onOpenDetails}
          aria-haspopup="dialog"
          aria-expanded={isInsightsOpen}
          data-testid="candidate-insights-trigger"
        >
          Детали
        </button>
        <button
          type="button"
          className={`ui-btn ui-btn--sm ${isInterviewScriptOpen ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
          onClick={onToggleScript}
          data-testid="candidate-script-trigger"
        >
          Скрипт интервью
        </button>
        {canScheduleInterview && (
          <button className="ui-btn ui-btn--primary ui-btn--sm" onClick={onScheduleSlot}>
            {scheduleLabel}
          </button>
        )}
        {test2Action && (
          <button
            className={`ui-btn ui-btn--sm ${canSendTest2 ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
            onClick={() => canSendTest2 && onActionClick(test2Action)}
            disabled={!canSendTest2 || actionPending}
          >
            Отправить Тест 2
          </button>
        )}
        {canScheduleIntroDay && (
          <button className="ui-btn ui-btn--primary ui-btn--sm" onClick={onScheduleIntroDay}>
            Назначить ОД
          </button>
        )}
        {inlineActions.map((action) => (
          <button
            key={action.key}
            className={`ui-btn ui-btn--sm ${action.variant === 'primary' ? 'ui-btn--primary' : action.variant === 'danger' ? 'ui-btn--danger' : 'ui-btn--ghost'}`}
            onClick={() => onActionClick(action)}
            disabled={actionPending}
          >
            {action.label}
          </button>
        ))}
        {overflowActions.length > 0 && (
          <details className="ui-disclosure cd-actions-overflow" data-testid="candidate-actions-overflow">
            <summary className="ui-disclosure__trigger">Ещё</summary>
            <div className="ui-disclosure__content cd-actions-overflow__content">
              {overflowActions.map((action) => (
                <button
                  key={action.key}
                  className={`ui-btn ui-btn--sm ${action.variant === 'primary' ? 'ui-btn--primary' : action.variant === 'danger' ? 'ui-btn--danger' : 'ui-btn--ghost'}`}
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
            className="ui-btn ui-btn--danger ui-btn--sm"
            onClick={() => onActionClick(rejectAction)}
            disabled={actionPending}
          >
            {rejectAction.label}
          </button>
        )}
      </div>
    </div>
  )
}
