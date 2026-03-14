/**
 * Telegram Mini App — Candidate detail view.
 * Shows profile, test results, timeline, notes.
 */
import { useEffect, useState } from 'react'
import { useParams } from '@tanstack/react-router'

interface CandidateDetail {
  id: number
  fio: string
  city: string | null
  phone: string | null
  status: string | null
  status_label: string | null
  transitions: Array<{ status: string; label: string }>
}

type TelegramWebAppWindow = Window & {
  Telegram?: {
    WebApp?: {
      initData?: string
    }
  }
}

function useTgInitData(): string {
  try {
    return (window as TelegramWebAppWindow).Telegram?.WebApp?.initData || ''
  } catch {
    return ''
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Не удалось выполнить действие'
}

export function TgCandidatePage() {
  const { candidateId } = useParams({ strict: false }) as { candidateId: string }
  const initData = useTgInitData()
  const [candidate, setCandidate] = useState<CandidateDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusMsg, setStatusMsg] = useState('')

  useEffect(() => {
    if (!initData || !candidateId) {
      setError('Откройте через Telegram')
      setLoading(false)
      return
    }

    fetch(`/api/webapp/recruiter/candidates/${candidateId}`, {
      headers: { 'X-Telegram-Init-Data': initData },
    })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setCandidate)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [initData, candidateId])

  const handleStatusChange = async (status: string) => {
    if (!initData || !candidateId) return
    setStatusMsg('Обновление...')
    try {
      const res = await fetch(`/api/webapp/recruiter/candidates/${candidateId}/status`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({ status }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `HTTP ${res.status}`)
      }
      setStatusMsg('Статус обновлён')
      // Reload candidate data
      const updated = await fetch(`/api/webapp/recruiter/candidates/${candidateId}`, {
        headers: { 'X-Telegram-Init-Data': initData },
      }).then(r => r.json())
      setCandidate(updated)
    } catch (error: unknown) {
      setStatusMsg(`Ошибка: ${errorMessage(error)}`)
    }
  }

  if (loading) {
    return <div style={{ padding: '24px', textAlign: 'center', color: '#999' }}>Загрузка...</div>
  }
  if (error || !candidate) {
    return <div style={{ padding: '24px', textAlign: 'center', color: '#666' }}>{error || 'Не найден'}</div>
  }

  return (
    <div>
      <h2 style={{ margin: '0 0 8px', fontSize: '20px' }}>{candidate.fio}</h2>

      <div style={{ fontSize: '14px', color: 'var(--tg-theme-hint-color, #999)', marginBottom: '16px' }}>
        {candidate.city || '—'} &middot; {candidate.phone || '—'}
      </div>

      <div
        style={{
          background: 'var(--tg-theme-secondary-bg-color, #f2f2f7)',
          borderRadius: '10px',
          padding: '12px',
          marginBottom: '12px',
        }}
      >
        <div style={{ fontSize: '13px', color: 'var(--tg-theme-hint-color, #999)' }}>Статус</div>
        <div style={{ fontWeight: 600, marginTop: '4px' }}>{candidate.status_label || 'Нет статуса'}</div>
      </div>

      {candidate.transitions.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{ fontSize: '13px', color: 'var(--tg-theme-hint-color, #999)', marginBottom: '8px' }}>
            Изменить статус:
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {candidate.transitions.map(t => (
              <button
                key={t.status}
                onClick={() => handleStatusChange(t.status)}
                style={{
                  padding: '6px 12px',
                  fontSize: '13px',
                  border: '1px solid var(--tg-theme-button-color, #007aff)',
                  borderRadius: '8px',
                  background: 'transparent',
                  color: 'var(--tg-theme-button-color, #007aff)',
                  cursor: 'pointer',
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {statusMsg && (
        <div style={{ padding: '8px', fontSize: '13px', color: '#007aff' }}>{statusMsg}</div>
      )}
    </div>
  )
}
