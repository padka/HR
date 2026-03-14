import { useEffect, useMemo, useState } from 'react'

import { scorecardRecommendationLabel } from '@/shared/utils/labels'

import {
  buildJourneySteps,
  buildNextAction,
  fieldFormatAnswer,
  formatFullDateTime,
  priorityTone,
  scoreTone,
  testSection,
  threadAvatar,
  upcomingSlot,
} from './messenger.utils'
import type { AISummary, CandidateChatThread, CandidateChatWorkspaceState, CandidateDetail } from './messenger.types'

type ThreadDetailProps = {
  activeThread: CandidateChatThread
  detail?: CandidateDetail
  aiSummary?: AISummary | null
  workspace?: CandidateChatWorkspaceState | null
  onScheduleIntroDay: () => void
  onArchiveToggle: () => void
  archivePending: boolean
  onClose: () => void
}

export function ThreadDetail({
  activeThread,
  detail,
  aiSummary,
  workspace,
  onScheduleIntroDay,
  onArchiveToggle,
  archivePending,
  onClose,
}: ThreadDetailProps) {
  const slot = upcomingSlot(detail)
  const journey = useMemo(() => buildJourneySteps(activeThread, detail), [activeThread, detail])
  const nextAction = useMemo(() => buildNextAction(activeThread, detail, aiSummary, workspace), [activeThread, aiSummary, detail, workspace])
  const [expandedStageKey, setExpandedStageKey] = useState<string | null>(journey.find((item) => item.state === 'active' || item.state === 'declined')?.key || journey[0]?.key || null)

  useEffect(() => {
    setExpandedStageKey(journey.find((item) => item.state === 'active' || item.state === 'declined')?.key || journey[0]?.key || null)
  }, [activeThread.candidate_id, journey])

  const scoreValue =
    typeof aiSummary?.scorecard?.final_score === 'number'
      ? `${Math.round(aiSummary.scorecard.final_score)}/100`
      : typeof activeThread.relevance_score === 'number'
        ? `${Math.round(activeThread.relevance_score)}/100`
        : activeThread.relevance_level || '—'
  const scoreToneValue =
    typeof aiSummary?.scorecard?.final_score === 'number'
      ? scoreTone(aiSummary.scorecard.final_score, null)
      : scoreTone(activeThread.relevance_score, activeThread.relevance_level)
  const recommendationLabel = scorecardRecommendationLabel(aiSummary?.scorecard?.recommendation || null)
  const currentStage = journey.find((item) => item.state === 'active' || item.state === 'declined')?.label || detail?.workflow_status_label || activeThread.status_label || 'В работе'
  const primaryRisk = aiSummary?.risks?.[0]
  const riskTone = primaryRisk?.severity === 'high' ? 'danger' : primaryRisk?.severity === 'medium' ? 'warning' : primaryRisk?.severity === 'low' ? 'info' : priorityTone(activeThread.priority_bucket)
  const riskLabel = primaryRisk?.label || activeThread.risk_hint || 'Критичных рисков не зафиксировано'
  const fieldMetric = aiSummary?.scorecard?.metrics?.find((item) => item.key === 'field_format_readiness')
  const fieldAnswer = fieldFormatAnswer(detail)
  const fieldTone =
    fieldMetric?.status === 'met' ? 'success' : fieldMetric?.status === 'not_met' ? 'danger' : fieldMetric?.status === 'unknown' ? 'warning' : 'neutral'
  const t1 = testSection(detail, 'test1')
  const t2 = testSection(detail, 'test2')
  const primaryButton =
    nextAction.ctaKind === 'intro_day' ? (
      <button className="ui-btn ui-btn--primary" onClick={onScheduleIntroDay}>
        {nextAction.ctaLabel || (slot?.purpose === 'intro_day' ? 'Обновить ОД' : 'Назначить ОД')}
      </button>
    ) : nextAction.ctaKind === 'profile' && activeThread.profile_url ? (
      <a className="ui-btn ui-btn--primary" href={activeThread.profile_url}>
        {nextAction.ctaLabel || 'Открыть карточку'}
      </a>
    ) : nextAction.ctaKind === 'archive' ? (
      <button className="ui-btn ui-btn--primary" onClick={onArchiveToggle} disabled={archivePending}>
        {archivePending ? 'Сохраняем…' : nextAction.ctaLabel || (activeThread.is_archived ? 'Вернуть из архива' : 'В архив')}
      </button>
    ) : null

  return (
    <div className="drawer-overlay" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <aside className="glass messenger-details-drawer" data-testid="messenger-details-drawer" onClick={(event) => event.stopPropagation()}>
        <header className="messenger-details-drawer__header">
          <div>
            <div className="messenger-card__eyebrow">Детали кандидата</div>
            <h3 className="messenger-details-drawer__title">{activeThread.title}</h3>
          </div>
          <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={onClose}>
            Закрыть
          </button>
        </header>

        <div className="messenger-details-drawer__body">
          <section className="messenger-card messenger-card--context messenger-detail-hero">
            <div className="messenger-detail-hero__top">
              <div className="messenger-context__identity">
                <div className="messenger-thread-card__avatar messenger-context__avatar">{threadAvatar(activeThread)}</div>
                <div className="messenger-context__identity-main">
                  <strong>{activeThread.title}</strong>
                  <span>{detail?.city || activeThread.city || 'Город не указан'}</span>
                  <span>{currentStage}</span>
                </div>
              </div>
              <div className="messenger-detail-hero__score">
                <span className={`messenger-tone-badge is-${scoreToneValue}`}>AI {scoreValue}</span>
                <span className="messenger-card__meta">{recommendationLabel}</span>
              </div>
            </div>
            <div className="messenger-detail-hero__stats">
              <div className="messenger-detail-stat">
                <span>Статус</span>
                <strong>{detail?.workflow_status_label || activeThread.status_label || 'В работе'}</strong>
              </div>
              <div className="messenger-detail-stat">
                <span>Риск</span>
                <strong className={`is-${riskTone}`}>{riskLabel}</strong>
              </div>
              <div className="messenger-detail-stat">
                <span>Последняя активность</span>
                <strong>{formatFullDateTime(activeThread.last_message_at || activeThread.created_at)}</strong>
              </div>
            </div>
          </section>

          <section className="messenger-card messenger-card--action">
            <div className="messenger-card__header">
              <span className="messenger-card__eyebrow">Что делать дальше</span>
              <span className={`messenger-tone-badge is-${nextAction.tone}`}>{currentStage}</span>
            </div>
            <strong className="messenger-card__title">{nextAction.label}</strong>
            <p className="messenger-card__text">{nextAction.reason}</p>
            <div className={`messenger-mini-banner is-${nextAction.tone}`}>
              <strong>После этого</strong>
              <span>{nextAction.outcome}</span>
            </div>
            <div className="messenger-details-drawer__actions">
              {primaryButton}
              {nextAction.ctaKind === 'none' ? <div className="messenger-empty-inline">Основное действие выполняется прямо в текущем чате или через карточку кандидата.</div> : null}
              <div className="messenger-card__actions">
                {activeThread.profile_url && nextAction.ctaKind !== 'profile' ? (
                  <a className="ui-btn ui-btn--ghost" href={activeThread.profile_url}>
                    Карточка кандидата
                  </a>
                ) : null}
                <button className="ui-btn ui-btn--ghost" onClick={onArchiveToggle} disabled={archivePending}>
                  {archivePending ? 'Сохраняем…' : activeThread.is_archived ? 'Вернуть из архива' : 'В архив'}
                </button>
              </div>
            </div>
          </section>

          <section className="messenger-card" data-testid="messenger-candidate-journey">
            <div className="messenger-card__header">
              <span className="messenger-card__eyebrow">Путь кандидата</span>
              <span className="messenger-card__meta">Текущий этап: {currentStage}</span>
            </div>
            <div className="messenger-journey">
              {journey.map((item, index) => {
                const isOpen = expandedStageKey === item.key
                return (
                  <button
                    key={item.key || index}
                    type="button"
                    className={`messenger-journey__step is-${item.state} ${isOpen ? 'is-open' : ''}`}
                    onClick={() => setExpandedStageKey((current) => (current === item.key ? null : item.key))}
                  >
                    <div className="messenger-journey__rail">
                      <span className="messenger-journey__dot" />
                      {index < journey.length - 1 ? <span className="messenger-journey__line" /> : null}
                    </div>
                    <div className="messenger-journey__content">
                      <div className="messenger-journey__head">
                        <strong>{item.label}</strong>
                        <span>{item.state === 'passed' ? 'Завершён' : item.state === 'active' ? 'Текущий' : item.state === 'declined' ? 'Проблема' : 'Ожидает'}</span>
                      </div>
                      <div className="messenger-journey__headline">{item.headline}</div>
                      {isOpen ? (
                        <div className="messenger-journey__details">
                          {item.detailLines.map((line) => (
                            <div key={line} className="messenger-journey__detail-line">{line}</div>
                          ))}
                          <div className="messenger-journey__next">Дальше: {item.nextHint}</div>
                        </div>
                      ) : null}
                    </div>
                  </button>
                )
              })}
            </div>
          </section>

          <section className="messenger-card" data-testid="messenger-candidate-analytics">
            <div className="messenger-card__header">
              <span className="messenger-card__eyebrow">Аналитика</span>
              <span className="messenger-card__meta">Только полезные сигналы для решения</span>
            </div>
            <div className="messenger-analytics-grid">
              <div className="messenger-analytics-tile">
                <span>Релевантность</span>
                <strong>AI {scoreValue}</strong>
                <p>{aiSummary?.fit?.rationale || aiSummary?.tldr || 'Сводка AI пока недоступна.'}</p>
              </div>
              <div className={`messenger-analytics-tile is-${fieldTone}`}>
                <span>Полевой формат</span>
                <strong>
                  {fieldMetric?.status === 'met'
                    ? 'Подтверждён'
                    : fieldMetric?.status === 'not_met'
                      ? 'Есть стоп-фактор'
                      : 'Нужно уточнение'}
                </strong>
                <p>{fieldMetric?.evidence || 'AI ещё не дал явного вывода по формату.'}</p>
                {fieldAnswer ? <div className="messenger-inline-chip">Ответ кандидата: {fieldAnswer}</div> : null}
              </div>
              <div className="messenger-analytics-tile">
                <span>Тест 1</span>
                <strong>{t1?.status_label || 'Нет данных'}</strong>
                <p>{t1?.summary || 'Тест 1 ещё не найден.'}</p>
              </div>
              <div className="messenger-analytics-tile">
                <span>Тест 2 / ОД</span>
                <strong>{t2?.status_label || (detail?.can_schedule_intro_day ? 'Можно назначать ОД' : 'Ещё рано')}</strong>
                <p>{t2?.summary || (detail?.can_schedule_intro_day ? 'Следующий этап можно открывать.' : 'Следующий этап пока не активен.')}</p>
              </div>
            </div>
            {aiSummary?.risks?.length ? (
              <div className="messenger-risk-list">
                {aiSummary.risks.slice(0, 3).map((item) => (
                  <div key={item.key} className={`messenger-risk-item is-${item.severity === 'high' ? 'danger' : item.severity === 'medium' ? 'warning' : 'info'}`}>
                    <strong>{item.label}</strong>
                    <span>{item.explanation}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </section>
        </div>
      </aside>
    </div>
  )
}
