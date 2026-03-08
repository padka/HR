import { useNavigate, useParams } from '@tanstack/react-router'
import { startTransition, useEffect, useState } from 'react'

import { exchangeCandidatePortalToken } from '@/api/candidate'
import { queryClient } from '@/api/client'
import '../candidate-portal.css'

export function CandidateStartPage() {
  const { token } = useParams({ from: '/candidate/start/$token' })
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      try {
        const payload = await exchangeCandidatePortalToken(token)
        if (cancelled) return
        queryClient.setQueryData(['candidate-portal-journey'], payload)
        startTransition(() => {
          void navigate({ to: '/candidate/journey' })
        })
      } catch (err) {
        if (cancelled) return
        const message = err instanceof Error ? err.message : 'Не удалось открыть ссылку.'
        setError(message || 'Не удалось открыть ссылку.')
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [navigate, token])

  return (
    <div className="candidate-portal">
      <div className="candidate-portal__loader">
        <div className="glass glass--elevated candidate-portal__card">
          <div className="candidate-portal__eyebrow">Candidate Portal</div>
          <h1 className="candidate-portal__title">Открываю вашу анкету</h1>
          <p className="candidate-portal__subtitle">
            Проверяю ссылку и восстанавливаю прогресс прохождения.
          </p>
          {error ? <p className="candidate-portal__error">{error}</p> : null}
        </div>
      </div>
    </div>
  )
}

