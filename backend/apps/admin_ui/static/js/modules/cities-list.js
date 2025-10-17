/* eslint-disable no-alert */
'use strict';

const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));
const on = (el, event, handler, options) => el?.addEventListener(event, handler, options);

const runWhenReady = (fn) => {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fn, { once: true });
  } else {
    fn();
  }
};

runWhenReady(initCitiesPage);

function initCitiesPage() {
  const table = $('#city_table');
  const tbody = $('#cities_tbody');

  if (!tbody) {
    return;
  }

  const sheet = $('#sheet');
  const sheetBackdrop = $('#sheet_backdrop');
  const sheetForm = $('#sheet_form');
  const sheetStages = $('#sheet_stages');
  const sheetStagesBody = $('#sheet_stages_body');
  const sheetTitle = $('#sheet-title');
  const sheetSub = $('#sheet-sub');
  const sheetClose = $('#sheet_close');
  const btnSave = $('#btn_save');
  const btnCancel = $('#btn_cancel');
  const btnDelete = $('#btn_delete');
  const saveStatus = $('#save_status');

  const inputId = $('#city_id');
  const selOwner = $('#owner_select');
  const inWeek = $('#plan_week');
  const inMonth = $('#plan_month');
  const taCriteria = $('#criteria');
  const taExperts = $('#experts');
  const prevCrit = $('#crit_preview');
  const prevExp = $('#exp_preview');

  const overviewName = $('#city_overview_name');
  const overviewTz = $('#city_overview_tz');
  const overviewId = $('#city_overview_id');
  const overviewOwner = $('#city_overview_owner');
  const overviewWeek = $('#city_overview_week');
  const overviewMonth = $('#city_overview_month');
  const overviewStages = $('#city_overview_stages');
  const btnExpandStages = $('#stages_expand');
  const btnCollapseStages = $('#stages_collapse');
  const totalCountEl = $('#total_count');

  clearOverview();

  const rows = $$('.city-row[data-id]', tbody);
  const truncate = (value, max = 120) => {
    if (!value) return '—';
    return value.length > max ? `${value.slice(0, max).trimEnd()}…` : value;
  };

  const stagePlaceholderHTML = '<p class="muted stage-placeholder">Выберите город в таблице, чтобы загрузить тексты.</p>';

  function resetStagePlaceholder() {
    if (sheetStagesBody) {
      sheetStagesBody.innerHTML = stagePlaceholderHTML;
    }
    setStageControlsDisabled(true);
  }

  function setStageControlsDisabled(disabled) {
    if (btnExpandStages) btnExpandStages.disabled = disabled;
    if (btnCollapseStages) btnCollapseStages.disabled = disabled;
  }

  function toggleAllStageDetails(expand) {
    const scope = sheetStagesBody || sheetStages;
    if (!scope) return;
    scope.querySelectorAll('details.stage-item').forEach((item) => {
      if (expand) item.setAttribute('open', '');
      else item.removeAttribute('open');
    });
  }

  function updateTotalCount() {
    if (totalCountEl) totalCountEl.textContent = rows.length;
  }

  function renderEmptyState() {
    if (!tbody || rows.length) return;
    if (tbody.querySelector('.city-row--empty')) return;
    const emptyRow = document.createElement('tr');
    emptyRow.className = 'city-row city-row--empty';
    const cell = document.createElement('td');
    cell.colSpan = 7;
    cell.className = 'city-empty-cell';
    cell.innerHTML = `
      <div class="city-empty card glass grain">
        <h3 class="section-title">Пока пусто</h3>
        <p class="page-description">Добавьте первый город, чтобы настроить планы и сообщения.</p>
        <div class="page-actions">
          <a class="btn btn-primary" href="/cities/new">+ Новый город</a>
        </div>
      </div>
    `;
    emptyRow.appendChild(cell);
    tbody.appendChild(emptyRow);
  }

  function setOverviewStages(custom, total) {
    if (!overviewStages) return;
    if (!total) {
      overviewStages.textContent = 'Этапы не подключены';
      return;
    }
    overviewStages.textContent = `Кастомных этапов: ${custom}/${total}`;
  }

  function clearOverview() {
    if (overviewName) overviewName.textContent = 'Город не выбран';
    if (overviewTz) overviewTz.textContent = 'Часовой пояс: —';
    if (overviewId) overviewId.textContent = 'ID —';
    if (overviewWeek) overviewWeek.textContent = 'План нед: —';
    if (overviewMonth) overviewMonth.textContent = 'План мес: —';
    if (overviewOwner) {
      overviewOwner.textContent = 'Ответственный не назначен';
      overviewOwner.classList.add('muted');
    }
    setOverviewStages(0, 0);
    setStageControlsDisabled(true);
  }

  function updateOverviewFromRow(row) {
    if (!row) return;
    const id = row.dataset.id || '—';
    const nameText = row.querySelector('.col-name .cell-title')?.textContent?.trim() || 'Город';
    const tzText = row.querySelector('.col-tz code')?.textContent?.trim() || 'Europe/Moscow';
    const ownerNode = row.querySelector('.owner-label');
    const ownerText = ownerNode?.textContent?.trim() || '';
    const weekText = row.querySelector('.col-week')?.textContent?.trim() || '—';
    const monthText = row.querySelector('.col-month')?.textContent?.trim() || '—';

    if (overviewName) overviewName.textContent = nameText;
    if (overviewTz) overviewTz.textContent = `Часовой пояс: ${tzText}`;
    if (overviewId) overviewId.textContent = `ID ${id}`;
    if (overviewWeek) overviewWeek.textContent = `План нед: ${weekText || '—'}`;
    if (overviewMonth) overviewMonth.textContent = `План мес: ${monthText || '—'}`;

    if (overviewOwner) {
      if (ownerNode && !ownerNode.classList.contains('muted') && ownerText) {
        overviewOwner.innerHTML = `Ответственный: <strong>${escapeHTML(ownerText)}</strong>`;
        overviewOwner.classList.remove('muted');
      } else {
        overviewOwner.textContent = 'Ответственный не назначен';
        overviewOwner.classList.add('muted');
      }
    }

    updateOverviewStagesFromDetails(row);
  }

  function updateOverviewStagesFromDetails(row) {
    if (!overviewStages) return;
    const details = getDetailsRow(row);
    if (!details) {
      setOverviewStages(0, 0);
      return;
    }
    const stageItems = Array.from(details.querySelectorAll('.stage-summary__item'));
    if (!stageItems.length) {
      setOverviewStages(0, 0);
      return;
    }
    const total = stageItems.length;
    const custom = stageItems.filter((item) => item.classList.contains('is-custom')).length;
    setOverviewStages(custom, total);
  }

  function getDetailsRow(row) {
    if (!row || !row.dataset) return null;
    return tbody.querySelector(`.city-row--details[data-details-for="${CSS.escape(row.dataset.id)}"]`);
  }

  function collapseRow(row) {
    const details = getDetailsRow(row);
    row.classList.remove('is-expanded');
    row.setAttribute('aria-expanded', 'false');
    if (details) {
      details.hidden = true;
    }
  }

  let expandedRow = null;
  function expandRow(row) {
    if (expandedRow && expandedRow !== row) {
      collapseRow(expandedRow);
    }
    expandedRow = row;
    row.classList.add('is-expanded');
    row.setAttribute('aria-expanded', 'true');
    const details = getDetailsRow(row);
    if (details) {
      details.hidden = false;
      updateOverviewStagesFromDetails(row);
    }
  }

  function toggleRow(row) {
    if (!row) return;
    if (row.classList.contains('is-expanded')) collapseRow(row);
    else expandRow(row);
  }

  function escapeHTML(str = '') {
    return str.replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[ch] || ch));
  }

  function toast(text, kind = 'info') {
    const wrap = $('#toasts');
    if (!wrap) return;
    const t = document.createElement('div');
    t.className = 'toast';
    t.dataset.kind = kind;
    t.role = 'status';
    t.textContent = text;
    wrap.appendChild(t);
    setTimeout(() => {
      t.classList.add('toast--hide');
    }, 2000);
    setTimeout(() => {
      t.remove();
    }, 2600);
  }

  const sortState = { key: 'name', dir: 'asc' };
  function getCellValue(row, key) {
    switch (key) {
      case 'name':
        return row.dataset.name || '';
      case 'tz':
        return row.dataset.tz || '';
      case 'owner':
        return row.dataset.owner || '';
      case 'week':
        return Number(row.querySelector('.col-week')?.dataset.sort || 0);
      case 'month':
        return Number(row.querySelector('.col-month')?.dataset.sort || 0);
      default:
        return '';
    }
  }

  function applySort() {
    const rowsArr = Array.from(rows).filter((r) => r.style.display !== 'none');
    rowsArr.sort((a, b) => {
      const av = getCellValue(a, sortState.key);
      const bv = getCellValue(b, sortState.key);
      if (typeof av === 'number' || typeof bv === 'number') {
        return sortState.dir === 'asc' ? av - bv : bv - av;
      }
      const cmp = String(av).localeCompare(String(bv), 'ru', { sensitivity: 'base' });
      return sortState.dir === 'asc' ? cmp : -cmp;
    });
    rowsArr.forEach((r) => {
      const details = getDetailsRow(r);
      tbody.appendChild(r);
      if (details) {
        tbody.appendChild(details);
      }
    });
    $$('.sort', table).forEach((btn) => {
      const dir = btn.dataset.key === sortState.key ? (sortState.dir === 'asc' ? 'ascending' : 'descending') : 'none';
      btn.setAttribute('aria-sort', dir);
      btn.classList.toggle('is-active', btn.dataset.key === sortState.key);
    });
  }

  on(table, 'click', (event) => {
    const btn = event.target.closest('button.sort');
    if (!btn) return;
    const key = btn.dataset.key;
    if (!key) return;
    if (sortState.key === key) {
      sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
    } else {
      sortState.key = key;
      sortState.dir = 'asc';
    }
    applySort();
  });

  let currentRow = null;
  let isDirty = false;
  function setDirty(value) {
    isDirty = value;
    saveStatus.textContent = value ? 'Есть несохранённые изменения' : 'Сохранено';
    saveStatus.classList.toggle('ok', !value);
    saveStatus.classList.toggle('err', false);
  }

  if (selOwner) {
    selOwner.addEventListener('change', () => {
      setDirty(true);
      if (!sheet.hidden) syncOverviewFromForm();
    });
  }

  [inWeek, inMonth].forEach((input) => {
    if (!input) return;
    input.addEventListener('input', () => {
      setDirty(true);
      if (!sheet.hidden) syncOverviewFromForm();
    });
  });

  on(btnExpandStages, 'click', () => toggleAllStageDetails(true));
  on(btnCollapseStages, 'click', () => toggleAllStageDetails(false));

  function openSheetForRow(row) {
    currentRow = row;
    const id = row.dataset.id;
    const name = row.querySelector('.col-name .cell-title')?.textContent?.trim() || 'Город';
    const tzLabel = row.querySelector('.col-tz code')?.textContent?.trim() || 'Europe/Moscow';
    sheetTitle.textContent = name;
    sheetSub.textContent = `Часовой пояс: ${tzLabel}`;
    updateOverviewFromRow(row);
    inputId.value = id;
    if (btnDelete) {
      btnDelete.disabled = false;
      btnDelete.textContent = 'Удалить';
    }

    selOwner.value = row.dataset.ownerId || '';
    inWeek.value = row.dataset.planWeek || '';
    inMonth.value = row.dataset.planMonth || '';
    taCriteria.value = row.dataset.criteria || '';
    taExperts.value = row.dataset.experts || '';
    prevCrit.textContent = truncate(taCriteria.value);
    prevExp.textContent = truncate(taExperts.value);

    if (sheetStagesBody) {
      sheetStagesBody.innerHTML = '';
      const tplEl = document.getElementById(`tpl-stages-${id}`);
      if (tplEl instanceof HTMLTemplateElement && tplEl.content) {
        const frag = tplEl.content.cloneNode(true);
        sheetStagesBody.appendChild(frag);
        sheetStagesBody.querySelectorAll('details.stage-item').forEach((details) => {
          const textarea = details.querySelector('textarea[data-stage]');
          const preview = details.querySelector('.stage-item__preview');
          const updatePreview = () => {
            preview.textContent = textarea.value.trim() ? truncate(textarea.value) : 'Текст по умолчанию';
          };
          if (textarea) {
            textarea.addEventListener('input', () => {
              setDirty(true);
              updatePreview();
              refreshStageSummaryFromEditor();
            });
            updatePreview();
          }
        });
        sheetStagesBody.querySelectorAll('.stage-default-btn').forEach((button) => {
          button.addEventListener('click', () => {
            const key = button.getAttribute('data-stage');
            if (!key) return;
            const textarea = sheetStagesBody.querySelector(`textarea[data-stage="${CSS.escape(key)}"]`);
            if (textarea) {
              textarea.value = textarea.dataset.default || '';
              textarea.dispatchEvent(new Event('input', { bubbles: true }));
              textarea.focus();
            }
          });
        });
        refreshStageSummaryFromEditor();
      } else {
        resetStagePlaceholder();
        refreshStageSummaryFromEditor();
      }
    }

    sheet.hidden = false;
    sheetBackdrop.hidden = false;
    document.body.classList.add('sheet-open');
    requestAnimationFrame(() => {
      sheet.classList.add('open');
      sheetBackdrop.classList.add('open');
    });
    setDirty(false);
    selOwner.focus();
    syncOverviewFromForm();
  }

  function tryCloseSheet() {
    if (isDirty) {
      const ok = confirm('Есть несохранённые изменения. Закрыть без сохранения?');
      if (!ok) return;
    }
    closeSheet(true);
  }

  function closeSheet(reset = false) {
    sheet.classList.remove('open');
    sheetBackdrop.classList.remove('open');
    setTimeout(() => {
      sheet.hidden = true;
      sheetBackdrop.hidden = true;
      document.body.classList.remove('sheet-open');
      if (reset) {
        sheetForm.reset();
        resetStagePlaceholder();
        prevCrit.textContent = '—';
        prevExp.textContent = '—';
      }
      sheetTitle.textContent = 'Настройки города';
      sheetSub.textContent = 'Выберите город в таблице.';
      clearOverview();
      currentRow = null;
      setDirty(false);
    }, 160);
  }

  on(sheetBackdrop, 'click', () => tryCloseSheet());
  on(sheetClose, 'click', () => tryCloseSheet());
  on(btnCancel, 'click', () => tryCloseSheet());

  on(table, 'click', (event) => {
    const rowToggle = event.target.closest('.row-expand');
    if (rowToggle) {
      const row = rowToggle.closest('.city-row[data-id]');
      toggleRow(row);
      return;
    }
    const editBtn = event.target.closest('.btn-edit[data-action="open-sheet"]');
    if (editBtn) {
      const targetId = editBtn.dataset.target;
      const row = tbody.querySelector(`.city-row[data-id="${CSS.escape(targetId)}"]`);
      if (row) openSheetForRow(row);
      return;
    }
    const row = event.target.closest('.city-row[data-id]');
    if (row) {
      expandRow(row);
      openSheetForRow(row);
    }
  });

  on(table, 'keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const row = event.target.closest('.city-row[data-id]');
    if (!row) return;
    event.preventDefault();
    expandRow(row);
    openSheetForRow(row);
  });

  function syncOverviewFromForm() {
    if (!currentRow) return;
    currentRow.dataset.planWeek = inWeek.value;
    currentRow.dataset.planMonth = inMonth.value;
    currentRow.dataset.criteria = taCriteria.value;
    currentRow.dataset.experts = taExperts.value;
    currentRow.dataset.ownerId = selOwner.value;

    const weekCell = currentRow.querySelector('.col-week');
    const monthCell = currentRow.querySelector('.col-month');
    const criteriaCell = currentRow.querySelector('.col-criteria');
    const expertsCell = currentRow.querySelector('.col-experts');
    const ownerLabel = currentRow.querySelector('.owner-label');

    if (weekCell) {
      weekCell.textContent = inWeek.value || '—';
      weekCell.dataset.sort = inWeek.value || '0';
    }
    if (monthCell) {
      monthCell.textContent = inMonth.value || '—';
      monthCell.dataset.sort = inMonth.value || '0';
    }
    if (criteriaCell) criteriaCell.textContent = truncate(taCriteria.value);
    if (expertsCell) expertsCell.textContent = truncate(taExperts.value);

    if (ownerLabel) {
      if (selOwner.value) {
        ownerLabel.textContent = selOwner.options[selOwner.selectedIndex]?.textContent || '—';
        ownerLabel.classList.remove('muted');
        currentRow.dataset.owner = ownerLabel.textContent.toLowerCase();
      } else {
        ownerLabel.textContent = 'Не назначен';
        ownerLabel.classList.add('muted');
        currentRow.dataset.owner = '';
      }
    }

    updateOverviewFromRow(currentRow);
  }

  function refreshStageSummaryFromEditor() {
    if (!currentRow) return;
    const details = getDetailsRow(currentRow);
    if (!details) return;
    let customCount = 0;
    const items = details.querySelectorAll('.stage-summary__item');
    items.forEach((item) => {
      const key = item.dataset.stage;
      const preview = item.querySelector('[data-role="stage-preview"]');
      const status = item.querySelector('[data-role="stage-status"]');
      if (!key || !preview || !status) return;
      const textarea = sheetStagesBody?.querySelector(`textarea[data-stage="${CSS.escape(key)}"]`);
      if (!textarea) return;
      const value = textarea.value.trim();
      const def = textarea.dataset.default?.trim() || '';
      const isCustom = Boolean(value) && value !== def;
      item.classList.toggle('is-custom', isCustom);
      if (isCustom) {
        customCount += 1;
        preview.hidden = false;
        preview.textContent = truncate(value);
        status.textContent = 'Своя версия';
      } else {
        preview.hidden = true;
        status.textContent = 'По умолчанию';
      }
    });
    setOverviewStages(customCount, items.length);
  }

  async function doSave() {
    if (!currentRow) return;

    const id = inputId.value;
    btnSave.disabled = true;
    btnSave.textContent = 'Сохраняем…';

    const payload = new FormData(sheetForm);
    sheetStagesBody?.querySelectorAll('textarea[data-stage]').forEach((ta) => {
      payload.set(ta.name, ta.value);
    });

    try {
      const resp = await fetch(`/cities/${encodeURIComponent(id)}`, {
        method: 'POST',
        body: payload,
      });
      if (!resp.ok) throw new Error(`save_failed_${resp.status}`);
      const json = await resp.json().catch(() => null);
      if (!json || json.ok !== true) throw new Error(json && json.error ? json.error : 'save_failed');
      toast('Сохранено', 'success');
      setDirty(false);
      syncOverviewFromForm();
    } catch (err) {
      console.error(err);
      toast('Не удалось сохранить', 'error');
    } finally {
      btnSave.disabled = false;
      btnSave.textContent = 'Сохранить';
    }
  }

  async function doDelete() {
    if (!currentRow) return;
    const id = inputId.value;
    const confirmDelete = confirm('Удалить город? Действие необратимо.');
    if (!confirmDelete) return;

    btnDelete.disabled = true;
    const prevLabel = btnDelete.textContent;
    btnDelete.textContent = 'Удаляем…';

    try {
      const resp = await fetch(`/cities/${encodeURIComponent(id)}`, {
        method: 'POST',
        headers: { Accept: 'application/json' },
      });
      let json = null;
      try {
        json = await resp.json();
      } catch (_err) {
        json = null;
      }
      if (!resp.ok || !json || json.ok !== true) {
        throw new Error(json && json.error ? json.error : 'delete_failed');
      }

      const detailsRow = getDetailsRow(currentRow);
      detailsRow?.remove();
      const tplEl = document.getElementById(`tpl-stages-${id}`);
      tplEl?.remove();

      const idx = rows.indexOf(currentRow);
      if (idx >= 0) {
        rows.splice(idx, 1);
      }
      if (expandedRow === currentRow) {
        expandedRow = null;
      }
      currentRow.remove();

      updateTotalCount();
      renderEmptyState();
      toast('Город удалён', 'success');
      closeSheet(true);
      applySort();
    } catch (err) {
      console.error(err);
      toast('Не удалось удалить', 'error');
      btnDelete.disabled = false;
      btnDelete.textContent = prevLabel;
    }
  }

  on(btnSave, 'click', doSave);
  on(btnDelete, 'click', doDelete);
  on(taCriteria, 'input', () => {
    prevCrit.textContent = truncate(taCriteria.value);
    setDirty(true);
  });
  on(taExperts, 'input', () => {
    prevExp.textContent = truncate(taExperts.value);
    setDirty(true);
  });

  window.addEventListener('beforeunload', (event) => {
    if (!sheet.hidden && isDirty) {
      event.preventDefault();
      event.returnValue = '';
    }
  });

  resetStagePlaceholder();
  applySort();
  refreshStageSummaryFromEditor();
  updateTotalCount();
  renderEmptyState();
}
