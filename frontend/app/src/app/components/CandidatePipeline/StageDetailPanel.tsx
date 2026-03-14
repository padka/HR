import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'

import { pipelinePanelVariants } from './pipeline.variants'
import type { PipelineStage } from './pipeline.types'
import { translateSystemMessage, translateSystemMessageList } from './pipeline.utils'

type StageDetailPanelProps = {
  stage: PipelineStage | null
  panelId: string
  reducedMotion: boolean
  onClose: () => void
}

export default function StageDetailPanel({
  stage,
  panelId,
  reducedMotion,
  onClose,
}: StageDetailPanelProps) {
  const description = translateSystemMessage(stage?.detail?.description)
  const metaItems = translateSystemMessageList(stage?.detail?.meta)
  const noticeTitle = translateSystemMessage(stage?.detail?.notice?.title)
  const noticeText = translateSystemMessage(stage?.detail?.notice?.text)
  const emptyText = translateSystemMessage(stage?.detail?.emptyText) || 'Для этого этапа пока нет событий.'

  return (
    <AnimatePresence initial={false} mode="wait">
      {stage ? (
        <motion.section
          key={stage.id}
          id={panelId}
          layout
          className="candidate-pipeline-panel"
          data-testid="candidate-funnel-detail"
          initial={reducedMotion ? false : 'hidden'}
          animate={reducedMotion ? undefined : 'visible'}
          exit={reducedMotion ? undefined : 'exit'}
          variants={reducedMotion ? undefined : pipelinePanelVariants}
        >
          <div className="candidate-pipeline-panel__header">
            <div>
              <div className="candidate-pipeline-panel__eyebrow">Этап воронки</div>
              <h3 className="candidate-pipeline-panel__title">{stage.title}</h3>
              {description ? (
                <p className="candidate-pipeline-panel__description">{description}</p>
              ) : null}
            </div>
            <button
              type="button"
              className="candidate-pipeline-panel__close"
              onClick={onClose}
              aria-label={`Закрыть детали этапа ${stage.title}`}
            >
              <X size={16} />
            </button>
          </div>

          {metaItems.length > 0 ? (
            <div className="candidate-pipeline-panel__meta">
              {metaItems.map((item) => (
                <span key={`${stage.id}-${item}`} className="candidate-pipeline-panel__chip">
                  {item}
                </span>
              ))}
            </div>
          ) : null}

          {stage.detail?.notice ? (
            <div className="candidate-pipeline-panel__notice">
              <div className="candidate-pipeline-panel__notice-title">{noticeTitle}</div>
              <div className="candidate-pipeline-panel__notice-text">{noticeText}</div>
            </div>
          ) : null}

          <div className="candidate-pipeline-panel__events">
            {stage.detail?.events && stage.detail.events.length > 0 ? (
              stage.detail.events.map((event) => (
                <article key={event.id} className="candidate-pipeline-panel__event">
                  <div className="candidate-pipeline-panel__event-head">
                    <strong>{translateSystemMessage(event.title)}</strong>
                    {event.timestamp ? (
                      <time dateTime={event.timestamp}>{event.timestamp}</time>
                    ) : null}
                  </div>
                  {event.meta ? <div className="candidate-pipeline-panel__event-meta">{translateSystemMessage(event.meta)}</div> : null}
                  {event.lines && event.lines.length > 0 ? (
                    <div className="candidate-pipeline-panel__event-lines">
                      {translateSystemMessageList(event.lines).map((line) => (
                        <span key={`${event.id}-${line}`}>{line}</span>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))
            ) : (
              <div className="candidate-pipeline-panel__empty">
                {emptyText}
              </div>
            )}
          </div>
        </motion.section>
      ) : null}
    </AnimatePresence>
  )
}
