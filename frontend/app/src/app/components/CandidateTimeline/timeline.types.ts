export type TimelineTone = 'accent' | 'success' | 'warning' | 'danger' | 'muted'

export type TimelineEvent = {
  id: string
  timestamp: string
  title: string
  description: string
  badge: string
  tone: TimelineTone
}
