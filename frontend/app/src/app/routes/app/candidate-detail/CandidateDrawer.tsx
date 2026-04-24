import { useEffect } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'

import QuickNotes from '@/app/components/QuickNotes/QuickNotes'
import { ModalPortal } from '@/shared/components/ModalPortal'
import { fadeIn, slideInRight } from '@/shared/motion'

import type { CandidateDetail } from './candidate-detail.types'

type CandidateDrawerProps = {
  candidateId: number
  candidate: CandidateDetail
  statusLabel: string
  isOpen: boolean
  onClose: () => void
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
  const quickNotesStorageKey = `candidate-quick-notes:${candidateId}`

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

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
                <section
                  className="glass panel candidate-insights-drawer__section"
                  data-testid="candidate-insights-notes"
                >
                  <QuickNotes storageKey={quickNotesStorageKey} />
                </section>
              </div>
            </motion.aside>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </ModalPortal>
  )
}
