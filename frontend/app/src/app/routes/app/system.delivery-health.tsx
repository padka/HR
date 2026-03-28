import type { MessengerHealthChannel, MessengerHealthPayload } from '@/api/services/system'

export function MessengerHealthCards({
  channels,
  portal,
}: {
  channels?: Record<string, MessengerHealthChannel> | null
  portal?: MessengerHealthPayload['portal']
}) {
  const items = Object.values(channels || {})
  if (items.length === 0 && !portal) return null

  return (
    <div className="data-grid" style={{ marginBottom: 16 }}>
      {portal ? (
        <article
          className="glass glass--interactive data-card"
          data-testid="messenger-health-portal"
        >
          <div className="data-card__label">PORTAL ENTRY</div>
          <div className="data-card__value">
            {portal.public_ready && portal.max_entry_ready ? 'ready' : 'attention'}
          </div>
          <div className="subtitle">public: {portal.public_ready ? 'ready' : 'blocked'}</div>
          <div className="subtitle">MAX mini app: {portal.max_entry_ready ? 'ready' : 'blocked'}</div>
          <div className="subtitle">webhook: {portal.webhook_public_ready ? 'ready' : 'blocked'}</div>
          <div className="subtitle">
            profile: {portal.bot_profile_resolved ? (portal.bot_profile_name || 'resolved') : 'unavailable'}
          </div>
          <div className="subtitle">
            link base: {portal.max_link_base_source || 'missing'} · {portal.max_link_base || portal.public_url || 'Публичный URL не задан'}
          </div>
          {portal.shared_access ? (
            <>
              <div className="subtitle">
                shared portal auth: {portal.shared_access.production_ready ? 'ready' : 'attention'} · store: {portal.shared_access.store_backend || 'memory'} · rate-limit: {portal.shared_access.rate_limit_ready ? 'ready' : 'attention'}
              </div>
              <div className="subtitle">
                challenge: {portal.shared_access.challenge_started ?? 0} · rate-limited: {portal.shared_access.challenge_rate_limited ?? 0}
              </div>
              <div className="subtitle">
                verify ok: {portal.shared_access.verify_success ?? 0} · failed: {portal.shared_access.verify_failed ?? 0} · expired: {portal.shared_access.verify_expired ?? 0}
              </div>
            </>
          ) : null}
          <div className="subtitle">
            {portal.public_message || portal.max_entry_message || portal.webhook_message || portal.subscription_message || 'Портал кандидата готов к выдаче ссылок'}
          </div>
        </article>
      ) : null}
      {items.map((channel) => (
        <article
          key={channel.channel}
          className="glass glass--interactive data-card"
          data-testid={`messenger-health-${channel.channel}`}
        >
          <div className="data-card__label">{channel.channel.toUpperCase()}</div>
          <div className="data-card__value">{channel.status || 'healthy'}</div>
          <div className="subtitle">queue: {channel.queue_depth} · dlq: {channel.dead_letter_count}</div>
          <div className="subtitle">
            oldest pending age: {channel.oldest_pending_age_seconds != null ? `${channel.oldest_pending_age_seconds}s` : '—'}
          </div>
          <div className="subtitle">{channel.degraded_reason || 'Нет активных проблем'}</div>
        </article>
      ))}
    </div>
  )
}
