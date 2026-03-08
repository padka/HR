/**
 * Telegram Mini App — Dashboard view.
 * Shows KPIs, today's schedule, and quick actions.
 */
import { useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'

interface DashboardData {
  waiting_candidates_total: number
  scheduled_today: number
  free_slots: number
  recruiter_name: string
}

function useTgInitData(): string {
  // In Telegram Mini App, window.Telegram.WebApp.initData is available
  try {
    return (window as any)?.Telegram?.WebApp?.initData || ''
  } catch {
    return ''
  }
}

async function fetchDashboard(initData: string): Promise<DashboardData> {
  const res = await fetch('/api/webapp/recruiter/dashboard', {
    headers: { 'X-Telegram-Init-Data': initData },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export function TgDashboardPage() {
  const initData = useTgInitData()
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!initData) {
      setError('Откройте через Telegram')
      return
    }
    fetchDashboard(initData).then(setData).catch(e => setError(e.message))
  }, [initData])

  if (error) {
    return <div style={{ padding: '24px', textAlign: 'center', color: '#666' }}>{error}</div>
  }
  if (!data) {
    return <div style={{ padding: '24px', textAlign: 'center', color: '#999' }}>Загрузка...</div>
  }

  return (
    <div>
      <h2 style={{ margin: '0 0 16px', fontSize: '20px' }}>
        {data.recruiter_name || 'Панель рекрутёра'}
      </h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: '16px' }}>
        <KpiCard label="Ожидают" value={data.waiting_candidates_total} color="#ff9500" />
        <KpiCard label="Встречи" value={data.scheduled_today} color="#007aff" />
        <KpiCard label="Слоты" value={data.free_slots} color="#34c759" />
      </div>

      <Link
        to="/tg-app/incoming"
        style={{
          display: 'block',
          padding: '12px 16px',
          background: 'var(--tg-theme-button-color, #007aff)',
          color: 'var(--tg-theme-button-text-color, #fff)',
          borderRadius: '10px',
          textDecoration: 'none',
          textAlign: 'center',
          fontWeight: 500,
        }}
      >
        Входящие кандидаты ({data.waiting_candidates_total})
      </Link>
    </div>
  )
}

function KpiCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div
      style={{
        background: 'var(--tg-theme-secondary-bg-color, #f2f2f7)',
        borderRadius: '10px',
        padding: '12px',
        textAlign: 'center',
      }}
    >
      <div style={{ fontSize: '24px', fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: '12px', color: 'var(--tg-theme-hint-color, #999)', marginTop: '4px' }}>
        {label}
      </div>
    </div>
  )
}
