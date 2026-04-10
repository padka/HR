import type { Ref, ReactNode } from 'react'
import {
  RecruiterActionBlock,
  RecruiterLifecycleStrip,
  RecruiterRiskBanner,
  RecruiterStateContext,
} from '@/app/components/RecruiterState'
import type {
  CandidateAction,
  CandidateBlockingState,
  CandidateDetail,
  TestSection,
} from '@/api/services/candidates'
import { normalizeConferenceUrl, normalizeTelegramUsername } from '@/shared/utils/normalizers'
import { buildCandidateSurfaceState } from '../candidate-state.adapter'

type CandidateActionsProps = {
  candidate: CandidateDetail
  statusSlug: string | null
  blockingState?: CandidateBlockingState | null
  test2Section?: TestSection
  actionPending: boolean
  maxLinkPending: boolean
  showInsightsAction?: boolean
  actionsRef?: Ref<HTMLDivElement>
  onOpenChat: () => void
  onOpenInsights: () => void
  onCopyMaxLink: () => void
  onScheduleSlot: () => void
  onScheduleIntroDay: () => void
  onActionClick: (action: CandidateAction) => void
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
  maxLinkPending,
  showInsightsAction = false,
  actionsRef,
  onOpenChat,
  onOpenInsights,
  onCopyMaxLink,
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
  const conferenceLink = normalizeConferenceUrl(candidate.telemost_url)
  const isMaxLinked = Boolean(candidate.max_user_id)
  const canOpenChat = Boolean(candidate.telegram_id || candidate.max_user_id)

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
    || (canScheduleInterview ? scheduleLabel : null)
    || (canScheduleIntroDay ? 'Назначить ОД' : null)
    || (test2Action ? 'Отправить Тест 2' : null)
    || surfaceState.nextActionLabel
    || 'Следующий шаг уточняется'
  const primaryActionEnabled = hasBackendPrimaryAction || canScheduleInterview || canScheduleIntroDay || Boolean(test2Action)

  const filteredActions = actions.filter((action) => {
    if (action === test2Action || action === rejectAction) return false
    if (backendPrimaryLegacyAction && action.key === backendPrimaryLegacyAction.key) return false
    if (['schedule_interview', 'reschedule_interview', 'schedule_intro_day'].includes(action.key)) return false
    return true
  })
  const inlineActions = filteredActions.slice(0, 2)
  const overflowActions = filteredActions.slice(2)

  return (
    <div className="cd-actions" ref={actionsRef}>
      <section className="cd-action-center" data-testid="candidate-action-center">
        <RecruiterActionBlock
          label={primaryActionLabel}
          explanation={surfaceState.nextActionExplanation || 'Система подсказывает следующий безопасный шаг для этого кандидата.'}
          tone={surfaceState.nextActionTone}
          enabled={primaryActionEnabled && !actionPending}
          eyebrow="Что делать сейчас"
          badgeLabel={surfaceState.urgencyLabel}
          action={renderPrimaryActionButton(primaryActionLabel, {
            pending: actionPending,
            disabled: !primaryActionEnabled || actionPending,
            onClick: handlePrimaryAction,
          })}
        />
        {(surfaceState.nextActionOwnerLabel || surfaceState.queueStateLabel) ? (
          <div className="toolbar toolbar--compact">
            {surfaceState.nextActionOwnerLabel ? <span className="cd-chip cd-chip--info">{surfaceState.nextActionOwnerLabel}</span> : null}
            {surfaceState.queueStateLabel ? <span className="cd-chip">{surfaceState.queueStateLabel}</span> : null}
          </div>
        ) : null}
        {surfaceState.riskLevel && surfaceState.riskTitle && surfaceState.riskMessage ? (
          <RecruiterRiskBanner
            level={surfaceState.riskLevel}
            title={surfaceState.riskTitle}
            message={surfaceState.riskMessage}
            recoveryHint={surfaceState.riskRecoveryHint}
            count={surfaceState.riskCount > 0 ? surfaceState.riskCount : undefined}
          />
        ) : null}
        <div className="cd-action-center__context">
          <RecruiterLifecycleStrip
            stageLabel={surfaceState.lifecycle.stage_label}
            recordState={surfaceState.lifecycle.record_state}
            finalOutcomeLabel={surfaceState.lifecycle.final_outcome_label || null}
          />
          <div className="cd-scheduling-card">
            <div className="cd-scheduling-card__title">Контекст назначения</div>
            <RecruiterStateContext
              bucketLabel={surfaceState.worklistBucketLabel}
              contextLine={surfaceState.stateContextLine}
              schedulingLine={surfaceState.schedulingContextLine}
            />
          </div>
        </div>
      </section>

      <section className="cd-actions__secondary">
        <div className="cd-channels" data-testid="candidate-channels">
          {telegramLink ? (
            <a
              href={telegramLink}
              className="cd-channel cd-channel--telegram"
              target="_blank"
              rel="noopener"
              title={telegramUsername ? `Telegram @${telegramUsername}` : 'Telegram'}
            >
              <span className="cd-channel__icon">TG</span>
              <span className="cd-channel__label">Telegram</span>
            </a>
          ) : (
            <span className="cd-channel cd-channel--disabled" title="Telegram не привязан">
              <span className="cd-channel__icon">TG</span>
              <span className="cd-channel__label">Telegram</span>
            </span>
          )}
          {hhLink ? (
            <a
              href={hhLink}
              className="cd-channel cd-channel--hh"
              target="_blank"
              rel="noopener"
              title="HeadHunter"
            >
              <span className="cd-channel__icon">hh</span>
              <span className="cd-channel__label">HeadHunter</span>
            </a>
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
          {isMaxLinked ? (
            <span className="cd-channel cd-channel--max" title="MAX привязан">
              <span className="cd-channel__icon">MX</span>
              <span className="cd-channel__label">MAX</span>
            </span>
          ) : (
            <button
              type="button"
              className="cd-channel cd-channel--max"
              onClick={onCopyMaxLink}
              disabled={maxLinkPending}
              title="Скопировать ссылку MAX"
            >
              <span className="cd-channel__icon">MX</span>
              <span className="cd-channel__label">{maxLinkPending ? 'Готовим…' : 'MAX'}</span>
            </button>
          )}
        </div>

        <div className="cd-action-rail" data-testid="candidate-actions">
          <div className="cd-action-rail__scroll">
            {showInsightsAction && (
              <button
                type="button"
                className="cd-rail-btn cd-rail-btn--secondary"
                data-testid="candidate-insights-trigger"
                aria-label="Открыть инсайты кандидата"
                onClick={onOpenInsights}
              >
                Инсайты
              </button>
            )}
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
                <summary className="cd-rail-btn cd-rail-btn--secondary">Ещё</summary>
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
      </section>
    </div>
  )
}
