import { useState, type FormEvent } from 'react'

export function LoginPage() {
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (!form.username.trim() || !form.password) {
      setError('Введите логин и пароль.')
      return
    }
    setLoading(true)
    try {
      const body = new URLSearchParams()
      body.set('username', form.username)
      body.set('password', form.password)
      body.set('redirect_to', '/app')

      const response = await fetch('/auth/login', {
        method: 'POST',
        body,
        credentials: 'include',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      if (!response.ok) {
        setError('Неверные учётные данные.')
        setLoading(false)
        return
      }
      window.location.href = '/app'
    } catch {
      setError('Не удалось выполнить вход. Проверьте соединение.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="glass glass--elevated login-card">
        <h1 className="title">Вход в систему</h1>
        <p className="subtitle">Используйте учётные данные администратора или рекрутёра.</p>
        <form onSubmit={submit} className="login-form">
          <div className="form-group">
            <label className="form-group__label">Логин</label>
            <input
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              autoComplete="username"
              placeholder="admin"
            />
          </div>
          <div className="form-group">
            <label className="form-group__label">Пароль</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              autoComplete="current-password"
              placeholder="••••••••"
            />
          </div>
          <button className="ui-btn ui-btn--primary ui-btn--lg" type="submit" disabled={loading}>
            {loading ? 'Вход...' : 'Войти'}
          </button>
          {error && <p className="form-group__error">{error}</p>}
          <a href="/auth/login?redirect_to=/app" className="text-muted text-sm" style={{ textAlign: 'center' }}>
            Открыть legacy страницу входа
          </a>
        </form>
      </div>
    </div>
  )
}
