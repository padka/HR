type ScriptNotesProps = {
  value: string
  onChange: (value: string) => void
}

export default function ScriptNotes({ value, onChange }: ScriptNotesProps) {
  return (
    <label className="interview-script__notes">
      <span className="interview-script__notes-label">Заметки рекрутера</span>
      <textarea
        rows={5}
        className="ui-input ui-input--multiline interview-script__notes-input"
        placeholder="Что важно зафиксировать по этому ответу?"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}
