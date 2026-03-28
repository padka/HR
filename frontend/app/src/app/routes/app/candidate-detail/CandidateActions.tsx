import type { Ref } from 'react'
import type {
  CandidateAction,
  CandidateChannelHealth,
  CandidateDetail,
  CandidateHHSummary,
  TestSection,
} from '@/api/services/candidates'
import { normalizeConferenceUrl, normalizeTelegramUsername } from '@/shared/utils/normalizers'

const DELIVERY_REASON_LABELS: Record<string, string> = {
  candidate_portal_public_url_missing: 'не настроен публичный URL кабинета',
  candidate_portal_public_url_not_https: 'публичный URL кабинета должен быть HTTPS',
  candidate_portal_public_url_loopback: 'публичный URL кабинета указывает на loopback',
  max_bot_disabled: 'MAX bot выключен в конфиге',
  max_token_missing: 'не настроен MAX_BOT_TOKEN',
  max_token_invalid: 'MAX токен отклонён провайдером',
  max_profile_unavailable: 'профиль MAX бота недоступен',
  max_bot_link_base_unresolved: 'не удалось определить публичную ссылку MAX бота',
  max_bot_link_base_not_https: 'публичная ссылка MAX бота должна быть HTTPS',
  max_not_linked: 'кандидат ещё не привязан к MAX',
  max_channel_degraded: 'канал MAX сейчас деградирован',
  telegram_bot_disabled: 'Telegram bot выключен в конфиге',
  telegram_token_missing: 'не настроен BOT_TOKEN',
  telegram_profile_unavailable: 'профиль Telegram бота недоступен',
  telegram_link_base_unresolved: 'не удалось определить публичную ссылку Telegram бота',
  telegram_entry_blocked: 'Telegram launcher сейчас недоступен',
  portal_entry_not_ready: 'публичный вход в кабинет не готов',
  hh_connection_missing: 'не настроено HH-подключение',
  hh_identity_not_linked: 'кандидат не привязан к HH',
  hh_negotiation_missing: 'HH negotiation ещё не импортирован',
  hh_actions_missing: 'HH actions snapshot ещё не загружен',
  hh_message_action_missing: 'HH не даёт action на отправку сообщения кандидату',
  candidate_uuid_missing: 'у кандидата отсутствует публичный cabinet id',
  shared_portal_phone_missing: 'у кандидата не заполнен телефон для shared portal',
}

function describeDeliveryReason(reason?: string | null) {
  const normalized = String(reason || '').trim()
  if (!normalized) return null
  return DELIVERY_REASON_LABELS[normalized] || normalized
}

type CandidateActionsProps = {
  candidate: CandidateDetail
  channelHealth?: CandidateChannelHealth | null
  hhSummary?: CandidateHHSummary | null
  statusSlug: string | null
  test2Section?: TestSection
  actionPending: boolean
  maxLinkPending: boolean
  restartPending: boolean
  hhSendPending: boolean
  showInsightsAction?: boolean
  actionsRef?: Ref<HTMLDivElement>
  onOpenChat: () => void
  onOpenInsights: () => void
  onCopyMaxLink: () => void
  onRestartPortal: () => void
  onSendHhEntryLink: () => void
  onOpenCandidateCabinet: () => void
  onOpenMaxPortal: () => void
  onOpenBrowserPortal: () => void
  onScheduleSlot: () => void
  onScheduleIntroDay: () => void
  onActionClick: (action: CandidateAction) => void
}

export function CandidateActions({
  candidate,
  channelHealth,
  hhSummary,
  statusSlug,
  test2Section,
  actionPending,
  maxLinkPending,
  restartPending,
  hhSendPending,
  showInsightsAction = false,
  actionsRef,
  onOpenChat,
  onOpenInsights,
  onCopyMaxLink,
  onRestartPortal,
  onSendHhEntryLink,
  onOpenCandidateCabinet,
  onOpenMaxPortal,
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
  const canOpenChat = Boolean(candidate.candidate_portal_url || candidate.telegram_id || candidate.max_user_id)
  const preferredChannel = channelHealth?.preferred_channel || candidate.messenger_platform || null
  const lastOutboundStatus =
    channelHealth?.last_outbound_delivery?.delivery_stage
    || channelHealth?.last_outbound_delivery?.status
    || null
  const lastOutboundError = channelHealth?.last_outbound_delivery?.error || null
  const lastPortalAccessStatus =
    channelHealth?.last_portal_access_delivery?.delivery_stage
    || channelHealth?.last_portal_access_delivery?.status
    || null
  const lastPortalAccessError = channelHealth?.last_portal_access_delivery?.error || null
  const lastPortalAccessAt = channelHealth?.last_portal_access_delivery?.created_at || null
  const activeInvite = channelHealth?.active_invite || null
  const publicLink = channelHealth?.public_link || null
  const browserLink = channelHealth?.browser_link || null
  const miniAppLink = channelHealth?.mini_app_link || null
  const telegramEntryLink = channelHealth?.telegram_link || null
  const hhEntryDelivery = hhSummary?.entry_delivery || null
  const sharedPortalUrl = channelHealth?.shared_portal_url || hhEntryDelivery?.shared_portal_url || null
  const sharedPortalReady = channelHealth?.shared_portal_ready !== false && hhEntryDelivery?.shared_portal_ready !== false
  const sharedPortalBlockedReason = describeDeliveryReason(channelHealth?.shared_portal_block_reason || hhEntryDelivery?.blocked_reason)
  const lastOtpDeliveryChannel = channelHealth?.last_otp_delivery_channel || hhEntryDelivery?.last_otp_delivery_channel || null
  const candidateCabinetUrl = candidate.candidate_portal_url || browserLink || publicLink || null
  const configErrors = channelHealth?.config_errors || []
  const restartAllowed = channelHealth?.restart_allowed !== false
  const deliveryReady = channelHealth?.delivery_ready !== false
  const deliveryBlockReason = describeDeliveryReason(channelHealth?.delivery_block_reason)
  const maxLinkBaseSource = channelHealth?.max_link_base_source || null
  const canReissuePortalAccess = Boolean(channelHealth?.portal_entry_ready)
  const reissueLabel = channelHealth?.max_entry_ready ? 'Переотправить ссылку' : 'Подготовить browser link'
  const hhReady = hhEntryDelivery?.ready !== false
  const hhBlockedReason = describeDeliveryReason(hhEntryDelivery?.blocked_reason || hhEntryDelivery?.last_block_reason)
  const hhLastSentAt = hhEntryDelivery?.last_sent_at || null

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
              <div className="section-title" style={{ margin: 0, fontSize: '0.95rem' }}>Candidate Cabinet</div>
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                Primary workspace: web cabinet
                {preferredChannel ? ` · delivery channel: ${preferredChannel === 'max' ? 'MAX' : preferredChannel === 'telegram' ? 'Telegram' : preferredChannel}` : ''}
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
            {candidateCabinetUrl ? (
              <span className="status-badge status-badge--success">cabinet: ready</span>
            ) : (
              <span className="status-badge status-badge--warning">cabinet: link missing</span>
            )}
            {lastOutboundStatus ? (
              <span className="status-badge status-badge--warning">
                send: {lastOutboundStatus}
              </span>
            ) : null}
            {lastPortalAccessStatus ? (
              <span className={`status-badge ${lastPortalAccessStatus === 'sent' ? 'status-badge--success' : 'status-badge--warning'}`}>
                portal package: {lastPortalAccessStatus}
              </span>
            ) : null}
          </div>

          <div style={{ marginTop: 10 }}>
            <p className="subtitle" style={{ margin: 0 }}>
              cabinet link: {candidateCabinetUrl ? 'ready' : 'missing'}
              {' · '}
              inbox: {canOpenChat ? 'available' : 'blocked'}
            </p>
            <p className="subtitle" style={{ margin: '4px 0 0' }}>
              shared portal: {sharedPortalReady ? 'ready' : 'blocked'}
              {sharedPortalUrl ? ` · ${sharedPortalUrl}` : ''}
            </p>
            <p className="subtitle" style={{ margin: 0 }}>
              portal: {channelHealth.portal_entry_ready ? 'public ready' : 'public blocked'}
              {' · '}
              MAX entry: {channelHealth.max_entry_ready ? 'ready' : 'blocked'}
              {' · '}
              TG entry: {channelHealth.telegram_entry_ready ? 'ready' : 'blocked'}
            </p>
            <p className="subtitle" style={{ margin: '4px 0 0' }}>
              delivery: {deliveryReady ? 'ready' : 'blocked'}
              {maxLinkBaseSource ? ` · link base: ${maxLinkBaseSource}` : ''}
            </p>
            {channelHealth.bot_profile_name ? (
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                MAX profile: {channelHealth.bot_profile_name}
              </p>
            ) : null}
            {channelHealth.active_journey_id ? (
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                journey: #{channelHealth.active_journey_id} · session v{channelHealth.session_version || 1}
              </p>
            ) : null}
            {candidate.last_activity_at ? (
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                last candidate activity: {new Date(candidate.last_activity_at).toLocaleString('ru-RU')}
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
            {lastPortalAccessAt ? (
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                last portal package: {new Date(lastPortalAccessAt).toLocaleString('ru-RU')}
              </p>
            ) : null}
            {lastOtpDeliveryChannel ? (
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                last OTP delivery: {lastOtpDeliveryChannel}
              </p>
            ) : null}
            {lastPortalAccessError ? (
              <p className="subtitle subtitle--danger" style={{ margin: '4px 0 0' }}>
                portal package error: {lastPortalAccessError}
              </p>
            ) : null}
            {sharedPortalBlockedReason ? (
              <p className="subtitle subtitle--danger" style={{ margin: '4px 0 0' }}>
                shared portal: {sharedPortalBlockedReason}
              </p>
            ) : null}
            {deliveryBlockReason ? (
              <p className="subtitle subtitle--danger" style={{ margin: '4px 0 0' }}>
                MAX delivery: {deliveryBlockReason}
              </p>
            ) : null}
            {configErrors.length > 0 ? (
              <p className="subtitle subtitle--danger" style={{ margin: '4px 0 0' }}>
                {configErrors.join(' · ')}
              </p>
            ) : null}
            {(miniAppLink || publicLink) ? (
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                live MAX entry готов для ручного smoke из админки.
              </p>
            ) : null}
            {!channelHealth.max_entry_ready && browserLink ? (
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                MAX недоступен для live-доставки. Browser link остаётся резервным входом.
              </p>
            ) : null}
            {telegramEntryLink ? (
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                Telegram launcher готов как альтернативный вход.
              </p>
            ) : null}
          </div>

          <div className="toolbar" style={{ flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
            <button
              type="button"
              className="ui-btn ui-btn--primary ui-btn--sm"
              onClick={onOpenCandidateCabinet}
              disabled={!candidateCabinetUrl}
            >
              Открыть кабинет
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={onCopyMaxLink}
              disabled={maxLinkPending || !canReissuePortalAccess}
              title={!canReissuePortalAccess ? deliveryBlockReason || 'Публичный вход в кабинет не готов' : undefined}
            >
              {maxLinkPending ? 'Отправляем…' : reissueLabel}
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={onOpenMaxPortal}
              disabled={!miniAppLink && !publicLink}
            >
              Открыть MAX launcher
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={onOpenBrowserPortal}
              disabled={!browserLink}
            >
              Открыть browser fallback
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={onRestartPortal}
              disabled={restartPending || !restartAllowed || !canReissuePortalAccess}
              title={!canReissuePortalAccess ? deliveryBlockReason || 'Публичный вход в кабинет не готов' : undefined}
            >
              {restartPending ? 'Перезапускаем…' : 'Начать заново'}
            </button>
          </div>
        </section>
      )}

      {hhSummary && (
        <section
          className="glass panel--tight"
          data-testid="candidate-hh-entry-health"
          style={{ padding: 14, marginTop: 12 }}
        >
          <div className="toolbar" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
            <div>
              <div className="section-title" style={{ margin: 0, fontSize: '0.95rem' }}>Entry / Delivery</div>
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                Рекрутер отправляет одну общую ссылку портала в HH. Candidate cabinet и OTP живут независимо от состояния мессенджеров.
              </p>
            </div>
            <span className={`status-badge ${hhReady ? 'status-badge--success' : 'status-badge--warning'}`}>
              Shared portal {hhReady ? 'ready' : 'blocked'}
            </span>
          </div>

          <div style={{ marginTop: 10 }}>
            <p className="subtitle" style={{ margin: 0 }}>
              shared URL: {hhEntryDelivery?.shared_portal_url || sharedPortalUrl || '—'}
            </p>
            <p className="subtitle" style={{ margin: 0 }}>
              selected channel: {hhEntryDelivery?.selected_channel || channelHealth?.last_entry_channel || 'web'}
            </p>
            <p className="subtitle" style={{ margin: '4px 0 0' }}>
              web: {channelHealth?.portal_entry_ready ? 'ready' : 'blocked'}
              {' · '}
              MAX: {channelHealth?.max_entry_ready ? 'ready' : 'blocked'}
              {' · '}
              Telegram: {channelHealth?.telegram_entry_ready ? 'ready' : 'blocked'}
            </p>
            {hhLastSentAt ? (
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                last shared portal sent: {new Date(hhLastSentAt).toLocaleString('ru-RU')}
              </p>
            ) : null}
            {hhEntryDelivery?.last_otp_delivery_channel ? (
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                last OTP delivery: {hhEntryDelivery.last_otp_delivery_channel}
              </p>
            ) : null}
            {hhEntryDelivery?.last_action_name ? (
              <p className="subtitle" style={{ margin: '4px 0 0' }}>
                last HH action: {hhEntryDelivery.last_action_name}
              </p>
            ) : null}
            {hhBlockedReason ? (
              <p className="subtitle subtitle--danger" style={{ margin: '4px 0 0' }}>
                HH block: {hhBlockedReason}
              </p>
            ) : null}
          </div>

          <div className="toolbar" style={{ flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
            <button
              type="button"
              className="ui-btn ui-btn--primary ui-btn--sm"
              onClick={onSendHhEntryLink}
              disabled={hhSendPending}
            >
              {hhSendPending ? 'Отправляем в HH…' : 'Отправить shared portal в HH'}
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={onOpenCandidateCabinet}
              disabled={!candidateCabinetUrl}
            >
              Открыть cabinet
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={onCopyMaxLink}
              disabled={maxLinkPending || !canReissuePortalAccess}
            >
              {maxLinkPending ? 'Готовим доступ…' : 'Переотправить доступ'}
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
