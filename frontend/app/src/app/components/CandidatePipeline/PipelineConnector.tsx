import { motion } from 'framer-motion'

import { pipelineRailVariants } from './pipeline.variants'
import type { PipelineConnectorState } from './pipeline.utils'

type PipelineConnectorProps = {
  fill: number
  state: PipelineConnectorState
  vertical?: boolean
  reducedMotion: boolean
}

export default function PipelineConnector({
  fill,
  state,
  vertical = false,
  reducedMotion,
}: PipelineConnectorProps) {
  const axis = vertical ? 'y' : 'x'
  const fillStyle = vertical ? { scaleY: fill, scaleX: 1 } : { scaleX: fill, scaleY: 1 }

  return (
    <div
      className={`candidate-pipeline-connector candidate-pipeline-connector--${state} ${vertical ? 'candidate-pipeline-connector--vertical' : ''}`}
      aria-hidden="true"
    >
      <span className="candidate-pipeline-connector__rail" />
      <motion.span
        className="candidate-pipeline-connector__fill"
        initial={reducedMotion ? fillStyle : 'hidden'}
        animate={reducedMotion ? fillStyle : { ...pipelineRailVariants.visible(axis), ...fillStyle }}
        style={{ originX: 0, originY: 0 }}
      />
      {state === 'active' ? <span className="candidate-pipeline-connector__edge" /> : null}
    </div>
  )
}
