import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'

type SimulatorStep = {
  id: number
  step_order: number
  step_key: string
  title: string
  status: 'success' | 'failed' | 'running'
  started_at?: string | null
  finished_at?: string | null
  duration_ms: number
  details?: Record<string, unknown>
}

type SimulatorRun = {
  id: number
  scenario: string
  status: 'completed' | 'failed' | 'running'
  started_at?: string | null
  finished_at?: string | null
  summary: {
    total_steps?: number
    successful_steps?: number
    failed_steps?: number
    total_duration_ms?: number
    final_status?: string
    bottlenecks?: Array<{ step_key: string; title: string; duration_ms: number }>
  }
  steps?: SimulatorStep[]
}

type SimulatorRunResponse = {
  ok: boolean
  run: SimulatorRun
}

type SimulatorReportResponse = {
  ok: boolean
  report: {
    run: SimulatorRun
    summary: SimulatorRun['summary']
    steps: SimulatorStep[]
  }
}

const SCENARIOS = [
  { key: 'happy_path', label: 'Happy path' },
  { key: 'reschedule_loop', label: 'Reschedule loop' },
  { key: 'decline_path', label: 'Decline path' },
  { key: 'intro_day_missing_feedback', label: 'Intro day missing feedback' },
] as const

function fmtMs(ms: number | undefined) {
  if (!ms || ms <= 0) return '0.0 s'
  return `${(ms / 1000).toFixed(1)} s`
}

export function SimulatorPage() {
  const enabled =
    String(import.meta.env.VITE_SIMULATOR_ENABLED || (import.meta.env.DEV ? 'true' : 'false')).toLowerCase() ===
    'true'
  const [scenario, setScenario] = useState<(typeof SCENARIOS)[number]['key']>('happy_path')
  const [runId, setRunId] = useState<number | null>(null)

  const runMutation = useMutation({
    mutationFn: async (scenarioKey: string) =>
      apiFetch<SimulatorRunResponse>('/simulator/runs', {
        method: 'POST',
        body: JSON.stringify({ scenario: scenarioKey }),
      }),
    onSuccess: (data) => {
      if (data?.run?.id) {
        setRunId(data.run.id)
      }
    },
  })

  const reportQuery = useQuery<SimulatorReportResponse>({
    queryKey: ['simulator-run-report', runId],
    queryFn: () => apiFetch(`/simulator/runs/${runId}/report`),
    enabled: Boolean(runId),
    refetchInterval: runId ? 2000 : false,
  })

  const steps = useMemo(() => reportQuery.data?.report?.steps || [], [reportQuery.data])
  const summary = reportQuery.data?.report?.summary

  return (
    <RoleGuard allow={['admin']}>
      <div className="page simulator-page">
        <section className="glass page-section">
          <div className="section-header" style={{ marginBottom: 16 }}>
            <h1 className="section-title">Scenario Simulator</h1>
          </div>
          <p className="subtitle">Локальный инструмент сценарного прогона. В проде отключается через флаг.</p>

          {!enabled ? (
            <p className="subtitle" style={{ color: '#f6c16b' }}>
              Simulator отключен. Установите <code>VITE_SIMULATOR_ENABLED=true</code>.
            </p>
          ) : (
            <>
              <div className="simulator-toolbar">
                <label className="simulator-toolbar__item">
                  <span>Сценарий</span>
                  <select value={scenario} onChange={(e) => setScenario(e.target.value as typeof scenario)}>
                    {SCENARIOS.map((s) => (
                      <option key={s.key} value={s.key}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="ui-btn ui-btn--primary"
                  onClick={() => runMutation.mutate(scenario)}
                  disabled={runMutation.isPending}
                >
                  {runMutation.isPending ? 'Запуск…' : 'Запустить'}
                </button>
              </div>

              {runMutation.error && (
                <p className="subtitle" style={{ color: '#f07373' }}>
                  {(runMutation.error as Error).message}
                </p>
              )}

              {summary && (
                <div className="simulator-summary">
                  <div className="simulator-summary__item">
                    <span>Статус</span>
                    <strong>{summary.final_status || '—'}</strong>
                  </div>
                  <div className="simulator-summary__item">
                    <span>Шаги</span>
                    <strong>{summary.successful_steps || 0}/{summary.total_steps || 0}</strong>
                  </div>
                  <div className="simulator-summary__item">
                    <span>Ошибки</span>
                    <strong>{summary.failed_steps || 0}</strong>
                  </div>
                  <div className="simulator-summary__item">
                    <span>Длительность</span>
                    <strong>{fmtMs(summary.total_duration_ms)}</strong>
                  </div>
                </div>
              )}

              {steps.length > 0 && (
                <div className="simulator-steps">
                  {steps.map((step) => (
                    <article key={step.id} className={`simulator-step simulator-step--${step.status}`}>
                      <div className="simulator-step__head">
                        <strong>{step.step_order}. {step.title}</strong>
                        <span>{fmtMs(step.duration_ms)}</span>
                      </div>
                      <div className="subtitle">{step.step_key}</div>
                    </article>
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
