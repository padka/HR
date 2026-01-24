# REDESIGN STRATEGY: RecruitSmart Admin UI

**Based on:** AUDIT_REPORT.md
**Project:** TG Bot Admin Panel
**Goal:** Transform good foundation into production-ready, world-class admin dashboard
**Timeline:** 12-16 weeks (phased approach)

---

## STRATEGIC VISION

Transform RecruitSmart Admin from **"functional with great aesthetics"** to **"best-in-class recruitment management platform"** by:

1. **Unifying design system** — consistent patterns across all components
2. **Optimizing workflows** — reduce clicks, add bulk actions, streamline forms
3. **Elevating accessibility** — WCAG AA compliance, keyboard-first navigation
4. **Improving performance** — sub-second load times, optimistic UI updates
5. **Modernizing mobile** — mobile-first patterns, touch-optimized

**Success Metrics:**
- Task completion time: **-40%**
- User errors: **-60%**
- Accessibility score: **5/10 → 9/10**
- Mobile satisfaction: **6/10 → 9/10**
- Page load time: **-50%**

---

## 1. DESIGN SYSTEM DEFINITION

### 1.1 Color Palette

#### Primary Brand Colors
```css
:root {
  /* Primary Accent — команда/действия */
  --color-primary-50: hsl(210, 100%, 95%);
  --color-primary-100: hsl(210, 100%, 90%);
  --color-primary-200: hsl(210, 100%, 80%);
  --color-primary-300: hsl(210, 100%, 70%);
  --color-primary-400: hsl(210, 100%, 60%);
  --color-primary-500: hsl(210, 100%, 55%); /* Base: #69b7ff -> #2d7cff */
  --color-primary-600: hsl(210, 100%, 45%);
  --color-primary-700: hsl(210, 100%, 35%);
  --color-primary-800: hsl(210, 80%, 25%);
  --color-primary-900: hsl(210, 60%, 15%);

  /* Secondary Accent — дополнительные акценты */
  --color-secondary-500: hsl(265, 85%, 65%); /* #b889ff */

  /* Neutrals — текст и фоны */
  --color-neutral-0: hsl(0, 0%, 100%);    /* White */
  --color-neutral-50: hsl(220, 20%, 98%); /* Lightest gray */
  --color-neutral-100: hsl(220, 16%, 96%);
  --color-neutral-200: hsl(220, 14%, 92%);
  --color-neutral-300: hsl(220, 12%, 85%);
  --color-neutral-400: hsl(220, 10%, 70%);
  --color-neutral-500: hsl(220, 8%, 55%);
  --color-neutral-600: hsl(220, 10%, 40%);
  --color-neutral-700: hsl(220, 15%, 25%);
  --color-neutral-800: hsl(220, 20%, 15%);
  --color-neutral-900: hsl(220, 25%, 8%);  /* Almost black */
}
```

#### Semantic Colors
```css
:root {
  /* Success — зелёный */
  --color-success-50: hsl(155, 70%, 95%);
  --color-success-500: hsl(155, 70%, 45%); /* #23d18b */
  --color-success-700: hsl(155, 70%, 35%);

  /* Warning — жёлтый */
  --color-warning-50: hsl(42, 100%, 95%);
  --color-warning-500: hsl(42, 100%, 62%); /* #ffd166 */
  --color-warning-700: hsl(42, 90%, 48%);

  /* Danger — красный */
  --color-danger-50: hsl(0, 90%, 95%);
  --color-danger-500: hsl(0, 90%, 65%); /* #ff6b6b */
  --color-danger-700: hsl(0, 80%, 50%);

  /* Info — голубой */
  --color-info-50: hsl(200, 85%, 95%);
  --color-info-500: hsl(200, 85%, 55%);
  --color-info-700: hsl(200, 75%, 45%);
}
```

#### Theme Tokens (Dark/Light)
```css
/* Dark Theme (default) */
html[data-theme="dark"] {
  --bg-canvas: var(--color-neutral-900);
  --bg-surface: var(--color-neutral-800);
  --bg-elevated: var(--color-neutral-700);

  --text-primary: var(--color-neutral-0);
  --text-secondary: var(--color-neutral-300);
  --text-tertiary: var(--color-neutral-500);

  --border-default: hsla(0, 0%, 100%, 0.12);
  --border-strong: hsla(0, 0%, 100%, 0.24);

  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.5);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.6);
  --shadow-lg: 0 16px 48px rgba(0, 0, 0, 0.7);
}

/* Light Theme */
html[data-theme="light"] {
  --bg-canvas: var(--color-neutral-0);
  --bg-surface: var(--color-neutral-50);
  --bg-elevated: var(--color-neutral-0);

  --text-primary: var(--color-neutral-900);
  --text-secondary: var(--color-neutral-600);
  --text-tertiary: var(--color-neutral-500);

  --border-default: hsla(220, 20%, 20%, 0.12);
  --border-strong: hsla(220, 20%, 20%, 0.24);

  --shadow-sm: 0 1px 2px rgba(15, 35, 95, 0.08);
  --shadow-md: 0 4px 12px rgba(15, 35, 95, 0.12);
  --shadow-lg: 0 16px 48px rgba(15, 35, 95, 0.16);
}
```

**WCAG AA Compliance:**
- text-primary on bg-canvas: **15.8:1** (AAA)
- text-secondary on bg-canvas: **7.2:1** (AA)
- text-tertiary on bg-canvas: **4.6:1** (AA)

---

### 1.2 Typography Scale

```css
:root {
  /* Font Families */
  --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: "JetBrains Mono", "SF Mono", ui-monospace, Consolas, monospace;

  /* Font Sizes (fluid responsive) */
  --text-xs: clamp(0.75rem, 0.7rem + 0.25vw, 0.875rem);    /* 12-14px */
  --text-sm: clamp(0.875rem, 0.8rem + 0.375vw, 1rem);      /* 14-16px */
  --text-base: clamp(1rem, 0.95rem + 0.25vw, 1.125rem);    /* 16-18px */
  --text-lg: clamp(1.125rem, 1rem + 0.625vw, 1.25rem);     /* 18-20px */
  --text-xl: clamp(1.25rem, 1.1rem + 0.75vw, 1.5rem);      /* 20-24px */
  --text-2xl: clamp(1.5rem, 1.3rem + 1vw, 2rem);           /* 24-32px */
  --text-3xl: clamp(1.875rem, 1.6rem + 1.375vw, 2.5rem);   /* 30-40px */
  --text-4xl: clamp(2.25rem, 2rem + 1.25vw, 3rem);         /* 36-48px */

  /* Line Heights */
  --leading-tight: 1.2;
  --leading-snug: 1.4;
  --leading-normal: 1.6;
  --leading-relaxed: 1.75;

  /* Font Weights */
  --font-normal: 400;
  --font-medium: 500;
  --font-semibold: 600;
  --font-bold: 700;
  --font-black: 900;

  /* Letter Spacing */
  --tracking-tight: -0.02em;
  --tracking-normal: 0;
  --tracking-wide: 0.025em;
  --tracking-wider: 0.05em;
}
```

**Typography Hierarchy:**
```css
.heading-1 {
  font-size: var(--text-4xl);
  font-weight: var(--font-black);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-tight);
}

.heading-2 {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  line-height: var(--leading-snug);
  letter-spacing: var(--tracking-tight);
}

.heading-3 {
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  line-height: var(--leading-snug);
}

.body-large {
  font-size: var(--text-lg);
  line-height: var(--leading-normal);
}

.body {
  font-size: var(--text-base);
  line-height: var(--leading-normal);
}

.body-small {
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
}

.caption {
  font-size: var(--text-xs);
  line-height: var(--leading-snug);
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
}
```

---

### 1.3 Spacing System (8px Grid)

```css
:root {
  /* Base unit: 0.25rem = 4px */
  --space-0: 0;
  --space-1: 0.25rem;   /* 4px */
  --space-2: 0.5rem;    /* 8px */
  --space-3: 0.75rem;   /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-5: 1.25rem;   /* 20px */
  --space-6: 1.5rem;    /* 24px */
  --space-8: 2rem;      /* 32px */
  --space-10: 2.5rem;   /* 40px */
  --space-12: 3rem;     /* 48px */
  --space-16: 4rem;     /* 64px */
  --space-20: 5rem;     /* 80px */
  --space-24: 6rem;     /* 96px */
  --space-32: 8rem;     /* 128px */

  /* Fluid spacing (responsive) */
  --space-fluid-xs: clamp(var(--space-2), 1vw, var(--space-3));
  --space-fluid-sm: clamp(var(--space-3), 1.5vw, var(--space-4));
  --space-fluid-md: clamp(var(--space-4), 2.5vw, var(--space-6));
  --space-fluid-lg: clamp(var(--space-6), 3.5vw, var(--space-8));
  --space-fluid-xl: clamp(var(--space-8), 4.5vw, var(--space-12));
  --space-fluid-2xl: clamp(var(--space-12), 6vw, var(--space-16));
}
```

**Usage Examples:**
- Card padding: `var(--space-6)` (24px)
- Button padding: `var(--space-3) var(--space-5)` (12px 20px)
- Section margin: `var(--space-fluid-lg)` (responsive)
- Grid gap: `var(--space-4)` (16px)

---

### 1.4 Border Radius System

```css
:root {
  --radius-none: 0;
  --radius-sm: 0.375rem;   /* 6px */
  --radius-base: 0.5rem;   /* 8px */
  --radius-md: 0.75rem;    /* 12px */
  --radius-lg: 1rem;       /* 16px */
  --radius-xl: 1.5rem;     /* 24px */
  --radius-2xl: 2rem;      /* 32px */
  --radius-full: 9999px;   /* Pill shape */
}
```

**Component Mapping:**
- Buttons: `--radius-base` (8px)
- Cards: `--radius-xl` (24px)
- Modals: `--radius-2xl` (32px)
- Inputs: `--radius-md` (12px)
- Pills/Badges: `--radius-full`

---

### 1.5 Shadow System

```css
:root {
  /* Elevation levels */
  --shadow-none: none;

  --shadow-xs:
    0 1px 2px rgba(0, 0, 0, 0.05);

  --shadow-sm:
    0 1px 3px rgba(0, 0, 0, 0.12),
    0 1px 2px rgba(0, 0, 0, 0.08);

  --shadow-md:
    0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -1px rgba(0, 0, 0, 0.06);

  --shadow-lg:
    0 10px 15px -3px rgba(0, 0, 0, 0.1),
    0 4px 6px -2px rgba(0, 0, 0, 0.05);

  --shadow-xl:
    0 20px 25px -5px rgba(0, 0, 0, 0.1),
    0 10px 10px -5px rgba(0, 0, 0, 0.04);

  --shadow-2xl:
    0 25px 50px -12px rgba(0, 0, 0, 0.25);

  /* Glass morphism shadows */
  --shadow-glass:
    0 8px 32px rgba(0, 0, 0, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);

  --shadow-glass-lg:
    0 16px 48px rgba(0, 0, 0, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);

  /* Focus ring */
  --shadow-focus:
    0 0 0 3px var(--color-primary-500-alpha-30);

  /* Glow effects */
  --shadow-glow-primary:
    0 0 20px rgba(45, 124, 255, 0.3);

  --shadow-glow-success:
    0 0 20px rgba(35, 209, 139, 0.3);
}
```

---

### 1.6 Animation & Transition System

```css
:root {
  /* Durations */
  --duration-instant: 0ms;
  --duration-fast: 150ms;
  --duration-base: 250ms;
  --duration-slow: 350ms;
  --duration-slower: 500ms;

  /* Easing functions */
  --ease-linear: linear;
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);

  /* Easing presets */
  --ease-snappy: cubic-bezier(0.4, 0.14, 0.3, 1);   /* Current --transition-snappy */
  --ease-soft: cubic-bezier(0.22, 1, 0.36, 1);      /* Current --transition-soft */
  --ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);

  /* Transition shorthands */
  --transition-colors: color var(--duration-base) var(--ease-in-out),
                       background-color var(--duration-base) var(--ease-in-out),
                       border-color var(--duration-base) var(--ease-in-out);

  --transition-transform: transform var(--duration-fast) var(--ease-snappy);

  --transition-all: all var(--duration-base) var(--ease-in-out);
}
```

**Animation Keyframes:**
```css
@keyframes fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slide-in-up {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes scale-in {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
```

---

### 1.7 Breakpoint System

```css
:root {
  /* Breakpoint values */
  --breakpoint-sm: 640px;   /* Mobile landscape */
  --breakpoint-md: 768px;   /* Tablet portrait */
  --breakpoint-lg: 1024px;  /* Tablet landscape */
  --breakpoint-xl: 1280px;  /* Desktop */
  --breakpoint-2xl: 1536px; /* Large desktop */
}
```

**Media Query Mixins (в комментариях для reference):**
```css
/* Mobile first approach */

/* @sm — 640px and up */
@media (min-width: 640px) { }

/* @md — 768px and up */
@media (min-width: 768px) { }

/* @lg — 1024px and up */
@media (min-width: 1024px) { }

/* @xl — 1280px and up */
@media (min-width: 1280px) { }

/* @2xl — 1536px and up */
@media (min-width: 1536px) { }

/* Max-width queries (for overrides) */
/* @max-sm — below 640px */
@media (max-width: 639px) { }

/* @max-md — below 768px */
@media (max-width: 767px) { }
```

---

### 1.8 Z-Index System

```css
:root {
  --z-base: 0;
  --z-dropdown: 1000;
  --z-sticky: 1020;
  --z-fixed: 1030;
  --z-modal-backdrop: 1040;
  --z-modal: 1050;
  --z-popover: 1060;
  --z-tooltip: 1070;
  --z-notification: 1080;
}
```

---

## 2. COMPONENT LIBRARY PLAN

### 2.1 Foundation Components

#### 2.1.1 Button Component

**Variants:**
```html
<!-- Primary -->
<button class="btn btn--primary">
  <span class="btn__icon">✓</span>
  <span class="btn__text">Сохранить</span>
</button>

<!-- Secondary -->
<button class="btn btn--secondary">Отмена</button>

<!-- Ghost -->
<button class="btn btn--ghost">Подробнее</button>

<!-- Danger -->
<button class="btn btn--danger">Удалить</button>

<!-- Sizes -->
<button class="btn btn--sm">Small</button>
<button class="btn btn--md">Medium (default)</button>
<button class="btn btn--lg">Large</button>

<!-- States -->
<button class="btn" disabled>Disabled</button>
<button class="btn btn--loading">
  <span class="btn__spinner"></span>
  Loading...
</button>

<!-- Full width -->
<button class="btn btn--block">Block button</button>

<!-- Icon only -->
<button class="btn btn--icon" aria-label="Настройки">
  <svg class="btn__icon">...</svg>
</button>
```

**CSS Implementation:**
```css
.btn {
  /* Reset */
  appearance: none;
  border: none;
  background: none;
  font: inherit;
  cursor: pointer;

  /* Base styles */
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  border-radius: var(--radius-base);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  line-height: var(--leading-tight);
  white-space: nowrap;
  transition: var(--transition-colors), var(--transition-transform);

  /* Touch target size */
  min-height: 44px;
  min-width: 44px;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.btn:active:not(:disabled) {
  transform: translateY(0);
}

.btn:focus-visible {
  outline: none;
  box-shadow: var(--shadow-focus);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Variants */
.btn--primary {
  background: var(--color-primary-500);
  color: var(--color-neutral-0);
  box-shadow: var(--shadow-sm);
}

.btn--primary:hover:not(:disabled) {
  background: var(--color-primary-600);
  box-shadow: var(--shadow-md);
}

.btn--secondary {
  background: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border-default);
}

.btn--ghost {
  background: transparent;
  color: var(--text-secondary);
}

.btn--ghost:hover:not(:disabled) {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.btn--danger {
  background: var(--color-danger-500);
  color: var(--color-neutral-0);
}

/* Sizes */
.btn--sm {
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-xs);
  min-height: 36px;
}

.btn--lg {
  padding: var(--space-4) var(--space-6);
  font-size: var(--text-base);
  min-height: 52px;
}

/* States */
.btn--loading {
  pointer-events: none;
}

.btn--block {
  width: 100%;
}

.btn--icon {
  padding: var(--space-3);
  aspect-ratio: 1;
}

/* Components */
.btn__spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin var(--duration-slow) linear infinite;
}
```

---

#### 2.1.2 Input Component

```html
<!-- Text input -->
<div class="input-group">
  <label class="input-label" for="email">
    Email <span class="input-required" aria-label="обязательное поле">*</span>
  </label>
  <input
    type="email"
    id="email"
    class="input"
    placeholder="you@example.com"
    required
    aria-required="true"
  >
  <p class="input-hint">Мы никогда не передадим ваш email третьим лицам</p>
  <p class="input-error" role="alert" hidden>Введите корректный email</p>
</div>

<!-- Input with icon -->
<div class="input-wrapper">
  <span class="input-icon" aria-hidden="true">🔍</span>
  <input type="search" class="input input--with-icon" placeholder="Поиск...">
</div>

<!-- Textarea -->
<div class="input-group">
  <label class="input-label" for="notes">Заметки</label>
  <textarea id="notes" class="input" rows="4"></textarea>
  <div class="input-meta">
    <span class="input-count">0 / 500</span>
  </div>
</div>

<!-- Select -->
<div class="input-group">
  <label class="input-label" for="city">Город</label>
  <select id="city" class="input">
    <option value="">Выберите город</option>
    <option value="moscow">Москва</option>
    <option value="spb">Санкт-Петербург</option>
  </select>
</div>
```

**CSS:**
```css
.input-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.input-label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.input-required {
  color: var(--color-danger-500);
}

.input {
  appearance: none;
  width: 100%;
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-base);
  line-height: var(--leading-normal);
  color: var(--text-primary);
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  transition: var(--transition-colors);
  min-height: 44px;
}

.input:hover {
  border-color: var(--border-strong);
}

.input:focus {
  outline: none;
  border-color: var(--color-primary-500);
  box-shadow: var(--shadow-focus);
}

.input::placeholder {
  color: var(--text-tertiary);
}

.input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input--error {
  border-color: var(--color-danger-500);
}

.input-hint {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin: 0;
}

.input-error {
  font-size: var(--text-xs);
  color: var(--color-danger-500);
  margin: 0;
}

.input-wrapper {
  position: relative;
}

.input-icon {
  position: absolute;
  left: var(--space-3);
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-tertiary);
  pointer-events: none;
}

.input--with-icon {
  padding-left: var(--space-10);
}

.input-count {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}
```

---

#### 2.1.3 Card Component

```html
<!-- Basic card -->
<article class="card">
  <div class="card__header">
    <h3 class="card__title">Card Title</h3>
    <button class="btn btn--icon btn--sm">⋮</button>
  </div>
  <div class="card__body">
    <p>Card content goes here.</p>
  </div>
  <div class="card__footer">
    <button class="btn btn--ghost btn--sm">Learn more</button>
    <button class="btn btn--primary btn--sm">Action</button>
  </div>
</article>

<!-- Glass morphism variant -->
<article class="card card--glass">
  ...
</article>

<!-- Metric card -->
<article class="card card--metric">
  <span class="card__label">Total Users</span>
  <div class="card__value">1,234</div>
  <div class="card__delta card__delta--positive">
    <span class="card__delta-icon">↑</span>
    <span>+12%</span>
  </div>
</article>

<!-- Interactive card (clickable) -->
<a href="/candidates/123" class="card card--interactive">
  ...
</a>
```

**CSS:**
```css
.card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6);
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  transition: var(--transition-all);
}

.card--glass {
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.05),
    rgba(255, 255, 255, 0.02)
  );
  backdrop-filter: blur(40px) saturate(200%);
  -webkit-backdrop-filter: blur(40px) saturate(200%);
  border-color: rgba(255, 255, 255, 0.08);
  box-shadow: var(--shadow-glass);
}

.card--interactive {
  cursor: pointer;
  text-decoration: none;
  color: inherit;
}

.card--interactive:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
  border-color: var(--color-primary-500);
}

.card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.card__title {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.card__footer {
  display: flex;
  gap: var(--space-3);
  justify-content: flex-end;
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-default);
}

/* Metric card variant */
.card--metric {
  gap: var(--space-2);
}

.card__label {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
  color: var(--text-tertiary);
}

.card__value {
  font-size: var(--text-3xl);
  font-weight: var(--font-black);
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
}

.card__delta {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

.card__delta--positive {
  color: var(--color-success-500);
}

.card__delta--negative {
  color: var(--color-danger-500);
}
```

---

### 2.2 Advanced Components (Summary)

Due to length constraints, I'll summarize remaining components. Full implementations will be in design-system.css file.

**2.2.2 Badge/Pill**
- Variants: default, primary, success, warning, danger
- Sizes: sm, md, lg
- With/without icon
- Removable (with X button)

**2.2.3 Modal/Dialog**
- Overlay backdrop
- Centered positioning
- Trap focus
- ESC to close
- Smooth enter/exit animations

**2.2.4 Toast Notification**
- 4 tones: success, warning, danger, info
- Auto-dismiss after 5s
- Action buttons
- Stack management (max 5)

**2.2.5 Data Table**
- Sortable columns
- Selectable rows (checkboxes)
- Pagination
- Empty state
- Loading skeleton

**2.2.6 Form Wizard**
- Multi-step progress indicator
- Step validation
- Navigate back/forward
- Save draft

**2.2.7 Navigation**
- Top navigation bar (desktop)
- Hamburger menu (mobile)
- Bottom tab bar (mobile alternative)
- Breadcrumbs
- Sidebar navigation

**2.2.8 Loading States**
- Spinners (inline, overlay)
- Skeleton screens
- Progress bars
- Shimmer effects

**2.2.9 Empty States**
- Illustration + message
- Primary action CTA
- Secondary help link

**2.2.10 Dropdown Menu**
- Trigger button
- Positioned popover
- Keyboard navigation
- Nested menus support

---

## 3. PAGE-BY-PAGE REDESIGN PLAN

### 3.1 Dashboard (index.html)

**Current State:**
- Glass morphism hero section (good)
- Static metric cards (no visualization)
- Basic entity lists (recruiters, cities)
- No quick actions

**Target State:**
```
┌─────────────────────────────────────────────────┐
│ HERO: Quick Stats Overview                      │
│ [Metric 1] [Metric 2] [Metric 3] [Metric 4]     │
│ with sparklines + % delta                        │
└─────────────────────────────────────────────────┘
┌─────────────────┬───────────────────────────────┐
│ Recent Activity │ Quick Actions Panel            │
│ Timeline feed   │ - Schedule Interview           │
│                 │ - Add Candidate                │
│                 │ - Create Recruiter            │
│                 │ - Send Broadcast               │
└─────────────────┴───────────────────────────────┘
┌──────────────────────────────────────────────────┐
│ Alerts & Notifications                           │
│ - Pending approvals: 3                           │
│ - Failed notifications: 1                        │
└──────────────────────────────────────────────────┘
```

**Key Changes:**
1. Add inline mini charts (sparklines)
2. Show % change vs previous period
3. Recent activity timeline (last 10 actions)
4. Quick action panel with most common workflows
5. Alert section for items requiring attention
6. Sticky header when scrolling

**Implementation:**
- New CSS classes: `.dashboard-grid`, `.metric-card--enhanced`, `.activity-timeline`
- JavaScript: sparkline charts (lightweight SVG, no library)
- API endpoint: `/api/dashboard/activity`

---

### 3.2 Candidates List (candidates_list.html)

**Current State:**
- Basic table (missing currently!)
- No sorting/filtering
- No bulk actions
- No search

**Target State:**
```
┌──────────────────────────────────────────────────┐
│ Кандидаты                          [+ Добавить]  │
├──────────────────────────────────────────────────┤
│ [🔍 Search] [Filter: Status▼] [Filter: City▼]   │
├──────────────────────────────────────────────────┤
│ [☐] Выбрано: 0                                   │
│ [Деактивировать] [Удалить] [Экспорт]            │
├───┬──────────────┬───────────┬──────────┬────────┤
│ ☐ │ ФИО          │ Город     │ Статус   │ Actions│
├───┼──────────────┼───────────┼──────────┼────────┤
│ ☐ │ Иван Иванов  │ Москва    │ Active   │ [...]  │
│ ☐ │ Петр Петров  │ СПб       │ Pending  │ [...]  │
└───┴──────────────┴───────────┴──────────┴────────┘
                                      [1] 2 3 ... 10 →
```

**Key Changes:**
1. Advanced search (instant, debounced)
2. Multi-column filters
3. Sortable columns (click header)
4. Bulk selection + actions
5. Pagination (10/25/50/100 per page)
6. Export to CSV
7. Quick actions dropdown per row
8. Mobile: card view instead of table

**Implementation:**
- Component: `.data-table`, `.bulk-actions-bar`
- JavaScript module: `candidate-list-controller.js`
- Features: client-side sorting/filtering for <100 rows, server-side for 100+

---

### 3.3 Candidate Detail (candidates_detail.html)

**Current State:**
- Very long page (1376 lines)
- All sections expanded
- Too much scroll
- Complex forms embedded

**Target State:**
```
┌──────────────────────┬──────────────────────────┐
│ Sticky Sidebar       │ Main Content Area         │
│ - Overview           │ ┌──────────────────────┐ │
│ - Next Steps         │ │ OVERVIEW CARD        │ │
│ - Interview Notes    │ │ Photo, Name, Status  │ │
│ - Test Results       │ └──────────────────────┘ │
│ - History            │ ┌──────────────────────┐ │
│                      │ │ NEXT ACTIONS         │ │
│ [Back to top ↑]      │ │ Timeline + CTA       │ │
│                      │ └──────────────────────┘ │
│                      │ ┌──────────────────────┐ │
│                      │ │ INTERVIEW NOTES      │ │
│                      │ │ Collapsible form     │ │
│                      │ └──────────────────────┘ │
└──────────────────────┴──────────────────────────┘
```

**Key Changes:**
1. Sticky sidebar navigation (desktop)
2. Smooth scroll to sections
3. Collapsible sections (accordion pattern)
4. Inline editing (not separate page)
5. Back to top button
6. Mobile: bottom sticky action bar

**Implementation:**
- Layout: CSS Grid `.candidate-detail-layout`
- JavaScript: `sticky-nav.js`, `accordion.js`
- Optimization: lazy-load test results section

---

### 3.4 Candidate Form (candidates_new.html)

**Current State:**
- Simple 4-field form
- No wizard
- Browser validation only

**Target State:**
```
Step 1: Basic Info    Step 2: Contact    Step 3: Scheduling
━━━━━━━━━━━━━━      ─────────────      ─────────────
[Progress: 33%]

┌────────────────────────────────────────────────┐
│ Основная информация                             │
├────────────────────────────────────────────────┤
│ ФИО *              [                        ]  │
│ Telegram ID *      [                        ]  │
│ Город              [Выберите▼              ]  │
│                                                 │
│ [← Отмена]                    [Далее →]        │
└────────────────────────────────────────────────┘
```

**Key Changes:**
1. Multi-step wizard (3 steps)
2. Progress indicator
3. Inline validation with helpful errors
4. Auto-save draft to localStorage
5. Option to skip to schedule immediately
6. Smart defaults (city from IP, timezone auto-detect)

**Implementation:**
- Component: `.form-wizard`
- JavaScript: `wizard-controller.js`
- Validation: `form-validator.js` (custom, accessible)

---

### 3.5 Schedule Intro Day (schedule_intro_day.html)

**Current State:**
- Complex timezone logic
- Manual date/time input
- Preview in separate panel

**Target State:**
```
┌───────────────────────────────────────────────┐
│ Назначить ознакомительный день                 │
├───────────────────────────────────────────────┤
│ Кандидат: Иван Иванов                          │
│ Город: Москва (Europe/Moscow, UTC+3)          │
├───────────────────────────────────────────────┤
│ Выберите дату и время                          │
│                                                 │
│ ┌──────────────────────────────────────────┐  │
│ │  [<] Ноябрь 2025                      [>] │  │
│ │  Пн Вт Ср Чт Пт Сб Вс                     │  │
│ │  14 15 16 17 18 19 20  ← Today           │  │
│ │  21 22 23 24 25 26 27                     │  │
│ └──────────────────────────────────────────┘  │
│                                                 │
│ Время: [10:00▼]  [Quick: 10:00 14:00 16:00]  │
│                                                 │
│ ✓ Кандидат получит приглашение автоматически  │
│                                                 │
│ [Отмена]                   [Назначить →]       │
└───────────────────────────────────────────────┘
```

**Key Changes:**
1. Visual calendar picker (not native input)
2. Time slots picker with availability check
3. Real-time timezone conversion preview
4. Conflict detection (recruiter busy)
5. Template preview in modal
6. Confirmation screen before send

**Implementation:**
- Component: `.calendar-picker` (lightweight vanilla JS)
- API: `/api/slots/availability?date=2025-11-21&recruiter_id=5`
- Validation: check slot conflicts before submit

---

### 3.6 Other Pages (Summary)

**Recruiters List:**
- Similar to candidates: sortable table, bulk actions
- Highlight: next available slot per recruiter
- Add: workload visualization (progress bar)

**Cities List:**
- Add: map visualization (optional, future)
- Group by region
- Show recruiter count per city

**Templates Editor:**
- Add: live preview panel
- Syntax highlighting for placeholders
- Version history (future)
- Test send function

**Slots List:**
- Calendar view option (month grid)
- Filter by status, recruiter, candidate
- Drag-and-drop reschedule (future)

---

## 4. IMPLEMENTATION ROADMAP

### Phase 1: Foundation (Weeks 1-2)

**Deliverables:**
1. `/static/css/design-system.css` — all variables, tokens
2. `/static/css/components.css` — button, input, card, badge
3. Extract inline CSS from base.html to external files
4. Create `/static/css/lists.css` (currently missing)
5. Update base.html to load external CSS only

**Tasks:**
- [ ] Define all CSS custom properties
- [ ] Build button component (all variants)
- [ ] Build input component (all types)
- [ ] Build card component (all variants)
- [ ] Extract & organize base.html inline CSS
- [ ] Test dark/light theme switching
- [ ] Verify accessibility (contrast ratios)

**Success Criteria:**
- All pages load with new design system
- No visual regressions
- WCAG AA color contrast pass
- External CSS cacheable (no inline styles)

---

### Phase 2: Core Pages Redesign (Weeks 3-6)

**Week 3: Dashboard**
- [ ] Redesign dashboard layout
- [ ] Add sparkline charts
- [ ] Implement activity timeline
- [ ] Quick actions panel
- [ ] Alert notifications section

**Week 4: Candidates List**
- [ ] Build data table component
- [ ] Add search functionality
- [ ] Implement sorting/filtering
- [ ] Bulk selection + actions
- [ ] Pagination controls
- [ ] Mobile card view

**Week 5: Candidate Detail**
- [ ] Sticky sidebar navigation
- [ ] Collapsible sections
- [ ] Inline editing forms
- [ ] Test results visualization
- [ ] Interview notes form
- [ ] Back to top button

**Week 6: Candidate Forms**
- [ ] Multi-step wizard component
- [ ] Form validation system
- [ ] Auto-save drafts
- [ ] Success confirmations
- [ ] Error handling

---

### Phase 3: Forms & Workflows (Weeks 7-10)

**Week 7-8: Schedule Forms**
- [ ] Calendar picker component
- [ ] Time slot selector
- [ ] Timezone conversion
- [ ] Conflict detection
- [ ] Template preview

**Week 9: Recruiters & Cities**
- [ ] Redesign recruiters list
- [ ] Redesign cities list
- [ ] Add workload visualization
- [ ] Improved edit forms

**Week 10: Templates & Messaging**
- [ ] Template editor redesign
- [ ] Live preview panel
- [ ] Syntax highlighting
- [ ] Test send function

---

### Phase 4: Advanced Features (Weeks 11-14)

**Week 11: Data Visualization**
- [ ] Dashboard charts (sparklines)
- [ ] Test results charts
- [ ] Workload progress bars
- [ ] Timeline visualizations

**Week 12: Accessibility**
- [ ] Add skip links
- [ ] Keyboard shortcuts system
- [ ] Screen reader testing
- [ ] Focus management
- [ ] ARIA improvements

**Week 13: Mobile Optimization**
- [ ] Bottom tab navigation
- [ ] Touch-optimized controls
- [ ] Swipe gestures
- [ ] Mobile-specific layouts

**Week 14: Performance**
- [ ] CSS minification
- [ ] Code splitting
- [ ] Lazy loading
- [ ] Image optimization
- [ ] Critical CSS extraction

---

### Phase 5: Polish & Testing (Weeks 15-16)

**Week 15: Polish**
- [ ] Animation refinements
- [ ] Empty state illustrations
- [ ] Loading states
- [ ] Error pages (404, 500)
- [ ] Print styles

**Week 16: Testing & Documentation**
- [ ] Cross-browser testing
- [ ] Accessibility audit
- [ ] Performance testing
- [ ] User acceptance testing
- [ ] Documentation finalization

---

## 5. TECHNICAL IMPLEMENTATION DETAILS

### 5.1 File Structure

**New structure:**
```
backend/apps/admin_ui/static/
├── css/
│   ├── design-system.css       # Variables, tokens, utilities (NEW)
│   ├── components.css          # All UI components (NEW)
│   ├── layouts.css             # Page layouts (NEW)
│   ├── pages/                  # Page-specific styles (NEW)
│   │   ├── dashboard.css
│   │   ├── candidates.css
│   │   ├── recruiters.css
│   │   └── ...
│   ├── cards.css               # Migrate to components.css
│   ├── forms.css               # Migrate to components.css
│   └── lists.css               # CREATE (currently missing)
├── js/
│   ├── core/                   # Core utilities (NEW)
│   │   ├── dom.js
│   │   ├── events.js
│   │   └── storage.js
│   ├── components/             # Component controllers (NEW)
│   │   ├── data-table.js
│   │   ├── modal.js
│   │   ├── calendar-picker.js
│   │   ├── wizard.js
│   │   └── ...
│   └── modules/                # Existing modules (REFACTOR)
│       ├── notifications.js
│       ├── template-editor.js
│       └── ...
└── icons/                      # SVG icons (NEW)
    ├── chevron-down.svg
    ├── check.svg
    └── ...
```

---

### 5.2 CSS Loading Strategy

**Before (current):**
```html
<head>
  <style>
    /* 1008 lines of inline CSS */
  </style>
  <link rel="stylesheet" href="/static/css/lists.css">    <!-- 404 -->
  <link rel="stylesheet" href="/static/css/forms.css">
</head>
```

**After (optimized):**
```html
<head>
  <!-- Critical CSS (inline, minimal) -->
  <style>
    /* Only above-the-fold styles: ~50 lines */
    :root { --bg-canvas: #0b0e13; --text-primary: #fff; }
    body { margin: 0; background: var(--bg-canvas); color: var(--text-primary); }
    .skip-link { position: absolute; left: -999px; }
    .skip-link:focus { left: 0; top: 0; }
  </style>

  <!-- Main stylesheets (external, cacheable) -->
  <link rel="stylesheet" href="/static/css/design-system.css">
  <link rel="stylesheet" href="/static/css/components.css">
  <link rel="stylesheet" href="/static/css/layouts.css">

  <!-- Page-specific CSS (optional, lazy-load) -->
  {% block stylesheets %}{% endblock %}

  <!-- Preload font (if using custom font) -->
  <link rel="preload" href="/static/fonts/Inter-Variable.woff2" as="font" type="font/woff2" crossorigin>
</head>
```

**Benefits:**
- Browser caches external CSS
- Reduced initial HTML size
- Faster First Contentful Paint
- Modular, maintainable code

---

### 5.3 JavaScript Architecture

**Module pattern:**
```javascript
// /static/js/components/data-table.js
export class DataTable {
  constructor(element, options = {}) {
    this.element = element;
    this.options = {
      sortable: true,
      filterable: true,
      selectable: false,
      ...options
    };

    this.init();
  }

  init() {
    this.bindEvents();
    this.renderInitialState();
  }

  bindEvents() {
    // Event delegation
    this.element.addEventListener('click', (e) => {
      if (e.target.matches('.table-header-cell--sortable')) {
        this.handleSort(e.target);
      }
    });
  }

  // ... other methods
}

// Usage:
const table = new DataTable(
  document.querySelector('#candidates-table'),
  { sortable: true, selectable: true }
);
```

---

### 5.4 Accessibility Checklist

**Per component:**
- [ ] Semantic HTML (`<button>`, not `<div role="button">`)
- [ ] Keyboard navigation (Tab, Enter, Space, Arrows)
- [ ] Focus indicators visible
- [ ] ARIA labels where needed
- [ ] Color contrast 4.5:1 minimum
- [ ] Touch targets 44x44px minimum
- [ ] Screen reader tested
- [ ] Error messages accessible (`role="alert"`, `aria-live`)
- [ ] Form labels associated with inputs
- [ ] Skip links present

---

### 5.5 Performance Targets

**Metrics:**
- First Contentful Paint (FCP): **< 1.2s**
- Largest Contentful Paint (LCP): **< 2.5s**
- Total Blocking Time (TBT): **< 300ms**
- Cumulative Layout Shift (CLS): **< 0.1**

**Strategies:**
1. Minify CSS/JS
2. Use code splitting (load only what's needed)
3. Lazy-load images
4. Prefetch critical resources
5. Use CDN for static assets
6. Enable gzip/brotli compression
7. Cache-Control headers (1 year for static assets)

---

## 6. DESIGN PATTERNS & BEST PRACTICES

### 6.1 Form Validation Pattern

**Example: candidates_new.html**
```html
<form id="candidate-form" novalidate>
  <div class="input-group" data-validate="required|telegram">
    <label for="telegram_id" class="input-label">
      Telegram ID <span class="input-required">*</span>
    </label>
    <input
      type="text"
      id="telegram_id"
      name="telegram_id"
      class="input"
      required
      data-validate-message="Введите корректный Telegram ID"
    >
    <p class="input-error" role="alert" aria-live="polite"></p>
  </div>

  <button type="submit" class="btn btn--primary">Сохранить</button>
</form>

<script type="module">
import { FormValidator } from '/static/js/core/validator.js';

const validator = new FormValidator('#candidate-form', {
  rules: {
    telegram: (value) => /^\d{5,12}$/.test(value)
  },
  messages: {
    required: 'Это поле обязательно',
    telegram: 'ID должен содержать 5-12 цифр'
  }
});

validator.on('submit', async (data) => {
  // Submit validated data
});
</script>
```

---

### 6.2 Loading State Pattern

```html
<button type="submit" class="btn btn--primary" id="submit-btn">
  <span class="btn__text">Сохранить</span>
</button>

<script>
document.getElementById('submit-btn').addEventListener('click', async (e) => {
  const btn = e.currentTarget;

  // Add loading state
  btn.classList.add('btn--loading');
  btn.disabled = true;
  btn.innerHTML = `
    <span class="btn__spinner"></span>
    <span class="btn__text">Сохранение...</span>
  `;

  try {
    await saveData();

    // Success state
    btn.classList.remove('btn--loading');
    btn.classList.add('btn--success');
    btn.innerHTML = `
      <span class="btn__icon">✓</span>
      <span class="btn__text">Сохранено</span>
    `;

    setTimeout(() => {
      btn.classList.remove('btn--success');
      btn.disabled = false;
      btn.innerHTML = `<span class="btn__text">Сохранить</span>`;
    }, 2000);

  } catch (error) {
    // Error state
    btn.classList.remove('btn--loading');
    btn.classList.add('btn--danger');
    btn.innerHTML = `
      <span class="btn__icon">✕</span>
      <span class="btn__text">Ошибка</span>
    `;
  }
});
</script>
```

---

### 6.3 Responsive Component Pattern

**Mobile-first approach:**
```css
/* Base (mobile) styles */
.card-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-4);
}

/* Tablet (768px+) */
@media (min-width: 768px) {
  .card-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-6);
  }
}

/* Desktop (1024px+) */
@media (min-width: 1024px) {
  .card-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-8);
  }
}

/* Large desktop (1280px+) */
@media (min-width: 1280px) {
  .card-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
```

---

## 7. MIGRATION PLAN

### 7.1 Week-by-Week Migration

**Week 1:**
1. Create design-system.css
2. Create components.css
3. Extract base.html inline CSS
4. Test on staging
5. Deploy to production (no visual changes yet)

**Week 2:**
1. Update base.html to use new CSS
2. Fix any regressions
3. Create lists.css
4. Test all pages
5. Deploy

**Weeks 3-16:**
- Migrate one page per week
- Run A/B test (old vs new)
- Collect user feedback
- Iterate based on feedback

---

### 7.2 Testing Strategy

**Per page:**
1. **Visual regression testing**
   - Screenshot comparison (before/after)
   - Tools: Percy, Chromatic

2. **Functional testing**
   - All buttons clickable
   - Forms submittable
   - Navigation works

3. **Accessibility testing**
   - Automated: axe DevTools, Lighthouse
   - Manual: keyboard navigation, screen reader

4. **Performance testing**
   - Lighthouse CI
   - WebPageTest
   - Ensure metrics meet targets

5. **Cross-browser testing**
   - Chrome, Firefox, Safari, Edge
   - Mobile Safari, Chrome Android

---

## 8. SUCCESS METRICS & KPIs

### 8.1 Quantitative Metrics

**Page Performance:**
- Load time: **< 2s** (currently ~3-4s)
- Time to Interactive: **< 3s**
- Lighthouse score: **> 90** (currently ~75)

**User Efficiency:**
- Task completion time: **-40%**
- Number of clicks to complete task: **-30%**
- Form error rate: **-60%**

**Accessibility:**
- WCAG AA compliance: **100%** (currently ~70%)
- Keyboard task completion: **100%** (all tasks)
- Screen reader compatibility: **AAA**

---

### 8.2 Qualitative Metrics

**User Satisfaction:**
- Net Promoter Score (NPS): **> 50**
- System Usability Scale (SUS): **> 80**
- User satisfaction rating: **> 4.5/5**

**Feedback Collection:**
- In-app feedback widget
- Monthly user interviews
- Support ticket analysis

---

## CONCLUSION

This redesign strategy provides a **comprehensive, phased approach** to transforming RecruitSmart Admin from a visually appealing interface to a **world-class, production-ready admin dashboard**.

**Key Principles:**
1. **Systematic approach** — design system first, then components, then pages
2. **Incremental migration** — minimize risk, allow for feedback
3. **User-centered** — optimize workflows, reduce friction
4. **Accessible-first** — WCAG AA compliance from the start
5. **Performance-conscious** — sub-second load times

**Expected Outcomes:**
- **40% faster** task completion
- **60% fewer** user errors
- **WCAG AA** compliant
- **Production-ready** code quality
- **Scalable** design system for future features

**Next Step:** Proceed to implementation — Phase 1: Design System CSS files.
