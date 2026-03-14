import { motion } from 'framer-motion'

import { pipelineRailVariants } from './pipeline.variants'

type PipelineConnectorProps = {
  fill: number
  currentEdge: boolean
  vertical?: boolean
  reducedMotion: boolean
}

export default function PipelineConnector({
  fill,
  currentEdge,
  vertical = false,
  reducedMotion,
}: PipelineConnectorProps) {
  const axis = vertical ? 'y' : 'x'
  const fillStyle = vertical ? { scaleY: fill, scaleX: 1 } : { scaleX: fill, scaleY: 1 }

  return (
    <div
      className={`candidate-pipeline-connector ${vertical ? 'candidate-pipeline-connector--vertical' : ''}`}
      aria-hidden="true"
    >
      <span className="candidate-pipeline-connector__rail" />
      <motion.span
        className="candidate-pipeline-connector__fill"
        initial={reducedMotion ? fillStyle : 'hidden'}
        animate={reducedMotion ? fillStyle : { ...pipelineRailVariants.visible(axis), ...fillStyle }}
        style={{ originX: 0, originY: 0 }}
      />
      {currentEdge ? <span className="candidate-pipeline-connector__edge" /> : null}
    </div>
  )
}
