(function () {
  const doc = document.documentElement;
  const DENSITY_KEY = 'tg-admin-density';
  const THEME_KEY = 'tg-admin-theme';
  const media = window.matchMedia('(prefers-color-scheme: dark)');

  const safeRead = (key) => {
    try {
      return window.localStorage.getItem(key);
    } catch (err) {
      return null;
    }
  };

  const safeWrite = (key, value) => {
    try {
      window.localStorage.setItem(key, value);
    } catch (err) {
      /* noop */
    }
  };

  const normaliseTheme = (value) => (value === 'light' || value === 'dark' || value === 'auto' ? value : 'auto');
  const systemTheme = () => (media.matches ? 'dark' : 'light');

  const currentTheme = () => normaliseTheme(doc.dataset.themeMode || safeRead(THEME_KEY) || 'auto');

  const setDocumentTheme = (mode, options = {}) => {
    const target = normaliseTheme(mode);
    if (target === 'light' || target === 'dark') {
      doc.dataset.theme = target;
      doc.style.colorScheme = target;
    } else {
      delete doc.dataset.theme;
      doc.style.colorScheme = systemTheme();
    }
    doc.dataset.themeMode = target;
    if (options.persist !== false) {
      safeWrite(THEME_KEY, target);
    }
    return target;
  };

  const syncThemeWithSystem = () => {
    if (currentTheme() === 'auto') {
      setDocumentTheme('auto', { persist: false });
    }
  };

  const patchThemeBridge = () => {
    if (!window.TGTheme || window.TGTheme.__uiBridge === true) {
      return;
    }
    const original = window.TGTheme.apply;
    window.TGTheme.apply = function patched(mode, options) {
      const result = original.call(this, mode, options);
      setDocumentTheme(window.TGTheme.getMode ? window.TGTheme.getMode() : mode, { persist: options && options.persist });
      return result;
    };
    window.TGTheme.__uiBridge = true;
    setDocumentTheme(window.TGTheme.getMode ? window.TGTheme.getMode() : currentTheme(), { persist: false });
  };

  const normaliseDensity = (value) => (value === 'compact' ? 'compact' : 'comfy');
  const readDensity = () => normaliseDensity(safeRead(DENSITY_KEY));

  const reflectDensityControls = (mode) => {
    document.querySelectorAll('[data-density-toggle]').forEach((btn) => {
      btn.dataset.density = mode;
      btn.setAttribute('aria-pressed', mode === 'compact' ? 'true' : 'false');
    });
    document.querySelectorAll('[data-density-option]').forEach((option) => {
      const isActive = option.dataset.densityOption === mode;
      option.setAttribute('aria-checked', isActive ? 'true' : 'false');
    });
  };

  const setDensity = (mode, options = {}) => {
    const target = normaliseDensity(mode);
    doc.dataset.density = target;
    reflectDensityControls(target);
    if (options.persist !== false) {
      safeWrite(DENSITY_KEY, target);
    }
    return target;
  };

  const cycleDensity = () => (doc.dataset.density === 'compact' ? 'comfy' : 'compact');

  const bindDensityControls = () => {
    document.querySelectorAll('[data-density-toggle]').forEach((btn) => {
      if (btn.dataset.boundDensity === 'true') {
        return;
      }
      btn.dataset.boundDensity = 'true';
      btn.addEventListener('click', () => {
        setDensity(cycleDensity());
      });
    });

    document.querySelectorAll('[data-density-option]').forEach((option) => {
      if (option.dataset.boundDensity === 'true') {
        return;
      }
      option.dataset.boundDensity = 'true';
      option.addEventListener('click', () => {
        setDensity(option.dataset.densityOption);
      });
    });
  };

  setDocumentTheme(currentTheme(), { persist: false });
  setDensity(readDensity(), { persist: false });

  if (typeof media.addEventListener === 'function') {
    media.addEventListener('change', syncThemeWithSystem);
  } else if (typeof media.addListener === 'function') {
    media.addListener(syncThemeWithSystem);
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindDensityControls();
    reflectDensityControls(doc.dataset.density || 'comfy');
    patchThemeBridge();
  });

  window.addEventListener('load', patchThemeBridge);

  window.UITheme = {
    applyTheme: (mode, options) => setDocumentTheme(mode, options),
    getTheme: currentTheme,
    applyDensity: (mode, options) => setDensity(mode, options),
    cycleDensity,
    getDensity: () => doc.dataset.density || 'comfy',
  };
})();
