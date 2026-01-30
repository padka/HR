import { Link, useNavigate } from '@tanstack/react-router'
import { useMutation, useQuery } from '@tanstack/react-query'
import { RoleGuard } from '@/app/components/RoleGuard'
import { apiFetch } from '@/api/client'

export function QuestionsPage() {
  const navigate = useNavigate()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['questions'],
    queryFn: () => apiFetch<any[]>('/questions'),
  })

  const cloneMutation = useMutation({
    mutationFn: async (questionId: number) => {
      return apiFetch(`/questions/${questionId}/clone`, { method: 'POST' })
    },
    onSuccess: (payload: any) => {
      if (payload?.id) {
        navigate({ to: '/app/questions/$questionId/edit', params: { questionId: String(payload.id) } })
      }
    },
  })

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <header className="glass glass--elevated page-header page-header--row">
          <h1 className="title">Вопросы</h1>
          <Link to="/app/questions/new" className="ui-btn ui-btn--primary">+ Новый вопрос</Link>
        </header>

        <section className="glass page-section">
          {isLoading && <p className="subtitle">Загрузка…</p>}
          {isError && <p className="text-danger">Ошибка: {(error as Error).message}</p>}
          {data && (
            <div className="page-section__content">
              {(data as any[]).map((group) => (
                <article key={group.test_id} className="glass glass--subtle data-card">
                  <h3 className="data-card__title">{group.title}</h3>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Индекс</th>
                        <th>Вопрос</th>
                        <th>Статус</th>
                        <th>Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.questions.map((q: any) => (
                        <tr key={q.id}>
                          <td>{q.id}</td>
                          <td>{q.index}</td>
                          <td>{q.title}</td>
                          <td>
                            <span className={`status-badge status-badge--${q.is_active ? 'success' : 'muted'}`}>
                              {q.is_active ? 'Активен' : 'Отключён'}
                            </span>
                          </td>
                          <td>
                            <div className="toolbar toolbar--compact">
                              <Link
                                to="/app/questions/$questionId/edit"
                                params={{ questionId: String(q.id) }}
                                className="ui-btn ui-btn--ghost ui-btn--sm"
                              >
                                Редактировать
                              </Link>
                              <button
                                className="ui-btn ui-btn--ghost ui-btn--sm"
                                onClick={() => cloneMutation.mutate(q.id)}
                                disabled={cloneMutation.isPending}
                              >
                                Клонировать
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
