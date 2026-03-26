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
          <div className="subtitle">{portal.public_url || portal.max_link_base || 'Публичный URL не задан'}</div>
          <div className="subtitle">
            {portal.public_message || portal.max_entry_message || 'Портал кандидата готов к выдаче ссылок'}
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
