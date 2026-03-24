import { Fragment, useMemo } from 'react'
import { LayoutGroup, useReducedMotion } from 'framer-motion'

import PipelineConnector from './PipelineConnector'
import PipelineStage from './PipelineStage'
import './candidate-pipeline.css'
import type { PipelineStage as PipelineStageRecord } from './pipeline.types'
import { getConnectorFill, getConnectorState, getCurrentStageIndex, translateSystemMessage } from './pipeline.utils'

type CandidatePipelineProps = {
  currentStateLabel?: string | null
  stages: PipelineStageRecord[]
  initialStageId?: string | null
  isMobile?: boolean
}

export default function CandidatePipeline({
  currentStateLabel,
  stages,
  isMobile = false,
}: CandidatePipelineProps) {
  const reducedMotion = useReducedMotion()
  const currentStageIndex = useMemo(() => getCurrentStageIndex(stages), [stages])
  const currentStage = stages[currentStageIndex]

  return (
    <section
      className="candidate-pipeline"
      data-motion={reducedMotion ? 'reduced' : 'full'}
      data-testid="candidate-pipeline"
    >
      <div className="candidate-pipeline__header">
        <div className="candidate-pipeline__status-block">
          {currentStage && (
            <span className={`candidate-pipeline__current-badge candidate-pipeline__current-badge--${currentStage.status}`}>
              {currentStage.title}
            </span>
          )}
          {currentStateLabel ? (
            <span className="candidate-pipeline__state-hint">
              {translateSystemMessage(currentStateLabel)}
            </span>
          ) : null}
        </div>
      </div>

      <div className={`candidate-pipeline__viewport ${isMobile ? 'candidate-pipeline__viewport--vertical' : ''}`}>
        <LayoutGroup>
          <div className={`candidate-pipeline__track ${isMobile ? 'candidate-pipeline__track--vertical' : ''}`}>
            {stages.map((stage, index) => (
              <Fragment key={stage.id}>
                <PipelineStage
                  stage={stage}
                  index={index}
                  total={stages.length}
                  reducedMotion={Boolean(reducedMotion)}
                />
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
    </section>
  )
}
