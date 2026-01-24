import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import { QuestionPayloadEditor } from '@/app/components/QuestionPayloadEditor'

const TEST_CHOICES: Array<{ id: string; label: string }> = [
  { id: 'test1', label: 'Анкета кандидата' },
  { id: 'test2', label: 'Инфо-тест' },
]

export function QuestionNewPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    title: '',
    test_id: 'test1',
    question_index: '',
    payload: '{}',
    is_active: true,
  })
  const [formError, setFormError] = useState<string | null>(null)
  const [payloadValid, setPayloadValid] = useState(true)

  const mutation = useMutation({
    mutationFn: async () => {
      setFormError(null)
      if (!form.test_id.trim()) {
        throw new Error('Укажите тест')
      }
      if (!form.payload.trim()) {
        throw new Error('Укажите payload')
      }
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
        question_index: form.question_index ? Number(form.question_index) : null,
        payload: form.payload,
        is_active: form.is_active,
      }
      return apiFetch('/questions', { method: 'POST', body: JSON.stringify(payload) })
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
              <h1 className="title">Новый вопрос</h1>
              <p className="subtitle">Создайте новый вопрос теста.</p>
            </div>
            <Link to="/app/questions" className="glass action-link">← Назад</Link>
          </div>

          <label style={{ display: 'grid', gap: 6 }}>
            Заголовок
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </label>

          <label style={{ display: 'grid', gap: 6 }}>
            Тест
            <select value={form.test_id} onChange={(e) => setForm({ ...form, test_id: e.target.value })}>
              {TEST_CHOICES.map((opt) => (
                <option key={opt.id} value={opt.id}>{opt.label}</option>
              ))}
            </select>
          </label>

          <label style={{ display: 'grid', gap: 6 }}>
            Индекс (опционально)
            <input
              type="number"
              value={form.question_index}
              onChange={(e) => setForm({ ...form, question_index: e.target.value })}
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
            {mutation.isPending ? 'Сохраняем…' : 'Создать'}
          </button>
          {formError && <p style={{ color: '#f07373' }}>Ошибка: {formError}</p>}
        </div>
      </div>
    </RoleGuard>
  )
}
