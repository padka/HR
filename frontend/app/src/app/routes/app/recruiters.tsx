import { Link } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type CSSProperties } from 'react'
import { apiFetch } from '@/api/client'
import { EmptyState, PageLoader } from '@/app/components/AppStates'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import { RoleGuard } from '@/app/components/RoleGuard'

type Recruiter = {
  id: number
  name: string
  tz?: string | null
  tg_chat_id?: string | null
  telemost_url?: string | null
  active?: boolean | null
  last_seen_at?: string | null
  is_online?: boolean | null
  city_ids?: number[]
  cities?: Array<{ name: string; tz?: string | null }>
  stats?: { total: number; free: number; pending: number; booked: number }
  next_free_local?: string | null
  next_is_future?: boolean
}

type RecruiterStats = NonNullable<Recruiter['stats']>
type BadgeTone = 'success' | 'warning' | 'danger' | 'info'

const DEFAULT_TZ = 'Europe/Moscow'
const EMPTY_STATS: RecruiterStats = { total: 0, free: 0, pending: 0, booked: 0 }
const pageStyle: CSSProperties = { display: 'grid', gap: 16 }
const eyebrowStyle: CSSProperties = {
  fontSize: 'var(--text-xs)',
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  color: 'var(--subtle)',
}
const summaryGridStyle: CSSProperties = {
  display: 'grid',
  gap: 12,
  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
}
const summaryCardStyle: CSSProperties = {
  display: 'grid',
  gap: 6,
  padding: '14px 16px',
  borderRadius: 18,
  border: '1px solid rgba(255, 255, 255, 0.08)',
  background: 'rgba(255, 255, 255, 0.04)',
  boxShadow: 'var(--shadow-sm)',
}
const groupHeadStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  gap: 12,
  flexWrap: 'wrap',
}
const groupCopyStyle: CSSProperties = { display: 'grid', gap: 4, minWidth: 0 }
const legendStyle: CSSProperties = { display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }
const rosterItemStyle: CSSProperties = { gap: 16, padding: 18 }
const rosterBodyStyle: CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 16,
  alignItems: 'stretch',
}
const rosterDetailsStyle: CSSProperties = { display: 'grid', gap: 14, minWidth: 0, flex: '1 1 420px' }
const rosterIdentityStyle: CSSProperties = { display: 'flex', gap: 14, alignItems: 'flex-start', minWidth: 0 }
const rosterIdentityCopyStyle: CSSProperties = { display: 'grid', gap: 10, minWidth: 0, flex: 1 }
const signalRowStyle: CSSProperties = { display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }
const cityBlockStyle: CSSProperties = { display: 'grid', gap: 8 }
const loadCardStyle: CSSProperties = {
  display: 'grid',
  gap: 10,
  padding: '14px 16px',
  borderRadius: 18,
  border: '1px solid rgba(255, 255, 255, 0.08)',
  background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.02)), rgba(12, 16, 26, 0.32)',
  flex: '1 1 260px',
}
const loadHeadStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'baseline',
  gap: 12,
}
const loadBarStyle: CSSProperties = {
  position: 'relative',
  height: 10,
  borderRadius: 999,
  overflow: 'hidden',
  background: 'rgba(255, 255, 255, 0.08)',
}
const loadMetaStyle: CSSProperties = { display: 'grid', gap: 8 }
const slotGridStyle: CSSProperties = { display: 'grid', gap: 10, gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }
const slotCellStyle: CSSProperties = { display: 'grid', gap: 4 }
const footerStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  gap: 12,
  flexWrap: 'wrap',
  paddingTop: 12,
  borderTop: '1px solid rgba(255, 255, 255, 0.08)',
}
const footerMetaStyle: CSSProperties = { display: 'grid', gap: 8, minWidth: 0, flex: '1 1 320px' }
const toggleStyle: CSSProperties = {
  width: 'fit-content',
  padding: '8px 12px',
  borderRadius: 999,
  border: '1px solid rgba(255, 255, 255, 0.08)',
  background: 'rgba(255, 255, 255, 0.04)',
}
const actionsStyle: CSSProperties = {
  display: 'flex',
  gap: 8,
  flexWrap: 'wrap',
  alignItems: 'center',
  justifyContent: 'flex-end',
}

function formatPlural(value: number, one: string, few: string, many: string) {
  const mod10 = value % 10
  const mod100 = value % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}

function getRecruiterStats(recruiter: Recruiter): RecruiterStats {
  return recruiter.stats || EMPTY_STATS
}

function getLoadPercent(stats: RecruiterStats) {
  return stats.total ? Math.round((stats.booked / stats.total) * 100) : 0
}

function getLoadState(stats: RecruiterStats): { tone: BadgeTone; label: string; detail: string } {
  const loadPercent = getLoadPercent(stats)
  const detail = `${stats.free} свободно · ${stats.pending} ожидают`
  if (stats.total === 0) {
    return { tone: 'warning', label: 'Без слотов', detail: 'Слоты ещё не заведены' }
  }
  if (loadPercent >= 80 || stats.free === 0) {
    return { tone: 'danger', label: 'Пиковая загрузка', detail }
  }
  if (loadPercent >= 45 || stats.pending > 0) {
    return { tone: 'warning', label: 'Нужно внимание', detail }
  }
  return { tone: 'success', label: 'Есть ресурс', detail }
}

function formatTimestamp(value?: string | null, timeZone?: string | null) {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: timeZone || DEFAULT_TZ,
    }).format(parsed)
  } catch {
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(parsed)
  }
}

function getPresenceState(recruiter: Recruiter): { tone: BadgeTone; label: string; detail: string } {
  if (!recruiter.active) {
    return {
      tone: 'warning',
      label: 'Отключён',
      detail: 'Не участвует в текущей нагрузке',
    }
  }
  if (recruiter.is_online) {
    return {
      tone: 'success',
      label: 'На линии',
      detail: 'Связь подтверждена',
    }
  }
  const lastSeen = formatTimestamp(recruiter.last_seen_at, recruiter.tz)
  return {
    tone: 'info',
    label: 'Вне сети',
    detail: lastSeen ? `Последняя активность ${lastSeen}` : 'Связь сейчас не подтверждена',
  }
}

function getNextSlotLabel(recruiter: Recruiter) {
  if (!recruiter.next_free_local) {
    return 'Свободных окон сейчас нет'
  }
  return recruiter.next_is_future
    ? `Следующее окно: ${recruiter.next_free_local}`
    : `Свободно сейчас: ${recruiter.next_free_local}`
}

function compareRecruiters(a: Recruiter, b: Recruiter) {
  const activeDiff = Number(Boolean(b.active)) - Number(Boolean(a.active))
  if (activeDiff) return activeDiff
  const onlineDiff = Number(Boolean(b.is_online)) - Number(Boolean(a.is_online))
  if (onlineDiff) return onlineDiff
  return a.name.localeCompare(b.name, 'ru')
}

function getLoadFillStyle(tone: BadgeTone, loadPercent: number): CSSProperties {
  const backgroundByTone = {
    success: 'linear-gradient(90deg, rgba(91, 225, 165, 0.92), rgba(44, 180, 137, 0.92))',
    warning: 'linear-gradient(90deg, rgba(246, 193, 107, 0.92), rgba(224, 148, 66, 0.92))',
    danger: 'linear-gradient(90deg, rgba(240, 115, 115, 0.94), rgba(214, 70, 70, 0.94))',
    info: 'linear-gradient(90deg, rgba(106, 165, 255, 0.92), rgba(70, 122, 214, 0.92))',
  } satisfies Record<BadgeTone, string>

  return {
    position: 'absolute',
    inset: '0 auto 0 0',
    width: `${Math.min(loadPercent, 100)}%`,
    borderRadius: 999,
    background: backgroundByTone[tone],
  }
}

export function RecruitersPage() {
  const queryClient = useQueryClient()
  const [rowError, setRowError] = useState<Record<number, string>>({})
  const { data, isLoading, isError, error, refetch } = useQuery<Recruiter[]>({
    queryKey: ['recruiters'],
    queryFn: () => apiFetch('/recruiters'),
  })

  const toggleMutation = useMutation({
    mutationFn: async (payload: { recruiter: Recruiter; active: boolean }) => {
      const { recruiter, active } = payload
      const body = {
        name: recruiter.name,
        tz: recruiter.tz || DEFAULT_TZ,
        tg_chat_id: recruiter.tg_chat_id ? Number(recruiter.tg_chat_id) : null,
        telemost_url: recruiter.telemost_url || null,
        active,
        city_ids: recruiter.city_ids || [],
      }
      return apiFetch(`/recruiters/${recruiter.id}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      })
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['recruiters'] })
      setRowError((prev) => {
        const next = { ...prev }
        delete next[variables.recruiter.id]
        return next
      })
    },
    onError: (err, variables) => {
      const message = err instanceof Error ? err.message : 'Ошибка обновления'
      setRowError((prev) => ({ ...prev, [variables.recruiter.id]: message }))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (recruiterId: number) =>
      apiFetch(`/recruiters/${recruiterId}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recruiters'] })
    },
    onError: (err, recruiterId) => {
      const message = err instanceof Error ? err.message : 'Ошибка удаления'
      setRowError((prev) => ({ ...prev, [recruiterId]: message }))
    },
  })

  const recruiters = [...(data || [])].sort(compareRecruiters)
  const activeRecruiters = recruiters.filter((recruiter) => recruiter.active)
  const inactiveRecruiters = recruiters.filter((recruiter) => !recruiter.active)
  const totals = recruiters.reduce(
    (acc, recruiter) => {
      const stats = getRecruiterStats(recruiter)
      acc.free += stats.free
      acc.pending += stats.pending
      acc.booked += stats.booked
      acc.total += stats.total
      return acc
    },
    { free: 0, pending: 0, booked: 0, total: 0 },
  )
  const overallLoadPercent = totals.total ? Math.round((totals.booked / totals.total) * 100) : 0
  const onlineCount = activeRecruiters.filter((recruiter) => recruiter.is_online).length
  const rosterSections = [
    {
      key: 'active',
      title: 'В работе',
      description: `${activeRecruiters.length} ${formatPlural(activeRecruiters.length, 'рекрутёр', 'рекрутёра', 'рекрутёров')} ${activeRecruiters.length === 1 ? 'участвует' : 'участвуют'} в текущей нагрузке`,
      recruiters: activeRecruiters,
      testId: 'recruiters-active-section',
    },
    {
      key: 'inactive',
      title: 'Отключённые',
      description: `${inactiveRecruiters.length} ${formatPlural(inactiveRecruiters.length, 'рекрутёр', 'рекрутёра', 'рекрутёров')} ${inactiveRecruiters.length === 1 ? 'сохранён' : 'сохранены'} для настройки, но не ${inactiveRecruiters.length === 1 ? 'участвует' : 'участвуют'} в расписании`,
      recruiters: inactiveRecruiters,
      testId: 'recruiters-inactive-section',
    },
  ].filter((section) => section.recruiters.length > 0)

  return (
    <RoleGuard allow={['admin']}>
      <div className="page" style={pageStyle}>
        <header className="glass glass--elevated page-header page-header--row">
          <div className="page-header__content">
            <div style={eyebrowStyle}>Операционный состав</div>
            <h1 className="title">Рекрутёры</h1>
            <p className="subtitle">
              Компактный состав по доступности, загрузке и закреплённым городам без перехода в карточку.
            </p>
          </div>
          <Link to="/app/recruiters/new" className="ui-btn ui-btn--primary" data-testid="recruiters-create-btn">
            + Добавить рекрутёра
          </Link>
        </header>

        {recruiters.length > 0 && (
          <section className="glass page-section" style={{ padding: 'var(--space-md)' }}>
            <div style={summaryGridStyle} data-testid="recruiters-summary">
              <article style={summaryCardStyle}>
                <span className="text-muted text-xs">В составе</span>
                <strong className="stat-value--lg">{activeRecruiters.length}</strong>
                <span className="text-muted text-sm">
                  {recruiters.length} {formatPlural(recruiters.length, 'сотрудник', 'сотрудника', 'сотрудников')} в составе
                </span>
              </article>
              <article style={summaryCardStyle}>
                <span className="text-muted text-xs">На линии</span>
                <strong className="stat-value--lg">{onlineCount}</strong>
                <span className="text-muted text-sm">с подтверждённой связью прямо сейчас</span>
              </article>
              <article style={summaryCardStyle}>
                <span className="text-muted text-xs">Свободные окна</span>
                <strong className="stat-value--lg">{totals.free}</strong>
                <span className="text-muted text-sm">{totals.pending} ожидают распределения</span>
              </article>
              <article style={summaryCardStyle}>
                <span className="text-muted text-xs">Общая загрузка</span>
                <strong className="stat-value--lg">{overallLoadPercent}%</strong>
                <span className="text-muted text-sm">
                  {totals.total ? `${totals.booked} занято из ${totals.total}` : 'Слоты ещё не заведены'}
                </span>
              </article>
            </div>
          </section>
        )}

        <section className="glass page-section">
          <div className="page-section__head">
            <div className="page-header__content">
              <h2 className="title title--sm">Доступность и нагрузка</h2>
              <p className="subtitle subtitle--sm">
                Активные рекрутёры вынесены вверх, отключённые сгруппированы отдельно. По каждой записи сразу видны города и ближайшее окно.
              </p>
            </div>
            {recruiters.length > 0 && (
              <div style={legendStyle} aria-label="Легенда статусов">
                <span className="status-badge status-badge--success">На линии</span>
                <span className="status-badge status-badge--info">Вне сети</span>
                <span className="status-badge status-badge--warning">Нужно внимание</span>
              </div>
            )}
          </div>

          {isLoading && (
            <PageLoader
              compact
              label="Загружаем состав"
              description="Подтягиваем доступность рекрутёров, слоты и закрепления по городам."
            />
          )}

          {isError && (
            <ApiErrorBanner
              error={error}
              title="Не удалось загрузить состав рекрутёров"
              retryLabel="Обновить список"
              onRetry={() => {
                void refetch()
              }}
            >
              <span className="text-muted text-sm">Без списка недоступны переключение статуса и быстрые переходы к настройке.</span>
            </ApiErrorBanner>
          )}

          {data && data.length === 0 && (
            <EmptyState
              compact
              title="Реестр рекрутёров пока пуст"
              description="Добавьте первого рекрутёра, чтобы назначать города, открывать слоты и управлять нагрузкой команды."
              actions={
                <Link to="/app/recruiters/new" className="ui-btn ui-btn--primary ui-btn--sm">
                  + Добавить рекрутёра
                </Link>
              }
              cardClassName="recruiters-page__state"
            />
          )}

          {recruiters.length > 0 && (
            <div style={{ display: 'grid', gap: 'var(--space-lg)' }}>
              {rosterSections.map((section) => (
                <section key={section.key} style={{ display: 'grid', gap: 'var(--space-sm)' }} data-testid={section.testId}>
                  <div style={groupHeadStyle}>
                    <div style={groupCopyStyle}>
                      <h3 className="title title--sm">{section.title}</h3>
                      <p className="subtitle subtitle--sm">{section.description}</p>
                    </div>
                    <span className="chip">
                      {section.recruiters.length} {formatPlural(section.recruiters.length, 'запись', 'записи', 'записей')}
                    </span>
                  </div>

                  <div className="page-section__content recruiters-page__list">
                    {section.recruiters.map((recruiter) => {
                      const stats = getRecruiterStats(recruiter)
                      const loadPercent = getLoadPercent(stats)
                      const loadState = getLoadState(stats)
                      const presence = getPresenceState(recruiter)
                      const presenceClass = recruiter.active
                        ? (recruiter.is_online ? 'is-online' : 'is-away')
                        : 'is-inactive'
                      const assignedCities = recruiter.cities || []
                      const cityPreview = assignedCities.slice(0, 4)
                      return (
                        <article key={recruiter.id} className="glass glass--interactive list-item recruiter-card" style={rosterItemStyle} data-testid="recruiter-row">
                          <div style={rosterBodyStyle}>
                            <div style={rosterDetailsStyle}>
                              <div style={rosterIdentityStyle}>
                                <div className={`recruiter-avatar ${presenceClass}`} aria-hidden="true">
                                  {recruiter.name
                                    .split(' ')
                                    .filter(Boolean)
                                    .slice(0, 2)
                                    .map((part) => part[0]?.toUpperCase())
                                    .join('') || 'RS'}
                                </div>
                                <div style={rosterIdentityCopyStyle}>
                                  <div style={signalRowStyle}>
                                    <span className={`status-badge status-badge--${presence.tone}`}>{presence.label}</span>
                                    <span className={`status-badge status-badge--${recruiter.active ? 'info' : 'warning'}`}>
                                      {recruiter.active ? 'В составе' : 'Отключён'}
                                    </span>
                                    <span className="chip">ID #{recruiter.id}</span>
                                    <span className="chip">TZ: {recruiter.tz || DEFAULT_TZ}</span>
                                  </div>
                                  <h4 className="list-item__title">{recruiter.name}</h4>
                                  <p className="list-item__subtitle">
                                    {presence.detail}
                                    {' · '}
                                    {getNextSlotLabel(recruiter)}
                                  </p>
                                </div>
                              </div>

                              <div style={cityBlockStyle}>
                                <div className="list-item__meta-label">Закреплённые города</div>
                                <div className="list-item__chips">
                                  {cityPreview.length > 0 ? (
                                    <>
                                      {cityPreview.map((city) => (
                                        <span key={city.name} className="chip chip--accent">{city.name}</span>
                                      ))}
                                      {assignedCities.length > cityPreview.length && (
                                        <span className="chip">+{assignedCities.length - cityPreview.length}</span>
                                      )}
                                    </>
                                  ) : (
                                    <span className="text-muted text-sm">Города пока не назначены</span>
                                  )}
                                </div>
                              </div>
                            </div>

                            <aside style={loadCardStyle} aria-label={`Нагрузка ${recruiter.name}`}>
                              <div style={loadHeadStyle}>
                                <span className="text-muted text-xs">Занятость</span>
                                <strong className="title title--sm" style={{ fontVariantNumeric: 'tabular-nums' }}>{loadPercent}%</strong>
                              </div>
                              <div
                                style={loadBarStyle}
                                role="progressbar"
                                aria-valuemin={0}
                                aria-valuemax={100}
                                aria-valuenow={loadPercent}
                              >
                                <span style={getLoadFillStyle(loadState.tone, loadPercent)} />
                              </div>
                              <div style={loadMetaStyle}>
                                <span className={`chip chip--${loadState.tone}`}>{loadState.label}</span>
                                <span className="text-muted text-sm">{loadState.detail}</span>
                              </div>
                              <div style={slotGridStyle}>
                                <div style={slotCellStyle}>
                                  <span className="text-muted text-xs">Всего</span>
                                  <strong className="title title--sm" style={{ fontVariantNumeric: 'tabular-nums' }}>{stats.total}</strong>
                                </div>
                                <div style={slotCellStyle}>
                                  <span className="text-muted text-xs">Занято</span>
                                  <strong className="title title--sm" style={{ fontVariantNumeric: 'tabular-nums' }}>{stats.booked}</strong>
                                </div>
                              </div>
                            </aside>
                          </div>

                          <div style={footerStyle}>
                            <div style={footerMetaStyle}>
                              <label className="ui-inline-checkbox" style={toggleStyle}>
                                <input
                                  type="checkbox"
                                  checked={Boolean(recruiter.active)}
                                  onChange={(event) => toggleMutation.mutate({ recruiter, active: event.target.checked })}
                                  disabled={toggleMutation.isPending}
                                />
                                <span>{recruiter.active ? 'Оставить в составе' : 'Вернуть в состав'}</span>
                              </label>
                              {rowError[recruiter.id] && (
                                <span role="alert" className="text-danger text-sm">
                                  {rowError[recruiter.id]}
                                </span>
                              )}
                            </div>
                            <div style={actionsStyle}>
                              <Link
                                to="/app/recruiters/$recruiterId/edit"
                                params={{ recruiterId: String(recruiter.id) }}
                                className="ui-btn ui-btn--ghost ui-btn--sm"
                              >
                                Открыть карточку
                              </Link>
                              <button
                                className="ui-btn ui-btn--danger ui-btn--sm"
                                onClick={() =>
                                  window.confirm(`Удалить рекрутёра ${recruiter.name}?`) && deleteMutation.mutate(recruiter.id)
                                }
                                disabled={deleteMutation.isPending}
                              >
                                Удалить
                              </button>
                            </div>
                          </div>
                        </article>
                      )
                    })}
                  </div>
                </section>
              ))}
            </div>
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
