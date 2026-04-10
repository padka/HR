import type { ReactNode } from 'react'

import './recruiter-state.css'

export type RecruiterRiskLevel = 'info' | 'warning' | 'blocker' | 'repair'
export type RecruiterKanbanColumnMode = 'interactive' | 'guided' | 'system'

type RecruiterActionBlockProps = {
  label?: string | null
  explanation?: string | null
  tone?: 'muted' | 'info' | 'warning' | 'danger' | 'success'
  enabled?: boolean
  eyebrow?: string | null
  badgeLabel?: string | null
  compact?: boolean
  action?: ReactNode
  className?: string
}

type RecruiterStateContextProps = {
  bucketLabel?: string | null
  contextLine?: string | null
  schedulingLine?: string | null
  compact?: boolean
  className?: string
}

type RecruiterRiskBannerProps = {
  level?: RecruiterRiskLevel | null
  title?: string | null
  message?: string | null
  recoveryHint?: string | null
  count?: number
  compact?: boolean
  className?: string
}

type RecruiterLifecycleStripProps = {
  stageLabel?: string | null
  recordState?: 'active' | 'closed' | null
  finalOutcomeLabel?: string | null
  compact?: boolean
  className?: string
}

type RecruiterKanbanColumnHeaderProps = {
  icon?: string | null
  label: string
  count?: number
  droppable?: boolean
  mode?: RecruiterKanbanColumnMode
  helperText?: string | null
  className?: string
}

type CandidateIdentityBlockProps = {
  title: ReactNode
  subtitle?: ReactNode
  meta?: ReactNode
  aside?: ReactNode
  compact?: boolean
  className?: string
}

function joinClassNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(' ')
}

function toneClass(value?: string | null) {
  if (value === 'danger' || value === 'warning' || value === 'success' || value === 'info') {
    return value
  }
  return 'muted'
}

function riskIcon(level?: RecruiterRiskLevel | null) {
  switch (level) {
    case 'repair':
      return '🛠'
    case 'blocker':
      return '⛔'
    case 'warning':
      return '⚠️'
    case 'info':
      return 'ℹ️'
    default:
      return 'ℹ️'
  }
}

function kanbanModeLabel(droppable?: boolean) {
  return droppable ? 'Можно перемещать' : 'Системная колонка'
}

function kanbanModeClass(mode: RecruiterKanbanColumnMode) {
  return `recruiter-kanban-header--${mode}`
}

function kanbanModeCopy(mode: RecruiterKanbanColumnMode, droppable?: boolean) {
  if (mode === 'guided') return 'Вести через действие'
  if (mode === 'system') return kanbanModeLabel(false)
  return kanbanModeLabel(droppable)
}

export function CandidateIdentityBlock({
  title,
  subtitle,
  meta,
  aside,
  compact = false,
  className,
}: CandidateIdentityBlockProps) {
  return (
    <div
      className={joinClassNames(
        'candidate-identity-block',
        compact && 'candidate-identity-block--compact',
        className,
      )}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 'var(--space-2)',
        minWidth: 0,
      }}
    >
      <div
        className="candidate-identity-block__main"
        style={{
          minWidth: 0,
          display: 'grid',
          gap: compact ? '2px' : '4px',
        }}
      >
        <div className="candidate-identity-block__title" style={{ color: 'var(--text-primary)', fontWeight: 'var(--font-semibold)' }}>{title}</div>
        {subtitle ? <div className="candidate-identity-block__subtitle" style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-xs)' }}>{subtitle}</div> : null}
        {meta ? <div className="candidate-identity-block__meta" style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-xs)' }}>{meta}</div> : null}
      </div>
      {aside ? <div className="candidate-identity-block__aside" style={{ flexShrink: 0 }}>{aside}</div> : null}
    </div>
  )
}

export function RecruiterActionBlock({
  label,
  explanation,
  tone = 'info',
  enabled = true,
  eyebrow = 'Следующий шаг',
  badgeLabel,
  compact = false,
  action,
  className,
}: RecruiterActionBlockProps) {
  if (!label) return null

  return (
    <section
      className={joinClassNames(
        'recruiter-action-block',
        `recruiter-action-block--${toneClass(tone)}`,
        compact && 'recruiter-action-block--compact',
        !enabled && 'recruiter-action-block--disabled',
        className,
      )}
      data-testid="recruiter-action-block"
    >
      <div className="recruiter-action-block__header">
        <span className="recruiter-action-block__eyebrow">{enabled ? eyebrow : `${eyebrow} недоступен`}</span>
        {badgeLabel ? (
          <span className={`recruiter-action-block__badge recruiter-action-block__badge--${toneClass(tone)}`}>
            {badgeLabel}
          </span>
        ) : null}
      </div>
      <div className="recruiter-action-block__body">
        <div className="recruiter-action-block__text">
          <strong className="recruiter-action-block__label">{label}</strong>
          {explanation ? (
            <p className="recruiter-action-block__explanation" data-testid="candidate-next-action-explanation">
              {explanation}
            </p>
          ) : null}
        </div>
        {action ? <div className="recruiter-action-block__cta">{action}</div> : null}
      </div>
    </section>
  )
}

export function RecruiterStateContext({
  bucketLabel,
  contextLine,
  schedulingLine,
  compact = false,
  className,
}: RecruiterStateContextProps) {
  if (!bucketLabel && !contextLine && !schedulingLine) return null

  return (
    <div
      className={joinClassNames(
        'recruiter-state-context',
        compact && 'recruiter-state-context--compact',
        className,
      )}
      data-testid="recruiter-state-context"
    >
      <div className="recruiter-state-context__row">
        {bucketLabel ? <span className="recruiter-state-context__bucket">{bucketLabel}</span> : null}
        {contextLine ? <span className="recruiter-state-context__line">{contextLine}</span> : null}
      </div>
      {schedulingLine ? <div className="recruiter-state-context__scheduling">{schedulingLine}</div> : null}
    </div>
  )
}

export function RecruiterRiskBanner({
  level,
  title,
  message,
  recoveryHint,
  count = 0,
  compact = false,
  className,
}: RecruiterRiskBannerProps) {
  if (!level || (!title && !message)) return null

  return (
    <div
      className={joinClassNames(
        'recruiter-risk-banner',
        `recruiter-risk-banner--${level}`,
        compact && 'recruiter-risk-banner--compact',
        className,
      )}
      data-testid="recruiter-risk-banner"
    >
      <div className="recruiter-risk-banner__icon" aria-hidden="true">
        {riskIcon(level)}
      </div>
      <div className="recruiter-risk-banner__content">
        {title ? (
          <div className="recruiter-risk-banner__title">
            <span>{title}</span>
            {count > 1 ? <span className="recruiter-risk-banner__count">{count}</span> : null}
          </div>
        ) : null}
        {message ? <div className="recruiter-risk-banner__message">{message}</div> : null}
        {recoveryHint ? <div className="recruiter-risk-banner__hint">{recoveryHint}</div> : null}
      </div>
    </div>
  )
}

export function RecruiterLifecycleStrip({
  stageLabel,
  recordState,
  finalOutcomeLabel,
  compact = false,
  className,
}: RecruiterLifecycleStripProps) {
  if (!stageLabel && !finalOutcomeLabel) return null

  return (
    <div
      className={joinClassNames(
        'recruiter-lifecycle-strip',
        compact && 'recruiter-lifecycle-strip--compact',
        className,
      )}
      data-testid="recruiter-lifecycle-strip"
    >
      <span className="recruiter-lifecycle-strip__label">Этап</span>
      {stageLabel ? <span className="recruiter-lifecycle-strip__stage">{stageLabel}</span> : null}
      {recordState === 'closed' && finalOutcomeLabel ? (
        <span className="recruiter-lifecycle-strip__outcome">{finalOutcomeLabel}</span>
      ) : null}
    </div>
  )
}

export function RecruiterKanbanColumnHeader({
  icon,
  label,
  count = 0,
  droppable = false,
  mode = droppable ? 'interactive' : 'system',
  helperText,
  className,
}: RecruiterKanbanColumnHeaderProps) {
  return (
    <div
      className={joinClassNames(
        'recruiter-kanban-header',
        kanbanModeClass(mode),
        droppable ? 'recruiter-kanban-header--interactive' : 'recruiter-kanban-header--locked',
        className,
      )}
    >
      <div className="recruiter-kanban-header__main">
        <div className="recruiter-kanban-header__title-row">
          <span className="recruiter-kanban-header__title">
            {icon ? `${icon} ` : ''}
            {label}
          </span>
          <span className="recruiter-kanban-header__count">{count}</span>
        </div>
        <div className="recruiter-kanban-header__meta">
          <span className="recruiter-kanban-header__mode">{kanbanModeCopy(mode, droppable)}</span>
          {helperText ? <span className="recruiter-kanban-header__helper">{helperText}</span> : null}
        </div>
      </div>
    </div>
  )
}

export const PrimaryActionBlock = RecruiterActionBlock
export const OneLineStateContext = RecruiterStateContext
export const RiskOrBlockBanner = RecruiterRiskBanner
export const LifecycleStrip = RecruiterLifecycleStrip
export const LockedOrGuidedColumnHeader = RecruiterKanbanColumnHeader
