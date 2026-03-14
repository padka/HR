import { motion } from 'framer-motion'

import { INTERVIEW_RECOMMENDATION_LABELS } from './script.prompts'
import { scriptScorecardItemVariants } from './script.variants'
import type { InterviewScriptQuestionState, InterviewScriptViewModel } from './script.types'

type ScriptScorecardProps = {
  viewModel: InterviewScriptViewModel
  questionState: Record<string, InterviewScriptQuestionState>
  overallRecommendation: 'recommend' | 'doubt' | 'not_recommend'
  finalComment: string
  onRecommendationChange: (value: 'recommend' | 'doubt' | 'not_recommend') => void
  onCommentChange: (value: string) => void
  onSave: () => void
  isSaving: boolean
}

const RECOMMENDATION_OPTIONS: Array<'recommend' | 'doubt' | 'not_recommend'> = ['recommend', 'doubt', 'not_recommend']

export default function ScriptScorecard({
  viewModel,
  questionState,
  overallRecommendation,
  finalComment,
  onRecommendationChange,
  onCommentChange,
  onSave,
  isSaving,
}: ScriptScorecardProps) {
  const rated = viewModel.questions.filter((question) => !questionState[question.id]?.skipped && questionState[question.id]?.rating != null)
  const average = rated.length > 0
    ? rated.reduce((sum, question) => sum + Number(questionState[question.id]?.rating || 0), 0) / rated.length
    : null

  return (
    <div className="interview-script__surface">
      <div className="interview-script__eyebrow">После разговора</div>
      <h3 className="interview-script__section-title">Scorecard</h3>

      <div className="interview-script__score-summary">
        <div className="interview-script__score-metric">
          <span className="interview-script__metric-label">Средняя оценка</span>
          <strong className="interview-script__score-value">{average != null ? average.toFixed(1) : '—'}</strong>
        </div>
        <div className="interview-script__score-metric">
          <span className="interview-script__metric-label">Вопросов оценено</span>
          <strong className="interview-script__score-value">{rated.length}/{viewModel.questions.length}</strong>
        </div>
      </div>

      <div className="interview-script__score-grid">
        {viewModel.questions.map((question, index) => (
          <motion.div
            key={question.id}
            className="interview-script__score-item"
            custom={index}
            variants={scriptScorecardItemVariants}
            initial="hidden"
            animate="visible"
          >
            <div className="interview-script__score-item-title">{question.text}</div>
            <div className="interview-script__score-item-meta">
              {questionState[question.id]?.skipped
                ? 'Пропущен'
                : questionState[question.id]?.rating != null
                  ? `${questionState[question.id]?.rating}/5`
                  : 'Не оценён'}
            </div>
          </motion.div>
        ))}
      </div>

      <div className="interview-script__stack">
        <div className="interview-script__stack-title">Общее впечатление</div>
        <div className="interview-script__recommendations">
          {RECOMMENDATION_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              className={`interview-script__recommendation ${overallRecommendation === option ? 'interview-script__recommendation--active' : ''}`}
              onClick={() => onRecommendationChange(option)}
            >
              {INTERVIEW_RECOMMENDATION_LABELS[option]}
            </button>
          ))}
        </div>
      </div>

      <label className="interview-script__notes">
        <span className="interview-script__notes-label">Финальный комментарий</span>
        <textarea
          rows={5}
          className="ui-input ui-input--multiline interview-script__notes-input"
          placeholder="Что важно передать менеджеру или зафиксировать в карточке кандидата?"
          value={finalComment}
          onChange={(event) => onCommentChange(event.target.value)}
        />
      </label>

      <div className="interview-script__score-actions">
        <button type="button" className="ui-btn ui-btn--primary" onClick={onSave} disabled={isSaving}>
          {isSaving ? 'Сохраняем…' : 'Сохранить результат'}
        </button>
      </div>
    </div>
  )
}
