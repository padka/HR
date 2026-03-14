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
          className="candidate-pipeline-indicator__ring candidate-pipeline-indicator__ring--outer"
          animate={reducedMotion ? undefined : { scale: [1, 1.18, 1], opacity: [0.44, 0.82, 0.44] }}
          transition={reducedMotion ? undefined : {
            duration: pipelineMotion.pulseDuration,
            repeat: Number.POSITIVE_INFINITY,
            ease: 'easeInOut',
          }}
        />
        <motion.span
          className="candidate-pipeline-indicator__ring candidate-pipeline-indicator__ring--inner"
          animate={reducedMotion ? undefined : { opacity: [0.7, 1, 0.7] }}
          transition={reducedMotion ? undefined : {
            duration: pipelineMotion.glowDuration,
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
