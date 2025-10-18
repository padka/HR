const contextEl = document.getElementById('slots_context');
const filterForm = document.getElementById('slots_filters');
const chipsWrap = document.getElementById('slots_filter_chips');
const resetButton = document.querySelector('[data-action="reset-filters"]');
const refreshButton = document.querySelector('[data-action="refresh-slots"]');
const inlineButtons = document.querySelectorAll('[data-inline-filter]');
const tableBody = document.getElementById('slots_tbody');
const modal = document.getElementById('slot_modal');
const modalForm = document.getElementById('slot_candidate_form');
const modalDismissButtons = modal ? modal.querySelectorAll('[data-modal-dismiss]') : [];
const modalTitle = modal ? modal.querySelector('#slot_modal_title') : null;
const modalSubtitle = modal ? modal.querySelector('#slot_modal_subtitle') : null;
const cancelButton = modal ? modal.querySelector('[data-action="slot-cancel"]') : null;
const restoreButton = modal ? modal.querySelector('[data-action="slot-restore"]') : null;
const toast = document.getElementById('slot_toast');
const loadingOverlay = document.getElementById('slots_loading');

const filterCity = document.getElementById('filter_city');
const filterRecruiter = document.getElementById('filter_recruiter');
const filterDateFrom = document.getElementById('filter_date_from');
const filterDateTo = document.getElementById('filter_date_to');
const filterStatus = document.getElementById('filter_status');
const filterSearch = document.getElementById('filter_search');

const context = parseContext(contextEl);
const slotsMap = buildSlotsMap(context?.slots ?? []);
let activeSlotId = null;
let lastFocusedElement = null;
let focusHandler = null;
let toastTimer = null;

bindFilters();
bindInlineFilters();
bindModal();
bindRows();

function parseContext(node) {
  if (!node) return {};
  try {
    return JSON.parse(node.textContent || '{}');
  } catch (err) {
    console.warn('slots.context.parse-error', err);
    return {};
  }
}

function buildSlotsMap(slots) {
  const map = new Map();
  slots.forEach((slot) => {
    if (!slot || !slot.id) return;
    map.set(String(slot.id), slot);
  });
  return map;
}

function bindFilters() {
  if (refreshButton) {
    refreshButton.addEventListener('click', () => window.location.reload());
  }
  if (resetButton) {
    resetButton.addEventListener('click', () => {
      if (filterCity) filterCity.value = '';
      if (filterRecruiter) filterRecruiter.value = '';
      if (filterDateFrom) filterDateFrom.value = '';
      if (filterDateTo) filterDateTo.value = '';
      if (filterSearch) filterSearch.value = '';
      if (filterStatus) {
        Array.from(filterStatus.options).forEach((option) => {
          option.selected = false;
        });
      }
      filterForm?.submit();
    });
  }
  if (chipsWrap) {
    chipsWrap.addEventListener('click', (event) => {
      const target = event.target.closest('button[data-chip-key]');
      if (!target) return;
      event.preventDefault();
      const key = target.dataset.chipKey;
      const value = target.dataset.chipValue || null;
      removeFilterChip(key, value);
      filterForm?.submit();
    });
  }
}

function removeFilterChip(key, value) {
  switch (key) {
    case 'city_id':
      if (filterCity) filterCity.value = '';
      break;
    case 'recruiter_id':
      if (filterRecruiter) filterRecruiter.value = '';
      break;
    case 'date_from':
      if (filterDateFrom) filterDateFrom.value = '';
      break;
    case 'date_to':
      if (filterDateTo) filterDateTo.value = '';
      break;
    case 'status':
      if (filterStatus) {
        Array.from(filterStatus.options).forEach((option) => {
          if (option.value === value) {
            option.selected = false;
          }
        });
      }
      break;
    case 'search':
      if (filterSearch) {
        const tokens = filterSearch.value
          .split(/\s+/)
          .filter(Boolean)
          .filter((token) => token !== value);
        filterSearch.value = tokens.join(' ');
      }
      break;
    default:
      break;
  }
}

function bindInlineFilters() {
  inlineButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const targetId = button.dataset.inlineFilter;
      if (!targetId) return;
      const target = document.getElementById(targetId);
      if (!target) return;
      target.focus({ preventScroll: false });
    });
  });
}

function bindRows() {
  if (!tableBody) return;
  tableBody.addEventListener('click', (event) => {
    const button = event.target.closest('[data-slot-detail]');
    if (!button) return;
    event.preventDefault();
    const slotId = String(button.dataset.slotDetail || '').trim();
    if (!slotId) return;
    openModal(slotId, button);
  });
}

function bindModal() {
  if (!modal) return;
  modalDismissButtons.forEach((button) => {
    button.addEventListener('click', () => closeModal());
  });
  modal.addEventListener('click', (event) => {
    if (event.target === modal) {
      closeModal();
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modal.hasAttribute('hidden')) {
      event.preventDefault();
      closeModal();
    }
  });
  if (modalForm) {
    modalForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!activeSlotId) return;
      const formData = new FormData(modalForm);
      const payload = buildCandidatePayload(formData);
      await submitCandidateUpdate(activeSlotId, payload);
    });
  }
  if (cancelButton) {
    cancelButton.addEventListener('click', async () => {
      if (!activeSlotId) return;
      await mutateSlot(`/api/slots/${activeSlotId}/cancel`, 'POST', 'Слот отменён');
    });
  }
  if (restoreButton) {
    restoreButton.addEventListener('click', async () => {
      if (!activeSlotId) return;
      await mutateSlot(`/api/slots/${activeSlotId}/restore`, 'POST', 'Слот восстановлен');
    });
  }
}

function openModal(slotId, trigger) {
  if (!modal) return;
  activeSlotId = slotId;
  lastFocusedElement = trigger || document.activeElement;
  modal.removeAttribute('hidden');
  modal.classList.add('is-open');
  lockFocus();
  loadSlot(slotId);
}

function closeModal() {
  if (!modal) return;
  unlockFocus();
  modal.classList.remove('is-open');
  modal.setAttribute('hidden', '');
  activeSlotId = null;
  if (modalForm) {
    modalForm.reset();
    setFormDisabled(false);
  }
  if (restoreButton) restoreButton.hidden = true;
  if (cancelButton) cancelButton.disabled = false;
  if (typeof lastFocusedElement?.focus === 'function') {
    lastFocusedElement.focus({ preventScroll: false });
  }
}

function lockFocus() {
  if (!modal) return;
  const focusable = getFocusable(modal);
  if (focusable.length) {
    focusable[0].focus({ preventScroll: true });
  }
  focusHandler = (event) => {
    if (event.key !== 'Tab') return;
    const elements = getFocusable(modal);
    if (!elements.length) return;
    const first = elements[0];
    const last = elements[elements.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };
  modal.addEventListener('keydown', focusHandler);
}

function unlockFocus() {
  if (!modal || !focusHandler) return;
  modal.removeEventListener('keydown', focusHandler);
  focusHandler = null;
}

function getFocusable(root) {
  return Array.from(
    root.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((el) => !el.hasAttribute('hidden'));
}

async function loadSlot(slotId) {
  showLoading(true);
  setFormDisabled(true);
  try {
    const response = await fetch(`/api/slots/${slotId}`);
    if (!response.ok) throw new Error('failed');
    const slot = await response.json();
    applySlotToModal(slot);
    slotsMap.set(String(slot.id), slot);
    setFormDisabled(false);
  } catch (err) {
    console.error('slots.modal.load-failed', err);
    showToast('Не удалось загрузить данные слота', 'error');
    closeModal();
  } finally {
    showLoading(false);
  }
}

function applySlotToModal(slot) {
  if (!modalForm) return;
  modalTitle.textContent = `Слот #${slot.id}`;
  const start = slot.start_at ? formatUtc(slot.start_at) : null;
  const city = slot.city?.name ?? '—';
  modalSubtitle.textContent = start ? `${start} · ${city}` : city;

  modalForm.full_name.value = slot.candidate?.full_name ?? '';
  modalForm.phone.value = slot.candidate?.phone ?? '';
  modalForm.email.value = slot.candidate?.email ?? '';
  modalForm.notes.value = slot.candidate?.notes ?? '';
  modalForm.booking_confirmed.checked = Boolean(slot.booking_confirmed);
  if (restoreButton) {
    restoreButton.hidden = !slot.cancelled_at;
  }
  if (cancelButton) {
    cancelButton.disabled = Boolean(slot.cancelled_at);
  }
}

function formatUtc(isoString) {
  try {
    const date = new Date(isoString);
    const formatter = new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
    return formatter.format(date);
  } catch (_err) {
    return '';
  }
}

function buildCandidatePayload(formData) {
  const payload = {
    full_name: formData.get('full_name'),
    phone: formData.get('phone'),
    email: formData.get('email'),
    notes: formData.get('notes'),
    booking_confirmed: formData.get('booking_confirmed') === 'on',
  };
  Object.keys(payload).forEach((key) => {
    const value = payload[key];
    if (typeof value === 'string') {
      const trimmed = value.trim();
      payload[key] = trimmed;
      if (!trimmed && key !== 'booking_confirmed') {
        delete payload[key];
      }
    }
  });
  if (!payload.booking_confirmed) {
    payload.booking_confirmed = false;
  }
  return payload;
}

async function submitCandidateUpdate(slotId, payload) {
  showLoading(true);
  setFormDisabled(true);
  try {
    const response = await fetch(`/api/slots/${slotId}/candidate`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error('failed');
    const data = await response.json();
    if (!data?.slot) throw new Error('invalid');
    slotsMap.set(String(data.slot.id), data.slot);
    updateTableRow(data.slot);
    applySlotToModal(data.slot);
    const message = data.slot.booking_confirmed ? 'Слот забронирован' : 'Слот обновлён';
    showToast(message, 'success');
    setFormDisabled(false);
  } catch (err) {
    console.error('slots.candidate.update-failed', err);
    showToast('Не удалось сохранить данные', 'error');
    setFormDisabled(false);
  } finally {
    showLoading(false);
  }
}

async function mutateSlot(url, method, successMessage) {
  showLoading(true);
  setFormDisabled(true);
  try {
    const response = await fetch(url, { method });
    if (!response.ok) throw new Error('failed');
    const data = await response.json();
    if (!data?.slot) throw new Error('invalid');
    slotsMap.set(String(data.slot.id), data.slot);
    updateTableRow(data.slot);
    applySlotToModal(data.slot);
    showToast(successMessage, 'success');
  } catch (err) {
    console.error('slots.mutate.failed', err);
    showToast('Не удалось обновить слот', 'error');
  } finally {
    setFormDisabled(false);
    showLoading(false);
  }
}

function updateTableRow(slot) {
  const row = tableBody?.querySelector(`[data-slot-id="${slot.id}"]`);
  if (!row) return;
  const candidateCell = row.querySelector('.slots-cell-candidate');
  if (candidateCell) {
    const main = candidateCell.querySelector('.slots-cell-main');
    if (main) main.textContent = slot.candidate?.full_name || '—';
    const sub = candidateCell.querySelector('.slots-cell-sub');
    const detail = slot.candidate?.phone || slot.candidate?.email || slot.candidate?.notes || '';
    if (sub) {
      if (detail) {
        sub.textContent = detail;
        sub.hidden = false;
      } else {
        sub.textContent = '';
        sub.hidden = true;
      }
    }
  }
  const statusBadge = row.querySelector('.slots-status');
  if (statusBadge) {
    const status = slot.status || 'Free';
    statusBadge.textContent = status;
    statusBadge.className = `slots-status slots-status--${status.toLowerCase()}`;
  }
}

function setFormDisabled(state) {
  if (!modalForm) return;
  const elements = modalForm.querySelectorAll('input, textarea, button');
  const currentSlot = activeSlotId ? slotsMap.get(String(activeSlotId)) : null;
  elements.forEach((el) => {
    if (state) {
      el.setAttribute('disabled', 'disabled');
    } else if (!(el.matches('[data-action="slot-restore"]') && el.hidden)) {
      el.removeAttribute('disabled');
    }
  });
  if (cancelButton) {
    if (state) {
      cancelButton.setAttribute('disabled', 'disabled');
    } else {
      cancelButton.disabled = Boolean(currentSlot?.cancelled_at);
    }
  }
  if (restoreButton) {
    if (state) {
      restoreButton.setAttribute('disabled', 'disabled');
    } else if (!restoreButton.hidden) {
      restoreButton.removeAttribute('disabled');
    } else {
      restoreButton.setAttribute('disabled', 'disabled');
    }
  }
}

function showLoading(state) {
  if (!loadingOverlay) return;
  loadingOverlay.hidden = !state;
}

function showToast(message, tone = 'info') {
  if (!toast) return;
  toast.textContent = message;
  toast.dataset.tone = tone;
  toast.classList.add('is-visible');
  if (toastTimer) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toast.classList.remove('is-visible');
    toast.textContent = '';
    toast.removeAttribute('data-tone');
  }, 4000);
}
