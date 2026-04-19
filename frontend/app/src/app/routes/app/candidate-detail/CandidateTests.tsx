import type { Ref } from 'react'
import type { TestAttempt, TestSection } from '@/api/services/candidates'
import { formatDateTime } from '@/shared/utils/formatters'

type CandidateTestsProps = {
  testSections: TestSection[]
  onOpenReportPreview: (title: string, url: string) => void
  onOpenAttemptPreview: (testTitle: string, attempt: TestAttempt) => void
  sectionRef?: Ref<HTMLDivElement>
  embedded?: boolean
}

export function TestScoreBar({ correct, total, score }: { correct: number; total: number; score?: number | null }) {
  const pct = total > 0 ? Math.round((correct / total) * 100) : 0
  const tone = pct >= 70 ? 'success' : pct >= 40 ? 'warning' : 'danger'
  const scoreValue = typeof score === 'number' ? Math.round(score) : pct

  return (
    <div className="cd-score">
      <div className="cd-score__header">
        <div className="cd-score__value">
          {scoreValue}
          <span>%</span>
        </div>
        <div className="cd-score__text">
          Верных ответов {correct}/{total}
          {typeof score === 'number' && <span className="cd-score__final">Итоговый балл {score.toFixed(1)}</span>}
        </div>
      </div>
      <div className="cd-score__bar">
        <div className={`cd-score__fill cd-score__fill--${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function CandidateTests({
  testSections,
  onOpenReportPreview,
  onOpenAttemptPreview,
  sectionRef,
  embedded = false,
}: CandidateTestsProps) {
  return (
    <div
      id="tests"
      ref={sectionRef}
      className={embedded ? 'cd-tests-panel' : 'cd-profile__section'}
      data-testid="candidate-tests-section"
    >
      {!embedded ? (
        <div className="cd-section-header">
          <h2 className="cd-section-title">Тесты</h2>
        </div>
      ) : null}
      {testSections.length === 0 && <p className="subtitle">Данные по тестам отсутствуют.</p>}
      {testSections.length > 0 && (
        <div className="cd-tests-grid">
          {testSections.map((section) => (
            <div key={section.key} className="cd-test-card">
              <div className="cd-test-card__header">
                <div className="cd-test-card__heading">
                  <span className="cd-test-card__title">{section.title}</span>
                  {section.summary && <div className="cd-test-card__summary">{section.summary}</div>}
                </div>
                <span className={`cd-test-status cd-test-status--${section.status || 'unknown'}`}>
                  {section.status_label || section.status || '—'}
                </span>
              </div>
              {section.details?.stats && (
                <TestScoreBar
                  correct={section.details.stats.correct_answers ?? 0}
                  total={section.details.stats.total_questions ?? 0}
                  score={section.details.stats.final_score}
                />
              )}
              {section.details?.stats && (
                <div className="cd-test-card__extra">
                  {typeof section.details.stats.total_time === 'number' && (
                    <span>Время: {Math.round(section.details.stats.total_time / 60)} мин</span>
                  )}
                  {typeof section.details.stats.overtime_questions === 'number' && section.details.stats.overtime_questions > 0 && (
                    <span>Просрочено: {section.details.stats.overtime_questions}</span>
                  )}
                </div>
              )}
              {section.report_url && (
                <button
                  type="button"
                  className="cd-test-card__report"
                  onClick={() => onOpenReportPreview(section.title || 'Отчёт', section.report_url || '')}
                >
                  Подробный отчёт
                </button>
              )}
              {section.history && section.history.length > 1 && (
                <details className="cd-test-card__history">
                  <summary>История попыток ({section.history.length})</summary>
                  <div className="cd-test-card__history-list">
                    {section.history.map((attempt) => (
                      <button
                        key={attempt.id}
                        type="button"
                        className="cd-test-card__history-item cd-test-card__history-item--button"
                        onClick={() => onOpenAttemptPreview(section.title, attempt)}
                      >
                        <span>{formatDateTime(attempt.completed_at)}</span>
                        <span>{typeof attempt.final_score === 'number' ? attempt.final_score.toFixed(1) : '—'}</span>
                        {attempt.source && <span className="cd-chip cd-chip--small">{attempt.source}</span>}
                        <span className="cd-test-card__history-link">Открыть</span>
                      </button>
                    ))}
                  </div>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
