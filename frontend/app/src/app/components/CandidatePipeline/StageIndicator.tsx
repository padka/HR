import { motion } from 'framer-motion'
import { Check } from 'lucide-react'

import { pipelineMotion } from './pipeline.variants'
import type { PipelineStageStatus } from './pipeline.types'

type StageIndicatorProps = {
  status: PipelineStageStatus
  reducedMotion: boolean
}

export default function StageIndicator({ status, reducedMotion }: StageIndicatorProps) {
  if (status === 'completed') {
    return (
      <span className="candidate-pipeline-indicator candidate-pipeline-indicator--completed" aria-hidden="true">
        <Check size={11} strokeWidth={2.5} />
      </span>
    )
  }

  if (status === 'current') {
    return (
      <span className="candidate-pipeline-indicator candidate-pipeline-indicator--current" aria-hidden="true">
        <motion.span
          className="candidate-pipeline-indicator__pulse"
          animate={reducedMotion ? undefined : { scale: [1, 1.2, 1], opacity: [0.24, 0.55, 0.24] }}
          transition={reducedMotion ? undefined : {
            duration: pipelineMotion.pulseDuration,
            repeat: Number.POSITIVE_INFINITY,
            ease: 'easeInOut',
          }}
        />
        <span className="candidate-pipeline-indicator__core" />
      </span>
    )
  }

  return <span className="candidate-pipeline-indicator candidate-pipeline-indicator--upcoming" aria-hidden="true" />
}
