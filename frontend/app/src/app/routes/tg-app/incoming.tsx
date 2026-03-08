/**
 * Telegram Mini App — Incoming candidates view.
 * Shows waiting candidates with status and action buttons.
 */
import { useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'

interface Candidate {
  id: number
  fio: string
  city: string | null
  status: string | null
  status_label: string | null
  waiting_hours: number | null
}

function useTgInitData(): string {
  try {
    return (window as any)?.Telegram?.WebApp?.initData || ''
  } catch {
    return ''
  }
}

export function TgIncomingPage() {
  const initData = useTgInitData()
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!initData) {
      setError('Откройте через Telegram')
      setLoading(false)
      return
    }

    fetch('/api/webapp/recruiter/incoming?limit=20', {
      headers: { 'X-Telegram-Init-Data': initData },
    })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(data => {
        setCandidates(data.candidates || [])
        setTotal(data.total || 0)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [initData])

  if (loading) {
    return <div style={{ padding: '24px', textAlign: 'center', color: '#999' }}>Загрузка...</div>
  }
  if (error) {
    return <div style={{ padding: '24px', textAlign: 'center', color: '#666' }}>{error}</div>
  }

  return (
    <div>
      <h2 style={{ margin: '0 0 12px', fontSize: '18px' }}>
        Входящие ({total})
      </h2>

      {candidates.length === 0 ? (
        <div style={{ padding: '24px', textAlign: 'center', color: '#999' }}>
          Нет ожидающих кандидатов
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {candidates.map(c => (
            <CandidateCard key={c.id} candidate={c} />
          ))}
        </div>
      )}
    </div>
  )
}

function CandidateCard({ candidate: c }: { candidate: Candidate }) {
  const waitLabel = c.waiting_hours != null
    ? `${Math.round(c.waiting_hours)}ч`
    : '—'

  return (
    <Link
      to="/tg-app/candidates/$candidateId"
      params={{ candidateId: String(c.id) }}
      style={{ textDecoration: 'none', color: 'inherit' }}
    >
      <div
        style={{
          background: 'var(--tg-theme-secondary-bg-color, #f2f2f7)',
          borderRadius: '10px',
          padding: '12px',
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: '4px' }}>{c.fio}</div>
        <div style={{ fontSize: '13px', color: 'var(--tg-theme-hint-color, #999)' }}>
          {c.city || '—'} &middot; {c.status_label || '—'} &middot; {waitLabel}
        </div>
        <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--tg-theme-link-color, #007aff)' }}>
          Открыть карточку →
        </div>
      </div>
    </Link>
  )
}
