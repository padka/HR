import ScriptNotes from './ScriptNotes'
import RatingScale from './RatingScale'
import type { InterviewScriptQuestionView } from './script.types'

type ScriptQuestionProps = {
  question: InterviewScriptQuestionView
  index: number
  total: number
  notes: string
  rating: number | null
  skipped: boolean
  onNotesChange: (value: string) => void
  onRatingChange: (value: number) => void
  onSkip: () => void
  onNext: () => void
}

export default function ScriptQuestion({
  question,
  index,
  total,
  notes,
  rating,
  skipped,
  onNotesChange,
  onRatingChange,
  onSkip,
  onNext,
}: ScriptQuestionProps) {
  return (
    <div className={`interview-script__surface ${skipped ? 'interview-script__surface--muted' : ''}`}>
      <div className="interview-script__question-head">
        <div className="interview-script__eyebrow">
          Q{index + 1} из {total}
        </div>
        <div className="interview-script__duration">~{question.estimatedMinutes} мин</div>
      </div>

      <h3 className="interview-script__question-title">{question.text}</h3>

      <div className="interview-script__card-grid">
        <div className="interview-script__callout">
          <div className="interview-script__callout-label">Зачем спрашиваем</div>
          <p>{question.why}</p>
        </div>
        <div className="interview-script__callout interview-script__callout--positive">
          <div className="interview-script__callout-label">Хороший ответ</div>
          <p>{question.goodAnswer}</p>
        </div>
        <div className="interview-script__callout interview-script__callout--danger">
          <div className="interview-script__callout-label">Красные флаги</div>
          <p>{question.redFlags}</p>
        </div>
      </div>

      <ScriptNotes value={notes} onChange={onNotesChange} />

      <div className="interview-script__question-footer">
        <div>
          <div className="interview-script__stack-title">Оценка ответа</div>
          <RatingScale value={rating} onChange={onRatingChange} />
        </div>
        <div className="interview-script__question-actions">
          <button type="button" className="ui-btn ui-btn--ghost" onClick={onSkip}>
            {skipped ? 'Вернуть вопрос' : 'Пропустить'}
          </button>
          <button type="button" className="ui-btn ui-btn--primary" onClick={onNext}>
            Далее
          </button>
        </div>
      </div>
    </div>
  )
}
