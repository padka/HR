import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'

type Vacancy = {
  id: number
  title: string
  slug: string
  city_id: number | null
  city_name: string | null
  is_active: boolean
  description: string | null
  test1_question_count: number
  test2_question_count: number
  created_at: string
  updated_at: string
}

type VacanciesResponse = {
  ok: boolean
  vacancies: Vacancy[]
}

async function fetchVacancies(): Promise<VacanciesResponse> {
  return apiFetch<VacanciesResponse>('/vacancies')
}

async function deleteVacancy(id: number): Promise<void> {
  await apiFetch<unknown>(`/vacancies/${id}`, { method: 'DELETE' })
}

async function toggleVacancy(v: Vacancy): Promise<void> {
  await apiFetch<unknown>(`/vacancies/${v.id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_active: !v.is_active }),
  })
}

function QuestionCountBadge({ count, label }: { count: number; label: string }) {
  return (
    <span className={`chip ${count === 0 ? 'chip--muted' : ''}`}>
      {label}: {count === 0 ? 'global' : `${count} вопр.`}
    </span>
  )
}

function VacancyCard({
  vacancy,
  onDelete,
  onToggle,
}: {
  vacancy: Vacancy
  onDelete: (id: number) => void
  onToggle: (v: Vacancy) => void
}) {
  return (
    <div className={`glass list-item ${!vacancy.is_active ? 'list-item--inactive' : ''}`} style={{ marginBottom: 8 }}>
      <div className="list-item__body">
        <div className="list-item__title">
          {vacancy.title}
          {!vacancy.is_active && (
            <span className="status-badge status-badge--muted" style={{ marginLeft: 8 }}>
              архив
            </span>
          )}
        </div>
        <div className="list-item__meta" style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
          slug: <code>{vacancy.slug}</code>
          {vacancy.city_name && <> · <strong>{vacancy.city_name}</strong></>}
        </div>
        {vacancy.description && (
          <div style={{ fontSize: 12, marginTop: 4, color: 'var(--fg-secondary)' }}>{vacancy.description}</div>
        )}
        <div className="list-item__chips" style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <QuestionCountBadge count={vacancy.test1_question_count} label="Test1" />
          <QuestionCountBadge count={vacancy.test2_question_count} label="Test2" />
        </div>
      </div>
      <div className="list-item__actions" style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
        <Link
          to="/app/vacancy-edit"
          search={{ id: vacancy.id }}
          className="ui-btn ui-btn--ghost ui-btn--sm"
        >
          Редактировать
        </Link>
        <button
          className="ui-btn ui-btn--ghost ui-btn--sm"
          onClick={() => onToggle(vacancy)}
          title={vacancy.is_active ? 'Архивировать' : 'Восстановить'}
        >
          {vacancy.is_active ? '⏸' : '▶'}
        </button>
        <button
          className="ui-btn ui-btn--danger ui-btn--sm"
          onClick={() => {
            if (confirm(`Удалить вакансию «${vacancy.title}»?`)) onDelete(vacancy.id)
          }}
        >
          ✕
        </button>
      </div>
    </div>
  )
}

export default function VacanciesPage() {
  const qc = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ['vacancies'],
    queryFn: fetchVacancies,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteVacancy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vacancies'] }),
  })

  const toggleMutation = useMutation({
    mutationFn: toggleVacancy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vacancies'] }),
  })

  const vacancies = data?.vacancies ?? []
  const globalVacancies = vacancies.filter((v) => v.city_id === null)
  const cityVacancies = vacancies.filter((v) => v.city_id !== null)

  // Group city vacancies by city
  const byCity = cityVacancies.reduce<Record<string, { name: string; items: Vacancy[] }>>(
    (acc, v) => {
      const key = String(v.city_id)
      if (!acc[key]) acc[key] = { name: v.city_name ?? String(v.city_id), items: [] }
      acc[key].items.push(v)
      return acc
    },
    {},
  )

  if (isLoading) return <div className="page"><div className="page-section">Загрузка...</div></div>
  if (error) return <div className="page"><div className="page-section">Ошибка загрузки</div></div>

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Вакансии</h1>
        <div className="page-header__actions">
          <Link to="/app/vacancy-edit" className="ui-btn ui-btn--primary">
            + Новая вакансия
          </Link>
        </div>
      </div>

      <div className="page-section">
        <h2 className="section-title" style={{ marginBottom: 12 }}>Глобальные</h2>
        {globalVacancies.length === 0 ? (
          <div className="empty-state">
            <p>Нет глобальных вакансий. Глобальные вакансии применяются во всех городах по умолчанию.</p>
          </div>
        ) : (
          globalVacancies.map((v) => (
            <VacancyCard
              key={v.id}
              vacancy={v}
              onDelete={(id) => deleteMutation.mutate(id)}
              onToggle={(vacancy) => toggleMutation.mutate(vacancy)}
            />
          ))
        )}
      </div>

      {Object.keys(byCity).length > 0 && (
        <div className="page-section">
          <h2 className="section-title" style={{ marginBottom: 12 }}>По городам</h2>
          {Object.entries(byCity).map(([cityId, group]) => (
            <div key={cityId} style={{ marginBottom: 24 }}>
              <div style={{ fontWeight: 600, marginBottom: 8, color: 'var(--fg-secondary)' }}>
                {group.name}
              </div>
              {group.items.map((v) => (
                <VacancyCard
                  key={v.id}
                  vacancy={v}
                  onDelete={(id) => deleteMutation.mutate(id)}
                  onToggle={(vacancy) => toggleMutation.mutate(vacancy)}
                />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
