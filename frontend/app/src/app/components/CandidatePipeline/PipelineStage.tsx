import { motion } from 'framer-motion'
import clsx from 'clsx'

import StageIndicator from './StageIndicator'
import { pipelineCardVariants } from './pipeline.variants'
import type { PipelineStage as PipelineStageRecord } from './pipeline.types'
import { translateSystemMessage } from './pipeline.utils'

type PipelineStageProps = {
  stage: PipelineStageRecord
  index: number
  total: number
  reducedMotion: boolean
}

export default function PipelineStage({
  stage,
  index,
  total,
  reducedMotion,
}: PipelineStageProps) {
  const subtitle = translateSystemMessage(stage.subtitle || stage.helper)
  const statusLabel =
    stage.status === 'completed' ? 'завершён' : stage.status === 'current' ? 'текущий' : ''
  const ariaLabel = `${index + 1} из ${total}. ${stage.title}${statusLabel ? `, ${statusLabel}` : ''}`

  return (
    <motion.div
      layout
      custom={index}
      variants={reducedMotion ? undefined : pipelineCardVariants}
      initial={reducedMotion ? false : 'hidden'}
      animate={reducedMotion ? undefined : 'visible'}
      className={clsx(
        'candidate-pipeline-stage',
        `candidate-pipeline-stage--${stage.status}`,
      )}
      aria-label={ariaLabel}
    >
      <div className="candidate-pipeline-stage__indicator-row">
        <StageIndicator status={stage.status} reducedMotion={reducedMotion} />
      </div>
      <div className="candidate-pipeline-stage__label">{stage.title}</div>
      {subtitle && <div className="candidate-pipeline-stage__hint">{subtitle}</div>}
    </motion.div>
  )
}
