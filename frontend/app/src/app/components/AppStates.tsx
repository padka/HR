import type { ReactNode } from 'react'

type AppStateTone = 'neutral' | 'info' | 'warning' | 'danger' | 'success'

type AppStateCardProps = {
  eyebrow?: string
  title: string
  description?: ReactNode
  tone?: AppStateTone
  actions?: ReactNode
  children?: ReactNode
  className?: string
  cardClassName?: string
  fullPage?: boolean
  compact?: boolean
  role?: 'status' | 'alert'
}

type PageLoaderProps = {
  label?: string
  description?: string
  className?: string
  cardClassName?: string
  fullPage?: boolean
  compact?: boolean
}

type AppStateVariantProps = {
  title?: string
  description?: ReactNode
  actions?: ReactNode
  children?: ReactNode
  className?: string
  cardClassName?: string
  fullPage?: boolean
  compact?: boolean
  role?: 'status' | 'alert'
}

function joinClassNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(' ')
}

export function AppStateCard({
  eyebrow,
  title,
  description,
  tone = 'neutral',
  actions,
  children,
  className,
  cardClassName,
  fullPage = false,
  compact = false,
  role = 'status',
}: AppStateCardProps) {
  return (
    <div
      className={joinClassNames(
        'app-state',
        fullPage && 'app-state--fullscreen',
        compact && 'app-state--compact',
        className,
      )}
    >
      <section
        className={joinClassNames(
        'app-state__card',
        'ui-surface',
        'ui-surface--raised',
        `app-state__card--${tone}`,
        cardClassName,
      )}
      role={role}
    >
        {eyebrow ? <div className="app-state__eyebrow">{eyebrow}</div> : null}
        <div className="app-state__content">
          <div className="app-state__title">{title}</div>
          {description ? <div className="app-state__description">{description}</div> : null}
        </div>
        {children ? <div className="app-state__body">{children}</div> : null}
        {actions ? <div className="app-state__actions">{actions}</div> : null}
      </section>
    </div>
  )
}

export function AuthCheckState({
  title = 'Подготавливаем cockpit',
  description = 'Проверяем сессию и открываем рабочую среду рекрутера.',
  className,
  cardClassName,
  fullPage = false,
  compact = false,
}: AppStateVariantProps) {
  return (
    <AppStateCard
      eyebrow="Проверка доступа"
      title={title}
      description={description}
      tone="info"
      className={className}
      cardClassName={cardClassName}
      fullPage={fullPage}
      compact={compact}
    >
      <div className="app-state__progress" aria-hidden="true">
        <span className="app-state__spinner" />
        <span className="app-state__progress-label">Подготавливаем рабочую среду</span>
      </div>
    </AppStateCard>
  )
}

export function AuthRequiredState({
  title = 'Нужно войти в cockpit',
  description = 'Сессия не активна. Авторизуйтесь, чтобы вернуться к очередям и действиям по кандидатам.',
  actions,
  className,
  cardClassName,
  fullPage = false,
  compact = false,
}: AppStateVariantProps) {
  return (
    <AppStateCard
      eyebrow="Доступ ограничен"
      title={title}
      description={description}
      tone="warning"
      actions={actions}
      className={className}
      cardClassName={cardClassName}
      fullPage={fullPage}
      compact={compact}
    />
  )
}

export function EmptyState({
  title = 'Пока ничего нет',
  description,
  actions,
  className,
  cardClassName,
  fullPage = false,
  compact = false,
}: AppStateVariantProps) {
  return (
    <AppStateCard
      eyebrow="Пустое состояние"
      title={title}
      description={description}
      tone="neutral"
      actions={actions}
      className={className}
      cardClassName={cardClassName}
      fullPage={fullPage}
      compact={compact}
    />
  )
}

export function ErrorState({
  title = 'Не удалось продолжить',
  description,
  actions,
  children,
  className,
  cardClassName,
  fullPage = false,
  compact = false,
  role = 'alert',
}: AppStateVariantProps) {
  return (
    <AppStateCard
      eyebrow="Ошибка"
      title={title}
      description={description}
      tone="danger"
      actions={actions}
      children={children}
      className={className}
      cardClassName={cardClassName}
      fullPage={fullPage}
      compact={compact}
      role={role}
    />
  )
}

export function InlineSuccessState({
  title = 'Готово',
  description,
  actions,
  className,
  cardClassName,
}: AppStateVariantProps) {
  return (
    <AppStateCard
      eyebrow="Успешно"
      title={title}
      description={description}
      tone="success"
      actions={actions}
      className={joinClassNames('app-state--inline-success', className)}
      cardClassName={cardClassName}
      compact
    />
  )
}

export function PageLoader({
  label = 'Загрузка…',
  description = 'Подготавливаем экран.',
  className,
  cardClassName,
  fullPage = false,
  compact = false,
}: PageLoaderProps) {
  return (
    <AuthCheckState
      title={label}
      description={description}
      className={joinClassNames('app-page-loader', className)}
      cardClassName={cardClassName}
      fullPage={fullPage}
      compact={compact}
    />
  )
}
