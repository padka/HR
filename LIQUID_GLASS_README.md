# 🌊 Liquid Glass Design System

> Apple-inspired glassmorphism дизайн-система для recruitsmart_admin

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![CSS](https://img.shields.io/badge/CSS-669%20lines-green)
![JavaScript](https://img.shields.io/badge/JavaScript-367%20lines-yellow)
![Browser Support](https://img.shields.io/badge/browsers-95%25-brightgreen)

## ✨ Что это?

**Liquid Glass** - современная дизайн-система с полупрозрачными поверхностями, размытием фона, плавными градиентами и интерактивными анимациями в стиле Apple Big Sur/Monterey.

## 🚀 Быстрый старт

### 1. Файлы уже подключены

Все необходимые файлы автоматически загружаются в `base.html`:

```html
<link rel="stylesheet" href="/static/css/liquid-glass.css">
<link rel="stylesheet" href="/static/css/liquid-glass-integration.css">
<script src="/static/js/modules/glass-effects.js" defer></script>
```

### 2. Используй компоненты

#### Карточка
```html
<div class="liquid-glass-card" data-animate-in>
  <h3>Заголовок</h3>
  <p>Контент с эффектом жидкого стекла</p>
</div>
```

#### Кнопка
```html
<button class="liquid-glass-btn liquid-glass-btn--primary">
  Сохранить
</button>
```

#### Badge
```html
<span class="liquid-glass-badge liquid-glass-badge--success">
  Активен
</span>
```

#### Таблица
```html
<div class="liquid-glass-table">
  <table>...</table>
</div>
```

### 3. Добавь эффекты

```html
<!-- Parallax эффект -->
<div class="liquid-glass-card" data-parallax>3D Tilt</div>

<!-- Появление при скролле -->
<div class="liquid-glass-card" data-animate-in>Fade In</div>

<!-- Пульсирующее свечение -->
<div class="liquid-glass-card" data-glow-pulse>Glow</div>

<!-- Плавающая анимация -->
<div class="liquid-glass-card" data-float>Float</div>
```

## 📦 Компоненты

### Cards

```html
<!-- Варианты -->
<div class="liquid-glass-card">Default</div>
<div class="liquid-glass-card liquid-glass-card--elevated">Elevated</div>
<div class="liquid-glass-card liquid-glass-card--subtle">Subtle</div>
<div class="liquid-glass-card liquid-glass-card--interactive" data-parallax>Interactive</div>
```

### Buttons

```html
<!-- Цвета -->
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

## 🎨 Примеры

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

### Таблица с данными

```html
<div class="liquid-glass-table" data-animate-in>
  <table>
    <thead>
      <tr>
        <th>Город</th>
        <th>Статус</th>
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
      </tr>
    </tbody>
  </table>
</div>
```

## 🔧 JavaScript API

```javascript
// Инициализация (автоматическая при загрузке)
window.LiquidGlass.init();

// Обновить эффекты (после AJAX загрузки)
window.LiquidGlass.refresh();

// Очистить все эффекты
window.LiquidGlass.cleanup();
```

## 🎯 Data Attributes

| Атрибут | Эффект |
|---------|--------|
| `data-parallax` | 3D tilt на hover |
| `data-animate-in` | Появление при скролле |
| `data-glow-pulse` | Пульсирующее свечение |
| `data-float` | Плавающая анимация |
| `data-loading="true"` | Shimmer loading |

## 📊 Статистика

- **CSS:** 669 строк (liquid-glass.css) + 459 строк (integration)
- **JavaScript:** 367 строк
- **Компонентов:** 15
- **Анимаций:** 7 интерактивных эффектов
- **Browser Support:** 95%+

## 📚 Документация

- **Quick Start:** `/docs/LIQUID_GLASS_QUICKSTART.md` - 5-минутный гайд
- **Full Guide:** `/docs/LIQUID_GLASS_GUIDE.md` - Полная документация
- **Implementation:** `/LIQUID_GLASS_IMPLEMENTATION.md` - Детали реализации

## 🎓 Примеры страниц

Смотри реализацию в:
- `/templates/cities_list.html` - Статистика, таблицы, badges
- `/templates/slots_list.html` - Карточки с parallax
- `/templates/recruiters_edit.html` - Формы, alerts

## 🌓 Dark/Light Mode

Автоматическая адаптация к теме:

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

## ♿ Accessibility

- ✅ WCAG 2.1 AA compliance
- ✅ Keyboard navigation
- ✅ Focus indicators
- ✅ ARIA labels support
- ✅ `prefers-reduced-motion` support
- ✅ High contrast mode
- ✅ Print styles

## 🌐 Browser Support

| Browser | Version | Support |
|---------|---------|---------|
| Chrome | 76+ | ✅ Full |
| Safari | 9+ | ✅ Full |
| Firefox | 103+ | ✅ Full |
| Edge | 79+ | ✅ Full |

Автоматический fallback для старых браузеров.

## 🎨 CSS Variables

### Blur
```css
--glass-blur-sm: 8px;
--glass-blur-md: 20px;
--glass-blur-lg: 32px;
--glass-blur-xl: 48px;
```

### Gradients
```css
--gradient-blue: linear-gradient(135deg, #2d7cff 0%, #00d4ff 100%);
--gradient-purple: linear-gradient(135deg, #a855f7 0%, #6366f1 100%);
--gradient-success: linear-gradient(135deg, #10b981 0%, #06b6d4 100%);
--gradient-warning: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%);
```

## 🐛 Troubleshooting

### Blur не работает?
Проверьте поддержку браузера и обновитесь.

### Анимации не запускаются?
Откройте консоль - должно быть: `[Liquid Glass] Initializing effects...`

### Низкая производительность?
- Ограничьте blur элементы (< 10)
- Используйте `--subtle` вариант
- Отключите parallax на мобильных

## 💡 Pro Tips

1. **Один эффект на элемент** - не перегружайте
2. **data-animate-in** - автоматический stagger
3. **Tone variants** - используйте `[data-tone]`
4. **Refresh после AJAX** - `window.LiquidGlass.refresh()`
5. **Print friendly** - автоматические print styles

## 🚀 Быстрая миграция

| Старый | Новый |
|--------|-------|
| `.card.glass` | `.liquid-glass-card` + `data-animate-in` |
| `.btn.btn-primary` | `.liquid-glass-btn.liquid-glass-btn--primary` |
| `.badge.badge--soft` | `.liquid-glass-badge.liquid-glass-badge--neutral` |
| `table.list-table` | Оберни в `.liquid-glass-table` |

## 📝 Changelog

### v1.0.0 (2025-11-16)
- ✨ Initial release
- 🎨 15 компонентов
- 🚀 7 интерактивных эффектов
- 📚 Полная документация
- ♿ WCAG AA compliance
- 🌐 95%+ browser support

## 🤝 Contributing

Для добавления новых компонентов:

1. Добавьте CSS в `liquid-glass.css`
2. Добавьте JS эффекты в `glass-effects.js`
3. Обновите документацию
4. Протестируйте на всех браузерах
5. Проверьте accessibility

## 📄 License

MIT License - используйте свободно!

## 🙏 Credits

Inspired by:
- Apple macOS Big Sur & Monterey
- iOS 15+ glassmorphism
- Material Design 3

---

**Powered by Claude Sonnet 4.5** ✨
*Created with attention to detail* ❤️

## 🔗 Links

- [Quick Start Guide](/docs/LIQUID_GLASS_QUICKSTART.md)
- [Full Documentation](/docs/LIQUID_GLASS_GUIDE.md)
- [Implementation Details](/LIQUID_GLASS_IMPLEMENTATION.md)

---

**Get started in 5 minutes!** 🚀
