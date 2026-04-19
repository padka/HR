import type { MessengerHealthChannel } from '@/api/services/system'

export function MessengerHealthCards({
  channels,
}: {
  channels?: Record<string, MessengerHealthChannel> | null
}) {
  const items = Object.values(channels || {})
  if (items.length === 0) return null

  return (
    <div className="data-grid" style={{ marginBottom: 16 }}>
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
