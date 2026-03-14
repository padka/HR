import { useState } from 'react'

import './candidate-timeline.css'

import TimelineEvent from './TimelineEvent'
import type { TimelineEvent as TimelineEventType } from './timeline.types'

type CandidateTimelineProps = {
  events: TimelineEventType[]
}

export default function CandidateTimeline({ events }: CandidateTimelineProps) {
  const [expanded, setExpanded] = useState(false)
  const visibleEvents = expanded ? events : events.slice(0, 20)

  return (
    <section className="glass panel candidate-insights-drawer__section">
      <div className="cd-section-header">
        <div>
          <h2 className="cd-section-title">Хронология</h2>
          <p className="subtitle">Единая лента значимых событий по кандидату.</p>
        </div>
        {events.length > 20 && (
          <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => setExpanded((prev) => !prev)}>
            {expanded ? 'Свернуть' : 'Показать все'}
          </button>
        )}
      </div>

      {events.length === 0 ? (
        <p className="subtitle">Событий пока нет.</p>
      ) : (
        <div className="candidate-timeline" data-testid="candidate-details-timeline">
          {visibleEvents.map((event) => (
            <TimelineEvent key={event.id} event={event} />
          ))}
        </div>
      )}
    </section>
  )
}
