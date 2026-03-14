import type { TimelineEvent as TimelineEventType } from './timeline.types'

type TimelineEventProps = {
  event: TimelineEventType
}

export default function TimelineEvent({ event }: TimelineEventProps) {
  return (
    <article className="candidate-timeline__item">
      <span className={`candidate-timeline__dot candidate-timeline__dot--${event.tone}`} aria-hidden="true" />
      <div className="candidate-timeline__title">{event.title}</div>
      <time className="candidate-timeline__time">{event.timestamp}</time>
      {event.meta ? <div className="candidate-timeline__meta">{event.meta}</div> : null}
    </article>
  )
}
