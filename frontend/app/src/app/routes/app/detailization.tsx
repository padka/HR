import { apiFetch } from '@/api/client'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useProfile } from '@/app/hooks/useProfile'

type DetailizationItem = {
  id: number
  assigned_at: string | null
  conducted_at: string | null
  expert_name: string
  is_attached: boolean | null
  recruiter: { id: number; name: string } | null
  city: { id: number; name: string } | null
  candidate: { id: number; name: string }
}

type DetailizationResponse = {
  ok: boolean
  items: DetailizationItem[]
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
  total: number
  page: number
  pages_total: number
}

function fmtDate(value: string | null): string {
  if (!value) return '—'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return '—'
  return dt.toLocaleDateString('ru-RU')
}

function fmtTime(value: string | null): string {
  if (!value) return '—'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return '—'
  return dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function isoDate(value: Date): string {
  return value.toISOString().slice(0, 10)
}

function attachLabel(value: boolean | null): { text: string; tone: string } {
  if (value === true) return { text: 'Да', tone: 'success' }
  if (value === false) return { text: 'Нет', tone: 'danger' }
  return { text: '—', tone: 'muted' }
}

export function DetailizationPage() {
  const profile = useProfile()
  const isAdmin = profile.data?.principal.type === 'admin'

  const [showCreate, setShowCreate] = useState(false)
  const [candidateQuery, setCandidateQuery] = useState('')
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateSearchItem | null>(null)
  const [createRecruiterId, setCreateRecruiterId] = useState<string>('') // optional; default from API list
  const [createCityId, setCreateCityId] = useState<string>('') // optional
  const [createAssignedAt, setCreateAssignedAt] = useState<string>(() => isoDate(new Date()))
  const [createConductedAt, setCreateConductedAt] = useState<string>('') // yyyy-mm-dd
  const [createExpertName, setCreateExpertName] = useState('')
  const [createIsAttached, setCreateIsAttached] = useState<'unknown' | 'yes' | 'no'>('unknown')
  const [createError, setCreateError] = useState<string>('')

  const [dirty, setDirty] = useState<Record<number, Partial<Pick<DetailizationItem, 'expert_name' | 'is_attached'>>>>({})
  const query = useQuery({
    queryKey: ['detailization'],
    queryFn: () => apiFetch<DetailizationResponse>('/detailization'),
  })

  const citiesQuery = useQuery<City[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
  })

  const cityById = new Map<number, City>()
  ;(citiesQuery.data || []).forEach((c) => cityById.set(c.id, c))

  const selectedCity = createCityId ? cityById.get(Number(createCityId)) : null
  const createExpertOptions = (selectedCity?.experts_items || []).filter((e) => e.is_active !== false)

  const recruitersQuery = useQuery<Recruiter[]>({
    queryKey: ['recruiters'],
    queryFn: () => apiFetch('/recruiters'),
    enabled: Boolean(isAdmin),
  })

  const candidatesSearchQuery = useQuery<CandidateSearchResponse>({
    queryKey: ['detailization-candidates-search', candidateQuery],
    queryFn: () =>
      apiFetch(
        `/candidates?search=${encodeURIComponent(candidateQuery)}&page=1&per_page=10&pipeline=intro_day`,
      ),
    enabled: Boolean(showCreate && !selectedCandidate && candidateQuery.trim().length >= 2),
    staleTime: 10_000,
  })

  const updateMutation = useMutation({
    mutationFn: async (payload: { id: number; patch: any }) =>
      apiFetch(`/detailization/${payload.id}`, { method: 'PATCH', body: JSON.stringify(payload.patch) }),
    onSuccess: async () => {
      setDirty({})
      await query.refetch()
    },
  })

  const createMutation = useMutation({
    mutationFn: async (payload: any) => apiFetch('/detailization', { method: 'POST', body: JSON.stringify(payload) }),
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
      setCreateIsAttached('unknown')
      await query.refetch()
    },
    onError: (err: any) => {
      const msg = err instanceof Error ? err.message : 'Ошибка создания'
      setCreateError(msg)
    },
  })

  const rows = query.data?.items ?? []

  const setRowPatch = (id: number, patch: any) => {
    setDirty((prev) => ({ ...prev, [id]: { ...(prev[id] || {}), ...patch } }))
  }

  const saveRow = async (id: number) => {
    const patch = dirty[id]
    if (!patch || Object.keys(patch).length === 0) return
    await updateMutation.mutateAsync({ id, patch })
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <div className="glass" style={{ padding: 18, display: 'grid', gap: 8 }}>
        <h1 style={{ margin: 0 }}>Детализация</h1>
        <p style={{ margin: 0, color: 'var(--muted)' }}>
          Кандидаты, дошедшие до ознакомительного дня (с исключениями: «не подходит по критериям» и «не пришел»).
        </p>
      </div>

      <div className="glass detailization-table" style={{ marginTop: 16, padding: 14 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <span className="text-muted text-sm">Строк: {rows.length}</span>
            {query.isFetching && <span className="text-muted text-sm">Обновление…</span>}
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button
              className="ui-btn ui-btn--primary"
              onClick={() => setShowCreate((v) => !v)}
              disabled={createMutation.isPending}
            >
              + Добавить вручную
            </button>
            <button className="ui-btn ui-btn--secondary" onClick={() => query.refetch()} disabled={query.isFetching}>
              Обновить
            </button>
          </div>
        </div>

        {showCreate && (
          <div className="glass" style={{ padding: 14, marginTop: 12, display: 'grid', gap: 10 }}>
            <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}>
              <div style={{ display: 'grid', gap: 6 }}>
                <div className="text-muted text-xs">Кандидат (ФИО)</div>
                <input
                  className="ui-input"
                  value={selectedCandidate?.fio || candidateQuery}
                  onChange={(e) => {
                    setSelectedCandidate(null)
                    setCandidateQuery(e.target.value)
                  }}
                  placeholder="Начните вводить ФИО…"
                />
                {selectedCandidate && (
                  <div className="text-muted text-xs">
                    Выбран: <strong>{selectedCandidate.fio || `ID ${selectedCandidate.id}`}</strong>
                    {selectedCandidate.city ? <> · {selectedCandidate.city}</> : null}
                    <button
                      type="button"
                      className="action-link"
                      style={{ marginLeft: 10 }}
                      onClick={() => {
                        setSelectedCandidate(null)
                        setCandidateQuery('')
                      }}
                    >
                      Очистить
                    </button>
                  </div>
                )}
                {!selectedCandidate && candidateQuery.trim().length >= 2 && (
                  <div className="glass" style={{ padding: 10, borderRadius: 12 }}>
                    {candidatesSearchQuery.isFetching && <div className="text-muted text-xs">Поиск…</div>}
                    {candidatesSearchQuery.isError && (
                      <div className="text-danger text-xs">Ошибка поиска</div>
                    )}
                    {!candidatesSearchQuery.isFetching &&
                      !candidatesSearchQuery.isError &&
                      (candidatesSearchQuery.data?.items || []).length === 0 && (
                        <div className="text-muted text-xs">Ничего не найдено</div>
                      )}
                    <div style={{ display: 'grid', gap: 6, marginTop: 6 }}>
                      {(candidatesSearchQuery.data?.items || []).map((c) => (
                        <button
                          key={c.id}
                          type="button"
                          className="ui-btn ui-btn--secondary"
                          style={{ justifyContent: 'space-between' }}
                          onClick={() => {
                            setSelectedCandidate(c)
                            setCandidateQuery(c.fio || '')
                          }}
                        >
                          <span style={{ display: 'flex', gap: 8, alignItems: 'baseline', minWidth: 0 }}>
                            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {c.fio || `ID ${c.id}`}
                            </span>
                            {c.city ? <span className="text-muted text-xs">{c.city}</span> : null}
                          </span>
                          <span className="text-muted text-xs">#{c.id}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div style={{ display: 'grid', gap: 6 }}>
                <div className="text-muted text-xs">Дата назначения</div>
                <input
                  className="ui-input"
                  type="date"
                  value={createAssignedAt}
                  onChange={(e) => setCreateAssignedAt(e.target.value)}
                />
              </div>

              <div style={{ display: 'grid', gap: 6 }}>
                <div className="text-muted text-xs">Дата проведения</div>
                <input
                  className="ui-input"
                  type="date"
                  value={createConductedAt}
                  onChange={(e) => setCreateConductedAt(e.target.value)}
                />
              </div>

              <div style={{ display: 'grid', gap: 6 }}>
                <div className="text-muted text-xs">Закрепление</div>
                <select
                  className="ui-select"
                  value={createIsAttached}
                  onChange={(e) => setCreateIsAttached(e.target.value as any)}
                >
                  <option value="unknown">—</option>
                  <option value="yes">Да</option>
                  <option value="no">Нет</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}>
              {isAdmin && (
                <div style={{ display: 'grid', gap: 6 }}>
                  <div className="text-muted text-xs">Рекрутер</div>
                  <select
                    className="ui-select"
                    value={createRecruiterId || ''}
                    onChange={(e) => setCreateRecruiterId(e.target.value)}
                    disabled={recruitersQuery.isLoading || (recruitersQuery.data?.length || 0) <= 1}
                  >
                    <option value="">—</option>
                    {(recruitersQuery.data || []).map((r) => (
                      <option key={r.id} value={String(r.id)}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div style={{ display: 'grid', gap: 6 }}>
                <div className="text-muted text-xs">Город</div>
                <select
                  className="ui-select"
                  value={createCityId || ''}
                  onChange={(e) => {
                    setCreateCityId(e.target.value)
                    setCreateExpertName('')
                  }}
                  disabled={citiesQuery.isLoading}
                >
                  <option value="">—</option>
                  {(citiesQuery.data || [])
                    .filter((c) => c.active !== false)
                    .map((c) => (
                      <option key={c.id} value={String(c.id)}>
                        {c.name}
                      </option>
                    ))}
                </select>
              </div>

              <div style={{ display: 'grid', gap: 6 }}>
                <div className="text-muted text-xs">Эксперт (ФИО)</div>
                <select
                  className="ui-select"
                  value={createExpertName}
                  onChange={(e) => setCreateExpertName(e.target.value)}
                  disabled={!createCityId || createExpertOptions.length === 0}
                >
                  <option value="">—</option>
                  {createExpertOptions.map((e) => (
                    <option key={e.id ?? e.name} value={e.name}>
                      {e.name}
                    </option>
                  ))}
                </select>
                {!createCityId && <div className="text-muted text-xs">Выберите город, чтобы увидеть экспертов</div>}
                {createCityId && createExpertOptions.length === 0 && (
                  <div className="text-muted text-xs">В этом городе не настроены эксперты</div>
                )}
              </div>
            </div>

            {createError && <div className="text-danger text-sm">{createError}</div>}

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
              {selectedCandidate && (
                <Link
                  to="/app/candidates/$candidateId"
                  params={{ candidateId: String(selectedCandidate.id) }}
                  className="ui-btn ui-btn--secondary"
                >
                  Открыть кандидата
                </Link>
              )}
              <button className="ui-btn ui-btn--secondary" onClick={() => setShowCreate(false)} disabled={createMutation.isPending}>
                Отмена
              </button>
              <button
                className="ui-btn ui-btn--primary"
                disabled={createMutation.isPending || !selectedCandidate || (isAdmin && !createRecruiterId.trim())}
                onClick={async () => {
                  setCreateError('')
                  if (!selectedCandidate) {
                    setCreateError('Выберите кандидата из списка')
                    return
                  }
                  if (isAdmin && !createRecruiterId.trim()) {
                    setCreateError('Выберите рекрутера')
                    return
                  }
                  const payload: any = {
                    candidate_id: selectedCandidate.id,
                    expert_name: createExpertName.trim() || null,
                    assigned_at: createAssignedAt.trim() || null,
                    conducted_at: createConductedAt.trim() || null,
                    is_attached: createIsAttached === 'unknown' ? null : createIsAttached === 'yes',
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

        {query.isError && (
          <div className="glass" style={{ padding: 12, marginTop: 12 }}>
            <strong>Ошибка загрузки</strong>
            <div className="text-muted text-sm">{String((query.error as Error)?.message || query.error)}</div>
          </div>
        )}

        <div className={`detailization-grid ${isAdmin ? '' : 'detailization-grid--recruiter'}`} style={{ marginTop: 12 }}>
          <div className="detailization-grid__head">
            <div>Дата назначения</div>
            {isAdmin && <div>Рекрутер</div>}
            <div>Дата проведения</div>
            <div>Город</div>
            <div>Эксперт (ФИО)</div>
            <div>Кандидат</div>
            <div>Закрепление</div>
            <div />
          </div>

          {rows.map((row) => {
            const patch = dirty[row.id] || {}
            const attached = attachLabel((patch as any).is_attached ?? row.is_attached)
            const canSave = Object.keys(patch).length > 0 && !updateMutation.isPending
            return (
              <div key={row.id} className="detailization-grid__row">
                <div className="text-sm">
                  <div>{fmtDate(row.assigned_at)}</div>
                  <div className="text-muted text-xs">{fmtTime(row.assigned_at)}</div>
                </div>

                {isAdmin && <div className="text-sm">{row.recruiter?.name || '—'}</div>}

                <div className="text-sm">
                  <div>{fmtDate(row.conducted_at)}</div>
                </div>

                <div className="text-sm">{row.city?.name || '—'}</div>

                <div>
                  {row.city?.id && (cityById.get(row.city.id)?.experts_items || []).length > 0 ? (
                    <select
                      className="ui-select"
                      value={(patch as any).expert_name ?? row.expert_name ?? ''}
                      onChange={(e) => setRowPatch(row.id, { expert_name: e.target.value })}
                    >
                      <option value="">—</option>
                      {(() => {
                        const opts = (cityById.get(row.city!.id)?.experts_items || []).filter(
                          (e) => e.is_active !== false,
                        )
                        const current = (patch as any).expert_name ?? row.expert_name ?? ''
                        const hasCurrent = current && opts.some((o) => o.name === current)
                        return (
                          <>
                            {!hasCurrent && current ? (
                              <option value={current}>{current} (текущее)</option>
                            ) : null}
                            {opts.map((e) => (
                              <option key={e.id ?? e.name} value={e.name}>
                                {e.name}
                              </option>
                            ))}
                          </>
                        )
                      })()}
                    </select>
                  ) : (
                    <input
                      className="ui-input"
                      value={(patch as any).expert_name ?? row.expert_name ?? ''}
                      onChange={(e) => setRowPatch(row.id, { expert_name: e.target.value })}
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
                    value={((patch as any).is_attached ?? row.is_attached) === null ? 'unknown' : ((patch as any).is_attached ?? row.is_attached) ? 'yes' : 'no'}
                    onChange={(e) => {
                      const v = e.target.value
                      setRowPatch(row.id, { is_attached: v === 'unknown' ? null : v === 'yes' })
                    }}
                    data-tone={attached.tone}
                  >
                    <option value="unknown">—</option>
                    <option value="yes">Да</option>
                    <option value="no">Нет</option>
                  </select>
                </div>

                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button className="ui-btn ui-btn--secondary" disabled={!canSave} onClick={() => saveRow(row.id)}>
                    Сохранить
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
