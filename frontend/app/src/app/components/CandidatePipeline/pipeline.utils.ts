import type { PipelineStage, PipelineStageStatus } from './pipeline.types'

const systemMessageTranslations: Record<string, string> = {
  'Initial backfill from current candidate status': 'Начальный статус при добавлении в воронку',
  'admin manual status update': 'Ручное обновление статуса',
  'manual status update': 'Ручное обновление статуса',
  backfill: 'Перенос данных',
  'status update': 'Обновление статуса',
  system: 'система',
  Passed: 'Пройден',
  Failed: 'Не пройден',
  Pending: 'Ожидание',
  Scheduled: 'Запланировано',
  Completed: 'Завершено',
  Cancelled: 'Отменено',
  Rejected: 'Отклонено',
  Approved: 'Одобрено',
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function translateSystemMessage(text?: string | null): string {
  const value = String(text || '').trim()
  if (!value) return ''
  if (systemMessageTranslations[value]) {
    return systemMessageTranslations[value]
  }

  let result = value
  for (const [source, target] of Object.entries(systemMessageTranslations)) {
    result = result.replace(new RegExp(escapeRegExp(source), 'gi'), target)
  }
  return result
}

export function translateSystemMessageList(values?: Array<string | null | undefined>): string[] {
  return (values || [])
    .map((value) => translateSystemMessage(value))
    .filter(Boolean)
}

export function getStageBadgeLabel(stage: PipelineStage): string | null {
  if (stage.status === 'completed') return translateSystemMessage(stage.badge) || 'Пройден'
  if (stage.status === 'current') return translateSystemMessage(stage.badge) || 'Текущий этап'
  return null
}

export function getStageAriaLabel(
  stage: PipelineStage,
  index: number,
  total: number,
  expanded: boolean,
): string {
  const statusLabel =
    stage.status === 'completed'
      ? 'этап завершён'
      : stage.status === 'current'
        ? 'текущий этап'
        : 'ожидает старта'
  const subtitleValue = translateSystemMessage(stage.subtitle)
  const subtitle = subtitleValue ? `. ${subtitleValue}` : ''
  const expandedLabel = expanded ? '. Детали раскрыты.' : '. Детали скрыты.'
  return `${index + 1} из ${total}. ${stage.title}, ${statusLabel}${subtitle}${expandedLabel}`
}

export function getConnectorFill(
  currentIndex: number,
  connectorIndex: number,
  currentStatus: PipelineStageStatus | undefined,
): number {
  if (connectorIndex < currentIndex) return 1
  if (connectorIndex === currentIndex && currentStatus === 'current') return 0.18
  return 0
}

export function getCurrentStageIndex(stages: PipelineStage[]): number {
  const currentIndex = stages.findIndex((stage) => stage.status === 'current')
  if (currentIndex >= 0) return currentIndex
  const completedIndex = stages.reduce((last, stage, index) => (
    stage.status === 'completed' ? index : last
  ), -1)
  return Math.max(0, completedIndex)
}
