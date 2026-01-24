# Liquid Glass Design System Guide

## Overview

Liquid Glass - это современная дизайн-система, вдохновлённая Apple glassmorphism эффектами. Она применяет полупрозрачные поверхности, размытие фона, яркие границы и плавные анимации для создания глубокого, многослойного интерфейса.

## Ключевые принципы

### 1. **Glassmorphism**
- Полупрозрачные фоны с размытием
- Многослойные тени для создания глубины
- Яркие границы (highlight borders)
- Эффект "матового стекла"

### 2. **Fluid Motion**
- Плавные переходы (0.3-0.5s)
- Cubic-bezier easings для natural motion
- Микро-анимации при hover
- Parallax эффекты на интерактивных элементах

### 3. **Depth & Layering**
- Использование z-index и box-shadow
- Градиенты для создания объёма
- Эффекты свечения (glow) для акцентов
- Backdrop blur для разделения слоёв

## Компоненты

### Glass Card (.liquid-glass-card)

Основной строительный блок - полупрозрачная карточка с glassmorphism эффектом.

**HTML:**
```html
<div class="liquid-glass-card">
  <h3>Заголовок карточки</h3>
  <p>Контент карточки с эффектом жидкого стекла</p>
</div>
```

**Варианты:**

```html
<!-- Elevated card (более высокий z-index) -->
<div class="liquid-glass-card liquid-glass-card--elevated">
  ...
</div>

<!-- Subtle card (менее заметный) -->
<div class="liquid-glass-card liquid-glass-card--subtle">
  ...
</div>

<!-- Interactive card (с parallax на hover) -->
<div class="liquid-glass-card liquid-glass-card--interactive" data-parallax>
  ...
</div>
```

**Модификаторы данных:**
- `data-parallax` - добавляет 3D parallax эффект при наведении
- `data-animate-in` - анимация появления при скролле
- `data-glow-pulse` - пульсирующее свечение
- `data-float` - плавающая анимация

### Glass Button (.liquid-glass-btn)

Кнопка с градиентным фоном и shimmer эффектом.

**HTML:**
```html
<button class="liquid-glass-btn liquid-glass-btn--primary">
  Сохранить
</button>
```

**Варианты:**

```html
<!-- Primary (синий градиент) -->
<button class="liquid-glass-btn liquid-glass-btn--primary">Primary</button>

<!-- Purple (фиолетовый градиент) -->
<button class="liquid-glass-btn liquid-glass-btn--purple">Purple</button>

<!-- Success (зелёный градиент) -->
<button class="liquid-glass-btn liquid-glass-btn--success">Success</button>

<!-- Ghost (полупрозрачный) -->
<button class="liquid-glass-btn liquid-glass-btn--ghost">Ghost</button>

<!-- Размеры -->
<button class="liquid-glass-btn liquid-glass-btn--sm">Small</button>
<button class="liquid-glass-btn">Default</button>
<button class="liquid-glass-btn liquid-glass-btn--lg">Large</button>
```

**Features:**
- Автоматический shimmer эффект на hover
- Ripple эффект на click (через JS)
- Плавный подъём на hover
- Glow эффект

### Glass Table (.liquid-glass-table)

Таблица с эффектом стекла.

**HTML:**
```html
<div class="liquid-glass-table">
  <table>
    <thead>
      <tr>
        <th>Название</th>
        <th>Значение</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Пример</td>
        <td>Данные</td>
      </tr>
    </tbody>
  </table>
</div>
```

**Features:**
- Размытие фона через backdrop-filter
- Hover эффект на строках
- Полупрозрачный header
- Тонкие разделители между строками

### Glass Badge (.liquid-glass-badge)

Компактный значок/метка с цветными вариантами.

**HTML:**
```html
<span class="liquid-glass-badge liquid-glass-badge--success">Success</span>
<span class="liquid-glass-badge liquid-glass-badge--warning">Warning</span>
<span class="liquid-glass-badge liquid-glass-badge--danger">Danger</span>
<span class="liquid-glass-badge liquid-glass-badge--info">Info</span>
<span class="liquid-glass-badge liquid-glass-badge--purple">Purple</span>
<span class="liquid-glass-badge liquid-glass-badge--neutral">Neutral</span>
```

**Features:**
- Цветная индикаторная точка (`::before`)
- Glow эффект в цвет badge
- Hover подъём
- Полупрозрачный фон

### Glass Input (.liquid-glass-input)

Поле ввода с эффектом стекла.

**HTML:**
```html
<input type="text" class="liquid-glass-input" placeholder="Введите текст">
<select class="liquid-glass-input">
  <option>Опция 1</option>
  <option>Опция 2</option>
</select>
<textarea class="liquid-glass-input" rows="4"></textarea>
```

**Features:**
- Focus состояние с синим glow
- Hover подсветка границы
- Полупрозрачный фон
- Плавные transitions

### Glass Section (.liquid-glass-section)

Крупная секция/панель контента.

**HTML:**
```html
<section class="liquid-glass-section">
  <h2>Раздел контента</h2>
  <p>Информация внутри секции...</p>
</section>
```

**Features:**
- Highlight line на верхней границе
- Margin-bottom для вертикального rhythm
- Padding адаптивный через clamp()

### Glass Navigation (.liquid-glass-nav)

Sticky навигация с максимальным blur.

**HTML:**
```html
<nav class="liquid-glass-nav">
  <a href="/">Главная</a>
  <a href="/about">О нас</a>
</nav>
```

**Features:**
- Sticky positioning
- Максимальный blur (48px)
- Тень для отделения от контента
- Высокий z-index (100)

## JavaScript Effects

Модуль `glass-effects.js` добавляет интерактивные эффекты:

### 1. Card Parallax

Добавляет 3D tilt эффект к карточкам при наведении.

**Применение:**
```html
<div class="liquid-glass-card liquid-glass-card--interactive" data-parallax>
  Контент с parallax
</div>
```

**Параметры:**
- Максимальный наклон: 3 градуса
- Smooth easing: 0.10
- Автоматический reset при mouseout

### 2. Button Ripple

Ripple эффект при клике на кнопки (Material Design style).

**Применение:**
- Автоматически на всех `.liquid-glass-btn`, `.btn`, `button`
- Ripple появляется в точке клика
- Удаляется через 650ms

### 3. Floating Elements

Плавающая анимация для декоративных элементов.

**Применение:**
```html
<div class="some-element" data-float>
  Плавающий элемент
</div>
```

### 4. Glow Pulse

Пульсирующее свечение.

**Применение:**
```html
<div class="liquid-glass-card" data-glow-pulse>
  Карточка с пульсацией
</div>
```

### 5. Scroll Animations

Элементы появляются при скролле.

**Применение:**
```html
<div class="liquid-glass-card" data-animate-in>
  Появится при прокрутке
</div>
```

### 6. Table Row Effects

Интерактивные эффекты для строк таблицы.

**Применение:**
- Автоматически на `.liquid-glass-table table` и `table.list-table`
- Строки сдвигаются вправо на 4px при hover

## API

### Window.LiquidGlass

Глобальный объект для управления эффектами:

```javascript
// Инициализация всех эффектов
window.LiquidGlass.init();

// Переинициализация (для динамического контента)
window.LiquidGlass.refresh();

// Полная очистка всех эффектов
window.LiquidGlass.cleanup();
```

**Пример использования:**
```javascript
// После AJAX загрузки контента
fetch('/api/data')
  .then(response => response.json())
  .then(data => {
    // Обновить DOM
    updateContent(data);

    // Переинициализировать эффекты
    window.LiquidGlass.refresh();
  });
```

## CSS Variables

### Blur Intensities

```css
--glass-blur-sm: 8px;
--glass-blur-md: 20px;
--glass-blur-lg: 32px;
--glass-blur-xl: 48px;
```

### Glass Backgrounds

**Dark Theme:**
```css
--glass-bg-primary: rgba(255, 255, 255, 0.05);
--glass-bg-secondary: rgba(255, 255, 255, 0.03);
--glass-bg-elevated: rgba(255, 255, 255, 0.10);
--glass-bg-hover: rgba(255, 255, 255, 0.12);
--glass-bg-active: rgba(255, 255, 255, 0.15);
```

**Light Theme:**
```css
--glass-bg-primary: rgba(255, 255, 255, 0.65);
--glass-bg-secondary: rgba(255, 255, 255, 0.45);
--glass-bg-elevated: rgba(255, 255, 255, 0.80);
--glass-bg-hover: rgba(255, 255, 255, 0.90);
--glass-bg-active: rgba(255, 255, 255, 0.95);
```

### Borders

```css
--glass-border-subtle: 1px solid rgba(255, 255, 255, 0.08);
--glass-border: 1px solid rgba(255, 255, 255, 0.14);
--glass-border-bright: 1px solid rgba(255, 255, 255, 0.22);
```

### Shadows

```css
--shadow-glass-sm: ...;
--shadow-glass-md: ...;
--shadow-glass-lg: ...;
--shadow-glass-xl: ...;
```

### Glows

```css
--shadow-glow-blue: 0 0 24px rgba(45, 124, 255, 0.35);
--shadow-glow-purple: 0 0 24px rgba(168, 85, 247, 0.35);
--shadow-glow-success: 0 0 24px rgba(16, 185, 129, 0.35);
--shadow-glow-warning: 0 0 24px rgba(245, 158, 11, 0.35);
```

### Gradients

```css
--gradient-primary: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
--gradient-blue: linear-gradient(135deg, #2d7cff 0%, #00d4ff 100%);
--gradient-purple: linear-gradient(135deg, #a855f7 0%, #6366f1 100%);
--gradient-success: linear-gradient(135deg, #10b981 0%, #06b6d4 100%);
--gradient-warning: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%);
```

## Utility Classes

### Blur

```html
<div class="liquid-blur-sm">Небольшое размытие</div>
<div class="liquid-blur-md">Среднее размытие</div>
<div class="liquid-blur-lg">Сильное размытие</div>
<div class="liquid-blur-xl">Экстра размытие</div>
```

### Animations

```html
<div class="liquid-float">Плавающий элемент</div>
<div class="liquid-glow-pulse">Пульсирующее свечение</div>
<div class="liquid-shimmer">Shimmer эффект</div>
```

## Best Practices

### 1. Performance

**DO:**
- Используйте `will-change: transform` на анимируемых элементах
- Ограничивайте количество одновременных blur эффектов
- Применяйте `contain: layout style paint` для изоляции

**DON'T:**
- Не используйте blur на всём body
- Избегайте вложенных blur элементов
- Не анимируйте blur значения (очень ресурсозатратно)

### 2. Accessibility

**DO:**
- Проверяйте контрастность текста на glass фонах
- Используйте `prefers-reduced-motion` для отключения анимаций
- Обеспечивайте keyboard navigation
- Добавляйте ARIA labels

**DON'T:**
- Не полагайтесь только на цвет для передачи информации
- Избегайте анимаций > 5 секунд
- Не используйте низкоконтрастные комбинации

### 3. Browser Compatibility

**Supported:**
- Chrome 76+ (backdrop-filter)
- Safari 9+ (webkit-backdrop-filter)
- Firefox 103+ (backdrop-filter)
- Edge 79+

**Fallbacks:**
Система автоматически предоставляет fallback для старых браузеров:

```css
/* Fallback без backdrop-filter */
.liquid-glass-card {
  background: linear-gradient(135deg,
    rgba(255, 255, 255, 0.08) 0%,
    rgba(255, 255, 255, 0.02) 100%);
}

/* С поддержкой backdrop-filter */
@supports (backdrop-filter: blur(20px)) {
  .liquid-glass-card {
    backdrop-filter: blur(20px) saturate(180%);
  }
}
```

### 4. Dark/Light Mode

Все компоненты автоматически адаптируются к теме через `html[data-theme="light"]`:

```css
html[data-theme="light"] .liquid-glass-card {
  --glass-bg-primary: rgba(255, 255, 255, 0.65);
  /* ... другие переменные */
}
```

### 5. Responsive Design

Используйте clamp() для адаптивных размеров:

```css
.liquid-glass-card {
  padding: clamp(20px, 2.8vw, 32px);
  border-radius: clamp(20px, 2.2vw, 28px);
}
```

Mobile breakpoints:
```css
@media (max-width: 768px) {
  .liquid-glass-card {
    padding: clamp(16px, 4vw, 20px);
  }
}
```

## Examples

### Статистическая карточка

```html
<div class="liquid-glass-card liquid-glass-card--interactive"
     data-parallax
     data-animate-in>
  <h3 class="stat-label">Всего пользователей</h3>
  <p class="stat-value">1,234</p>
  <span class="liquid-glass-badge liquid-glass-badge--success">
    +15% за неделю
  </span>
</div>
```

### Форма с glass эффектом

```html
<form class="liquid-glass-section">
  <h2>Регистрация</h2>

  <label for="name">Имя</label>
  <input type="text"
         id="name"
         class="liquid-glass-input"
         placeholder="Введите имя">

  <label for="email">Email</label>
  <input type="email"
         id="email"
         class="liquid-glass-input"
         placeholder="your@email.com">

  <button type="submit"
          class="liquid-glass-btn liquid-glass-btn--primary">
    Зарегистрироваться
  </button>
</form>
```

### Таблица с данными

```html
<div class="liquid-glass-table" data-animate-in>
  <table>
    <thead>
      <tr>
        <th>Город</th>
        <th>Статус</th>
        <th>План</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Москва</td>
        <td>
          <span class="liquid-glass-badge liquid-glass-badge--success">
            Активен
          </span>
        </td>
        <td>120</td>
      </tr>
      <tr>
        <td>Санкт-Петербург</td>
        <td>
          <span class="liquid-glass-badge liquid-glass-badge--warning">
            Ожидает
          </span>
        </td>
        <td>85</td>
      </tr>
    </tbody>
  </table>
</div>
```

## Troubleshooting

### Blur не работает

**Проблема:** `backdrop-filter` не поддерживается браузером.

**Решение:**
1. Проверьте версию браузера
2. Для Safari используйте `-webkit-backdrop-filter`
3. Система уже включает fallback - проверьте, что CSS загружен

### Анимации не запускаются

**Проблема:** `glass-effects.js` не загружен или не инициализирован.

**Решение:**
1. Проверьте консоль: должно быть `[Liquid Glass] Initializing effects...`
2. Убедитесь, что скрипт загружен после DOM
3. Проверьте `prefers-reduced-motion` - анимации отключены при reduce motion

### Низкая производительность

**Проблема:** Слишком много blur элементов или анимаций.

**Решение:**
1. Ограничьте количество одновременных blur эффектов (< 10)
2. Используйте `will-change` для анимируемых элементов
3. Отключите parallax на мобильных устройствах
4. Рассмотрите использование `--subtle` варианта для менее важных элементов

### Контрастность текста

**Проблема:** Текст плохо читается на glass фоне.

**Решение:**
1. Увеличьте opacity фона glass элемента
2. Добавьте text-shadow для улучшения читаемости:
   ```css
   text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
   ```
3. Используйте более тёмный/светлый текст
4. Проверьте контрастность инструментом (минимум 4.5:1)

## Migration Guide

### От старой системы к Liquid Glass

**1. Замена классов карточек:**
```html
<!-- До -->
<div class="card glass grain">...</div>

<!-- После -->
<div class="liquid-glass-card" data-animate-in>...</div>
```

**2. Замена кнопок:**
```html
<!-- До -->
<button class="btn btn-primary">Сохранить</button>

<!-- После -->
<button class="liquid-glass-btn liquid-glass-btn--primary">Сохранить</button>
```

**3. Замена badges:**
```html
<!-- До -->
<span class="badge badge--soft">Статус</span>

<!-- После -->
<span class="liquid-glass-badge liquid-glass-badge--info">Статус</span>
```

**4. Замена таблиц:**
```html
<!-- До -->
<table class="list-table">...</table>

<!-- После -->
<div class="liquid-glass-table">
  <table class="list-table">...</table>
</div>
```

## Resources

- **CSS File:** `/static/css/liquid-glass.css`
- **JS Module:** `/static/js/modules/glass-effects.js`
- **Examples:** См. `cities_list.html`, `slots_list.html`, `recruiters_edit.html`
- **Browser Support:** [Can I Use - backdrop-filter](https://caniuse.com/css-backdrop-filter)

## Credits

Inspired by:
- Apple's macOS Big Sur & Monterey design language
- iOS 15+ glassmorphism effects
- Material Design 3 elevation system
