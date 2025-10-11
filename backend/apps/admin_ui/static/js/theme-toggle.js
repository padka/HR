(function () {
  const storageKey = 'tg-admin-theme';
  const cycleOrder = ['auto', 'light', 'dark'];
  const docEl = document.documentElement;
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const subscribers = new Set();

  function systemTheme() {
    return media.matches ? 'dark' : 'light';
  }

  function normalise(value) {
    if (value === 'light' || value === 'dark' || value === 'auto') {
      return value;
    }
    return 'auto';
  }

  function readStorage() {
    try {
      return normalise(window.localStorage.getItem(storageKey));
    } catch (err) {
      return 'auto';
    }
  }

  function writeStorage(value) {
    try {
      window.localStorage.setItem(storageKey, normalise(value));
    } catch (err) {
      /* noop */
    }
  }

  function setColorScheme(theme) {
    if (theme === 'light' || theme === 'dark') {
      docEl.dataset.theme = theme;
      docEl.style.colorScheme = theme;
    } else {
      delete docEl.dataset.theme;
      docEl.style.colorScheme = systemTheme();
    }
    docEl.dataset.themeMode = theme;
  }

  function applyTheme(theme, options) {
    const mode = normalise(theme);
    const persist = !(options && options.persist === false);
    setColorScheme(mode);
    if (persist) {
      writeStorage(mode);
    }
    const detail = { mode, system: systemTheme() };
    subscribers.forEach((fn) => {
      try {
        fn(detail);
      } catch (err) {
        /* noop */
      }
    });
  }

  function nextMode(current) {
    const index = cycleOrder.indexOf(normalise(current));
    return cycleOrder[(index + 1) % cycleOrder.length];
  }

  function describe(mode) {
    switch (mode) {
      case 'light':
        return {
          label: 'Светлая тема',
          action: 'Переключить на тёмную тему',
          pressed: 'false',
        };
      case 'dark':
        return {
          label: 'Тёмная тема',
          action: 'Переключить на автоматическую тему',
          pressed: 'true',
        };
      default:
        return {
          label: 'Автоматическая тема',
          action: 'Переключить на светлую тему',
          pressed: 'mixed',
        };
    }
  }

  function reflectControl(control, mode) {
    const info = describe(mode);
    control.dataset.themeState = mode;
    control.setAttribute('aria-pressed', info.pressed);
    control.setAttribute('aria-label', info.action);
    const labelEl = control.querySelector('[data-theme-label]');
    if (labelEl) {
      labelEl.textContent = info.label;
    }
  }

  function attachToggle(control) {
    if (!control || control.dataset.themeBound === 'true') {
      return;
    }

    const update = (detail) => {
      reflectControl(control, detail.mode);
    };

    subscribers.add(update);
    control.dataset.themeBound = 'true';
    control.addEventListener('click', () => {
      const current = docEl.dataset.themeMode || readStorage();
      const target = nextMode(current);
      applyTheme(target);
    });

    reflectControl(control, docEl.dataset.themeMode || readStorage());
  }

  function handleSystemChange() {
    const stored = readStorage();
    if (stored === 'auto') {
      applyTheme('auto', { persist: false });
    } else {
      setColorScheme(stored);
    }
  }

  if (typeof media.addEventListener === 'function') {
    media.addEventListener('change', handleSystemChange);
  }

  const initialMode = docEl.dataset.themeMode || readStorage();
  setColorScheme(initialMode);

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-theme-toggle]').forEach(attachToggle);
  });

  window.TGTheme = {
    apply: applyTheme,
    attachToggle,
    getMode: () => normalise(docEl.dataset.themeMode || readStorage()),
  };
})();
