import type { Ref } from 'react'
import type { CandidateAction, CandidateChannelHealth, CandidateDetail, TestSection } from '@/api/services/candidates'
import { normalizeConferenceUrl, normalizeTelegramUsername } from '@/shared/utils/normalizers'

type CandidateActionsProps = {
  candidate: CandidateDetail
  channelHealth?: CandidateChannelHealth | null
  statusSlug: string | null
  test2Section?: TestSection
  actionPending: boolean
  maxLinkPending: boolean
  restartPending: boolean
  showInsightsAction?: boolean
  actionsRef?: Ref<HTMLDivElement>
  onOpenChat: () => void
  onOpenInsights: () => void
  onCopyMaxLink: () => void
  onRestartPortal: () => void
  onOpenBrowserPortal: () => void
  onScheduleSlot: () => void
  onScheduleIntroDay: () => void
  onActionClick: (action: CandidateAction) => void
}

export function CandidateActions({
  candidate,
  channelHealth,
  statusSlug,
  test2Section,
  actionPending,
  maxLinkPending,
  restartPending,
  showInsightsAction = false,
  actionsRef,
  onOpenChat,
  onOpenInsights,
  onCopyMaxLink,
  onRestartPortal,
  onOpenBrowserPortal,
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
  const preferredChannel = channelHealth?.preferred_channel || candidate.messenger_platform || null
  const lastOutboundStatus =
    channelHealth?.last_outbound_delivery?.delivery_stage
    || channelHealth?.last_outbound_delivery?.status
    || null
  const lastOutboundError = channelHealth?.last_outbound_delivery?.error || null
  const activeInvite = channelHealth?.active_invite || null
  const browserLink = channelHealth?.browser_link || null
  const configErrors = channelHealth?.config_errors || []
  const restartAllowed = channelHealth?.restart_allowed !== false

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
    <div className="cd-actions" ref={actionsRef}>
      {/* Communication channels - branded */}
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
            title="Скопировать MAX-бота"
          >
            <span className="cd-channel__icon">MX</span>
            <span className="cd-channel__label">{maxLinkPending ? 'Готовим…' : 'MAX bot'}</span>
          </button>
        )}
      </div>

      {channelHealth && (
        <section
          className="glass panel--tight"
          data-testid="candidate-channel-health"
          style={{ padding: 14, marginTop: 12 }}
        >
          <div className="toolbar" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
            <div>
              <div className="section-title" style={{ margin: 0, fontSize: '0.95rem' }}>Channel Health</div>
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                Preferred channel: {preferredChannel === 'max' ? 'MAX' : preferredChannel === 'telegram' ? 'Telegram' : '—'}
              </p>
            </div>
            {channelHealth.conflict_badge ? (
              <span className="status-badge status-badge--danger">invite conflict</span>
            ) : null}
          </div>

          <div className="toolbar" style={{ flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
            <span className={`status-badge ${channelHealth.telegram_linked ? 'status-badge--success' : 'status-badge--muted'}`}>
              Telegram {channelHealth.telegram_linked ? 'linked' : 'not linked'}
            </span>
            <span className={`status-badge ${channelHealth.max_linked ? 'status-badge--info' : 'status-badge--muted'}`}>
              MAX {channelHealth.max_linked ? 'linked' : 'not linked'}
            </span>
            {activeInvite?.status ? (
              <span className="status-badge status-badge--warning">
                invite: {activeInvite.status}
              </span>
            ) : null}
            {lastOutboundStatus ? (
              <span className="status-badge status-badge--warning">
                send: {lastOutboundStatus}
              </span>
            ) : null}
          </div>

          <div style={{ marginTop: 10 }}>
            <p className="subtitle" style={{ margin: 0 }}>
              portal: {channelHealth.portal_entry_ready ? 'public ready' : 'public blocked'}
              {' · '}
              MAX entry: {channelHealth.max_entry_ready ? 'ready' : 'blocked'}
            </p>
            {channelHealth.active_journey_id ? (
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                journey: #{channelHealth.active_journey_id} · session v{channelHealth.session_version || 1}
              </p>
            ) : null}
            {activeInvite?.used_by_external_id ? (
              <p className="subtitle" style={{ margin: channelHealth.active_journey_id ? '4px 0 0' : 0 }}>
                invite user: {activeInvite.used_by_external_id}
              </p>
            ) : null}
            <p className="subtitle" style={{ margin: activeInvite?.used_by_external_id ? '4px 0 0' : 0 }}>
              last inbound: {channelHealth.last_inbound_at ? new Date(channelHealth.last_inbound_at).toLocaleString('ru-RU') : '—'}
            </p>
            {channelHealth.last_link_issued_at ? (
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                last link: {new Date(channelHealth.last_link_issued_at).toLocaleString('ru-RU')}
              </p>
            ) : null}
            {lastOutboundError ? (
              <p className="subtitle subtitle--danger" style={{ margin: '4px 0 0' }}>
                {lastOutboundError}
              </p>
            ) : null}
            {configErrors.length > 0 ? (
              <p className="subtitle subtitle--danger" style={{ margin: '4px 0 0' }}>
                {configErrors.join(' · ')}
              </p>
            ) : null}
          </div>

          <div className="toolbar" style={{ flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
            <button
              type="button"
              className="ui-btn ui-btn--primary ui-btn--sm"
              onClick={onCopyMaxLink}
              disabled={maxLinkPending}
            >
              {maxLinkPending ? 'Отправляем…' : 'Переотправить ссылку'}
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={onOpenBrowserPortal}
              disabled={!browserLink}
            >
              Открыть browser link
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={onRestartPortal}
              disabled={restartPending || !restartAllowed}
            >
              {restartPending ? 'Перезапускаем…' : 'Начать заново'}
            </button>
          </div>
        </section>
      )}

      {/* Action buttons */}
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
    </div>
  )
}
