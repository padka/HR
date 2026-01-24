import { Link, useNavigate } from '@tanstack/react-router'
import { useMutation, useQuery } from '@tanstack/react-query'
import { RoleGuard } from '@/app/components/RoleGuard'
import { apiFetch } from '@/api/client'

export function QuestionsPage() {
  const navigate = useNavigate()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['questions'],
    queryFn: () => apiFetch('/questions'),
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
        <div className="glass panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <h1 className="title">Вопросы</h1>
            <Link to="/app/questions/new" className="glass action-link">+ Новый вопрос</Link>
          </div>
          {isLoading && <p className="subtitle">Загрузка…</p>}
          {isError && <p style={{ color: '#f07373' }}>Ошибка: {(error as Error).message}</p>}
          {data && (
            <div style={{ display: 'grid', gap: 12, marginTop: 12 }}>
              {(data as any[]).map((group) => (
                <div key={group.test_id} className="glass panel--tight" style={{ display: 'grid', gap: 8 }}>
                  <div style={{ fontWeight: 700 }}>{group.title}</div>
                  <table className="table">
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
                        <tr key={q.id} className="glass">
                          <td>{q.id}</td>
                          <td>{q.index}</td>
                          <td>{q.title}</td>
                          <td>{q.is_active ? 'Активен' : 'Отключён'}</td>
                          <td>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                              <Link to="/app/questions/$questionId/edit" params={{ questionId: String(q.id) }}>
                                Редактировать
                              </Link>
                              <button
                                className="ui-btn ui-btn--ghost"
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
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </RoleGuard>
  )
}
