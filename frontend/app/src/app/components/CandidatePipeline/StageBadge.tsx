import type { PipelineStage } from './pipeline.types'
import { getStageBadgeLabel } from './pipeline.utils'

type StageBadgeProps = {
  stage: PipelineStage
}

export default function StageBadge({ stage }: StageBadgeProps) {
  const label = getStageBadgeLabel(stage)

  if (stage.status === 'upcoming') {
    return <span className="candidate-pipeline-badge candidate-pipeline-badge--ghost">Ожидает</span>
  }

  if (!label) return null

  return (
    <span
      className={`candidate-pipeline-badge ${
        stage.status === 'current'
          ? 'candidate-pipeline-badge--current'
          : 'candidate-pipeline-badge--completed'
      }`}
    >
      {label}
    </span>
  )
}
