# 🎨 Design System: Страница "Кандидаты" | Liquid Glass Улучшения

**Дата**: 2025-11-06
**Дизайнер**: UI/UX Design Team
**Для разработчика**: Backend/Frontend Implementation Team
**Версия**: 2.0 (Улучшенный Liquid Glass)

---

## 📋 Содержание

1. [Анализ текущего состояния](#анализ-текущего-состояния)
2. [Цели улучшения](#цели-улучшения)
3. [Улучшенная физика Liquid Glass](#улучшенная-физика-liquid-glass)
4. [Паттерны взаимодействия](#паттерны-взаимодействия)
5. [Система компонентов](#система-компонентов)
6. [Анимации и микроинтеракции](#анимации-и-микроинтеракции)
7. [Руководство по реализации](#руководство-по-реализации)

---

## 🔍 Анализ текущего состояния

### Что работает хорошо ✅
- **Базовая liquid glass эстетика**: Градиенты, blur, прозрачность присутствуют
- **Адаптивность**: Responsive дизайн реализован
- **Иерархия компонентов**: Карточки, модальные окна, таблицы структурированы
- **Цветовая схема**: Акцентные цвета и тональности определены

### Что нужно улучшить 🔧

#### 1. Физика стекла (Glass Physics)
```
ТЕКУЩЕЕ СОСТОЯНИЕ:
- Blur: 40px (слишком сильный, теряется четкость)
- Opacity фона: 0.05-0.09 (слишком прозрачно)
- Границы: rgba(255,255,255,0.08) (едва видны)
- Тени: статичные, не реагируют на depth

ПРОБЛЕМЫ:
❌ Эффект "мутного стекла" вместо "жидкого стекла"
❌ Недостаточная глубина (depth perception)
❌ Слабая иерархия z-index визуально
❌ Тени не передают "парение" элементов
```

#### 2. Анимации
```
ТЕКУЩЕЕ СОСТОЯНИЕ:
- Transition: 0.4-0.5s (медленно)
- Easing: cubic-bezier(0.4, 0, 0.2, 1) (стандартный)
- Transform: translateY(-6px) scale(1.02) (грубо)

ПРОБЛЕМЫ:
❌ Анимации не fluid, чувствуется "скачок"
❌ Нет предвосхищения (anticipation)
❌ Отсутствует эффект "viscosity" (вязкость жидкости)
```

#### 3. Модальные окна (Filters Modal)
```
ТЕКУЩЕЕ СОСТОЯНИЕ:
- Backdrop blur: 12px
- Panel border-radius: 32px
- Открытие: простое появление

ПРОБЛЕМЫ:
❌ Недостаточная изоляция фокуса
❌ Нет эффекта "depth stacking"
❌ Backdrop слишком простой
```

---

## 🎯 Цели улучшения

### 1. **Реалистичная физика Apple-style Liquid Glass**
Создать ощущение, что интерфейс сделан из **живого, жидкого стекла**, которое:
- Реагирует на движение курсора (proximity effects)
- Имеет вязкость при анимациях
- Показывает глубину через shadow stacking
- Отражает свет как настоящее стекло

### 2. **Улучшенная иерархия взаимодействий**
- Модальные окна появляются с эффектом "всплытия из глубины"
- Карточки реагируют на hover как жидкость
- Кнопки имеют "ripple effect" при клике

### 3. **Микроанимации мирового класса**
- Spring physics для всех движений
- Stagger animations для списков
- Morphing transitions между состояниями

---

## 💎 Улучшенная физика Liquid Glass

### CSS Custom Properties (Обновленные)

```css
:root {
  /* === ОСНОВА LIQUID GLASS === */

  /* 1. Базовый слой стекла */
  --liquid-glass-bg: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.12) 0%,    /* ↑ Увеличено с 0.05 */
    rgba(255, 255, 255, 0.06) 100%   /* ↑ Увеличено с 0.02 */
  );

  /* 2. Hover состояние */
  --liquid-glass-bg-hover: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.18) 0%,    /* ↑ Увеличено */
    rgba(255, 255, 255, 0.10) 100%   /* ↑ Увеличено */
  );

  /* 3. Активное/Pressed состояние (НОВОЕ) */
  --liquid-glass-bg-active: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.22) 0%,
    rgba(255, 255, 255, 0.14) 100%
  );

  /* 4. Границы с градиентом (НОВОЕ) */
  --liquid-glass-border: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.20) 0%,    /* ↑ Увеличено с 0.08 */
    rgba(255, 255, 255, 0.10) 50%,
    rgba(255, 255, 255, 0.05) 100%
  );

  /* 5. Внутренний highlight (спекуляр) */
  --liquid-glass-highlight: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.25) 0%,    /* ↑ Увеличено с 0.12 */
    rgba(255, 255, 255, 0.05) 30%,
    rgba(255, 255, 255, 0) 60%
  );

  /* 6. Улучшенные тени (многослойные) */
  --liquid-glass-shadow-ambient:
    0 2px 8px -2px rgba(0, 0, 0, 0.08);
  --liquid-glass-shadow-penumbra:
    0 8px 24px -4px rgba(0, 0, 0, 0.12);
  --liquid-glass-shadow-umbra:
    0 16px 48px -8px rgba(0, 0, 0, 0.16);
  --liquid-glass-shadow-inset:
    inset 0 1px 2px 0 rgba(255, 255, 255, 0.15);

  /* Комбинированная тень для покоя */
  --liquid-glass-shadow:
    var(--liquid-glass-shadow-ambient),
    var(--liquid-glass-shadow-penumbra),
    var(--liquid-glass-shadow-inset);

  /* Комбинированная тень для hover */
  --liquid-glass-shadow-hover:
    0 4px 12px -2px rgba(0, 0, 0, 0.10),
    0 12px 32px -4px rgba(0, 0, 0, 0.15),
    0 24px 64px -8px rgba(0, 0, 0, 0.20),
    inset 0 1px 3px 0 rgba(255, 255, 255, 0.20);

  /* 7. Blur эффекты (уменьшенные для четкости) */
  --liquid-glass-blur: blur(28px);           /* ↓ Уменьшено с 40px */
  --liquid-glass-blur-strong: blur(36px);
  --liquid-glass-blur-subtle: blur(16px);

  /* 8. Saturation (насыщенность через фильтр) */
  --liquid-glass-saturate: saturate(180%);   /* Apple использует 160-200% */

  /* 9. Brightness overlay (НОВОЕ) */
  --liquid-glass-brightness: brightness(1.05);
}

/* === СВЕТЛАЯ ТЕМА === */
html[data-theme="light"] {
  --liquid-glass-bg: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.75) 0%,    /* ↑ Больше непрозрачности */
    rgba(255, 255, 255, 0.55) 100%
  );

  --liquid-glass-bg-hover: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.90) 0%,
    rgba(255, 255, 255, 0.70) 100%
  );

  --liquid-glass-border: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.60) 0%,
    rgba(255, 255, 255, 0.30) 50%,
    rgba(255, 255, 255, 0.20) 100%
  );

  --liquid-glass-highlight: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.98) 0%,
    rgba(255, 255, 255, 0.20) 30%,
    rgba(255, 255, 255, 0) 60%
  );

  --liquid-glass-shadow:
    0 2px 8px -2px rgba(31, 38, 135, 0.12),
    0 8px 24px -4px rgba(31, 38, 135, 0.15),
    inset 0 1px 2px 0 rgba(255, 255, 255, 0.80);

  --liquid-glass-shadow-hover:
    0 4px 12px -2px rgba(31, 38, 135, 0.15),
    0 12px 32px -4px rgba(31, 38, 135, 0.20),
    0 24px 64px -8px rgba(31, 38, 135, 0.25),
    inset 0 1px 3px 0 rgba(255, 255, 255, 0.95);

  --liquid-glass-blur: blur(24px);
  --liquid-glass-saturate: saturate(160%);
}
```

### Базовый Glass Card Component (Улучшенный)

```css
.glass-card {
  position: relative;
  isolation: isolate;

  /* Основа */
  background: var(--liquid-glass-bg);
  border: 1px solid transparent; /* Градиент применим через ::before */
  border-radius: clamp(20px, 2.2vw, 32px);

  /* Фильтры */
  backdrop-filter:
    var(--liquid-glass-blur)
    var(--liquid-glass-saturate)
    var(--liquid-glass-brightness);
  -webkit-backdrop-filter:
    var(--liquid-glass-blur)
    var(--liquid-glass-saturate)
    var(--liquid-glass-brightness);

  /* Тени */
  box-shadow: var(--liquid-glass-shadow);

  /* Анимация с spring physics */
  transition:
    transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1),  /* Spring bounce */
    box-shadow 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94),
    background 0.3s ease-out;

  /* Prevent layout shift */
  transform: translateZ(0);
  will-change: transform;
}

/* Градиентная граница через pseudo-element */
.glass-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1px; /* Толщина границы */
  background: var(--liquid-glass-border);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
  opacity: 1;
  transition: opacity 0.3s ease;
}

/* Specular highlight (отражение света) */
.glass-card::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: var(--liquid-glass-highlight);
  pointer-events: none;
  opacity: 0.6;
  mix-blend-mode: overlay;
  transition: opacity 0.3s ease;
}

/* === HOVER STATE === */
.glass-card:hover {
  /* Lift effect с spring physics */
  transform: translateY(-8px) scale(1.015);
  box-shadow: var(--liquid-glass-shadow-hover);
  background: var(--liquid-glass-bg-hover);
}

.glass-card:hover::before {
  opacity: 1;
}

.glass-card:hover::after {
  opacity: 0.85; /* Больше света */
}

/* === ACTIVE/PRESSED STATE === */
.glass-card:active {
  transform: translateY(-4px) scale(1.008);
  background: var(--liquid-glass-bg-active);
  transition-duration: 0.1s; /* Быстрый отклик */
}

/* === FOCUS STATE === */
.glass-card:focus-within {
  outline: none;
  box-shadow:
    var(--liquid-glass-shadow-hover),
    0 0 0 4px rgba(var(--accent-rgb), 0.15);
}
```

---

## 🎭 Паттерны взаимодействия

### 1. Modal Opening Animation (Filters Modal)

**Концепция**: Модальное окно "всплывает из глубины" как пузырь в жидкости

```css
/* === BACKDROP === */
.filters-modal__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(8, 12, 18, 0.50);  /* ↑ Темнее для контраста */
  backdrop-filter: blur(20px) saturate(120%);  /* ↑ Сильнее blur */
  -webkit-backdrop-filter: blur(20px) saturate(120%);

  /* Анимация появления */
  opacity: 0;
  animation: backdrop-fade-in 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94) forwards;
}

@keyframes backdrop-fade-in {
  from {
    opacity: 0;
    backdrop-filter: blur(0px) saturate(100%);
  }
  to {
    opacity: 1;
    backdrop-filter: blur(20px) saturate(120%);
  }
}

/* === PANEL === */
.filters-modal__panel {
  position: relative;
  width: min(960px, 100%);

  /* Glass styling */
  background: var(--liquid-glass-bg);
  border: 1px solid transparent;
  border-radius: 40px;  /* ↑ Больше для "bubble" эффекта */
  padding: 40px;

  /* Filters */
  backdrop-filter:
    var(--liquid-glass-blur-strong)
    var(--liquid-glass-saturate);
  -webkit-backdrop-filter:
    var(--liquid-glass-blur-strong)
    var(--liquid-glass-saturate);

  /* Multi-layer shadow для depth */
  box-shadow:
    0 8px 32px -4px rgba(0, 0, 0, 0.20),
    0 24px 64px -8px rgba(0, 0, 0, 0.28),
    0 48px 96px -12px rgba(0, 0, 0, 0.35),
    inset 0 2px 4px 0 rgba(255, 255, 255, 0.12);

  /* Анимация появления: "всплытие из глубины" */
  opacity: 0;
  transform: scale(0.88) translateY(60px) rotateX(12deg);  /* 3D эффект */
  transform-origin: center bottom;
  perspective: 1200px;

  animation: panel-emerge 0.65s cubic-bezier(0.34, 1.26, 0.64, 1) forwards;
  animation-delay: 0.1s;
}

@keyframes panel-emerge {
  0% {
    opacity: 0;
    transform: scale(0.88) translateY(60px) rotateX(12deg);
  }
  60% {
    opacity: 1;
    transform: scale(1.02) translateY(-4px) rotateX(-2deg);  /* Overshoot */
  }
  100% {
    opacity: 1;
    transform: scale(1) translateY(0) rotateX(0deg);
  }
}

/* === PANEL GRADIENT BORDER === */
.filters-modal__panel::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: inherit;
  padding: 2px;
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.35) 0%,
    rgba(255, 255, 255, 0.15) 50%,
    rgba(255, 255, 255, 0.08) 100%
  );
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
  z-index: 1;
}

/* === SPECULAR HIGHLIGHT === */
.filters-modal__panel::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 60%;
  background: var(--liquid-glass-highlight);
  border-radius: 40px 40px 0 0;
  pointer-events: none;
  opacity: 0.75;
  mix-blend-mode: overlay;
  z-index: 0;
}
```

### 2. Card Hover Interaction (Candidate Cards)

**Концепция**: Карточка реагирует как капля воды - плавная деформация

```css
.candidate-card {
  position: relative;
  padding: 24px;
  border-radius: 28px;

  background: var(--liquid-glass-bg);
  border: 1px solid transparent;

  backdrop-filter:
    var(--liquid-glass-blur)
    var(--liquid-glass-saturate);
  -webkit-backdrop-filter:
    var(--liquid-glass-blur)
    var(--liquid-glass-saturate);

  box-shadow: var(--liquid-glass-shadow);

  /* Transition с viscosity (вязкость) */
  transition:
    transform 0.55s cubic-bezier(0.34, 1.45, 0.64, 1),  /* Spring */
    box-shadow 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94),
    background 0.3s ease-out,
    border-color 0.3s ease-out;

  transform: translateZ(0);
  will-change: transform;
}

/* Gradient border */
.candidate-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1px;
  background: var(--liquid-glass-border);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

/* Specular highlight */
.candidate-card::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: var(--liquid-glass-highlight);
  pointer-events: none;
  opacity: 0.5;
  mix-blend-mode: overlay;
  transition: opacity 0.3s ease;
}

/* === HOVER: Liquid deformation === */
.candidate-card:hover {
  /* Subtle liquid "squeeze" effect */
  transform:
    translateY(-10px)
    scale(1.02)
    rotateX(1deg);  /* Minimal 3D tilt */

  box-shadow: var(--liquid-glass-shadow-hover);
  background: var(--liquid-glass-bg-hover);
}

.candidate-card:hover::after {
  opacity: 0.8;
}

/* === ACTIVE: Press down === */
.candidate-card:active {
  transform:
    translateY(-6px)
    scale(1.01);
  transition-duration: 0.12s;
}
```

### 3. Button Ripple Effect

**Концепция**: Материал дизайн ripple + liquid glass

```css
.btn {
  position: relative;
  overflow: hidden;

  /* Glass base */
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.12),
    rgba(255, 255, 255, 0.06)
  );
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 14px;
  padding: 12px 24px;

  backdrop-filter: blur(20px) saturate(160%);
  -webkit-backdrop-filter: blur(20px) saturate(160%);

  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.08),
    inset 0 1px 1px rgba(255, 255, 255, 0.15);

  transition:
    transform 0.18s cubic-bezier(0.34, 1.2, 0.64, 1),
    box-shadow 0.18s ease,
    background 0.18s ease;
}

.btn::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.25);
  transform: translate(-50%, -50%);
  transition: width 0.6s ease-out, height 0.6s ease-out;
}

.btn:hover {
  transform: translateY(-2px);
  box-shadow:
    0 4px 12px rgba(0, 0, 0, 0.12),
    inset 0 1px 2px rgba(255, 255, 255, 0.20);
}

.btn:active::before {
  width: 300px;
  height: 300px;
  transition: width 0s, height 0s;
}

.btn:active {
  transform: translateY(-1px) scale(0.98);
  transition-duration: 0.08s;
}
```

---

## 📦 Система компонентов

### Компоненты и их иерархия

```
УРОВЕНЬ 0 (Фон)
└─ Backdrop / Background

УРОВЕНЬ 1 (Карточки сводки)
└─ candidate-summary__card
   ├─ Glass effect: базовый
   ├─ Elevation: низкая (8dp)
   └─ Hover lift: 6px

УРОВЕНЬ 2 (Основные карточки)
└─ candidate-card
   ├─ Glass effect: средний
   ├─ Elevation: средняя (12dp)
   └─ Hover lift: 10px

УРОВЕНЬ 3 (Модальные окна)
└─ filters-modal__panel
   ├─ Glass effect: сильный
   ├─ Elevation: высокая (24dp)
   └─ Backdrop blur: 20px

УРОВЕНЬ 4 (Dropdown / Tooltip)
└─ [Будущие компоненты]
   ├─ Glass effect: максимальный
   ├─ Elevation: очень высокая (32dp)
   └─ Backdrop blur: 28px
```

### Z-Index Scale

```css
:root {
  --z-base: 0;
  --z-cards: 1;
  --z-sticky: 10;
  --z-dropdown: 50;
  --z-modal-backdrop: 100;
  --z-modal-panel: 110;
  --z-tooltip: 200;
  --z-notification: 300;
}
```

---

## ✨ Анимации и микроинтеракции

### Spring Physics Parameters

```css
/* === EASING FUNCTIONS === */
:root {
  /* Для lift/hover эффектов */
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);

  /* Для модальных окон */
  --ease-modal: cubic-bezier(0.34, 1.26, 0.64, 1);

  /* Для fade эффектов */
  --ease-fade: cubic-bezier(0.25, 0.46, 0.45, 0.94);

  /* Для sharp движений (кнопки) */
  --ease-sharp: cubic-bezier(0.4, 0, 0.2, 1);

  /* Для organic движений (scroll) */
  --ease-organic: cubic-bezier(0.65, 0, 0.35, 1);
}
```

### Stagger Animation для списков

```css
/* Появление карточек по очереди */
@keyframes card-enter {
  from {
    opacity: 0;
    transform: translateY(24px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.candidate-card {
  animation: card-enter 0.5s var(--ease-spring) backwards;
}

/* Stagger delay через nth-child */
.candidate-card:nth-child(1) { animation-delay: 0.05s; }
.candidate-card:nth-child(2) { animation-delay: 0.10s; }
.candidate-card:nth-child(3) { animation-delay: 0.15s; }
.candidate-card:nth-child(4) { animation-delay: 0.20s; }
.candidate-card:nth-child(5) { animation-delay: 0.25s; }
.candidate-card:nth-child(6) { animation-delay: 0.30s; }
/* И так далее... или использовать JS */
```

### Proximity Effect (Отслеживание курсора)

```javascript
// Для будущей реализации разработчиком
document.querySelectorAll('.candidate-card').forEach(card => {
  card.addEventListener('mousemove', (e) => {
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const deltaX = (x - centerX) / centerX;
    const deltaY = (y - centerY) / centerY;

    // Subtle tilt based on cursor position
    card.style.transform = `
      translateY(-10px)
      scale(1.02)
      rotateY(${deltaX * 2}deg)
      rotateX(${-deltaY * 2}deg)
    `;
  });

  card.addEventListener('mouseleave', () => {
    card.style.transform = '';
  });
});
```

---

## 🛠️ Руководство по реализации

### Этап 1: Обновить CSS переменные
**Файл**: `backend/apps/admin_ui/templates/candidates_list.html` (строки 37-77)

**Задача**: Заменить текущие переменные на улучшенные из раздела "Улучшенная физика Liquid Glass"

**Критично**:
- Уменьшить blur с 40px до 28px
- Увеличить opacity фона
- Добавить многослойные тени
- Добавить saturate и brightness

### Этап 2: Обновить компонент .candidate-summary__card
**Файл**: `candidates_list.html` (строки 260-312)

**Задача**:
- Применить новый glass-card паттерн
- Добавить градиентную границу через ::before
- Добавить specular highlight через ::after
- Обновить transition с spring easing

### Этап 3: Обновить компонент .candidate-card
**Файл**: `candidates_list.html` (строки 392-420)

**Задача**:
- Применить улучшенную hover анимацию
- Добавить proximity effect (опционально, через JS)
- Обновить box-shadow на многослойные

### Этап 4: Обновить .filters-modal__panel
**Файл**: `candidates_list.html` (строки 124-151)

**Задача**:
- Изменить анимацию появления на "emerge from depth"
- Увеличить backdrop blur до 20px
- Добавить 3D трансформации
- Обновить box-shadow

### Этап 5: Добавить stagger animations
**Новый файл**: `backend/apps/admin_ui/static/js/modules/candidates-animations.js`

**Задача**:
- Создать скрипт для stagger delay
- Применить к .candidate-card при загрузке страницы

### Этап 6: Добавить button ripple
**Файл**: `backend/apps/admin_ui/static/css/lists.css` (строки 241-286)

**Задача**:
- Обновить .btn классы
- Добавить ripple effect через ::before pseudo-element

---

## 📐 Design Tokens Summary

```css
/* SPACING */
--space-xs: 8px;
--space-sm: 12px;
--space-md: 16px;
--space-lg: 24px;
--space-xl: 32px;
--space-2xl: 48px;

/* BORDER RADIUS */
--radius-sm: 12px;
--radius-md: 16px;
--radius-lg: 24px;
--radius-xl: 32px;
--radius-2xl: 40px;
--radius-full: 9999px;

/* BLUR */
--blur-sm: 16px;
--blur-md: 24px;
--blur-lg: 28px;
--blur-xl: 36px;

/* TRANSITIONS */
--duration-instant: 0.08s;
--duration-fast: 0.18s;
--duration-normal: 0.3s;
--duration-slow: 0.5s;
--duration-slower: 0.65s;

/* ELEVATIONS (box-shadow presets) */
--elevation-0: none;
--elevation-1:
  0 2px 8px -2px rgba(0, 0, 0, 0.08),
  inset 0 1px 1px rgba(255, 255, 255, 0.10);
--elevation-2:
  0 4px 12px -2px rgba(0, 0, 0, 0.10),
  0 8px 24px -4px rgba(0, 0, 0, 0.12),
  inset 0 1px 2px rgba(255, 255, 255, 0.12);
--elevation-3:
  0 8px 24px -4px rgba(0, 0, 0, 0.12),
  0 16px 48px -8px rgba(0, 0, 0, 0.16),
  inset 0 1px 2px rgba(255, 255, 255, 0.15);
--elevation-4:
  0 12px 32px -4px rgba(0, 0, 0, 0.15),
  0 24px 64px -8px rgba(0, 0, 0, 0.20),
  inset 0 2px 4px rgba(255, 255, 255, 0.18);
```

---

## ✅ Чеклист для разработчика

- [ ] Обновить CSS custom properties (blur, opacity, тени)
- [ ] Применить градиентные границы через ::before
- [ ] Добавить specular highlights через ::after
- [ ] Обновить transitions на spring easing
- [ ] Реализовать анимацию модального окна "emerge from depth"
- [ ] Добавить stagger animations для списков карточек
- [ ] Реализовать button ripple effect
- [ ] Добавить proximity hover effect (опционально)
- [ ] Протестировать performance (60fps required)
- [ ] Проверить accessibility (анимации должны уважать prefers-reduced-motion)

---

## 🎯 Ожидаемый результат

После реализации пользователь должен ощущать:
1. **Физическую глубину** - элементы находятся на разных уровнях
2. **Отзывчивость** - каждое действие имеет плавную реакцию
3. **Премиальность** - интерфейс ощущается дорогим и продуманным
4. **Жидкость** - анимации похожи на движение жидкости/стекла

**Референсы вдохновения**:
- Apple Vision Pro UI
- iOS 17 Control Center
- macOS Sonoma System Settings
- Windows 11 Acrylic Material

---

**Готов к реализации** ✨
_Дизайнер передает документ разработчику для implementation_
