import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import {
  STAGE_LABELS,
  TEMPLATE_META,
  templateDesc,
  templateStage,
  templateTitle,
  type TemplateStage,
} from './template_meta'

type MessageTemplate = {
  id: number
  key: string
  locale: string
  channel: string
  city_id?: number | null
  city_name?: string | null
  version?: number
  is_active?: boolean
  preview?: string | null
  body?: string | null
}

type MessageTemplatesPayload = {
  templates: MessageTemplate[]
  cities: Array<{ id: number | null; name: string }>
}

type TemplateIndexEntry = {
  global?: MessageTemplate
  city: Map<number, MessageTemplate>
}

const ALL_STAGES: TemplateStage[] = [
  'registration',
  'testing',
  'interview',
  'intro_day',
  'reminders',
  'results',
  'service',
]

const DEFAULT_LOCALE = 'ru'
const DEFAULT_CHANNEL = 'tg'

function pickLatest(current: MessageTemplate | undefined, candidate: MessageTemplate): MessageTemplate {
  if (!current) return candidate
  const currentVersion = current.version ?? 0
  const nextVersion = candidate.version ?? 0
  return nextVersion >= currentVersion ? candidate : current
}

export function TemplateListPage() {
  const { data, isLoading, isError, error } = useQuery<MessageTemplatesPayload>({
    queryKey: ['message-templates-summary'],
    queryFn: () => apiFetch('/message-templates'),
  })

  const [selectedCity, setSelectedCity] = useState<string>('global')
  const [collapsedStages, setCollapsedStages] = useState<Record<string, boolean>>({})

  const cityOptions = useMemo(() => {
    const cities = data?.cities || []
    return cities
      .filter((c) => c.id != null)
      .map((c) => ({ id: String(c.id), name: c.name }))
  }, [data?.cities])

  const filteredTemplates = useMemo(() => {
    const items = data?.templates || []
    return items.filter((tmpl) => tmpl.locale === DEFAULT_LOCALE && tmpl.channel === DEFAULT_CHANNEL)
  }, [data?.templates])

  const templateIndex = useMemo(() => {
    const index = new Map<string, TemplateIndexEntry>()
    filteredTemplates.forEach((tmpl) => {
      const entry = index.get(tmpl.key) || { city: new Map<number, MessageTemplate>() }
      if (tmpl.city_id == null) {
        entry.global = pickLatest(entry.global, tmpl)
      } else {
        const current = entry.city.get(tmpl.city_id)
        entry.city.set(tmpl.city_id, pickLatest(current, tmpl))
      }
      index.set(tmpl.key, entry)
    })
    return index
  }, [filteredTemplates])

  const allKeys = useMemo(() => {
    const keys = new Set<string>(Object.keys(TEMPLATE_META))
    filteredTemplates.forEach((tmpl) => keys.add(tmpl.key))
    return Array.from(keys)
  }, [filteredTemplates])

  const groupedKeys = useMemo(() => {
    const groups: Record<TemplateStage, string[]> = {
      registration: [],
      testing: [],
      interview: [],
      intro_day: [],
      reminders: [],
      results: [],
      service: [],
    }
    allKeys.forEach((key) => {
      const stage = templateStage(key)
      groups[stage].push(key)
    })
    ALL_STAGES.forEach((stage) => {
      groups[stage].sort((a, b) => templateTitle(a).localeCompare(templateTitle(b), 'ru'))
    })
    return groups
  }, [allKeys])

  const selectedCityId = selectedCity === 'global' ? null : Number(selectedCity)
  const selectedCityName = selectedCityId != null
    ? cityOptions.find((c) => Number(c.id) === selectedCityId)?.name || `Город #${selectedCityId}`
    : 'Глобальные настройки'

  const toggleStage = (stage: string) =>
    setCollapsedStages((prev) => ({ ...prev, [stage]: !prev[stage] }))

  const renderRow = (key: string) => {
    const entry = templateIndex.get(key)
    const globalTemplate = entry?.global
    const cityTemplate = selectedCityId != null ? entry?.city.get(selectedCityId) : undefined
    const effectiveTemplate = selectedCityId != null ? (cityTemplate ?? globalTemplate) : globalTemplate
    const isOverride = Boolean(cityTemplate)
    const isFallback = selectedCityId != null && !cityTemplate && Boolean(globalTemplate)
    const overrideCount = entry?.city.size ?? 0
    const isActive = effectiveTemplate?.is_active ?? false
    const title = templateTitle(key)
    const desc = templateDesc(key)

    const statusChip = effectiveTemplate
      ? (isActive ? ['Активен', 'chip chip--success'] : ['Отключён', 'chip chip--danger'])
      : ['Нет шаблона', 'chip chip--warning']

    const scopeChip = selectedCityId != null
      ? (isOverride
        ? ['Переопределён', 'chip chip--accent']
        : (globalTemplate ? ['Глобальный', 'chip'] : ['Нет', 'chip chip--warning']))
      : (globalTemplate ? ['Глобальный', 'chip'] : ['Нет', 'chip chip--warning'])

    let actionLabel = 'Создать'
    let actionTo: { to: string; params?: Record<string, string>; search?: Record<string, string | number> }

    if (selectedCityId != null) {
      if (cityTemplate) {
        actionLabel = 'Редактировать'
        actionTo = { to: '/app/templates/$templateId/edit', params: { templateId: String(cityTemplate.id) } }
      } else {
        actionLabel = globalTemplate ? `Переопределить для ${selectedCityName}` : `Создать для ${selectedCityName}`
        actionTo = { to: '/app/templates/new', search: { city_id: selectedCityId, key } }
      }
    } else {
      if (globalTemplate) {
        actionLabel = 'Редактировать'
        actionTo = { to: '/app/templates/$templateId/edit', params: { templateId: String(globalTemplate.id) } }
      } else {
        actionLabel = 'Создать'
        actionTo = { to: '/app/templates/new', search: { key } }
      }
    }

    const rowStyle = {
      display: 'grid',
      gridTemplateColumns: 'minmax(240px, 2fr) minmax(180px, 1fr) minmax(160px, 0.6fr)',
      gap: 12,
      alignItems: 'center',
      padding: '10px 12px',
      borderBottom: '1px solid rgba(255,255,255,0.06)',
      background: isOverride ? 'rgba(106, 165, 255, 0.08)' : 'transparent',
      opacity: isFallback ? 0.6 : 1,
    }

    return (
      <div key={key} style={rowStyle}>
        <div>
          <div style={{ fontWeight: 600 }}>{title}</div>
          {desc && <div className="text-muted" style={{ fontSize: 12 }}>{desc}</div>}
          <div className="text-muted" style={{ fontSize: 11 }}><code>{key}</code></div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          <span className={statusChip[1]}>{statusChip[0]}</span>
          <span className={scopeChip[1]}>{scopeChip[0]}</span>
          {selectedCityId == null && overrideCount > 0 && (
            <span className="chip chip--accent">+{overrideCount} город(а)</span>
          )}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Link
            to={actionTo.to}
            params={actionTo.params}
            search={actionTo.search}
            className={`ui-btn ui-btn--sm ${actionLabel.startsWith('Редактировать') ? 'ui-btn--ghost' : 'ui-btn--primary'}`}
          >
            {actionLabel}
          </Link>
        </div>
      </div>
    )
  }

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <header className="glass glass--elevated page-header page-header--row">
          <div>
            <h1 className="title">Шаблоны сообщений</h1>
            <p className="subtitle">Единая консоль управления текстами по городам и этапам.</p>
          </div>
          <div className="toolbar" style={{ gap: 8 }}>
            <select value={selectedCity} onChange={(e) => setSelectedCity(e.target.value)}>
              <option value="global">Глобальные настройки</option>
              {cityOptions.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <Link to="/app/templates/new" className="ui-btn ui-btn--primary">+ Новый шаблон</Link>
          </div>
        </header>

        <section className="glass page-section">
          {isLoading && <p className="subtitle">Загрузка…</p>}
          {isError && <p className="text-danger">Ошибка: {(error as Error).message}</p>}

          {!isLoading && !isError && (
            <div className="page-section__content" style={{ display: 'grid', gap: 16 }}>
              {ALL_STAGES.map((stage) => {
                const keys = groupedKeys[stage] || []
                if (!keys.length) return null
                const label = STAGE_LABELS[stage]
                const collapsed = collapsedStages[stage]
                return (
                  <div key={stage}>
                    <div
                      style={{ cursor: 'pointer', userSelect: 'none', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                      onClick={() => toggleStage(stage)}
                    >
                      <div>
                        <h3 className="section-title" style={{ margin: 0 }}>
                          {collapsed ? '▸' : '▾'} {label.title}
                          <span className="text-muted" style={{ fontWeight: 400, fontSize: 13, marginLeft: 8 }}>
                            ({keys.length})
                          </span>
                        </h3>
                        <p className="text-muted" style={{ margin: '2px 0 0 0' }}>{label.desc}</p>
                      </div>
                    </div>

                    {!collapsed && (
                      <div style={{ marginTop: 10 }}>
                        <div
                          style={{
                            display: 'grid',
                            gridTemplateColumns: 'minmax(240px, 2fr) minmax(180px, 1fr) minmax(160px, 0.6fr)',
                            gap: 12,
                            padding: '6px 12px',
                            fontSize: 11,
                            textTransform: 'uppercase',
                            letterSpacing: '0.04em',
                            color: 'var(--muted)',
                            borderBottom: '1px solid rgba(255,255,255,0.08)',
                          }}
                        >
                          <span>Шаблон</span>
                          <span>Статус</span>
                          <span style={{ textAlign: 'right' }}>Действия</span>
                        </div>
                        {keys.map((key) => renderRow(key))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
