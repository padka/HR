import { useState, type FormEvent } from 'react'

type LoginField = 'username' | 'password'

type LoginFieldErrors = Partial<Record<LoginField, string>>

export function LoginPage() {
  const [form, setForm] = useState({ username: '', password: '' })
  const [fieldErrors, setFieldErrors] = useState<LoginFieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const usernameId = 'login-username'
  const passwordId = 'login-password'
  const usernameErrorId = 'login-username-error'
  const passwordErrorId = 'login-password-error'
  const formErrorId = 'login-form-error'

  const validate = () => {
    const nextErrors: LoginFieldErrors = {}
    if (!form.username.trim()) nextErrors.username = 'Введите логин.'
    if (!form.password) nextErrors.password = 'Введите пароль.'
    setFieldErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const updateField = (field: LoginField, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
    setFieldErrors((current) => {
      if (!current[field]) return current
      const next = { ...current }
      delete next[field]
      return next
    })
    setFormError(null)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setFormError(null)
    if (!validate()) {
      setFormError('Проверьте обязательные поля и попробуйте снова.')
      return
    }
    setLoading(true)
    try {
      const body = new URLSearchParams()
      body.set('username', form.username)
      body.set('password', form.password)
      body.set('redirect_to', '/app')

      // raw fetch: legacy form login posts outside /api and expects form-encoded body.
      const response = await fetch('/auth/login', {
        method: 'POST',
        body,
        credentials: 'include',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      if (!response.ok) {
        setFormError(
          response.status === 400 || response.status === 401
            ? 'Неверные учётные данные.'
            : 'Не удалось выполнить вход. Попробуйте ещё раз.',
        )
        setLoading(false)
        return
      }
      window.location.href = '/app'
    } catch {
      setFormError('Не удалось выполнить вход. Проверьте соединение.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card panel">
        <h1 className="title">Вход в систему</h1>
        <p className="subtitle">Используйте учётные данные администратора или рекрутёра, чтобы продолжить работу в RecruitSmart.</p>
        <form onSubmit={submit} className="login-form" aria-busy={loading}>
          {formError && (
            <div className="login-form__summary" id={formErrorId} role="alert">
              <strong>Не удалось войти</strong>
              <span>{formError}</span>
            </div>
          )}
          <div className="form-group">
            <label className="form-group__label" htmlFor={usernameId}>Логин</label>
            <div className="form-group__input">
              <input
                id={usernameId}
                value={form.username}
                onChange={(e) => updateField('username', e.target.value)}
                autoComplete="username"
                placeholder="admin"
                aria-invalid={fieldErrors.username ? 'true' : 'false'}
                aria-describedby={fieldErrors.username ? usernameErrorId : undefined}
                disabled={loading}
              />
            </div>
            {fieldErrors.username && <p className="form-group__error" id={usernameErrorId}>{fieldErrors.username}</p>}
          </div>
          <div className="form-group">
            <label className="form-group__label" htmlFor={passwordId}>Пароль</label>
            <div className="form-group__input">
              <input
                id={passwordId}
                type="password"
                value={form.password}
                onChange={(e) => updateField('password', e.target.value)}
                autoComplete="current-password"
                placeholder="••••••••"
                aria-invalid={fieldErrors.password ? 'true' : 'false'}
                aria-describedby={fieldErrors.password ? passwordErrorId : undefined}
                disabled={loading}
              />
            </div>
            {fieldErrors.password && <p className="form-group__error" id={passwordErrorId}>{fieldErrors.password}</p>}
          </div>
          <button
            className="ui-btn ui-btn--primary ui-btn--lg"
            type="submit"
            disabled={loading}
            aria-describedby={formError ? formErrorId : undefined}
          >
            {loading ? 'Вход...' : 'Войти'}
          </button>
          <div className="login-form__secondary">
            <a href="/auth/login?redirect_to=/app" className="ui-link">
              Открыть legacy страницу входа
            </a>
          </div>
        </form>
      </div>
    </div>
  )
}
