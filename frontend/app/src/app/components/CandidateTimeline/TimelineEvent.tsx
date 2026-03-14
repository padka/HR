import type { TimelineEvent as TimelineEventType } from './timeline.types'

type TimelineEventProps = {
  event: TimelineEventType
}

export default function TimelineEvent({ event }: TimelineEventProps) {
  return (
    <div className="candidate-timeline__item">
      <div className={`candidate-timeline__dot candidate-timeline__dot--${event.tone}`} aria-hidden="true" />
      <div className="candidate-timeline__card">
        <div className="candidate-timeline__top">
          <span className={`candidate-timeline__badge candidate-timeline__badge--${event.tone}`}>{event.badge}</span>
          <span className="candidate-timeline__time">{event.timestamp}</span>
        </div>
        <div className="candidate-timeline__title">{event.title}</div>
        <div className="candidate-timeline__description">{event.description}</div>
      </div>
    </div>
  )
}
