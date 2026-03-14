export type PipelineStageStatus = 'completed' | 'current' | 'upcoming'

export type StageDetailEvent = {
  id: string
  title: string
  meta?: string
  lines?: string[]
  timestamp?: string | null
}

export type StageDetail = {
  description?: string
  meta?: string[]
  notice?: {
    title: string
    text: string
  } | null
  events?: StageDetailEvent[]
  emptyText?: string
}

export type PipelineStage = {
  id: string
  title: string
  subtitle?: string
  status: PipelineStageStatus
  badge?: string
  helper?: string
  detail?: StageDetail
}
