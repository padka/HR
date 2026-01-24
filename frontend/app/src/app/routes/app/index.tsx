export function IndexPage() {
  return (
    <div className="page">
      <div className="glass panel" style={{ display: 'grid', gap: 12 }}>
        <h1 className="title">Главная SPA</h1>
        <p className="subtitle">Используйте меню сверху, чтобы открыть разделы. В первую очередь переносим «Слоты».</p>
        <p className="subtitle" style={{ margin: 0 }}>Сейчас доступны: список слотов, карточки, sheet, фильтры, пагинация, быстрая форма создания.</p>
      </div>
    </div>
  )
}
