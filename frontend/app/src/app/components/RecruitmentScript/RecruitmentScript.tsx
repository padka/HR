import { useCallback, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { buildScriptSections, type AiInsightsData, type ScriptBlock, type ScriptSection } from './script-sections'
import './recruitment-script.css'

type RecruitmentScriptProps = {
  isOpen: boolean
  candidateName: string
  aiData?: AiInsightsData | null
  onClose: () => void
}

function ScriptBlockView({ block }: { block: ScriptBlock }) {
  switch (block.type) {
    case 'speech':
      return <p className="rs-block rs-block--speech">{block.text}</p>
    case 'prompt':
      return (
        <div className="rs-block rs-block--prompt">
          <span className="rs-block__prompt-icon">?</span>
          <p>{block.text}</p>
        </div>
      )
    case 'note':
      return <p className="rs-block rs-block--note">{block.text}</p>
    case 'ai-hint':
      return (
        <div className="rs-block rs-block--ai-hint">
          <span className="rs-block__ai-icon">{block.icon}</span>
          <div className="rs-block__ai-body">
            <span className="rs-block__ai-label">{block.label}</span>
            <span className="rs-block__ai-text">{block.text}</span>
          </div>
        </div>
      )
    case 'branch':
      return (
        <div className="rs-block rs-block--branch">
          {block.options.map((opt) => (
            <div key={opt.label} className="rs-branch-option">
              <span className="rs-branch-option__label">{opt.label}:</span>
              <span className="rs-branch-option__text">{opt.text}</span>
            </div>
          ))}
        </div>
      )
    case 'divider':
      return <hr className="rs-divider" />
    default:
      return null
  }
}

function ScriptSectionView({
  section,
  isOpen,
  onToggle,
  hasAiHints,
}: {
  section: ScriptSection
  isOpen: boolean
  onToggle: () => void
  hasAiHints: boolean
}) {
  return (
    <div className={`rs-section ${isOpen ? 'rs-section--open' : ''}`}>
      <button type="button" className="rs-section__header" onClick={onToggle}>
        <span className="rs-section__step">{section.step}</span>
        <span className="rs-section__title">{section.title}</span>
        {hasAiHints && <span className="rs-section__ai-badge">AI</span>}
        {section.duration && <span className="rs-section__duration">{section.duration}</span>}
        <span className="rs-section__chevron">{isOpen ? '−' : '+'}</span>
      </button>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            className="rs-section__body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
          >
            <div className="rs-section__content">
              {section.blocks.map((block, i) => (
                <ScriptBlockView key={i} block={block} />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function RecruitmentScript({ isOpen, candidateName, aiData, onClose }: RecruitmentScriptProps) {
  const sections = useMemo(() => buildScriptSections(candidateName, aiData), [candidateName, aiData])
  const [openSections, setOpenSections] = useState<Set<string>>(() => new Set(['opening']))

  const hasAnyAi = useMemo(
    () => sections.some((s) => s.blocks.some((b) => b.type === 'ai-hint')),
    [sections],
  )

  const toggleSection = useCallback((id: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const expandAll = useCallback(() => {
    setOpenSections(new Set(sections.map((s) => s.id)))
  }, [sections])

  const collapseAll = useCallback(() => {
    setOpenSections(new Set())
  }, [])

  useEffect(() => {
    if (!isOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isOpen, onClose])

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.aside
          className="recruitment-script"
          initial={{ opacity: 0, y: 24, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 24, scale: 0.96 }}
          transition={{ duration: 0.3, ease: [0.34, 1.56, 0.64, 1] }}
          role="complementary"
          aria-label="Скрипт собеседования"
        >
          <div className="recruitment-script__header">
            <div className="recruitment-script__title-row">
              <h3 className="recruitment-script__title">Скрипт собеседования</h3>
              <div className="recruitment-script__actions">
                <button type="button" className="rs-icon-btn" onClick={expandAll} title="Раскрыть все">
                  ↕
                </button>
                <button type="button" className="rs-icon-btn" onClick={collapseAll} title="Свернуть все">
                  ═
                </button>
                <button type="button" className="rs-icon-btn rs-icon-btn--close" onClick={onClose} title="Закрыть">
                  ✕
                </button>
              </div>
            </div>
            <div className="recruitment-script__meta">
              <span className="recruitment-script__subtitle">
                Smart Service &middot; {candidateName}
              </span>
              {hasAnyAi && <span className="recruitment-script__ai-tag">Адаптирован под кандидата</span>}
            </div>
          </div>
          <div className="recruitment-script__body">
            {sections.map((section) => (
              <ScriptSectionView
                key={section.id}
                section={section}
                isOpen={openSections.has(section.id)}
                onToggle={() => toggleSection(section.id)}
                hasAiHints={section.blocks.some((b) => b.type === 'ai-hint')}
              />
            ))}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}

export function ScriptFab({ isOpen, onClick }: { isOpen: boolean; onClick: () => void }) {
  return (
    <motion.button
      type="button"
      className={`script-fab ${isOpen ? 'script-fab--active' : ''}`}
      onClick={onClick}
      title={isOpen ? 'Закрыть скрипт' : 'Скрипт собеседования'}
      whileHover={{ scale: 1.06 }}
      whileTap={{ scale: 0.94 }}
    >
      <span className="script-fab__icon">📋</span>
      <span className="script-fab__label">{isOpen ? 'Закрыть' : 'Скрипт'}</span>
    </motion.button>
  )
}
