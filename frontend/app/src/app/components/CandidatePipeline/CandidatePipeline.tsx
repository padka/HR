import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { LayoutGroup, useReducedMotion } from 'framer-motion'

import PipelineConnector from './PipelineConnector'
import PipelineStage from './PipelineStage'
import StageDetailPanel from './StageDetailPanel'
import './candidate-pipeline.css'
import type { PipelineStage as PipelineStageRecord } from './pipeline.types'
import { getConnectorFill, getConnectorState, getCurrentStageIndex, translateSystemMessage } from './pipeline.utils'

type CandidatePipelineProps = {
  title?: string
  currentStateLabel?: string | null
  stages: PipelineStageRecord[]
  initialStageId?: string | null
  isMobile?: boolean
}

export default function CandidatePipeline({
  title = 'Воронка',
  currentStateLabel,
  stages,
  initialStageId,
  isMobile = false,
}: CandidatePipelineProps) {
  const reducedMotion = useReducedMotion()
  const [openStageId, setOpenStageId] = useState<string | null>(initialStageId ?? stages[0]?.id ?? null)
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const dragRef = useRef<{ startX: number; scrollLeft: number; dragging: boolean } | null>(null)

  useEffect(() => {
    setOpenStageId(initialStageId ?? stages[0]?.id ?? null)
  }, [initialStageId, stages])

  const currentStageIndex = useMemo(() => getCurrentStageIndex(stages), [stages])
  const openStage = useMemo(
    () => stages.find((stage) => stage.id === openStageId) || null,
    [openStageId, stages],
  )

  const panelId = openStage ? `candidate-pipeline-panel-${openStage.id}` : 'candidate-pipeline-panel'

  const toggleStage = (stageId: string) => {
    if (dragRef.current?.dragging) {
      dragRef.current = null
      return
    }
    setOpenStageId((current) => (current === stageId ? null : stageId))
  }

  return (
    <section
      className="candidate-pipeline glass panel app-page__section"
      data-motion={reducedMotion ? 'reduced' : 'full'}
      data-testid="candidate-pipeline"
      onKeyDown={(event) => {
        if (event.key === 'Escape') setOpenStageId(null)
      }}
    >
      <div className="candidate-pipeline__header">
        <h2 className="candidate-pipeline__title">{title}</h2>
        {currentStateLabel ? (
          <div className="candidate-pipeline__state">
            <span className="candidate-pipeline__state-label">Текущее состояние</span>
            <span className="candidate-pipeline__state-value">{translateSystemMessage(currentStateLabel)}</span>
          </div>
        ) : null}
      </div>

      <div
        ref={viewportRef}
        className={`candidate-pipeline__viewport ${isMobile ? 'candidate-pipeline__viewport--vertical' : ''}`}
        onPointerDown={(event) => {
          if (isMobile || !viewportRef.current) return
          dragRef.current = {
            startX: event.clientX,
            scrollLeft: viewportRef.current.scrollLeft,
            dragging: false,
          }
        }}
        onPointerMove={(event) => {
          if (isMobile || !viewportRef.current || !dragRef.current) return
          const delta = event.clientX - dragRef.current.startX
          if (Math.abs(delta) > 4) dragRef.current.dragging = true
          viewportRef.current.scrollLeft = dragRef.current.scrollLeft - delta
        }}
        onPointerUp={() => { dragRef.current = null }}
        onPointerCancel={() => { dragRef.current = null }}
      >
        <LayoutGroup>
          <div className={`candidate-pipeline__track ${isMobile ? 'candidate-pipeline__track--vertical' : ''}`}>
            {stages.map((stage, index) => (
              <Fragment key={stage.id}>
                <PipelineStage
                  stage={stage}
                  index={index}
                  total={stages.length}
                  isOpen={openStageId === stage.id}
                  reducedMotion={Boolean(reducedMotion)}
                  controlsId={panelId}
                  onToggle={() => toggleStage(stage.id)}
                />
                {isMobile && openStageId === stage.id ? (
                  <StageDetailPanel
                    stage={stage}
                    panelId={panelId}
                    reducedMotion={Boolean(reducedMotion)}
                    onClose={() => setOpenStageId(null)}
                  />
                ) : null}
                {index < stages.length - 1 ? (
                  <PipelineConnector
                    fill={getConnectorFill(currentStageIndex, index, stages[currentStageIndex]?.status)}
                    state={getConnectorState(currentStageIndex, index, stages[currentStageIndex]?.status)}
                    vertical={isMobile}
                    reducedMotion={Boolean(reducedMotion)}
                  />
                ) : null}
              </Fragment>
            ))}
          </div>
        </LayoutGroup>
      </div>

      {!isMobile ? (
        <StageDetailPanel
          stage={openStage}
          panelId={panelId}
          reducedMotion={Boolean(reducedMotion)}
          onClose={() => setOpenStageId(null)}
        />
      ) : null}
    </section>
  )
}
