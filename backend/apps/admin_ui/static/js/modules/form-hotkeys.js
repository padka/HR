export function bindSubmitHotkey(form, options = {}) {
  if (!form) { return () => {}; }

  const config = {
    key: 's',
    ctrlKey: false,
    metaKey: false,
    ctrlOrMeta: true,
    preventDefault: true,
    scope: document,
    ...options
  };

  const handler = (event) => {
    const matchesKey = event.key && event.key.toLowerCase() === String(config.key).toLowerCase();
    if (!matchesKey) { return; }
    if (config.ctrlOrMeta) {
      if (!(event.ctrlKey || event.metaKey)) { return; }
    } else {
      if (config.ctrlKey && !event.ctrlKey) { return; }
      if (config.metaKey && !event.metaKey) { return; }
    }
    if (config.altKey && !event.altKey) { return; }
    if (config.shiftKey && !event.shiftKey) { return; }
    if (config.preventDefault) {
      event.preventDefault();
    }
    form.requestSubmit();
  };

  config.scope.addEventListener('keydown', handler);
  return () => config.scope.removeEventListener('keydown', handler);
}
