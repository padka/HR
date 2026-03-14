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
    <section className="glass panel candidate-insights-drawer__section">
      <div className="cd-section-header">
        <div>
          <h2 className="cd-section-title">Быстрые заметки</h2>
          <p className="subtitle">Локальные заметки рекрутера по кандидату.</p>
        </div>
        <span className="subtitle">{savedAt ? `Сохранено ${new Date(savedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}` : 'Автосохранение'}</span>
      </div>

      <textarea
        rows={6}
        maxLength={2000}
        className="ui-input ui-input--multiline"
        placeholder="Заметки по кандидату..."
        value={text}
        onChange={(event) => setText(event.target.value)}
        data-testid="candidate-quick-notes"
      />

      <div className="toolbar toolbar--compact">
        <span className="subtitle">{text.length}/2000</span>
      </div>
    </section>
  )
}
