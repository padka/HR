import { useEffect, useState } from 'react'

type QuickNotesProps = {
  storageKey: string
}

type StoredQuickNote = {
  text: string
  savedAt: string | null
}

function readStoredNote(key: string): StoredQuickNote {
  if (typeof window === 'undefined') return { text: '', savedAt: null }
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return { text: '', savedAt: null }
    const parsed = JSON.parse(raw) as StoredQuickNote
    return {
      text: String(parsed.text || ''),
      savedAt: parsed.savedAt || null,
    }
  } catch {
    return { text: '', savedAt: null }
  }
}

export default function QuickNotes({ storageKey }: QuickNotesProps) {
  const [text, setText] = useState('')
  const [savedAt, setSavedAt] = useState<string | null>(null)
  const savedAtLabel = savedAt
    ? `Сохранено ${new Date(savedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`
    : 'Автосохранение'

  useEffect(() => {
    const stored = readStoredNote(storageKey)
    setText(stored.text)
    setSavedAt(stored.savedAt)
  }, [storageKey])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const timeout = window.setTimeout(() => {
      const payload = {
        text,
        savedAt: new Date().toISOString(),
      }
      window.localStorage.setItem(storageKey, JSON.stringify(payload))
      setSavedAt(payload.savedAt)
    }, 1000)
    return () => window.clearTimeout(timeout)
  }, [storageKey, text])

  return (
    <section className="glass panel candidate-insights-drawer__section candidate-insights-drawer__section--notes">
      <div className="quick-notes">
        <div className="quick-notes__surface" data-testid="candidate-quick-notes-surface">
          <div className="quick-notes__header">
            <div>
              <h2 className="cd-section-title">Заметки</h2>
              <p className="subtitle">Рабочий журнал рекрутера по кандидату.</p>
            </div>
            <span className="quick-notes__status">{savedAtLabel}</span>
          </div>

          {text.trim() ? (
            <div className="quick-notes__content" aria-label="Текст заметок">
              {text}
            </div>
          ) : (
            <div className="quick-notes__empty">
              Здесь будут заметки по кандидату. Используйте этот блок как короткий рабочий журнал рекрутера.
            </div>
          )}
        </div>

        <div className="quick-notes__composer" data-testid="candidate-quick-notes-composer">
          <textarea
            rows={4}
            maxLength={2000}
            className="quick-notes-textarea"
            placeholder="Напишите заметку…"
            value={text}
            onChange={(event) => setText(event.target.value)}
            data-testid="candidate-quick-notes"
          />

          <div className="quick-notes-meta">
            <span>Автосохранение включено</span>
            <span>{text.length}/2000</span>
          </div>
        </div>
      </div>
    </section>
  )
}
