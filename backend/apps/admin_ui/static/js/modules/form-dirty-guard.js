export function installDirtyGuard(form, { message = 'У вас есть несохранённые изменения.' } = {}) {
  if (!form) return () => {};
  let isDirty = false;
  const markDirty = () => {
    if (!isDirty) {
      isDirty = true;
      form.dataset.dirty = 'true';
    }
  };
  const resetDirty = () => {
    isDirty = false;
    delete form.dataset.dirty;
  };

  const handleBeforeUnload = (event) => {
    if (!isDirty) return;
    event.preventDefault();
    event.returnValue = message;
    return message;
  };

  const handleSubmit = () => {
    resetDirty();
    window.removeEventListener('beforeunload', handleBeforeUnload);
  };

  form.addEventListener('input', markDirty, { passive: true });
  form.addEventListener('change', markDirty, { passive: true });
  form.addEventListener('submit', handleSubmit);
  form.addEventListener('reset', resetDirty);
  window.addEventListener('beforeunload', handleBeforeUnload);

  return () => {
    form.removeEventListener('input', markDirty);
    form.removeEventListener('change', markDirty);
    form.removeEventListener('submit', handleSubmit);
    form.removeEventListener('reset', resetDirty);
    window.removeEventListener('beforeunload', handleBeforeUnload);
  };
}
