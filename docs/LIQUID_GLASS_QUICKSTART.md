# Liquid Glass Design System - Quick Start

## Что это?

**Liquid Glass** - современная дизайн-система в стиле Apple glassmorphism для recruitsmart_admin. Включает полупрозрачные поверхности, размытие фона, плавные анимации и интерактивные эффекты.

## 🚀 Быстрый старт (5 минут)

### 1. Файлы уже подключены

В `base.html` автоматически загружаются:

```html
<link rel="stylesheet" href="/static/css/liquid-glass.css">
<link rel="stylesheet" href="/static/css/liquid-glass-integration.css">
<script src="/static/js/modules/glass-effects.js" defer></script>
```

### 2. Базовое использование

#### Карточка

```html
<!-- Было -->
<div class="card glass grain">
  <h3>Заголовок</h3>
  <p>Контент</p>
</div>

<!-- Стало -->
<div class="liquid-glass-card" data-animate-in>
  <h3>Заголовок</h3>
  <p>Контент</p>
</div>
```

#### Кнопка

```html
<!-- Было -->
<button class="btn btn-primary">Сохранить</button>

<!-- Стало -->
<button class="liquid-glass-btn liquid-glass-btn--primary">Сохранить</button>
```

#### Badge

```html
<!-- Было -->
<span class="badge badge--soft">Статус</span>

<!-- Стало -->
<span class="liquid-glass-badge liquid-glass-badge--success">Статус</span>
```

#### Таблица

```html
<!-- Было -->
<table class="list-table">...</table>

<!-- Стало -->
<div class="liquid-glass-table">
  <table class="list-table">...</table>
</div>
```

### 3. Добавление эффектов

```html
<!-- Parallax эффект при наведении -->
<div class="liquid-glass-card liquid-glass-card--interactive" data-parallax>
  Контент с 3D эффектом
</div>

<!-- Анимация появления при скролле -->
<div class="liquid-glass-card" data-animate-in>
  Появится плавно
</div>

<!-- Пульсирующее свечение -->
<div class="liquid-glass-card" data-glow-pulse>
  Светится
</div>

<!-- Плавающая анимация -->
<div class="liquid-glass-card" data-float>
  Плавает
</div>
```

## 📦 Компоненты

### Cards

```html
<!-- Обычная -->
<div class="liquid-glass-card">...</div>

<!-- Elevated (выше z-index) -->
<div class="liquid-glass-card liquid-glass-card--elevated">...</div>

<!-- Subtle (менее заметная) -->
<div class="liquid-glass-card liquid-glass-card--subtle">...</div>

<!-- Interactive (с parallax) -->
<div class="liquid-glass-card liquid-glass-card--interactive" data-parallax>...</div>
```

### Buttons

```html
<!-- Варианты -->
<button class="liquid-glass-btn liquid-glass-btn--primary">Primary</button>
<button class="liquid-glass-btn liquid-glass-btn--purple">Purple</button>
<button class="liquid-glass-btn liquid-glass-btn--success">Success</button>
<button class="liquid-glass-btn liquid-glass-btn--ghost">Ghost</button>

<!-- Размеры -->
<button class="liquid-glass-btn liquid-glass-btn--sm">Small</button>
<button class="liquid-glass-btn">Default</button>
<button class="liquid-glass-btn liquid-glass-btn--lg">Large</button>
```

### Badges

```html
<span class="liquid-glass-badge liquid-glass-badge--success">Success</span>
<span class="liquid-glass-badge liquid-glass-badge--warning">Warning</span>
<span class="liquid-glass-badge liquid-glass-badge--danger">Danger</span>
<span class="liquid-glass-badge liquid-glass-badge--info">Info</span>
<span class="liquid-glass-badge liquid-glass-badge--purple">Purple</span>
<span class="liquid-glass-badge liquid-glass-badge--neutral">Neutral</span>
```

### Inputs

```html
<input type="text" class="liquid-glass-input" placeholder="Текст">
<select class="liquid-glass-input">
  <option>Опция 1</option>
</select>
<textarea class="liquid-glass-input" rows="4"></textarea>
```

## 🎨 Примеры готовых паттернов

### Статистическая карточка

```html
<div class="liquid-glass-card liquid-glass-card--interactive"
     data-parallax
     data-animate-in>
  <span class="slot-summary__label">Всего пользователей</span>
  <span class="slot-summary__value">1,234</span>
  <span class="liquid-glass-badge liquid-glass-badge--success">
    +15% за неделю
  </span>
</div>
```

### Форма

```html
<div class="liquid-glass-section">
  <h2>Регистрация</h2>

  <input type="text"
         class="liquid-glass-input"
         placeholder="Ваше имя">

  <input type="email"
         class="liquid-glass-input"
         placeholder="Email">

  <button class="liquid-glass-btn liquid-glass-btn--primary">
    Зарегистрироваться
  </button>
</div>
```

### Таблица с данными

```html
<div class="liquid-glass-table" data-animate-in>
  <table>
    <thead>
      <tr>
        <th>Название</th>
        <th>Статус</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Элемент 1</td>
        <td>
          <span class="liquid-glass-badge liquid-glass-badge--success">
            Активен
          </span>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

## 🎯 Data Attributes

| Атрибут | Эффект | Пример |
|---------|--------|--------|
| `data-parallax` | 3D tilt на hover | `<div class="liquid-glass-card" data-parallax>` |
| `data-animate-in` | Появление при скролле | `<div class="liquid-glass-card" data-animate-in>` |
| `data-glow-pulse` | Пульсирующее свечение | `<div class="liquid-glass-card" data-glow-pulse>` |
| `data-float` | Плавающая анимация | `<div data-float>` |
| `data-loading` | Shimmer loading | `<div class="liquid-glass-card" data-loading="true">` |

## 🔧 JavaScript API

```javascript
// Инициализация всех эффектов
window.LiquidGlass.init();

// Переинициализация (после AJAX)
window.LiquidGlass.refresh();

// Очистка всех эффектов
window.LiquidGlass.cleanup();
```

## 🎨 CSS Variables

### Blur

```css
--glass-blur-sm: 8px;
--glass-blur-md: 20px;
--glass-blur-lg: 32px;
--glass-blur-xl: 48px;
```

### Backgrounds (Dark)

```css
--glass-bg-primary: rgba(255, 255, 255, 0.05);
--glass-bg-secondary: rgba(255, 255, 255, 0.03);
--glass-bg-elevated: rgba(255, 255, 255, 0.10);
--glass-bg-hover: rgba(255, 255, 255, 0.12);
```

### Borders

```css
--glass-border-subtle: 1px solid rgba(255, 255, 255, 0.08);
--glass-border: 1px solid rgba(255, 255, 255, 0.14);
--glass-border-bright: 1px solid rgba(255, 255, 255, 0.22);
```

### Gradients

```css
--gradient-blue: linear-gradient(135deg, #2d7cff 0%, #00d4ff 100%);
--gradient-purple: linear-gradient(135deg, #a855f7 0%, #6366f1 100%);
--gradient-success: linear-gradient(135deg, #10b981 0%, #06b6d4 100%);
--gradient-warning: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%);
```

## 🌓 Dark/Light Mode

Все компоненты автоматически адаптируются:

```css
/* Dark mode (по умолчанию) */
.liquid-glass-card {
  background: rgba(255, 255, 255, 0.05);
}

/* Light mode */
html[data-theme="light"] .liquid-glass-card {
  background: rgba(255, 255, 255, 0.65);
}
```

## 📱 Responsive

Используется `clamp()` для адаптивных размеров:

```css
.liquid-glass-card {
  padding: clamp(20px, 2.8vw, 32px);
  border-radius: clamp(20px, 2.2vw, 28px);
}
```

Mobile breakpoints автоматически:
- `768px` - планшеты
- `640px` - мобильные

## ♿ Accessibility

### Автоматически:
- Focus visible states
- Keyboard navigation
- ARIA labels поддержка
- High contrast mode support
- `prefers-reduced-motion` - отключает анимации

### Вручную добавь:
```html
<button class="liquid-glass-btn"
        aria-label="Описание действия">
  Кнопка
</button>
```

## 🚫 Частые ошибки

### ❌ НЕ делать:

```html
<!-- Не вкладывай blur в blur -->
<div class="liquid-glass-card">
  <div class="liquid-glass-card">Bad!</div>
</div>

<!-- Не используй слишком много parallax -->
<div data-parallax data-float data-glow-pulse>Too much!</div>
```

### ✅ Делать:

```html
<!-- Один эффект на элемент -->
<div class="liquid-glass-card liquid-glass-card--interactive" data-parallax>
  <h3>Good!</h3>
</div>

<!-- Комбинируй с умом -->
<div class="liquid-glass-card" data-animate-in>
  <span class="liquid-glass-badge liquid-glass-badge--success">Good!</span>
</div>
```

## 🎓 Шпаргалка замены

| Старый класс | Новый класс | Примечание |
|-------------|-------------|------------|
| `.card.glass` | `.liquid-glass-card` | Добавь `data-animate-in` |
| `.btn.btn-primary` | `.liquid-glass-btn.liquid-glass-btn--primary` | Ripple автоматически |
| `.badge.badge--soft` | `.liquid-glass-badge.liquid-glass-badge--neutral` | 6 цветов |
| `table.list-table` | Оберни в `.liquid-glass-table` | Сохрани внутренний table |

## 📚 Полная документация

Для детального изучения см. `/docs/LIQUID_GLASS_GUIDE.md`

## 🎉 Готовые примеры

Посмотри реализацию в:
- `/templates/cities_list.html` - статистика, таблицы
- `/templates/slots_list.html` - карточки с parallax
- `/templates/recruiters_edit.html` - формы, alerts

## 🐛 Troubleshooting

### Blur не работает?

```javascript
// Проверь поддержку
if (CSS.supports('backdrop-filter', 'blur(10px)')) {
  console.log('Поддерживается!');
}
```

### Анимации не запускаются?

```javascript
// Проверь консоль
// Должно быть: [Liquid Glass] Initializing effects...
```

### Низкая производительность?

- Ограничь blur элементы (< 10 одновременно)
- Используй `--subtle` вариант
- Отключи parallax на мобильных

## 💡 Pro Tips

1. **Группируй карточки**: Используй `display: grid` для красивых раскладок
2. **Stagger animations**: `data-animate-in` автоматически с задержкой
3. **Tone variants**: Используй `[data-tone="success"]` для автоматических стилей
4. **Loading states**: `data-loading="true"` для shimmer эффекта
5. **Print friendly**: Автоматические print styles включены

## 🚀 Начни с малого

1. Замени одну карточку
2. Добавь `data-animate-in` к секциям
3. Обнови badges в таблице
4. Добавь parallax к статистике
5. Profit! ✨

---

**Создано с любовью к деталям** ❤️
*Powered by Claude Sonnet 4.5*
