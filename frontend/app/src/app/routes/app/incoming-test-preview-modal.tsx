import { ModalPortal } from '@/shared/components/ModalPortal'
import type { CandidateDetail } from '@/api/services/candidates'

import { resolveTest1Section, resolveTestTone, TestScoreBar, formatDuration } from './incoming.utils'
import type { IncomingCandidate } from './incoming.types'

type IncomingTestPreviewModalProps = {
  candidate: IncomingCandidate
  detail?: CandidateDetail
  isLoading: boolean
  isError: boolean
  error: Error | null
  isMobile: boolean
  canSchedule: boolean
  onClose: () => void
  onSchedule: () => void
}

export function IncomingTestPreviewModal({
  candidate,
  detail,
  isLoading,
  isError,
  error,
  isMobile,
  canSchedule,
  onClose,
  onSchedule,
}: IncomingTestPreviewModalProps) {
  const test1Section = resolveTest1Section(detail)
  const stats = test1Section?.details?.stats
  const questions = test1Section?.details?.questions || []
  const correctAnswers = stats?.correct_answers ?? questions.filter((question) => question.is_correct).length
  const totalQuestions = stats?.total_questions ?? questions.length
  const showQuestions = questions.length > 0

  return (
    <ModalPortal>
      <div
        className="modal-overlay"
        onClick={(e) => e.target === e.currentTarget && onClose()}
        role="dialog"
        aria-modal="true"
        data-testid="incoming-test-preview-modal"
      >
        <div className={`glass glass--elevated modal modal--md ${isMobile ? 'modal--sheet' : ''}`} onClick={(e) => e.stopPropagation()}>
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Результат Теста 1</h2>
              <p className="modal__subtitle">{candidate.name || 'Кандидат'}</p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>
              Закрыть
            </button>
          </div>
          <div className="modal__body">
            {isLoading && <p className="subtitle">Загружаем результаты теста…</p>}
            {isError && <p className="text-danger">{error?.message || 'Не удалось загрузить результаты теста'}</p>}

            {!isLoading && !isError && test1Section && (
              <div className="cd-test-preview">
                <div className="cd-test-preview__hero">
                  <div className="cd-test-preview__hero-main">
                    <span className={`cd-chip cd-chip--${resolveTestTone(test1Section.status)}`}>
                      {test1Section.status_label || test1Section.status || 'Статус неизвестен'}
                    </span>
                    <h3>{test1Section.summary || 'Тест 1'}</h3>
                  </div>
                  {typeof stats?.total_time === 'number' ? (
                    <span className="cd-chip">{formatDuration(stats.total_time)}</span>
                  ) : null}
                </div>

                <TestScoreBar
                  correct={correctAnswers}
                  total={totalQuestions}
                  score={stats?.final_score}
                />

                {showQuestions ? (
                  <div className="cd-question-list">
                    {questions.map((question) => (
                      <div
                        key={`${candidate.id}-${question.question_index ?? question.question_text ?? 'question'}`}
                        className="cd-question-card"
                      >
                        <div className="cd-question-card__head">
                          <strong>{question.question_text}</strong>
                          <span className={`cd-chip cd-chip--${question.is_correct ? 'success' : 'danger'}`}>
                            {question.is_correct ? 'Верно' : 'Ошибка'}
                          </span>
                        </div>
                        {question.user_answer ? (
                          <div className="cd-question-card__answer">
                            <span>Ответ кандидата:</span>
                            <strong>{question.user_answer}</strong>
                          </div>
                        ) : null}
                        {question.correct_answer ? (
                          <div className="cd-question-card__answer">
                            <span>Ожидалось:</span>
                            <strong>{question.correct_answer}</strong>
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="subtitle">Детализация вопросов пока недоступна.</p>
                )}
              </div>
            )}
          </div>
          <div className="modal__footer">
            {canSchedule ? (
              <button
                className="ui-btn ui-btn--primary"
                data-testid="incoming-test-preview-schedule"
                onClick={onSchedule}
              >
                Предложить время
              </button>
            ) : null}
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>
              Закрыть
            </button>
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}
