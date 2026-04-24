import type { Ref, ReactNode } from 'react'
import {
  RecruiterActionBlock,
} from '@/app/components/RecruiterState'
import type {
  CandidateAction,
  CandidateBlockingState,
  CandidateDetail,
  TestSection,
} from '@/api/services/candidates'
import { normalizeConferenceUrl, normalizeTelegramUsername } from '@/shared/utils/normalizers'
import { formatChannelLinkStatus } from './candidate-detail.constants'
import { buildCandidateSurfaceState } from '../candidate-state.adapter'

type CandidateActionsProps = {
  candidate: CandidateDetail
  statusSlug: string | null
  blockingState?: CandidateBlockingState | null
  test2Section?: TestSection
  actionPending: boolean
  showInsightsAction?: boolean
  actionsRef?: Ref<HTMLDivElement>
  onOpenChat: () => void
  onOpenTests: () => void
  onOpenInsights: () => void
  onOpenHh: () => void
  onScheduleSlot: () => void
  onScheduleIntroDay: () => void
  onActionClick: (action: CandidateAction) => void
}

function isTest2Action(action: CandidateAction | null | undefined): boolean {
  if (!action) return false
  const key = action.key?.toLowerCase?.() || ''
  const label = action.label?.toLowerCase?.() || ''
  return action.target_status === 'test2_sent' || key.includes('test2') || label.includes('тест 2')
}

function renderPrimaryActionButton(
  label: string,
  options: { pending: boolean; disabled: boolean; onClick: () => void },
): ReactNode {
  return (
    <button
      type="button"
      className="ui-btn ui-btn--primary"
      onClick={options.onClick}
      disabled={options.disabled}
    >
      {options.pending ? 'Сохраняем…' : label}
    </button>
  )
}

export function CandidateActions({
  candidate,
  statusSlug,
  blockingState = null,
  test2Section,
  actionPending,
  showInsightsAction = false,
  actionsRef,
  onOpenChat,
  onOpenTests,
  onOpenInsights,
  onOpenHh,
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
  const maxLinked = Boolean(candidate.max?.linked || candidate.linked_channels?.max)
  const hhLink = candidate.hh_profile_url || null
  const hasHhProfile = Boolean(
    hhLink
    || candidate.hh_resume_id
    || candidate.hh_negotiation_id
    || candidate.hh_sync_status,
  )
  const conferenceLink = normalizeConferenceUrl(candidate.telemost_url)
  const canOpenChat = Boolean(candidate.telegram_id || telegramUsername || candidate.linked_channels?.telegram || maxLinked)

  const hasUpcomingSlot = slots.some((slot) => {
    const status = String(slot.status || '').toUpperCase()
    return ['BOOKED', 'PENDING', 'CONFIRMED', 'CONFIRMED_BY_CANDIDATE'].includes(status)
  })
  const hasIntroDay = slots.some((slot) => slot.purpose === 'intro_day')

  const actions = candidate.candidate_actions || []
  const nextAction = candidate.candidate_next_action || null
  const backendPrimaryAction = nextAction?.primary_action || null
  const backendPrimaryLegacyAction = backendPrimaryAction?.legacy_action_key
    ? actions.find((action) => action.key === backendPrimaryAction.legacy_action_key)
    : null
  const test2Action = actions.find((action) => action.key === 'resend_test2')
    || actions.find((action) => isTest2Action(action))
  const scheduleAction = actions.find((action) =>
    ['schedule_interview', 'reschedule_interview'].includes(action.key)
  )
  const rejectAction = actions.find((action) => action.key === 'reject' || action.target_status === 'interview_declined')

  const canSendTest2 = Boolean(test2Action)
  const test2Passed = test2Section?.status === 'passed' || statusSlug === 'test2_completed'
  const isWaitingIntroDay = statusSlug === 'test2_completed'
  const canScheduleIntroDay = canOpenChat && !hasIntroDay && test2Passed && isWaitingIntroDay
  const canScheduleInterview = canOpenChat && Boolean(scheduleAction)
    && (scheduleAction?.key === 'reschedule_interview' || !hasUpcomingSlot)
  const scheduleLabel = scheduleAction?.key === 'reschedule_interview' || statusSlug === 'slot_pending'
    ? 'Предложить другое время'
    : 'Предложить время'
  const hasBackendPrimaryAction = Boolean(
    backendPrimaryAction
    && backendPrimaryAction.enabled !== false
    && (
      backendPrimaryAction.ui_action
      || backendPrimaryLegacyAction
    )
  )

  const surfaceState = buildCandidateSurfaceState({
    status_slug: candidate.candidate_status_slug,
    status_display: candidate.candidate_status_display,
    lifecycle_summary: candidate.lifecycle_summary,
    scheduling_summary: candidate.scheduling_summary,
    candidate_next_action: candidate.candidate_next_action,
    operational_summary: candidate.operational_summary,
    state_reconciliation: candidate.state_reconciliation,
    blocking_state: blockingState,
  })

  const handleBackendPrimaryAction = () => {
    if (!backendPrimaryAction || backendPrimaryAction.enabled === false) return
    switch (backendPrimaryAction.ui_action) {
      case 'open_schedule_slot_modal':
        onScheduleSlot()
        return
      case 'open_schedule_intro_day_modal':
        onScheduleIntroDay()
        return
      case 'open_chat':
        onOpenChat()
        return
      default:
        if (backendPrimaryLegacyAction) {
          onActionClick(backendPrimaryLegacyAction)
        }
    }
  }

  const handlePrimaryAction = () => {
    if (backendPrimaryAction) {
      if (hasBackendPrimaryAction) {
        handleBackendPrimaryAction()
      }
      return
    }
    if (hasBackendPrimaryAction) {
      handleBackendPrimaryAction()
      return
    }
    if (canScheduleInterview) {
      onScheduleSlot()
      return
    }
    if (canScheduleIntroDay) {
      onScheduleIntroDay()
      return
    }
    if (test2Action && canSendTest2) {
      onActionClick(test2Action)
    }
  }

  const primaryActionLabel = backendPrimaryAction?.label
    || (!backendPrimaryAction
      ? ((canScheduleInterview ? scheduleLabel : null)
        || (canScheduleIntroDay ? 'Назначить ОД' : null)
        || (test2Action ? 'Отправить Тест 2' : null))
      : null)
    || surfaceState.nextActionLabel
    || 'Следующий шаг уточняется'
  const primaryActionEnabled = backendPrimaryAction
    ? Boolean(hasBackendPrimaryAction && backendPrimaryAction.enabled !== false)
    : (canScheduleInterview || canScheduleIntroDay || Boolean(test2Action))
  const primaryActionUsesTest2 = Boolean(
    test2Action
    && (
      (!backendPrimaryAction && !canScheduleInterview && !canScheduleIntroDay)
      || isTest2Action(backendPrimaryLegacyAction)
    )
  )
  const test2RailAction = primaryActionUsesTest2 ? null : test2Action

  const filteredActions = actions.filter((action) => {
    if (isTest2Action(action) || action === rejectAction) return false
    if (backendPrimaryLegacyAction && action.key === backendPrimaryLegacyAction.key) return false
    if (['schedule_interview', 'reschedule_interview', 'schedule_intro_day'].includes(action.key)) return false
    return true
  })
  const inlineActions = filteredActions.slice(0, 2)
  const overflowActions = filteredActions.slice(2)
  const hasSecondaryActions = Boolean(test2RailAction) || inlineActions.length > 0 || overflowActions.length > 0 || Boolean(rejectAction)

  return (
    <div className="cd-actions" ref={actionsRef} data-testid="candidate-actions">
      <section className="cd-action-center" data-testid="candidate-action-center">
        <div className="cd-action-center__toolbar">
          <div className="cd-action-center__tools">
            <button
              type="button"
              className="cd-rail-btn cd-rail-btn--secondary"
              data-testid="candidate-tests-trigger"
              onClick={onOpenTests}
            >
              Тесты
            </button>
            {showInsightsAction ? (
              <button
                type="button"
                className="cd-rail-btn cd-rail-btn--secondary"
                data-testid="candidate-insights-trigger"
                aria-label="Открыть заметки по кандидату"
                onClick={onOpenInsights}
              >
                Заметки
              </button>
            ) : null}
          </div>
        </div>
        <RecruiterActionBlock
          label={primaryActionLabel}
          explanation={surfaceState.nextActionExplanation || 'Система подсказывает следующий безопасный шаг для этого кандидата.'}
          tone={surfaceState.nextActionTone}
          enabled={primaryActionEnabled && !actionPending}
          eyebrow="Что делать сейчас"
          badgeLabel={surfaceState.urgencyLabel}
          className="cd-action-center__block"
          action={renderPrimaryActionButton(primaryActionLabel, {
            pending: actionPending,
            disabled: !primaryActionEnabled || actionPending,
            onClick: handlePrimaryAction,
          })}
        />
        {(surfaceState.nextActionOwnerLabel || surfaceState.queueStateLabel || surfaceState.lifecycle.stage_label) ? (
          <div className="toolbar toolbar--compact cd-action-center__signals">
            {surfaceState.lifecycle.stage_label ? <span className="cd-chip cd-chip--info">{surfaceState.lifecycle.stage_label}</span> : null}
            {surfaceState.nextActionOwnerLabel ? <span className="cd-chip">{surfaceState.nextActionOwnerLabel}</span> : null}
            {surfaceState.queueStateLabel ? <span className="cd-chip">{surfaceState.queueStateLabel}</span> : null}
          </div>
        ) : null}
        {hasSecondaryActions ? (
          <div className="cd-action-rail" data-testid="candidate-action-rail">
            <div className="cd-action-rail__scroll">
              {test2RailAction ? (
                <button
                  className={`cd-rail-btn ${test2RailAction.variant === 'primary' ? 'cd-rail-btn--primary' : 'cd-rail-btn--secondary'}`}
                  onClick={() => onActionClick(test2RailAction)}
                  disabled={actionPending}
                >
                  {test2RailAction.label}
                </button>
              ) : null}
              {inlineActions.map((action) => (
                <button
                  key={action.key}
                  className={`cd-rail-btn ${action.variant === 'primary' ? 'cd-rail-btn--primary' : 'cd-rail-btn--secondary'}`}
                  onClick={() => onActionClick(action)}
                  disabled={actionPending}
                >
                  {action.label}
                </button>
              ))}
              {overflowActions.length > 0 && (
                <details className="ui-disclosure cd-actions-overflow" data-testid="candidate-actions-overflow">
                  <summary className="cd-rail-btn cd-rail-btn--secondary">Ещё действия</summary>
                  <div className="ui-disclosure__content cd-actions-overflow__content">
                    {overflowActions.map((action) => (
                      <button
                        key={action.key}
                        className={`cd-rail-btn ${action.variant === 'primary' ? 'cd-rail-btn--primary' : 'cd-rail-btn--secondary'}`}
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
        ) : null}
      </section>

      <aside className="cd-actions__rail">
        <section className="cd-actions__panel cd-actions__panel--channels">
          <div className="cd-actions__section-label">Связь и материалы</div>
          <div className="cd-channels" data-testid="candidate-channels">
            {telegramLink ? (
              <a
                href={telegramLink}
                className="cd-channel cd-channel--telegram"
                target="_blank"
                rel="noopener"
                title={`Telegram: ${formatChannelLinkStatus(true)}`}
              >
                <span className="cd-channel__icon">TG</span>
                <span className="cd-channel__label">Telegram</span>
              </a>
            ) : (
              <span className="cd-channel cd-channel--disabled" title={`Telegram: ${formatChannelLinkStatus(false)}`}>
                <span className="cd-channel__icon">TG</span>
                <span className="cd-channel__label">Telegram</span>
              </span>
            )}
            {maxLinked ? (
              <span className="cd-channel cd-channel--max" title={`MAX: ${formatChannelLinkStatus(true)}`}>
                <span className="cd-channel__icon">MX</span>
                <span className="cd-channel__label">MAX</span>
              </span>
            ) : (
              <span className="cd-channel cd-channel--max cd-channel--disabled" title={`MAX: ${formatChannelLinkStatus(false)}`}>
                <span className="cd-channel__icon">MX</span>
                <span className="cd-channel__label">MAX</span>
              </span>
            )}
            {hasHhProfile ? (
              <button
                type="button"
                className="cd-channel cd-channel--hh"
                data-testid="candidate-hh-trigger"
                onClick={onOpenHh}
                title={hhLink ? 'Открыть резюме HH' : 'Открыть карточку HH'}
              >
                <span className="cd-channel__icon">hh</span>
                <span className="cd-channel__label">HeadHunter</span>
              </button>
            ) : (
              <span className="cd-channel cd-channel--disabled" title="HH не привязан">
                <span className="cd-channel__icon">hh</span>
                <span className="cd-channel__label">HeadHunter</span>
              </span>
            )}
            {conferenceLink ? (
              <a
                href={conferenceLink}
                className="cd-channel cd-channel--conference"
                target="_blank"
                rel="noopener noreferrer"
                title="Видеоконференция"
              >
                <span className="cd-channel__icon">▶</span>
                <span className="cd-channel__label">Конференция</span>
              </a>
            ) : (
              <span className="cd-channel cd-channel--disabled" title="Конференция не настроена">
                <span className="cd-channel__icon">▶</span>
                <span className="cd-channel__label">Конференция</span>
              </span>
            )}
            <button
              type="button"
              className="cd-channel cd-channel--chat"
              onClick={onOpenChat}
              disabled={!canOpenChat}
            >
              <span className="cd-channel__icon">💬</span>
              <span className="cd-channel__label">Чат</span>
            </button>
          </div>
        </section>
      </aside>
    </div>
  )
}
