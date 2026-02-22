import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
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
}

type MessageTemplatesPayload = {
  templates: MessageTemplate[]
  cities: Array<{ id: number | null; name: string }>
}

type TemplateIndexEntry = {
  global?: MessageTemplate
  city: Map<number, MessageTemplate>
}

const DEFAULT_LOCALE = 'ru'
const DEFAULT_CHANNEL = 'tg'

const STAGES: TemplateStage[] = [
  'registration',
  'testing',
  'interview',
  'intro_day',
  'reminders',
  'results',
  'service',
]

function pickLatest(current: MessageTemplate | undefined, candidate: MessageTemplate): MessageTemplate {
  if (!current) return candidate
  const currentVersion = current.version ?? 0
  const nextVersion = candidate.version ?? 0
  return nextVersion >= currentVersion ? candidate : current
}

export function TemplateListPage() {
  const navigate = useNavigate()
  const { data, isLoading, isError, error } = useQuery<MessageTemplatesPayload>({
    queryKey: ['message-templates-summary'],
    queryFn: () => apiFetch('/message-templates'),
  })

  const [selectedCity, setSelectedCity] = useState<string>('global')
  const [search, setSearch] = useState('')
  const [stageFilter, setStageFilter] = useState<string>('all')

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

  const keys = useMemo(() => {
    const set = new Set<string>(Object.keys(TEMPLATE_META))
    filteredTemplates.forEach((tmpl) => set.add(tmpl.key))
    return Array.from(set)
  }, [filteredTemplates])

  const selectedCityId = selectedCity === 'global' ? null : Number(selectedCity)

  const rows = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()

    return keys
      .map((key) => {
        const entry = templateIndex.get(key)
        const globalTemplate = entry?.global
        const cityTemplate = selectedCityId != null ? entry?.city.get(selectedCityId) : undefined
        const effectiveTemplate = selectedCityId != null ? cityTemplate ?? globalTemplate : globalTemplate
        const stage = templateStage(key)
        const title = templateTitle(key)
        const desc = templateDesc(key)
        const overrideCount = entry?.city.size ?? 0
        const status = effectiveTemplate ? (effectiveTemplate.is_active ? 'active' : 'draft') : 'missing'
        const source = selectedCityId == null ? 'global' : cityTemplate ? 'city' : globalTemplate ? 'fallback' : 'missing'

        return {
          key,
          id: effectiveTemplate?.id ?? null,
          stage,
          title,
          desc,
          status,
          source,
          overrideCount,
        }
      })
      .filter((row) => (stageFilter === 'all' ? true : row.stage === stageFilter))
      .filter((row) => {
        if (!normalizedSearch) return true
        return [row.title, row.desc, row.key].join(' ').toLowerCase().includes(normalizedSearch)
      })
      .sort((a, b) => {
        const stageCmp = STAGES.indexOf(a.stage) - STAGES.indexOf(b.stage)
        if (stageCmp !== 0) return stageCmp
        return a.title.localeCompare(b.title, 'ru')
      })
  }, [keys, templateIndex, selectedCityId, stageFilter, search])

  const openEditor = (row: (typeof rows)[number]) => {
    if (selectedCityId != null && row.source !== 'city') {
      navigate({ to: '/app/templates/new', search: { city_id: selectedCityId, key: row.key } })
      return
    }
    if (row.id) {
      navigate({ to: '/app/templates/$templateId/edit', params: { templateId: String(row.id) } })
      return
    }
    navigate({ to: '/app/templates/new', search: { key: row.key } })
  }

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <section className="glass panel" style={{ display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <h1 className="title">Шаблоны</h1>
              <p className="subtitle">Простой режим редактирования шаблонов по этапам и городам.</p>
            </div>
            <Link to="/app/templates/new" className="ui-btn ui-btn--primary">+ Новый шаблон</Link>
          </div>

          <div className="action-row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <input
              placeholder="Поиск по названию, ключу, описанию"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ minWidth: 260 }}
            />
            <select value={selectedCity} onChange={(e) => setSelectedCity(e.target.value)}>
              <option value="global">Глобальные настройки</option>
              {cityOptions.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <select value={stageFilter} onChange={(e) => setStageFilter(e.target.value)}>
              <option value="all">Все этапы</option>
              {STAGES.map((stage) => (
                <option key={stage} value={stage}>{STAGE_LABELS[stage].title}</option>
              ))}
            </select>
          </div>

          {isLoading && <p className="subtitle">Загрузка…</p>}
          {isError && <p className="text-danger">Ошибка: {(error as Error).message}</p>}

          {!isLoading && !isError && (
            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Этап</th>
                    <th>Шаблон</th>
                    <th>Источник</th>
                    <th>Статус</th>
                    <th>Действие</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={5} className="text-muted">Шаблоны не найдены.</td>
                    </tr>
                  )}
                  {rows.map((row) => {
                    const actionLabel = row.id && (selectedCityId == null || row.source === 'city')
                      ? 'Редактировать'
                      : selectedCityId != null
                        ? 'Создать для города'
                        : 'Создать'

                    return (
                      <tr key={row.key}>
                        <td>{STAGE_LABELS[row.stage].title}</td>
                        <td>
                          <div style={{ fontWeight: 600 }}>{row.title}</div>
                          <div className="text-muted" style={{ fontSize: 12 }}>{row.desc || row.key}</div>
                          <div className="text-muted" style={{ fontSize: 11 }}><code>{row.key}</code></div>
                        </td>
                        <td>
                          {row.source === 'city' && <span className="chip chip--accent">Город</span>}
                          {row.source === 'global' && <span className="chip">Глобальный</span>}
                          {row.source === 'fallback' && <span className="chip">Глобальный fallback</span>}
                          {row.source === 'missing' && <span className="chip chip--warning">Нет шаблона</span>}
                          {selectedCityId == null && row.overrideCount > 0 && (
                            <div className="text-muted" style={{ marginTop: 4, fontSize: 11 }}>Переопределений: {row.overrideCount}</div>
                          )}
                        </td>
                        <td>
                          {row.status === 'active' && <span className="chip chip--success">Активен</span>}
                          {row.status === 'draft' && <span className="chip chip--danger">Отключён</span>}
                          {row.status === 'missing' && <span className="chip chip--warning">Нет</span>}
                        </td>
                        <td>
                          <button
                            type="button"
                            className={`ui-btn ui-btn--sm ${actionLabel === 'Редактировать' ? 'ui-btn--ghost' : 'ui-btn--primary'}`}
                            onClick={() => openEditor(row)}
                          >
                            {actionLabel}
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
