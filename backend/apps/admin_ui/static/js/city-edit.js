const ready = (callback) => {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', callback, { once: true });
  } else {
    callback();
  }
};

ready(() => {
  const form = document.getElementById('city_form');
  if (!form) return;

  const cityId = form.dataset.cityId;
  const nameInput = form.querySelector('#city_name');
  const tzInput = form.querySelector('#city_tz');
  const activeInput = form.querySelector('#city_active');
  const ownerSelect = form.querySelector('#city_owner');
  const planWeekInput = form.querySelector('#plan_week');
  const planMonthInput = form.querySelector('#plan_month');
  const criteriaInput = form.querySelector('#criteria');
  const expertsInput = form.querySelector('#experts');
  const stageInputs = Array.from(form.querySelectorAll('[data-stage-input]'));
  const stageDefaultButtons = Array.from(form.querySelectorAll('[data-stage-default]'));
  const statusText = form.querySelector('[data-status-text]');
  const saveButton = form.querySelector('[data-save]');
  const cancelButton = form.querySelector('[data-cancel]');
  const deleteButton = form.querySelector('[data-delete]');
  const cityChip = document.querySelector('[data-city-chip]');
  const activeBadge = document.querySelector('[data-active-badge]');
  const activeLabel = activeBadge ? activeBadge.querySelector('[data-active-label]') : null;

  let isDirty = false;
  let saving = false;
  let initialState = snapshot();

  function snapshot() {
    const templates = {};
    stageInputs.forEach((textarea) => {
      const key = textarea.dataset.stageInput || '';
      templates[key] = textarea.value || '';
    });
    return {
      name: (nameInput?.value || '').trim(),
      tz: (tzInput?.value || '').trim(),
      active: Boolean(activeInput?.checked),
      owner: ownerSelect?.value || '',
      planWeek: planWeekInput?.value || '',
      planMonth: planMonthInput?.value || '',
      criteria: criteriaInput?.value || '',
      experts: expertsInput?.value || '',
      templates,
    };
  }

  function statesEqual(a, b) {
    if (!a || !b) return false;
    const keys = ['name', 'tz', 'active', 'owner', 'planWeek', 'planMonth', 'criteria', 'experts'];
    for (const key of keys) {
      if (a[key] !== b[key]) return false;
    }
    const aKeys = Object.keys(a.templates || {});
    const bKeys = Object.keys(b.templates || {});
    if (aKeys.length !== bKeys.length) return false;
    for (const key of aKeys) {
      if ((a.templates || {})[key] !== (b.templates || {})[key]) {
        return false;
      }
    }
    return true;
  }

  function updateStatus(message, tone) {
    if (!statusText) return;
    statusText.textContent = message;
    statusText.dataset.tone = tone || '';
    statusText.classList.toggle('text-[rgb(249,110,101)]', tone === 'error');
    statusText.classList.toggle('text-accent', tone === 'success');
    if (tone !== 'success' && tone !== 'error') {
      statusText.classList.remove('text-[rgb(249,110,101)]', 'text-accent');
    }
  }

  function evaluateDirty() {
    const current = snapshot();
    const equal = statesEqual(current, initialState);
    isDirty = !equal;
    updateStatus(equal ? 'Изменений нет' : 'Есть несохранённые изменения', equal ? 'idle' : 'dirty');
    return current;
  }

  function updateChip() {
    if (!cityChip) return;
    const name = (nameInput?.value || '').trim() || 'Город';
    const tz = (tzInput?.value || '').trim() || 'Europe/Moscow';
    cityChip.textContent = `${name} · ${tz}`;
  }

  function updateActiveBadge() {
    if (!activeBadge || !activeLabel) return;
    const isOn = Boolean(activeInput?.checked);
    activeBadge.dataset.state = isOn ? 'on' : 'off';
    activeLabel.textContent = isOn ? 'Активен' : 'Выключен';
  }

  function refreshStageStatus(textarea) {
    const key = textarea.dataset.stageInput;
    if (!key) return;
    const container = form.querySelector(`[data-stage-item="${key}"]`);
    const status = container ? container.querySelector('[data-stage-status]') : null;
    if (!status) return;
    const currentValue = (textarea.value || '').trim();
    const defaultValue = (textarea.dataset.stageDefaultText || '').trim();
    const isCustom = currentValue.length > 0 && currentValue !== defaultValue;
    status.textContent = isCustom ? 'Своя версия' : 'По умолчанию';
  }

  function buildPayload() {
    const templates = {};
    stageInputs.forEach((textarea) => {
      const key = textarea.dataset.stageInput;
      if (key) {
        templates[key] = textarea.value || '';
      }
    });
    return {
      name: (nameInput?.value || '').trim(),
      tz: (tzInput?.value || '').trim(),
      active: Boolean(activeInput?.checked),
      responsible_recruiter_id: ownerSelect?.value || '',
      plan_week: planWeekInput?.value || '',
      plan_month: planMonthInput?.value || '',
      criteria: (criteriaInput?.value || '').trim(),
      experts: (expertsInput?.value || '').trim(),
      templates,
    };
  }

  function setSavingState(state) {
    saving = state;
    if (saveButton) {
      saveButton.disabled = state;
      saveButton.textContent = state ? 'Сохраняем…' : 'Сохранить';
    }
  }

  async function handleSave() {
    if (!cityId || saving) return;
    setSavingState(true);
    updateStatus('Сохраняем…', 'progress');
    const payload = buildPayload();
    try {
      const response = await fetch(`/cities/${cityId}/settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify(payload),
      });
      let json = null;
      try {
        json = await response.json();
      } catch (err) {
        json = null;
      }
      if (!response.ok || !json || json.ok !== true) {
        const errorMessage = json && json.error ? json.error : 'save_failed';
        throw new Error(errorMessage);
      }
      initialState = snapshot();
      isDirty = false;
      updateStatus('Изменения сохранены', 'success');
      setTimeout(() => {
        evaluateDirty();
      }, 2000);
    } catch (error) {
      console.error(error);
      updateStatus('Не удалось сохранить', 'error');
      setTimeout(() => {
        evaluateDirty();
      }, 2200);
    } finally {
      setSavingState(false);
    }
  }

  async function handleDelete() {
    if (!cityId || !deleteButton) return;
    const cityName = (nameInput?.value || '').trim() || 'город';
    const confirmed = window.confirm(`Удалить город «${cityName}»? Действие нельзя отменить.`);
    if (!confirmed) return;
    const originalText = deleteButton.textContent;
    deleteButton.disabled = true;
    deleteButton.textContent = 'Удаляем…';
    updateStatus('Удаляем…', 'progress');
    try {
      const response = await fetch(`/cities/${cityId}/delete`, {
        method: 'POST',
        headers: { Accept: 'application/json' },
      });
      let json = null;
      try {
        json = await response.json();
      } catch (err) {
        json = null;
      }
      if (!response.ok || !json || json.ok !== true) {
        throw new Error(json && json.error ? json.error : 'delete_failed');
      }
      isDirty = false;
      updateStatus('Город удалён', 'success');
      setTimeout(() => {
        window.location.href = '/cities';
      }, 600);
    } catch (error) {
      console.error(error);
      updateStatus('Не удалось удалить', 'error');
      setTimeout(() => {
        evaluateDirty();
      }, 2200);
      deleteButton.disabled = false;
      deleteButton.textContent = originalText;
      return;
    }
  }

  const tracked = [
    nameInput,
    tzInput,
    planWeekInput,
    planMonthInput,
    criteriaInput,
    expertsInput,
  ];

  tracked.forEach((input) => {
    if (!input) return;
    const eventName = input.tagName === 'SELECT' ? 'change' : 'input';
    input.addEventListener(eventName, () => {
      if (input === nameInput || input === tzInput) {
        updateChip();
      }
      evaluateDirty();
    });
  });

  if (ownerSelect) {
    ownerSelect.addEventListener('change', () => {
      evaluateDirty();
    });
  }

  if (activeInput) {
    activeInput.addEventListener('change', () => {
      updateActiveBadge();
      evaluateDirty();
    });
  }

  stageInputs.forEach((textarea) => {
    refreshStageStatus(textarea);
    textarea.addEventListener('input', () => {
      refreshStageStatus(textarea);
      evaluateDirty();
    });
  });

  stageDefaultButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const key = button.dataset.stageDefault;
      if (!key) return;
      const target = form.querySelector(`[data-stage-input="${key}"]`);
      if (!target) return;
      target.value = target.dataset.stageDefaultText || '';
      target.dispatchEvent(new Event('input', { bubbles: true }));
    });
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    handleSave();
  });

  if (saveButton) {
    saveButton.addEventListener('click', (event) => {
      event.preventDefault();
      handleSave();
    });
  }

  if (cancelButton) {
    cancelButton.addEventListener('click', () => {
      if (isDirty) {
        const confirmed = window.confirm('Есть несохранённые изменения. Выйти без сохранения?');
        if (!confirmed) {
          return;
        }
      }
      isDirty = false;
      window.location.href = '/cities';
    });
  }

  if (deleteButton) {
    deleteButton.addEventListener('click', (event) => {
      event.preventDefault();
      handleDelete();
    });
  }

  window.addEventListener('beforeunload', (event) => {
    if (!isDirty) return;
    event.preventDefault();
    event.returnValue = '';
  });

  updateChip();
  updateActiveBadge();
  evaluateDirty();
});
