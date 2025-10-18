const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const contextEl = document.getElementById('slots_context');
const slotsContext = contextEl ? safeJson(contextEl.textContent) : {};

const table = document.getElementById('slots_table');
const tbody = document.getElementById('slots_tbody');
let rows = tbody ? Array.from(tbody.querySelectorAll('.slot-row')) : [];

const perPageForm = document.getElementById('slots_per_page_form');
const perPageSelect = perPageForm ? perPageForm.querySelector('#per_page') : null;

const onlyFutureToggle = document.getElementById('slots_only_future');
const roleSwitchButtons = $$('.slots-role-switch__btn');
const searchInput = document.getElementById('slots_search_input');
const searchTokensWrap = document.getElementById('slots_search_tokens');
const bulkBar = document.getElementById('slots_bulk_bar');
const bulkCount = document.getElementById('slots_bulk_count');
const bulkAssignSelect = document.getElementById('slots_bulk_assign');
const bulkButtons = $$('[data-bulk-action]');
const chipTriggers = $$('.chip--trigger');
const activeTagsWrap = document.getElementById('slots_active_tags');
const filterSheet = document.getElementById('slots_filter_sheet');
const filterBackdrop = document.getElementById('slots_filter_backdrop');
const filterCloseBtn = filterSheet ? filterSheet.querySelector('[data-filter-close]') : null;
const filterApplyBtn = filterSheet ? filterSheet.querySelector('[data-filter-apply]') : null;
const filterResetBtn = filterSheet ? filterSheet.querySelector('[data-filter-reset]') : null;
const deleteAllBtn = document.getElementById('delete_all_slots');
const toastStack = document.getElementById('toasts');
const emptyCard = document.getElementById('slot_empty_state');
const selectAll = document.getElementById('slots_select_all');

const sheetBackdrop = document.getElementById('slot_backdrop');
const sheet = document.getElementById('slot_sheet');

const sheetRefs = sheet ? {
  title: sheet.querySelector('#slot_sheet_title'),
  sub: sheet.querySelector('#slot_sheet_sub'),
  id: sheet.querySelector('#slot_sheet_id'),
  status: sheet.querySelector('#slot_sheet_status'),
  utc: sheet.querySelector('#slot_sheet_utc'),
  local: sheet.querySelector('#slot_sheet_local'),
  cityWrap: sheet.querySelector('#slot_sheet_city_wrap'),
  city: sheet.querySelector('#slot_sheet_city'),
  cityTz: sheet.querySelector('#slot_sheet_city_tz'),
  localCandidateWrap: sheet.querySelector('#slot_sheet_local_candidate_wrap'),
  localCandidate: sheet.querySelector('#slot_sheet_local_candidate'),
  rel: sheet.querySelector('#slot_sheet_rel'),
  recruiter: sheet.querySelector('#slot_sheet_recruiter'),
  candidateSection: sheet.querySelector('#slot_sheet_candidate_section'),
  candidate: sheet.querySelector('#slot_sheet_candidate'),
  candidateActions: sheet.querySelector('#slot_sheet_candidate_actions'),
  reschedule: sheet.querySelector('#slot_reschedule_btn'),
  reject: sheet.querySelector('#slot_reject_btn'),
  outcomeSection: sheet.querySelector('#slot_sheet_outcome_section'),
  outcomeHint: sheet.querySelector('#slot_sheet_outcome_hint'),
  outcomeActions: sheet.querySelector('#slot_sheet_outcome_actions'),
  outcomeStatus: sheet.querySelector('#slot_sheet_outcome_status'),
  meta: sheet.querySelector('#slot_sheet_meta'),
  delete: sheet.querySelector('#slot_delete_btn'),
  close: sheet.querySelector('#slot_sheet_close'),
} : {};

const kpiIds = {
  total: document.getElementById('cnt-total'),
  free: document.getElementById('cnt-free'),
  pending: document.getElementById('cnt-pending'),
  booked: document.getElementById('cnt-booked'),
  confirmed: document.getElementById('cnt-confirmed'),
};

const state = {
  sort: { key: 'time', dir: 'asc' },
  role: readInitialRole(),
  onlyFuture: readFutureFlag(),
  tokens: readInitialTokens(),
  filters: {
    recruiter: String(slotsContext?.filters?.recruiter_id ?? '') || '',
    status: String(slotsContext?.filters?.status ?? '') || '',
    city: String(slotsContext?.filters?.city_id ?? '') || '',
  },
  selection: new Set(),
  deleteConfirmRow: null,
  bulkConfirm: null,
};

let relTimer = null;

init();

function init() {
  if (!table || !tbody) return;

  applyInitialRole();
  applyInitialFuture();
  hydrateTokens();
  bindEvents();
  applyFilters();
  applySort('time', 'asc', { silent: true });
  scheduleRelativeUpdates();
}

function safeJson(text) {
  try {
    return JSON.parse(text || '{}');
  } catch (err) {
    console.warn('slots-context.parse-error', err);
    return {};
  }
}

function readInitialTokens() {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get('search');
  if (!raw) return [];
  return raw
    .split(',')
    .map((token) => token.trim())
    .filter(Boolean);
}

function readInitialRole() {
  const params = new URLSearchParams(window.location.search);
  const value = params.get('role');
  return value === 'candidate' ? 'candidate' : 'recruiter';
}

function readFutureFlag() {
  const params = new URLSearchParams(window.location.search);
  return params.get('future') === '1';
}

function bindEvents() {
  if (perPageSelect && perPageForm) {
    perPageSelect.addEventListener('change', () => perPageForm.submit());
  }

  if (onlyFutureToggle) {
    onlyFutureToggle.checked = state.onlyFuture;
    onlyFutureToggle.addEventListener('change', () => {
      state.onlyFuture = !!onlyFutureToggle.checked;
      applyFilters();
      syncQueryState();
    });
  }

  roleSwitchButtons.forEach((btn) => {
    btn.classList.toggle('is-active', btn.dataset.roleTarget === state.role);
    btn.addEventListener('click', () => {
      if (btn.dataset.roleTarget === state.role) return;
      state.role = btn.dataset.roleTarget === 'candidate' ? 'candidate' : 'recruiter';
      applyRole();
      syncQueryState();
    });
  });

  if (searchInput) {
    searchInput.addEventListener('keydown', handleSearchKey);
    searchInput.addEventListener('blur', () => addTokenFromInput());
  }

  if (searchTokensWrap) {
    searchTokensWrap.addEventListener('click', (event) => {
      const target = event.target.closest('[data-token-remove]');
      if (!target) return;
      const token = target.dataset.tokenRemove;
      removeToken(token);
    });
  }

  if (selectAll) {
    selectAll.addEventListener('change', () => {
      const checked = selectAll.checked;
      getSelectableRows().forEach((row) => {
        const checkbox = row.querySelector('.slot-select');
        if (!checkbox) return;
        checkbox.checked = checked;
        toggleSelection(row.dataset.id, checked);
      });
      updateSelectionUI();
    });
  }

  rows.forEach((row) => {
    const checkbox = row.querySelector('.slot-select');
    if (checkbox) {
      checkbox.addEventListener('change', () => {
        toggleSelection(row.dataset.id, checkbox.checked);
        updateSelectionUI();
      });
    }

    const tgButton = row.querySelector('button[data-action="write-tg"]');
    if (tgButton) {
      tgButton.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        handleRowAction(row, 'write-tg', tgButton);
      });
    }

    row.addEventListener('click', (event) => {
      if (event.target.closest('button') || event.target.closest('a') || event.target.matches('input')) {
        return;
      }
      openSheetWithRow(row);
    });

    const menuRoot = row.querySelector('.slot-actions');
    const menuTrigger = row.querySelector('.slot-actions__trigger');
    if (menuRoot && menuTrigger) {
      menuTrigger.addEventListener('click', (event) => {
        event.stopPropagation();
        const isOpen = menuRoot.classList.toggle('is-open');
        menuTrigger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      });
      document.addEventListener('click', (event) => {
        if (!menuRoot.contains(event.target)) {
          menuRoot.classList.remove('is-open');
          menuTrigger.setAttribute('aria-expanded', 'false');
        }
      });

      menuRoot.addEventListener('click', (event) => {
        const actionBtn = event.target.closest('button[data-action]');
        if (!actionBtn) return;
        event.preventDefault();
        event.stopPropagation();
        menuRoot.classList.remove('is-open');
        handleRowAction(row, actionBtn.dataset.action, actionBtn);
      });
    }
  });

  $$('[data-sort]', table).forEach((btn) => {
    btn.addEventListener('click', () => {
      const key = btn.dataset.sort;
      const dir = state.sort.key === key && state.sort.dir === 'asc' ? 'desc' : 'asc';
      applySort(key, dir);
    });
  });

  chipTriggers.forEach((chip) => {
    chip.addEventListener('click', () => openFilterDrawer(chip.dataset.chip));
  });

  if (filterCloseBtn) filterCloseBtn.addEventListener('click', closeFilterDrawer);
  if (filterBackdrop) filterBackdrop.addEventListener('click', closeFilterDrawer);

  if (filterApplyBtn) {
    filterApplyBtn.addEventListener('click', () => {
      const payload = readFilterForm();
      applyFilterSelection(payload);
    });
  }

  if (filterResetBtn) {
    filterResetBtn.addEventListener('click', () => {
      resetFilterForm();
      applyFilterSelection({ recruiter: '', status: '', city: '' });
    });
  }

  if (activeTagsWrap) {
    activeTagsWrap.addEventListener('click', (event) => {
      const resetBtn = event.target.closest('[data-action="reset-filters"]');
      if (resetBtn) {
        event.preventDefault();
        applyFilterSelection({ recruiter: '', status: '', city: '' });
        return;
      }
      const tagBtn = event.target.closest('[data-remove-filter]');
      if (!tagBtn) return;
      const key = tagBtn.dataset.removeFilter;
      if (!key) return;
      const next = { ...state.filters };
      next[key] = '';
      applyFilterSelection(next);
    });
  }

  if (bulkButtons.length) {
    bulkButtons.forEach((btn) => {
      btn.addEventListener('click', () => handleBulkAction(btn.dataset.bulkAction, btn));
    });
  }

  if (deleteAllBtn) {
    deleteAllBtn.addEventListener('click', async () => {
      if (!confirm('Удалить все доступные слоты? Это действие нельзя отменить.')) return;
      try {
        const response = await fetch('/slots/delete_all', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ force: true }),
        });
        const data = await response.json();
        toast(data?.ok ? 'Все слоты удалены' : 'Не удалось удалить слоты', data?.ok ? 'success' : 'danger');
        if (data?.ok) window.location.reload();
      } catch (err) {
        console.error('slots.delete-all', err);
        toast('Не удалось удалить слоты', 'danger');
      }
    });
  }

  if (sheetRefs.close) sheetRefs.close.addEventListener('click', closeSheet);
  if (sheetBackdrop) sheetBackdrop.addEventListener('click', closeSheet);

  if (sheetRefs.reschedule) {
    sheetRefs.reschedule.addEventListener('click', () => {
      if (currentRow) triggerReschedule(currentRow);
    });
  }
  if (sheetRefs.reject) {
    sheetRefs.reject.addEventListener('click', () => {
      if (currentRow) triggerReject(currentRow);
    });
  }
  if (sheetRefs.delete) {
    sheetRefs.delete.addEventListener('click', () => {
      if (currentRow) triggerDelete(currentRow, { force: sheetRefs.delete.dataset.forceAllowed === '1' });
    });
  }
  if (sheetRefs.outcomeActions) {
    sheetRefs.outcomeActions.addEventListener('click', (event) => {
      const btn = event.target.closest('button[data-outcome]');
      if (!btn || !currentRow) return;
      triggerOutcome(currentRow, btn.dataset.outcome, btn);
    });
  }
}

function applyInitialRole() {
  roleSwitchButtons.forEach((btn) => {
    btn.classList.toggle('is-active', btn.dataset.roleTarget === state.role);
  });
  applyRole();
}

function applyRole() {
  rows.forEach((row) => updateTimeCells(row));
  syncQueryState();
}

function applyInitialFuture() {
  if (onlyFutureToggle) {
    onlyFutureToggle.checked = state.onlyFuture;
  }
}

function hydrateTokens() {
  state.tokens.forEach((token) => renderToken(token));
  updateSearchPlaceholder();
  if (!state.tokens.length && searchInput) {
    searchInput.value = '';
  }
  applyFilters();
}

function addTokenFromInput() {
  if (!searchInput) return;
  const value = searchInput.value.trim();
  if (!value) return;
  searchInput.value = '';
  addToken(value);
}

function handleSearchKey(event) {
  if (event.key === 'Enter') {
    event.preventDefault();
    addTokenFromInput();
  } else if (event.key === 'Backspace' && !searchInput.value && state.tokens.length) {
    event.preventDefault();
    removeToken(state.tokens[state.tokens.length - 1]);
  }
}

function addToken(token) {
  const normalized = token.trim();
  if (!normalized || state.tokens.includes(normalized)) return;
  state.tokens.push(normalized);
  renderToken(normalized);
  updateSearchPlaceholder();
  applyFilters();
  syncQueryState();
}

function renderToken(token) {
  if (!searchTokensWrap) return;
  const item = document.createElement('span');
  item.className = 'slots-search__token';
  item.dataset.token = token;
  item.textContent = token;

  const removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.dataset.tokenRemove = token;
  removeBtn.setAttribute('data-token-remove', token);
  removeBtn.textContent = '×';
  item.appendChild(removeBtn);

  searchTokensWrap.appendChild(item);
}

function removeToken(token) {
  const idx = state.tokens.indexOf(token);
  if (idx === -1) return;
  state.tokens.splice(idx, 1);
  if (searchTokensWrap) {
    const el = searchTokensWrap.querySelector(`[data-token="${CSS.escape(token)}"]`);
    if (el) el.remove();
  }
  updateSearchPlaceholder();
  applyFilters();
  syncQueryState();
}

function updateSearchPlaceholder() {
  if (!searchInput) return;
  searchInput.placeholder = state.tokens.length ? '' : 'Поиск по кандидату, городу, ID…';
}

function toggleSelection(id, checked) {
  if (!id) return;
  if (checked) state.selection.add(id);
  else state.selection.delete(id);
}

function updateSelectionUI() {
  const count = state.selection.size;

  if (bulkBar && bulkCount) {
    bulkCount.textContent = String(count);
    bulkBar.hidden = count === 0;
    bulkBar.setAttribute('aria-hidden', count === 0 ? 'true' : 'false');
    if (count === 0) {
      state.bulkConfirm = null;
      bulkButtons.forEach((btn) => btn.removeAttribute('data-confirming'));
    }
  }

  if (selectAll) {
    const selectableRows = getSelectableRows();
    if (!selectableRows.length) {
      selectAll.indeterminate = false;
      selectAll.checked = false;
    } else {
      const selectedVisible = selectableRows.filter((row) => state.selection.has(row.dataset.id)).length;
      selectAll.checked = selectedVisible > 0 && selectedVisible === selectableRows.length;
      selectAll.indeterminate = selectedVisible > 0 && selectedVisible < selectableRows.length;
      if (!selectAll.indeterminate && !selectAll.checked) {
        selectAll.checked = false;
      }
    }
  }
}

function applyFilters() {
  const now = Date.now();
  let visible = 0;
  const tokens = state.tokens.map((token) => token.toLowerCase());

  rows.forEach((row) => {
    let show = true;
    if (state.filters.recruiter && row.dataset.recruiterId !== state.filters.recruiter) show = false;
    if (show && state.filters.status && row.dataset.status !== state.filters.status) show = false;
    if (show && state.filters.city && row.dataset.cityId !== state.filters.city) show = false;
    if (show && state.onlyFuture) {
      const ts = Date.parse(row.dataset.startIso || '') || 0;
      if (ts < now) show = false;
    }
    if (show && tokens.length) {
      const haystack = [
        row.dataset.id,
        row.dataset.recruiter,
        row.dataset.candidate,
        row.dataset.cityName,
      ]
        .join(' ')
        .toLowerCase();
      show = tokens.every((token) => haystack.includes(token));
    }
    row.style.display = show ? '' : 'none';
    row.classList.toggle('is-hidden', !show);
    if (show) {
      visible += 1;
      updateTimeCells(row);
      updateDeadline(row);
    }
  });

  updateCounts();
  toggleEmptyState(visible);
  updateSelectionUI();
}

function updateCounts() {
  const totals = { total: 0, free: 0, pending: 0, booked: 0, confirmed: 0 };
  rows.forEach((row) => {
    if (row.style.display === 'none') return;
    totals.total += 1;
    const status = row.dataset.status;
    if (status === 'FREE') totals.free += 1;
    else if (status === 'PENDING') totals.pending += 1;
    else if (status === 'BOOKED') totals.booked += 1;
    else if (status === 'CONFIRMED_BY_CANDIDATE' || status === 'CONFIRMED') totals.confirmed += 1;
  });
  if (kpiIds.total) kpiIds.total.textContent = totals.total;
  if (kpiIds.free) kpiIds.free.textContent = totals.free;
  if (kpiIds.pending) kpiIds.pending.textContent = totals.pending;
  if (kpiIds.booked) kpiIds.booked.textContent = totals.booked;
  if (kpiIds.confirmed) kpiIds.confirmed.textContent = totals.confirmed;
}

function toggleEmptyState(visibleCount) {
  if (!emptyCard) return;
  const show = visibleCount === 0;
  emptyCard.hidden = !show;
  emptyCard.setAttribute('aria-hidden', show ? 'false' : 'true');
}

function applySort(key, dir, { silent = false } = {}) {
  state.sort = { key, dir };
  const sorted = rows.slice().sort((a, b) => {
    const av = getSortValue(a, key);
    const bv = getSortValue(b, key);
    if (av < bv) return dir === 'asc' ? -1 : 1;
    if (av > bv) return dir === 'asc' ? 1 : -1;
    return 0;
  });
  sorted.forEach((row) => tbody.appendChild(row));
  updateSortIndicators();
  if (!silent) syncQueryState();
}

function updateSortIndicators() {
  $$('[data-sort]', table).forEach((btn) => {
    const key = btn.dataset.sort;
    const active = state.sort.key === key;
    btn.classList.toggle('is-active', active);
    btn.setAttribute('aria-sort', active ? (state.sort.dir === 'asc' ? 'ascending' : 'descending') : 'none');
  });
}

function getSortValue(row, key) {
  switch (key) {
    case 'id':
      return Number.parseInt(row.dataset.id || '0', 10);
    case 'candidate':
      return (row.dataset.candidate || '').toLowerCase();
    case 'recruiter':
      return (row.dataset.recruiter || '').toLowerCase();
    case 'status':
      return Number.parseInt(row.dataset.statusOrder || '9', 10);
    case 'time':
    default:
      return Date.parse(row.dataset.startIso || '') || 0;
  }
}

function scheduleRelativeUpdates() {
  updateDeadlines();
  if (relTimer) clearInterval(relTimer);
  relTimer = setInterval(updateDeadlines, 60_000);
}

function updateDeadlines() {
  rows.forEach((row) => updateDeadline(row));
  if (currentRow && sheetRefs.rel) {
    const ts = Date.parse(currentRow.dataset.startIso || '');
    sheetRefs.rel.textContent = formatRelative(ts);
  }
}

function updateDeadline(row) {
  const badge = row.querySelector('[data-role="deadline"]');
  if (!badge) return;
  const ts = Date.parse(row.dataset.startIso || '');
  if (!Number.isFinite(ts)) {
    badge.textContent = '—';
    row.classList.remove('is-soon', 'is-past');
    return;
  }
  const diffMin = Math.round((ts - Date.now()) / 60000);
  if (diffMin < -5) {
    badge.textContent = 'Прошло';
    row.classList.add('is-past');
    row.classList.remove('is-soon');
  } else if (diffMin <= 120) {
    badge.textContent = diffMin > 0 ? `Через ${diffMin} мин` : 'Сообщите сейчас';
    row.classList.add('is-soon');
    row.classList.remove('is-past');
  } else {
    badge.textContent = formatRelative(ts);
    row.classList.remove('is-soon', 'is-past');
  }
}

function updateTimeCells(row) {
  const primary = row.querySelector('[data-role="time-primary"]');
  const secondary = row.querySelector('[data-role="time-secondary"]');
  const candidate = row.querySelector('[data-role="time-candidate"]');
  if (state.role === 'candidate' && candidate) {
    if (primary) primary.textContent = candidate.textContent;
    if (secondary) secondary.textContent = `Рекрутёр · ${row.dataset.startRec || ''}`;
  } else {
    if (primary) primary.textContent = row.dataset.startRec || '';
    if (secondary) secondary.textContent = `UTC ${row.dataset.startUtc || ''}`;
  }
}

function openFilterDrawer(targetKey) {
  if (!filterSheet || !filterBackdrop) return;
  filterSheet.hidden = false;
  filterBackdrop.hidden = false;
  filterSheet.dataset.activeFilter = targetKey || '';
  document.body.classList.add('sheet-open');
}

function closeFilterDrawer() {
  if (!filterSheet || !filterBackdrop) return;
  filterSheet.hidden = true;
  filterBackdrop.hidden = true;
  filterSheet.dataset.activeFilter = '';
  document.body.classList.remove('sheet-open');
}

function readFilterForm() {
  if (!filterSheet) return { ...state.filters };
  const recruiter = filterSheet.querySelector('input[name="filter_recruiter"]:checked');
  const status = filterSheet.querySelector('input[name="filter_status"]:checked');
  const city = filterSheet.querySelector('input[name="filter_city"]:checked');
  return {
    recruiter: recruiter ? recruiter.value : '',
    status: status ? status.value : '',
    city: city ? city.value : '',
  };
}

function resetFilterForm() {
  if (!filterSheet) return;
  filterSheet.querySelectorAll('input[type="radio"]').forEach((input) => {
    if (input.value === '') input.checked = true;
    else input.checked = false;
  });
}

function applyFilterSelection(nextFilters) {
  state.filters = { ...nextFilters };
  const params = new URLSearchParams(window.location.search);
  params.set('page', '1');
  if (state.filters.recruiter) params.set('recruiter_id', state.filters.recruiter);
  else params.delete('recruiter_id');
  if (state.filters.status) params.set('status', state.filters.status);
  else params.delete('status');
  if (state.filters.city) params.set('city_id', state.filters.city);
  else params.delete('city_id');
  if (perPageSelect && perPageSelect.value) params.set('per_page', perPageSelect.value);
  window.location.href = `${window.location.pathname}?${params.toString()}`;
}

function syncQueryState() {
  const params = new URLSearchParams(window.location.search);
  if (state.onlyFuture) params.set('future', '1');
  else params.delete('future');
  if (state.role === 'candidate') params.set('role', 'candidate');
  else params.delete('role');
  if (state.tokens.length) params.set('search', state.tokens.join(','));
  else params.delete('search');
  const queryString = params.toString();
  const url = queryString ? `${window.location.pathname}?${queryString}` : window.location.pathname;
  window.history.replaceState(null, '', url);
}

function handleRowAction(row, action, button) {
  switch (action) {
    case 'open-slot':
      openSheetWithRow(row);
      break;
    case 'delete-slot':
      triggerDelete(row, { force: false, source: button });
      break;
    case 'copy-slot':
      copySlotLink(row);
      break;
    case 'duplicate-slot':
      duplicateSlot(row);
      break;
    case 'write-tg':
      openTg(button?.dataset.tgId || row.dataset.candidateId);
      break;
    default:
      break;
  }
}

function openSheetWithRow(row) {
  currentRow = row;
  fillSheet(row);
  openSheet();
}

function openSheet() {
  if (!sheet || !sheetBackdrop) return;
  sheet.hidden = false;
  sheetBackdrop.hidden = false;
  requestAnimationFrame(() => {
    sheet.classList.add('open');
    sheetBackdrop.classList.add('open');
    document.body.classList.add('sheet-open');
  });
}

function closeSheet() {
  if (!sheet || !sheetBackdrop) return;
  sheet.classList.remove('open');
  sheetBackdrop.classList.remove('open');
  setTimeout(() => {
    sheet.hidden = true;
    sheetBackdrop.hidden = true;
    document.body.classList.remove('sheet-open');
    currentRow = null;
    resetSheet();
  }, 200);
}

function fillSheet(row) {
  if (!sheetRefs.title) return;
  sheetRefs.title.textContent = `Слот ${row.dataset.id}`;
  if (sheetRefs.sub) sheetRefs.sub.textContent = `${row.dataset.cityName || '—'} · ${row.dataset.startRec || ''}`;
  if (sheetRefs.id) sheetRefs.id.textContent = `ID ${row.dataset.id}`;
  if (sheetRefs.status) {
    sheetRefs.status.textContent = `Статус: ${row.dataset.statusLabel || '—'}`;
    sheetRefs.status.dataset.tone = toneForStatus(row.dataset.status);
  }
  if (sheetRefs.utc) sheetRefs.utc.textContent = row.dataset.startUtc || '—';
  if (sheetRefs.local) sheetRefs.local.textContent = row.dataset.startRec || '—';
  if (sheetRefs.city) sheetRefs.city.textContent = row.dataset.cityName || '—';
  if (sheetRefs.cityTz) {
    if (row.dataset.cityTz) {
      sheetRefs.cityTz.textContent = row.dataset.cityTz;
      sheetRefs.cityTz.hidden = false;
    } else {
      sheetRefs.cityTz.hidden = true;
    }
  }
  if (sheetRefs.cityWrap) sheetRefs.cityWrap.hidden = !row.dataset.cityName;
  if (sheetRefs.localCandidateWrap) {
    if (row.dataset.startCand) {
      sheetRefs.localCandidateWrap.hidden = false;
      sheetRefs.localCandidate.textContent = row.dataset.startCand;
    } else {
      sheetRefs.localCandidateWrap.hidden = true;
    }
  }
  if (sheetRefs.rel) sheetRefs.rel.textContent = formatRelative(Date.parse(row.dataset.startIso || ''));
  if (sheetRefs.recruiter) {
    sheetRefs.recruiter.innerHTML = row.dataset.recruiter
      ? `<p>${row.dataset.recruiter}</p><p class="muted">ID ${row.dataset.recruiterId || '—'}</p>`
      : '<p class="muted">Не назначен</p>';
  }
  if (sheetRefs.candidateSection) {
    if (row.dataset.candidate) {
      sheetRefs.candidateSection.hidden = false;
      if (sheetRefs.candidate) {
        sheetRefs.candidate.innerHTML = `
          <p>${row.dataset.candidate}</p>
          <p class="muted">tg_id: ${row.dataset.candidateId || '—'}</p>
        `;
      }
      if (sheetRefs.candidateActions) sheetRefs.candidateActions.hidden = false;
      if (sheetRefs.reschedule) sheetRefs.reschedule.disabled = false;
      if (sheetRefs.reject) sheetRefs.reject.disabled = false;
    } else {
      sheetRefs.candidateSection.hidden = true;
      if (sheetRefs.reschedule) sheetRefs.reschedule.disabled = true;
      if (sheetRefs.reject) sheetRefs.reject.disabled = true;
    }
  }
  if (sheetRefs.outcomeSection) {
    if (row.dataset.candidate) {
      sheetRefs.outcomeSection.hidden = false;
      sheetRefs.outcomeActions?.querySelectorAll('button').forEach((btn) => {
        btn.disabled = false;
        btn.classList.toggle('is-active', btn.dataset.outcome === row.dataset.outcome);
      });
      if (sheetRefs.outcomeStatus) {
        sheetRefs.outcomeStatus.textContent = row.dataset.outcome
          ? `Исход: ${row.dataset.outcome}`
          : 'Исход не выбран';
      }
    } else {
      sheetRefs.outcomeSection.hidden = true;
    }
  }
  if (sheetRefs.meta) {
    sheetRefs.meta.innerHTML = '';
    const duration = document.createElement('li');
    duration.textContent = `Длительность: ${row.dataset.duration} мин`;
    sheetRefs.meta.appendChild(duration);
  }
  if (sheetRefs.delete) {
    sheetRefs.delete.disabled = row.dataset.canDelete !== '1';
    sheetRefs.delete.dataset.slotId = row.dataset.id || '';
    sheetRefs.delete.dataset.forceAllowed = row.dataset.canDelete === '1' ? '0' : '1';
  }
}

function resetSheet() {
  if (!sheetRefs.title) return;
  sheetRefs.title.textContent = 'Слот не выбран';
  if (sheetRefs.sub) sheetRefs.sub.textContent = 'Выберите запись в таблице.';
  if (sheetRefs.id) sheetRefs.id.textContent = 'ID —';
  if (sheetRefs.status) {
    sheetRefs.status.textContent = 'Статус: —';
    sheetRefs.status.dataset.tone = 'info';
  }
  if (sheetRefs.utc) sheetRefs.utc.textContent = '—';
  if (sheetRefs.local) sheetRefs.local.textContent = '—';
  if (sheetRefs.cityWrap) sheetRefs.cityWrap.hidden = true;
  if (sheetRefs.localCandidateWrap) sheetRefs.localCandidateWrap.hidden = true;
  if (sheetRefs.rel) sheetRefs.rel.textContent = '—';
  if (sheetRefs.recruiter) sheetRefs.recruiter.innerHTML = '<p class="muted">Не назначен</p>';
  if (sheetRefs.candidateSection) sheetRefs.candidateSection.hidden = true;
  if (sheetRefs.outcomeSection) sheetRefs.outcomeSection.hidden = true;
  if (sheetRefs.meta) sheetRefs.meta.innerHTML = '';
  if (sheetRefs.delete) sheetRefs.delete.disabled = true;
}

function toneForStatus(status) {
  if (status === 'FREE') return 'success';
  if (status === 'PENDING') return 'warning';
  if (status === 'BOOKED') return 'progress';
  if (status === 'CONFIRMED' || status === 'CONFIRMED_BY_CANDIDATE') return 'success';
  return 'muted';
}

function formatRelative(timestamp) {
  if (!Number.isFinite(timestamp)) return '—';
  const diff = timestamp - Date.now();
  const minutes = Math.round(Math.abs(diff) / 60000);
  if (minutes < 1) return diff >= 0 ? 'через минуту' : 'только что';
  if (minutes < 60) return diff >= 0 ? `через ${minutes} мин` : `${minutes} мин назад`;
  const hours = Math.round(minutes / 60);
  return diff >= 0 ? `через ${hours} ч` : `${hours} ч назад`;
}

function handleBulkAction(action, button) {
  if (!state.selection.size) return;
  if (action === 'assign') {
    const recruiterId = bulkAssignSelect ? bulkAssignSelect.value : '';
    if (!recruiterId) {
      toast('Выберите рекрутёра для назначения', 'warning');
      return;
    }
    performBulkAssign(recruiterId);
    return;
  }
  if (action === 'remind') {
    performBulkRemind();
    return;
  }
  if (action === 'delete') {
    if (state.bulkConfirm !== 'delete') {
      state.bulkConfirm = 'delete';
      button.dataset.confirming = 'true';
      button.textContent = 'Подтвердить удаление';
      setTimeout(() => {
        if (button.dataset.confirming === 'true') {
          button.dataset.confirming = 'false';
          button.textContent = 'Удалить';
          state.bulkConfirm = null;
        }
      }, 4000);
      return;
    }
    button.dataset.confirming = 'false';
    button.textContent = 'Удалить';
    state.bulkConfirm = null;
    performBulkDelete();
  }
}

async function performBulkAssign(recruiterId) {
  try {
    const response = await fetch('/slots/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'assign', slot_ids: Array.from(state.selection), recruiter_id: Number(recruiterId) }),
    });
    const data = await response.json();
    if (response.ok && data?.ok) {
      toast(`Назначено: ${data.updated}`, 'success');
      window.location.reload();
    } else {
      toast(data?.detail || 'Не удалось назначить', 'danger');
    }
  } catch (err) {
    console.error('slots.bulk-assign', err);
    toast('Ошибка при назначении', 'danger');
  }
}

async function performBulkRemind() {
  try {
    const response = await fetch('/slots/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'remind', slot_ids: Array.from(state.selection) }),
    });
    const data = await response.json();
    if (response.ok && data?.ok) {
      toast(`Запланировано напоминаний: ${data.scheduled}`, 'success');
    } else {
      toast(data?.detail || 'Не удалось запланировать напоминания', 'danger');
    }
  } catch (err) {
    console.error('slots.bulk-remind', err);
    toast('Ошибка при планировании', 'danger');
  }
}

async function performBulkDelete() {
  try {
    const response = await fetch('/slots/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'delete', slot_ids: Array.from(state.selection), force: true }),
    });
    const data = await response.json();
    if (response.ok && data?.ok) {
      toast(`Удалено: ${data.deleted}`, 'success');
      window.location.reload();
    } else {
      toast(data?.detail || 'Не удалось удалить', 'danger');
    }
  } catch (err) {
    console.error('slots.bulk-delete', err);
    toast('Ошибка удаления', 'danger');
  }
}

function triggerDelete(row, { force = false, source = null }) {
  if (!row) return;
  if (!force && row.dataset.canDelete !== '1') {
    if (source) {
      if (source.dataset.confirming === 'true') {
        performDelete(row, true);
        source.dataset.confirming = 'false';
        source.textContent = 'Удалить';
      } else {
        source.dataset.confirming = 'true';
        source.textContent = 'Подтвердите';
        setTimeout(() => {
          if (source.dataset.confirming === 'true') {
            source.dataset.confirming = 'false';
            source.textContent = 'Удалить';
          }
        }, 4000);
      }
    }
    return;
  }
  performDelete(row, force);
}

async function performDelete(row, force = false) {
  try {
    const response = await fetch(`/slots/${row.dataset.id}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force }),
    });
    const data = await response.json();
    if (response.ok && data?.ok) {
      toast('Слот удалён', 'success');
      row.remove();
      state.selection.delete(row.dataset.id);
      rows = rows.filter((item) => item !== row);
      updateSelectionUI();
      applyFilters();
    } else if (data?.code === 'requires_force') {
      toast('Нужно подтвердить удаление ещё раз', 'warning');
    } else {
      toast(data?.message || 'Не удалось удалить слот', 'danger');
    }
  } catch (err) {
    console.error('slots.delete', err);
    toast('Не удалось удалить слот', 'danger');
  }
}

async function triggerReschedule(row) {
  try {
    const response = await fetch(`/slots/${row.dataset.id}/reschedule`, { method: 'POST' });
    const data = await response.json();
    toast(data?.message || 'Готово', data?.ok ? 'success' : 'danger');
  } catch (err) {
    console.error('slots.reschedule', err);
    toast('Не удалось отправить напоминание', 'danger');
  }
}

async function triggerReject(row) {
  try {
    const response = await fetch(`/slots/${row.dataset.id}/reject_booking`, { method: 'POST' });
    const data = await response.json();
    toast(data?.message || 'Готово', data?.ok ? 'success' : 'danger');
  } catch (err) {
    console.error('slots.reject', err);
    toast('Не удалось отправить отказ', 'danger');
  }
}

async function triggerOutcome(row, outcome, button) {
  if (!row || !outcome) return;
  const slotId = row.dataset.id;
  if (!slotId) return;
  if (button) button.disabled = true;
  try {
    const response = await fetch(`/slots/${slotId}/outcome`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ outcome }),
    });
    const data = await response.json();
    if (response.ok && data?.ok) {
      toast(data?.message || 'Исход обновлён', 'success');
      row.dataset.outcome = data.outcome || '';
      if (currentRow === row) {
        fillSheet(row);
      }
    } else {
      toast(data?.message || 'Не удалось обновить исход', 'danger');
    }
  } catch (err) {
    console.error('slots.outcome', err);
    toast('Не удалось обновить исход', 'danger');
  } finally {
    if (button) button.disabled = false;
  }
}

function copySlotLink(row) {
  const url = `${window.location.origin}/slots?slot=${row.dataset.id}`;
  copyToClipboard(url);
  toast('Ссылка скопирована', 'success');
}

function duplicateSlot(row) {
  const summary = `Слот ${row.dataset.id}\nРекрутёр: ${row.dataset.recruiter || '—'}\nГород: ${row.dataset.cityName || '—'}\nВремя: ${row.dataset.startRec || ''}`;
  copyToClipboard(summary);
  toast('Параметры скопированы', 'info');
}

function openTg(candidateId) {
  if (!candidateId) {
    toast('Нет tg_id', 'warning');
    return;
  }
  const link = `tg://user?id=${candidateId}`;
  window.open(link, '_blank');
}

function copyToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).catch((err) => console.error('clipboard.write', err));
  } else {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
    } catch (err) {
      console.error('clipboard.exec', err);
    }
    document.body.removeChild(textarea);
  }
}

function toast(text, kind = 'info') {
  if (!toastStack) return;
  const node = document.createElement('div');
  node.className = 'toast';
  node.dataset.kind = kind;
  node.textContent = text;
  toastStack.appendChild(node);
  requestAnimationFrame(() => node.classList.add('toast--show'));
  setTimeout(() => node.classList.add('toast--hide'), 2200);
  setTimeout(() => node.remove(), 2600);
}

let currentRow = null;

function getSelectableRows() {
  return rows.filter((row) => {
    if (!row || !row.isConnected) return false;
    if (row.style.display === 'none' || row.classList.contains('is-hidden')) return false;
    const checkbox = row.querySelector('.slot-select');
    return !!checkbox && !checkbox.disabled;
  });
}
