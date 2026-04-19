import { useEffect } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'

import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import QuickNotes from '@/app/components/QuickNotes/QuickNotes'
import { ModalPortal } from '@/shared/components/ModalPortal'
import { fadeIn, slideInRight } from '@/shared/motion'
import { formatDateTime } from '@/shared/utils/formatters'

import { useCandidateHh, type CandidateAiController } from './candidate-detail.api'
import { getHhSyncBadge } from './candidate-detail.constants'
import type { CandidateDetail } from './candidate-detail.types'

type CandidateDrawerProps = {
  candidateId: number
  candidate: CandidateDetail
  ai: CandidateAiController
  statusLabel: string
  isOpen: boolean
  onClose: () => void
  onOpenInterviewScript: () => void
  onInsertChatDraft: (text: string) => void
}

export function CandidateDrawer(props: CandidateDrawerProps) {
  const {
    candidateId,
    candidate,
    statusLabel,
    isOpen,
    onClose,
  } = props
  const reduceMotion = useReducedMotion()
  const hhSummaryQuery = useCandidateHh(candidateId, isOpen)

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  const hhSummary = hhSummaryQuery.data
  const hhBadge = getHhSyncBadge(hhSummary?.sync_status ?? candidate.hh_sync_status)
  const hhUrl = hhSummary?.resume?.url || candidate.hh_profile_url || null
  const hhTitle = hhSummary?.resume?.title || candidate.hh_resume_id || 'Резюме не привязано'
  let hhMeta = 'HH-связка ещё не настроена'
  if (hhSummary?.linked && hhSummary?.last_hh_sync_at) {
    hhMeta = `Синхронизировано ${formatDateTime(hhSummary.last_hh_sync_at)}`
  } else if (hhSummary?.linked) {
    hhMeta = 'HH-связка активна'
  } else if (hhUrl) {
    hhMeta = 'Есть ссылка на профиль кандидата'
  }
  const quickNotesStorageKey = `candidate-quick-notes:${candidateId}`
  let hhBadgeClassName: string | null = null
  if (hhBadge?.tone === 'success') hhBadgeClassName = 'cd-chip cd-chip--success'
  else if (hhBadge?.tone === 'danger') hhBadgeClassName = 'cd-chip cd-chip--danger'
  else if (hhBadge?.tone === 'warning') hhBadgeClassName = 'cd-chip cd-chip--warning'
  else if (hhBadge) hhBadgeClassName = 'cd-chip cd-chip--accent'

  return (
    <ModalPortal>
      <AnimatePresence>
        {isOpen ? (
          <motion.div
            className="drawer-overlay candidate-drawer-overlay candidate-drawer-overlay--insights"
            onClick={(event) => event.target === event.currentTarget && onClose()}
            initial={reduceMotion ? false : fadeIn.initial}
            animate={reduceMotion ? undefined : fadeIn.animate}
            exit={reduceMotion ? undefined : fadeIn.exit}
            transition={reduceMotion ? { duration: 0 } : fadeIn.transition}
          >
            <motion.aside
              className="candidate-chat-drawer candidate-drawer candidate-insights-drawer glass"
              onClick={(event) => event.stopPropagation()}
              data-testid="candidate-insights-drawer"
              initial={reduceMotion ? false : slideInRight.initial}
              animate={reduceMotion ? undefined : slideInRight.animate}
              exit={reduceMotion ? undefined : slideInRight.exit}
              transition={reduceMotion ? { duration: 0 } : slideInRight.transition}
            >
              <header className="candidate-chat-drawer__header candidate-drawer__header">
                <div className="candidate-drawer__headline">
                  <h3 className="candidate-chat-drawer__title">Заметки по кандидату</h3>
                  <p className="subtitle candidate-drawer__subtitle">
                    {candidate.fio || `Кандидат #${candidateId}`}{' '}
                    <span className="candidate-drawer__subtitle-separator">·</span>{' '}
                    {statusLabel}
                  </p>
                </div>
                <button type="button" className="ui-btn ui-btn--ghost" onClick={onClose}>
                  Закрыть
                </button>
              </header>

              <div className="candidate-chat-drawer__body candidate-drawer__body candidate-insights-drawer__body">
                <QuickNotes storageKey={quickNotesStorageKey} />

                <section
                  className="glass panel candidate-insights-drawer__section candidate-insights-drawer__section--mini-hh"
                  data-testid="candidate-insights-hh"
                >
                  <div className="cd-section-header">
                    <div>
                      <h2 className="cd-section-title">HeadHunter</h2>
                      <p className="subtitle candidate-insights-mini-hh__caption">
                        Короткий доступ к резюме без лишней аналитики.
                      </p>
                    </div>
                    {hhUrl ? (
                      <a
                        href={hhUrl}
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Открыть в HH
                      </a>
                    ) : null}
                  </div>

                  {hhSummaryQuery.isPending ? (
                    <div className="ui-state ui-state--loading">
                      <p className="ui-state__text">Загружаю краткую HH-сводку…</p>
                    </div>
                  ) : hhSummaryQuery.isError ? (
                    <ApiErrorBanner
                      title="Не удалось загрузить HH-сводку"
                      error={hhSummaryQuery.error}
                      onRetry={() => hhSummaryQuery.refetch()}
                    />
                  ) : (
                    <div className="candidate-insights-mini-hh">
                      <div className="candidate-insights-mini-hh__top">
                        <div className="candidate-insights-mini-hh__identity">
                          <div className="candidate-insights-mini-hh__title">{hhTitle}</div>
                          <div className="candidate-insights-mini-hh__meta">{hhMeta}</div>
                        </div>
                        {hhBadge && hhBadgeClassName ? (
                          <span className={hhBadgeClassName}>
                            {hhBadge.label}
                          </span>
                        ) : null}
                      </div>

                      <div className="candidate-insights-mini-hh__facts">
                        {hhSummary?.vacancy?.title ? (
                          <span className="cd-chip cd-chip--small">{hhSummary.vacancy.title}</span>
                        ) : null}
                        {hhSummary?.vacancy?.area_name ? (
                          <span className="cd-chip cd-chip--small">{hhSummary.vacancy.area_name}</span>
                        ) : null}
                        {!hhSummary?.linked && !hhUrl ? (
                          <span className="cd-chip cd-chip--small">Нет HH-профиля</span>
                        ) : null}
                      </div>

                      {hhSummary?.sync_error ? (
                        <p className="subtitle subtitle--danger candidate-insights-mini-hh__error">
                          Ошибка синхронизации: {hhSummary.sync_error}
                        </p>
                      ) : null}
                    </div>
                  )}
                </section>
              </div>
            </motion.aside>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </ModalPortal>
  )
}
