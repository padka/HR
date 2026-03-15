import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useProfile } from '@/app/hooks/useProfile'

type FinalOutcome = 'attached' | 'not_attached' | 'not_counted' | null

type DetailizationItem = {
  id: number
  assigned_at: string | null
  conducted_at: string | null
  expert_name: string
  is_attached: boolean | null
  final_outcome: FinalOutcome
  final_outcome_label?: string | null
  final_outcome_reason?: string | null
  recruiter: { id: number; name: string } | null
  city: { id: number; name: string } | null
  candidate: { id: number; name: string }
}

type DetailizationAggregateRow = {
  id?: number | null
  name: string
  total: number
  outcomes: Record<string, number>
}

type DetailizationResponse = {
  ok: boolean
  items: DetailizationItem[]
  summary: {
    total: number
    outcomes: Record<string, number>
    by_recruiter: DetailizationAggregateRow[]
    by_city: DetailizationAggregateRow[]
  }
  range?: {
    date_from?: string | null
    date_to?: string | null
  }
}

type City = {
  id: number
  name: string
  tz?: string | null
  active?: boolean | null
  experts_items?: Array<{ id: number | null; name: string; is_active: boolean }>
}

type Recruiter = {
  id: number
  name: string
  active?: boolean | null
}

type CandidateSearchItem = {
  id: number
  fio?: string | null
  city?: string | null
}

type CandidateSearchResponse = {
  items: CandidateSearchItem[]
}

type DirtyPatch = Partial<Pick<DetailizationItem, 'expert_name' | 'final_outcome' | 'final_outcome_reason'>>

function fmtDateTime(value: string | null): string {
  if (!value) return '—'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return '—'
  return dt.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function isoDate(value: Date): string {
  return value.toISOString().slice(0, 10)
}

function outcomeLabel(value: FinalOutcome): string {
  if (value === 'attached') return 'Закреплен'
  if (value === 'not_attached') return 'Не закреплен'
  if (value === 'not_counted') return 'Не засчитан'
  return '—'
}

function outcomeTone(value: FinalOutcome): string {
  if (value === 'attached') return 'success'
  if (value === 'not_attached') return 'danger'
  if (value === 'not_counted') return 'warning'
  return 'muted'
}

function summaryValue(summary: DetailizationResponse['summary'] | undefined, key: string): number {
  return Number(summary?.outcomes?.[key] || 0)
}

export function DetailizationPage() {
  const profile = useProfile()
  const isAdmin = profile.data?.principal.type === 'admin'

  const today = useMemo(() => new Date(), [])
  const weekStart = useMemo(() => {
    const value = new Date(today)
    const day = value.getDay() || 7
    value.setDate(value.getDate() - day + 1)
    return isoDate(value)
  }, [today])
  const monthStart = useMemo(() => {
    const value = new Date(today.getFullYear(), today.getMonth(), 1)
    return isoDate(value)
  }, [today])

  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [candidateQuery, setCandidateQuery] = useState('')
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateSearchItem | null>(null)
  const [createRecruiterId, setCreateRecruiterId] = useState('')
  const [createCityId, setCreateCityId] = useState('')
  const [createAssignedAt, setCreateAssignedAt] = useState<string>(() => isoDate(new Date()))
  const [createConductedAt, setCreateConductedAt] = useState<string>('')
  const [createExpertName, setCreateExpertName] = useState('')
  const [createFinalOutcome, setCreateFinalOutcome] = useState<'unknown' | 'attached' | 'not_attached' | 'not_counted'>('unknown')
  const [createFinalOutcomeReason, setCreateFinalOutcomeReason] = useState('')
  const [createError, setCreateError] = useState('')
  const [dirty, setDirty] = useState<Record<number, DirtyPatch>>({})

  const queryString = useMemo(() => {
    const params = new URLSearchParams()
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    return params.toString()
  }, [dateFrom, dateTo])

  const query = useQuery({
    queryKey: ['detailization', queryString],
    queryFn: () => apiFetch<DetailizationResponse>(`/detailization${queryString ? `?${queryString}` : ''}`),
  })

  const citiesQuery = useQuery<City[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
  })

  const recruitersQuery = useQuery<Recruiter[]>({
    queryKey: ['recruiters'],
    queryFn: () => apiFetch('/recruiters'),
    enabled: Boolean(isAdmin),
  })

  const candidatesSearchQuery = useQuery<CandidateSearchResponse>({
    queryKey: ['detailization-candidates-search', candidateQuery],
    queryFn: () => apiFetch(`/candidates?search=${encodeURIComponent(candidateQuery)}&page=1&per_page=10&pipeline=intro_day`),
    enabled: Boolean(showCreate && !selectedCandidate && candidateQuery.trim().length >= 2),
    staleTime: 10_000,
  })

  const updateMutation = useMutation({
    mutationFn: async (payload: { id: number; patch: Record<string, unknown> }) =>
      apiFetch(`/detailization/${payload.id}`, { method: 'PATCH', body: JSON.stringify(payload.patch) }),
    onSuccess: async () => {
      setDirty({})
      await query.refetch()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => apiFetch(`/detailization/${id}`, { method: 'DELETE' }),
    onSuccess: async () => {
      await query.refetch()
    },
  })

  const createMutation = useMutation({
    mutationFn: async (payload: Record<string, unknown>) => apiFetch('/detailization', { method: 'POST', body: JSON.stringify(payload) }),
    onSuccess: async () => {
      setCreateError('')
      setShowCreate(false)
      setCandidateQuery('')
      setSelectedCandidate(null)
      setCreateRecruiterId('')
      setCreateCityId('')
      setCreateAssignedAt(isoDate(new Date()))
      setCreateConductedAt('')
      setCreateExpertName('')
      setCreateFinalOutcome('unknown')
      setCreateFinalOutcomeReason('')
      await query.refetch()
    },
    onError: (error) => {
      setCreateError(error instanceof Error ? error.message : 'Ошибка создания')
    },
  })

  const cityById = useMemo(() => {
    const map = new Map<number, City>()
    for (const city of citiesQuery.data || []) {
      map.set(city.id, city)
    }
    return map
  }, [citiesQuery.data])

  const selectedCity = createCityId ? cityById.get(Number(createCityId)) : null
  const createExpertOptions = (selectedCity?.experts_items || []).filter((item) => item.is_active !== false)
  const rows = query.data?.items || []

  const setRowPatch = (id: number, patch: DirtyPatch) => {
    setDirty((prev) => ({ ...prev, [id]: { ...(prev[id] || {}), ...patch } }))
  }

  const saveRow = async (id: number) => {
    const patch = dirty[id]
    if (!patch || Object.keys(patch).length === 0) return
    await updateMutation.mutateAsync({ id, patch })
  }

  const exportCsv = () => {
    const suffix = queryString ? `?${queryString}` : ''
    window.open(`/api/detailization/export.csv${suffix}`, '_blank', 'noopener')
  }

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div style={{ padding: 24, maxWidth: 1320, margin: '0 auto', display: 'grid', gap: 16 }}>
      <div className="glass" style={{ padding: 18, display: 'grid', gap: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <h1 style={{ margin: 0 }}>Детализация ознакомительных дней</h1>
            <p style={{ margin: '8px 0 0', color: 'var(--muted)' }}>
              База кандидатов, реально дошедших до ОД. Финальный исход теперь фиксируется отдельно: закреплен / не закреплен / не засчитан.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="ui-btn ui-btn--ghost" onClick={() => { setDateFrom(weekStart); setDateTo(isoDate(new Date())) }}>
              Текущая неделя
            </button>
            <button className="ui-btn ui-btn--ghost" onClick={() => { setDateFrom(monthStart); setDateTo(isoDate(new Date())) }}>
              Текущий месяц
            </button>
            <button className="ui-btn ui-btn--ghost" onClick={() => { setDateFrom(''); setDateTo('') }}>
              Сбросить период
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'end' }}>
          <label style={{ display: 'grid', gap: 4 }}>
            <span className="text-muted text-xs">Дата с</span>
            <input className="ui-input" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
          </label>
          <label style={{ display: 'grid', gap: 4 }}>
            <span className="text-muted text-xs">Дата по</span>
            <input className="ui-input" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
          </label>
          <button className="ui-btn ui-btn--secondary" onClick={() => query.refetch()} disabled={query.isFetching}>
            {query.isFetching ? 'Обновляем…' : 'Обновить'}
          </button>
          <button className="ui-btn ui-btn--ghost" onClick={exportCsv}>
            Экспорт CSV
          </button>
          <button className="ui-btn ui-btn--primary" onClick={() => setShowCreate((value) => !value)} disabled={createMutation.isPending}>
            + Добавить вручную
          </button>
        </div>
      </div>

      {query.isError && <ApiErrorBanner error={query.error} title="Не удалось загрузить детализацию" onRetry={() => query.refetch()} />}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
        {[
          { key: 'total', label: 'Всего', value: query.data?.summary.total || 0, tone: 'neutral' },
          { key: 'attached', label: 'Закреплены', value: summaryValue(query.data?.summary, 'attached'), tone: 'success' },
          { key: 'not_attached', label: 'Не закреплены', value: summaryValue(query.data?.summary, 'not_attached'), tone: 'danger' },
          { key: 'not_counted', label: 'Не засчитаны', value: summaryValue(query.data?.summary, 'not_counted'), tone: 'warning' },
        ].map((card) => (
          <div key={card.key} className={`glass slots-summary__card slots-summary__card--${card.tone}`}>
            <span className="slots-summary__label">{card.label}</span>
            <span className="slots-summary__value">{card.value}</span>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.6fr) minmax(280px, 0.9fr)', gap: 16, alignItems: 'start' }}>
        <div className="glass detailization-table" style={{ padding: 14, display: 'grid', gap: 12 }}>
          {showCreate && (
            <div className="glass" style={{ padding: 14, display: 'grid', gap: 12 }}>
              <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}>
                <div style={{ display: 'grid', gap: 6 }}>
                  <div className="text-muted text-xs">Кандидат (ФИО)</div>
                  <input
                    className="ui-input"
                    value={selectedCandidate?.fio || candidateQuery}
                    onChange={(event) => {
                      setSelectedCandidate(null)
                      setCandidateQuery(event.target.value)
                    }}
                    placeholder="Введите ФИО"
                  />
                  {!selectedCandidate && candidateQuery.trim().length >= 2 && (
                    <div className="glass" style={{ padding: 10, borderRadius: 12 }}>
                      {candidatesSearchQuery.isFetching && <div className="text-muted text-xs">Поиск…</div>}
                      {!candidatesSearchQuery.isFetching && (candidatesSearchQuery.data?.items || []).length === 0 && (
                        <div className="text-muted text-xs">Ничего не найдено</div>
                      )}
                      <div style={{ display: 'grid', gap: 6, marginTop: 6 }}>
                        {(candidatesSearchQuery.data?.items || []).map((candidate) => (
                          <button
                            key={candidate.id}
                            type="button"
                            className="ui-btn ui-btn--secondary"
                            style={{ justifyContent: 'space-between' }}
                            onClick={() => {
                              setSelectedCandidate(candidate)
                              setCandidateQuery(candidate.fio || '')
                            }}
                          >
                            <span>{candidate.fio || `ID ${candidate.id}`}</span>
                            <span className="text-muted text-xs">{candidate.city || '—'}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {selectedCandidate && (
                    <div className="text-muted text-xs">
                      Выбран: <strong>{selectedCandidate.fio || `ID ${selectedCandidate.id}`}</strong>
                      {selectedCandidate.city ? <> · {selectedCandidate.city}</> : null}
                    </div>
                  )}
                </div>

                <label style={{ display: 'grid', gap: 6 }}>
                  <span className="text-muted text-xs">Дата назначения</span>
                  <input className="ui-input" type="date" value={createAssignedAt} onChange={(event) => setCreateAssignedAt(event.target.value)} />
                </label>

                <label style={{ display: 'grid', gap: 6 }}>
                  <span className="text-muted text-xs">Дата проведения</span>
                  <input className="ui-input" type="date" value={createConductedAt} onChange={(event) => setCreateConductedAt(event.target.value)} />
                </label>
              </div>

              <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
                {isAdmin && (
                  <label style={{ display: 'grid', gap: 6 }}>
                    <span className="text-muted text-xs">Рекрутер</span>
                    <select className="ui-select" value={createRecruiterId} onChange={(event) => setCreateRecruiterId(event.target.value)}>
                      <option value="">—</option>
                      {(recruitersQuery.data || []).map((recruiter) => (
                        <option key={recruiter.id} value={String(recruiter.id)}>
                          {recruiter.name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}

                <label style={{ display: 'grid', gap: 6 }}>
                  <span className="text-muted text-xs">Город</span>
                  <select className="ui-select" value={createCityId} onChange={(event) => { setCreateCityId(event.target.value); setCreateExpertName('') }}>
                    <option value="">—</option>
                    {(citiesQuery.data || []).filter((city) => city.active !== false).map((city) => (
                      <option key={city.id} value={String(city.id)}>
                        {city.name}
                      </option>
                    ))}
                  </select>
                </label>

                <label style={{ display: 'grid', gap: 6 }}>
                  <span className="text-muted text-xs">Эксперт</span>
                  <select className="ui-select" value={createExpertName} onChange={(event) => setCreateExpertName(event.target.value)} disabled={!createCityId || createExpertOptions.length === 0}>
                    <option value="">—</option>
                    {createExpertOptions.map((expert) => (
                      <option key={expert.id ?? expert.name} value={expert.name}>
                        {expert.name}
                      </option>
                    ))}
                  </select>
                </label>

                <label style={{ display: 'grid', gap: 6 }}>
                  <span className="text-muted text-xs">Исход</span>
                  <select className="ui-select" value={createFinalOutcome} onChange={(event) => setCreateFinalOutcome(event.target.value as typeof createFinalOutcome)}>
                    <option value="unknown">—</option>
                    <option value="attached">Закреплен</option>
                    <option value="not_attached">Не закреплен</option>
                    <option value="not_counted">Не засчитан</option>
                  </select>
                </label>
              </div>

              <label style={{ display: 'grid', gap: 6 }}>
                <span className="text-muted text-xs">Причина / комментарий к исходу</span>
                <textarea
                  className="ui-input"
                  rows={3}
                  value={createFinalOutcomeReason}
                  onChange={(event) => setCreateFinalOutcomeReason(event.target.value)}
                  placeholder="Например: не подлежит оплате, перенос, отказ кандидата"
                />
              </label>

              {createError && <div className="text-danger text-sm">{createError}</div>}

              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                {selectedCandidate && (
                  <Link to="/app/candidates/$candidateId" params={{ candidateId: String(selectedCandidate.id) }} className="ui-btn ui-btn--secondary">
                    Открыть кандидата
                  </Link>
                )}
                <button className="ui-btn ui-btn--secondary" onClick={() => setShowCreate(false)} disabled={createMutation.isPending}>
                  Отмена
                </button>
                <button
                  className="ui-btn ui-btn--primary"
                  disabled={createMutation.isPending || !selectedCandidate || (isAdmin && !createRecruiterId)}
                  onClick={async () => {
                    setCreateError('')
                    if (!selectedCandidate) {
                      setCreateError('Выберите кандидата из списка')
                      return
                    }
                    if (isAdmin && !createRecruiterId) {
                      setCreateError('Выберите рекрутера')
                      return
                    }
                    const payload: Record<string, unknown> = {
                      candidate_id: selectedCandidate.id,
                      expert_name: createExpertName.trim() || null,
                      assigned_at: createAssignedAt.trim() || null,
                      conducted_at: createConductedAt.trim() || null,
                      final_outcome: createFinalOutcome === 'unknown' ? null : createFinalOutcome,
                      final_outcome_reason: createFinalOutcomeReason.trim() || null,
                    }
                    if (isAdmin && createRecruiterId) payload.recruiter_id = Number(createRecruiterId)
                    if (createCityId) payload.city_id = Number(createCityId)
                    await createMutation.mutateAsync(payload)
                  }}
                >
                  Создать
                </button>
              </div>
            </div>
          )}

          <div className={`detailization-grid ${isAdmin ? '' : 'detailization-grid--recruiter'}`} style={{ marginTop: 4 }}>
            <div className="detailization-grid__head" style={{ gridTemplateColumns: isAdmin ? '1.1fr 1fr 1.1fr 1fr 1fr 1.2fr 1.1fr 1.4fr auto' : '1.1fr 1.1fr 1fr 1fr 1.2fr 1.1fr 1.4fr auto' }}>
              <div>Назначен</div>
              {isAdmin && <div>Рекрутер</div>}
              <div>Проведён</div>
              <div>Город</div>
              <div>Эксперт</div>
              <div>Кандидат</div>
              <div>Исход</div>
              <div>Причина</div>
              <div />
            </div>

            {rows.map((row) => {
              const patch = dirty[row.id] || {}
              const currentOutcome = (patch.final_outcome ?? row.final_outcome ?? null) as FinalOutcome
              const currentReason = patch.final_outcome_reason ?? row.final_outcome_reason ?? ''
              const canSave = Object.keys(patch).length > 0 && !updateMutation.isPending
              const cityExperts = row.city?.id ? (cityById.get(row.city.id)?.experts_items || []).filter((item) => item.is_active !== false) : []
              const selectedExpert = patch.expert_name ?? row.expert_name ?? ''

              return (
                <div key={row.id} className="detailization-grid__row" style={{ gridTemplateColumns: isAdmin ? '1.1fr 1fr 1.1fr 1fr 1fr 1.2fr 1.1fr 1.4fr auto' : '1.1fr 1.1fr 1fr 1fr 1.2fr 1.1fr 1.4fr auto' }}>
                  <div className="text-sm">{fmtDateTime(row.assigned_at)}</div>
                  {isAdmin && <div className="text-sm">{row.recruiter?.name || '—'}</div>}
                  <div className="text-sm">{fmtDateTime(row.conducted_at)}</div>
                  <div className="text-sm">{row.city?.name || '—'}</div>
                  <div>
                    {cityExperts.length > 0 ? (
                      <select className="ui-select" value={selectedExpert} onChange={(event) => setRowPatch(row.id, { expert_name: event.target.value })}>
                        <option value="">—</option>
                        {cityExperts.map((expert) => (
                          <option key={expert.id ?? expert.name} value={expert.name}>
                            {expert.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        className="ui-input"
                        value={selectedExpert}
                        onChange={(event) => setRowPatch(row.id, { expert_name: event.target.value })}
                        placeholder="ФИО эксперта"
                      />
                    )}
                  </div>
                  <div className="text-sm">
                    <Link to="/app/candidates/$candidateId" params={{ candidateId: String(row.candidate.id) }} className="action-link">
                      {row.candidate.name}
                    </Link>
                  </div>
                  <div>
                    <select
                      className="ui-select"
                      value={currentOutcome || 'unknown'}
                      onChange={(event) => setRowPatch(row.id, { final_outcome: event.target.value === 'unknown' ? null : (event.target.value as FinalOutcome) })}
                      data-tone={outcomeTone(currentOutcome)}
                    >
                      <option value="unknown">—</option>
                      <option value="attached">Закреплен</option>
                      <option value="not_attached">Не закреплен</option>
                      <option value="not_counted">Не засчитан</option>
                    </select>
                    <div className="text-muted text-xs" style={{ marginTop: 4 }}>{row.final_outcome_label || outcomeLabel(currentOutcome)}</div>
                  </div>
                  <div>
                    <textarea
                      className="ui-input"
                      rows={2}
                      value={currentReason}
                      onChange={(event) => setRowPatch(row.id, { final_outcome_reason: event.target.value })}
                      placeholder="Причина / комментарий"
                    />
                  </div>
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                    <button className="ui-btn ui-btn--secondary" disabled={!canSave} onClick={() => saveRow(row.id)}>
                      Сохранить
                    </button>
                    <button
                      className="ui-btn ui-btn--danger"
                      disabled={deleteMutation.isPending}
                      onClick={async () => {
                        if (!window.confirm('Удалить строку детализации?')) return
                        await deleteMutation.mutateAsync(row.id)
                      }}
                    >
                      Удалить
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div style={{ display: 'grid', gap: 12 }}>
          <div className="glass" style={{ padding: 14, display: 'grid', gap: 10 }}>
            <strong>По рекрутерам</strong>
            {(query.data?.summary.by_recruiter || []).length === 0 && <p className="subtitle">Нет данных за выбранный период.</p>}
            {(query.data?.summary.by_recruiter || []).map((row) => (
              <div key={`recruiter-${row.id ?? row.name}`} className="glass panel--tight" style={{ padding: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <strong>{row.name}</strong>
                  <span>{row.total}</span>
                </div>
                <div className="text-muted text-xs" style={{ marginTop: 6 }}>
                  Закреплен: {row.outcomes.attached || 0} · Не закреплен: {row.outcomes.not_attached || 0} · Не засчитан: {row.outcomes.not_counted || 0}
                </div>
              </div>
            ))}
          </div>

          <div className="glass" style={{ padding: 14, display: 'grid', gap: 10 }}>
            <strong>По городам</strong>
            {(query.data?.summary.by_city || []).length === 0 && <p className="subtitle">Нет данных за выбранный период.</p>}
            {(query.data?.summary.by_city || []).map((row) => (
              <div key={`city-${row.id ?? row.name}`} className="glass panel--tight" style={{ padding: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <strong>{row.name}</strong>
                  <span>{row.total}</span>
                </div>
                <div className="text-muted text-xs" style={{ marginTop: 6 }}>
                  Закреплен: {row.outcomes.attached || 0} · Не закреплен: {row.outcomes.not_attached || 0} · Не засчитан: {row.outcomes.not_counted || 0}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      </div>
    </RoleGuard>
  )
}
