export type TimelineTone = 'status' | 'test' | 'system'

export type TimelineEvent = {
  id: string
  timestamp: string
  title: string
  meta?: string
  tone: TimelineTone
}
