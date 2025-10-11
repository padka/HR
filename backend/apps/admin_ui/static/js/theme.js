(function () {
  const doc = document.documentElement;
  const KEY = 'tg-admin-density';
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const read = () => { try { const value = window.localStorage.getItem(KEY); return value === 'compact' ? 'compact' : 'comfy'; } catch (err) { return 'comfy'; } };
  const write = (value) => { try { window.localStorage.setItem(KEY, value); } catch (err) {} };
  const reflect = (value) => {
    document.querySelectorAll('[data-density-toggle]').forEach((btn) => { btn.dataset.density = value; btn.setAttribute('aria-pressed', value === 'compact' ? 'true' : 'false'); });
    document.querySelectorAll('[data-density-option]').forEach((opt) => { opt.setAttribute('aria-checked', opt.dataset.densityOption === value ? 'true' : 'false'); });
  };
  const apply = (value, options) => { const mode = value === 'compact' ? 'compact' : 'comfy'; doc.dataset.density = mode; reflect(mode); if (!options || options.persist !== false) write(mode); return mode; };
  const cycle = () => (doc.dataset.density === 'compact' ? 'comfy' : 'compact');
  const currentScheme = () => { const theme = doc.dataset.theme; const stored = doc.dataset.themeMode; if (theme === 'light' || theme === 'dark') return theme; if (stored === 'light' || stored === 'dark') return stored; return media.matches ? 'dark' : 'light'; };
  const updateScheme = () => { doc.style.colorScheme = currentScheme(); };
  media.addEventListener('change', () => { if (!doc.dataset.theme || doc.dataset.theme === 'auto') updateScheme(); });
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-density-toggle]').forEach((btn) => { if (btn.dataset.boundDensity === 'true') return; btn.dataset.boundDensity = 'true'; btn.addEventListener('click', () => { apply(cycle()); }); });
    document.querySelectorAll('[data-density-option]').forEach((opt) => { if (opt.dataset.boundDensity === 'true') return; opt.dataset.boundDensity = 'true'; opt.addEventListener('click', () => { apply(opt.dataset.densityOption); }); });
    updateScheme();
    reflect(doc.dataset.density || 'comfy');
  });
  apply(read(), { persist: false });
  updateScheme();
  if (window.TGTheme && typeof window.TGTheme.apply === 'function') { const original = window.TGTheme.apply; window.TGTheme.apply = (mode, options) => { original(mode, options); updateScheme(); }; updateScheme(); }
  window.UITheme = { applyDensity: apply, cycleDensity: cycle, getDensity: () => doc.dataset.density || 'comfy' };
})();
