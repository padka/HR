import { motion } from 'framer-motion'
import clsx from 'clsx'

import StageBadge from './StageBadge'
import StageIndicator from './StageIndicator'
import { pipelineCardVariants, pipelineMotion } from './pipeline.variants'
import type { PipelineStage as PipelineStageRecord } from './pipeline.types'
import { getStageAriaLabel, translateSystemMessage } from './pipeline.utils'

type PipelineStageProps = {
  stage: PipelineStageRecord
  index: number
  total: number
  isOpen: boolean
  reducedMotion: boolean
  controlsId: string
  onToggle: () => void
}

export default function PipelineStage({
  stage,
  index,
  total,
  isOpen,
  reducedMotion,
  controlsId,
  onToggle,
}: PipelineStageProps) {
  const subtitle = translateSystemMessage(stage.subtitle || stage.helper) || 'Без деталей'

  return (
    <motion.button
      type="button"
      layout
      custom={index}
      variants={reducedMotion ? undefined : pipelineCardVariants}
      initial={reducedMotion ? false : 'hidden'}
      animate={reducedMotion ? undefined : 'visible'}
      whileHover={reducedMotion ? undefined : { y: -2, transition: { duration: pipelineMotion.hoverDuration } }}
      whileTap={reducedMotion ? undefined : { scale: 0.995 }}
      className={clsx(
        'candidate-pipeline-stage',
        `candidate-pipeline-stage--${stage.status}`,
        isOpen && 'candidate-pipeline-stage--open',
      )}
      aria-controls={controlsId}
      aria-expanded={isOpen}
      aria-label={getStageAriaLabel(stage, index, total, isOpen)}
      onClick={onToggle}
    >
      <div className="candidate-pipeline-stage__header">
        <StageIndicator status={stage.status} reducedMotion={reducedMotion} />
        <StageBadge stage={stage} />
      </div>

      <div className="candidate-pipeline-stage__body">
        <div className="candidate-pipeline-stage__title">{stage.title}</div>
        <div className="candidate-pipeline-stage__subtitle">{subtitle}</div>
      </div>
    </motion.button>
  )
}
