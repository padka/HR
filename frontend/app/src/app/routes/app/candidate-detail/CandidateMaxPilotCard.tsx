import type { CandidateMaxRollout, CandidateMaxRolloutAction } from '@/api/services/candidates'
import { formatDateTime } from '@/shared/utils/formatters'
import { formatMaxRolloutStatus } from './candidate-detail.constants'
import { resolveMaxRolloutAction, resolveMaxRolloutPreview } from './candidate-detail.utils'

type CandidateMaxPilotCardProps = {
  rollout: CandidateMaxRollout
  actionPending: boolean
  onPreview: () => void
  onActionClick: (action: CandidateMaxRolloutAction) => void
}

export function CandidateMaxPilotCard({
  rollout,
  actionPending,
  onPreview,
  onActionClick,
}: CandidateMaxPilotCardProps) {
  const preview = resolveMaxRolloutPreview(rollout)
  const sendAction = resolveMaxRolloutAction(rollout, 'send')
  const reissueAction = resolveMaxRolloutAction(rollout, 'reissue')
  const revokeAction = resolveMaxRolloutAction(rollout, 'revoke')
  const launchObserved = rollout.launch_state === 'launched' || Boolean(rollout.launch_observation?.launched)
  const launchedAt = formatDateTime(rollout.launch_observation?.launched_at)
  const hasPreviewContent = Boolean(
    preview?.message_preview || preview?.max_launch_url || preview?.max_chat_url,
  )
  const previewAction = resolveMaxRolloutAction(rollout, 'preview')
  const canPreview = hasPreviewContent || Boolean(previewAction)

  return (
    <section className="cd-profile__section cd-detail-section" data-testid="candidate-detail-max-pilot">
      <div className="cd-section-header">
        <div>
          <h2 className="cd-section-title">Пилот MAX</h2>
          <p className="subtitle subtitle--mt-0">
            {rollout.summary || rollout.hint || 'Контроль выдачи доступа к mini-приложению MAX в операторском сценарии.'}
          </p>
        </div>
        {(rollout.status_label || rollout.status) ? (
          <span className="cd-chip cd-chip--info">{formatMaxRolloutStatus(rollout.status, rollout.status_label)}</span>
        ) : null}
      </div>

      <div className="cd-hh-panel__grid">
        <div className="cd-hh-card">
          <div className="cd-hh-card__label">Статус</div>
          <div className="cd-hh-card__value">{formatMaxRolloutStatus(rollout.status, rollout.status_label)}</div>
        </div>
        <div className="cd-hh-card">
          <div className="cd-hh-card__label">Событие</div>
          <div className="cd-hh-card__value">{formatDateTime(rollout.issued_at || rollout.sent_at) || '—'}</div>
        </div>
        <div className="cd-hh-card">
          <div className="cd-hh-card__label">Истекает</div>
          <div className="cd-hh-card__value">{formatDateTime(preview?.expires_at || rollout.expires_at) || '—'}</div>
        </div>
        <div className="cd-hh-card">
          <div className="cd-hh-card__label">Режим</div>
          <div className="cd-hh-card__value">{preview?.dry_run || rollout.dry_run ? 'Проверка' : 'Боевой'}</div>
        </div>
        <div className="cd-hh-card" data-testid="candidate-detail-max-pilot-launch">
          <div className="cd-hh-card__label">Запуск mini-приложения</div>
          <div className="cd-hh-card__value">
            {launchObserved ? 'Кандидат открыл mini-приложение MAX' : 'Кандидат ещё не открывал mini-приложение MAX'}
          </div>
          {launchObserved && launchedAt ? (
            <div className="subtitle">{launchedAt}</div>
          ) : null}
        </div>
      </div>

      {rollout.flow_statuses?.length ? (
        <div className="cd-hh-panel__grid" data-testid="candidate-detail-max-pilot-flow-statuses">
          {rollout.flow_statuses.map((item) => (
            <div key={item.key || item.label} className="cd-hh-card">
              <div className="cd-hh-card__label">{item.label || item.key || 'MAX'}</div>
              <div className="cd-hh-card__value">{item.status_label || item.status || '—'}</div>
              {item.detail ? <div className="subtitle">{item.detail}</div> : null}
            </div>
          ))}
        </div>
      ) : null}

      <div className="toolbar toolbar--compact" data-testid="candidate-detail-max-pilot-actions">
        <button
          type="button"
          className="ui-btn ui-btn--ghost ui-btn--sm"
          onClick={onPreview}
          disabled={!canPreview || actionPending}
        >
          Предпросмотр
        </button>
        {sendAction ? (
          <button
            type="button"
            className="ui-btn ui-btn--primary ui-btn--sm"
            onClick={() => onActionClick(sendAction)}
            disabled={actionPending}
          >
            Отправить
          </button>
        ) : null}
        {reissueAction ? (
          <button
            type="button"
            className="ui-btn ui-btn--ghost ui-btn--sm"
            onClick={() => onActionClick(reissueAction)}
            disabled={actionPending}
          >
            Перевыпустить
          </button>
        ) : null}
        {revokeAction ? (
          <button
            type="button"
            className="ui-btn ui-btn--ghost ui-btn--sm"
            onClick={() => onActionClick(revokeAction)}
            disabled={actionPending}
          >
            Отозвать
          </button>
        ) : null}
      </div>
    </section>
  )
}
