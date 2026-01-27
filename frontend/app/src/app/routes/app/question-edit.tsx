import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import { QuestionPayloadEditor } from '@/app/components/QuestionPayloadEditor'

type QuestionDetail = {
  id: number
  title: string
  test_id: string
  question_index: number
  payload: string
  is_active: boolean
  test_choices: [string, string][]
}

export function QuestionEditPage() {
  const params = useParams({ from: '/app/questions/$questionId/edit' })
  const questionId = Number(params.questionId)
  const navigate = useNavigate()

  const detailQuery = useQuery<QuestionDetail>({
    queryKey: ['question-detail', questionId],
    queryFn: () => apiFetch(`/questions/${questionId}`),
  })

  const [form, setForm] = useState({
    title: '',
    test_id: 'test1',
    question_index: 1,
    payload: '{}',
    is_active: true,
  })
  const [formError, setFormError] = useState<string | null>(null)
  const [payloadValid, setPayloadValid] = useState(true)

  useEffect(() => {
    if (!detailQuery.data) return
    setForm({
      title: detailQuery.data.title || '',
      test_id: detailQuery.data.test_id || 'test1',
      question_index: detailQuery.data.question_index || 1,
      payload: detailQuery.data.payload || '{}',
      is_active: detailQuery.data.is_active,
    })
  }, [detailQuery.data])

  const mutation = useMutation({
    mutationFn: async () => {
      setFormError(null)
      if (!payloadValid) {
        throw new Error('Payload содержит ошибку JSON')
      }
      try {
        JSON.parse(form.payload)
      } catch {
        throw new Error('Payload должен быть валидным JSON')
      }
      const payload = {
        title: form.title,
        test_id: form.test_id,
        question_index: Number(form.question_index),
        payload: form.payload,
        is_active: form.is_active,
      }
      return apiFetch(`/questions/${questionId}`, { method: 'PUT', body: JSON.stringify(payload) })
    },
    onSuccess: () => navigate({ to: '/app/questions' }),
    onError: (err) => {
      let message = err instanceof Error ? err.message : 'Ошибка'
      try {
        const parsed = JSON.parse(message)
        if (parsed?.error) {
          message = parsed.error
        }
      } catch {
        // ignore parsing errors
      }
      setFormError(message)
    },
  })

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <div className="glass panel" style={{ display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <div>
              <h1 className="title">Редактирование вопроса</h1>
              <p className="subtitle">ID: {questionId}</p>
            </div>
            <Link to="/app/questions" className="glass action-link">← Назад</Link>
          </div>

          {detailQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {detailQuery.isError && <p style={{ color: '#f07373' }}>Ошибка: {(detailQuery.error as Error).message}</p>}

          {!detailQuery.isLoading && (
            <>
              <label style={{ display: 'grid', gap: 6 }}>
                Заголовок
                <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
              </label>
              <label style={{ display: 'grid', gap: 6 }}>
                Тест
                <select value={form.test_id} onChange={(e) => setForm({ ...form, test_id: e.target.value })}>
                  {(detailQuery.data?.test_choices || []).map(([id, label]) => (
                    <option key={id} value={id}>{label}</option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'grid', gap: 6 }}>
                Индекс
                <input
                  type="number"
                  value={form.question_index}
                  onChange={(e) => setForm({ ...form, question_index: Number(e.target.value) })}
                />
              </label>
              <div className="subtitle">Payload (JSON)</div>
              <QuestionPayloadEditor
                value={form.payload}
                onChange={(payload) => setForm({ ...form, payload })}
                onValidityChange={setPayloadValid}
              />
              <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
                Активен
              </label>
              <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
                {mutation.isPending ? 'Сохраняем…' : 'Сохранить'}
              </button>
              {formError && <p style={{ color: '#f07373' }}>Ошибка: {formError}</p>}
            </>
          )}
        </div>
      </div>
    </RoleGuard>
  )
}
