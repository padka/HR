function normalize(text) {
  return (text || '')
    .toString()
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ');
}

function getOptionInput(option) {
  return option.querySelector('input[type="checkbox"]');
}

function updateEmptyState(root, options) {
  const emptyState = root.querySelector('[data-empty-state]');
  if (!emptyState) return;
  const anyVisible = options.some((option) => !option.hasAttribute('hidden'));
  if (anyVisible) {
    emptyState.hidden = true;
  } else {
    emptyState.hidden = false;
  }
}

function updateChips(root, options) {
  const chipsHost = root.querySelector('[data-selected-chips]');
  const summaryCount = root.querySelector('[data-selected-count]');
  const live = root.querySelector('[data-city-live]');
  const selected = options.filter((option) => getOptionInput(option)?.checked);

  if (summaryCount) {
    summaryCount.textContent = selected.length.toString();
  }

  if (!chipsHost) {
    return;
  }

  chipsHost.innerHTML = '';
  if (!selected.length) {
    chipsHost.hidden = true;
    return;
  }

  chipsHost.hidden = false;
  selected.forEach((option) => {
    const input = getOptionInput(option);
    if (!input) return;
    const name = option.querySelector('.city-option__name')?.textContent?.trim() || input.value;
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'city-chip city-chip--pill';
    chip.dataset.cityId = input.value;
    chip.innerHTML = `<span>${name}</span><span aria-hidden="true">×</span>`;
    chip.setAttribute('aria-label', `Убрать ${name}`);
    chip.addEventListener('click', () => {
      input.checked = false;
      input.dispatchEvent(new Event('change', { bubbles: true }));
      if (live) {
        live.textContent = `${name} исключён из выбора`;
      }
    });
    chipsHost.appendChild(chip);
  });
}

function applyFilter(root, options, searchValue) {
  const term = normalize(searchValue);
  const mode = root.dataset.mode || 'tiles';
  if (!term || mode !== 'list') {
    options.forEach((option) => {
      option.removeAttribute('hidden');
    });
    updateEmptyState(root, options);
    return;
  }

  options.forEach((option) => {
    const name = option.dataset.name || '';
    const tz = option.dataset.tz || '';
    const match = name.includes(term) || tz.includes(term);
    if (match) {
      option.removeAttribute('hidden');
    } else {
      option.setAttribute('hidden', 'hidden');
    }
  });
  updateEmptyState(root, options);
}

function selectInScope(options, checked) {
  options.forEach((option) => {
    const input = getOptionInput(option);
    if (!input || input.disabled || option.hasAttribute('hidden')) return;
    input.checked = checked;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

export function initCitySelector(root) {
  if (!root) return;
  const threshold = Number.parseInt(root.dataset.threshold || '16', 10);
  const total = Number.parseInt(root.dataset.total || '0', 10);
  const initialMode = root.dataset.mode || (total > threshold ? 'list' : 'tiles');
  root.dataset.mode = initialMode;

  const options = Array.from(root.querySelectorAll('[data-city-option]'));
  const searchWrap = root.querySelector('[data-city-search]');
  const searchInput = root.querySelector('[data-city-search-input]');
  const selectAllBtn = root.querySelector('[data-select="all"]');
  const clearAllBtn = root.querySelector('[data-select="none"]');
  const live = root.querySelector('[data-city-live]');

  if (searchWrap) {
    searchWrap.hidden = root.dataset.mode !== 'list';
  }

  options.forEach((option) => {
    const input = getOptionInput(option);
    if (!input) return;
    option.classList.toggle('is-checked', input.checked);
    input.addEventListener('change', () => {
      option.classList.toggle('is-checked', input.checked);
      updateChips(root, options);
    });
  });

  if (searchInput) {
    searchInput.addEventListener('input', () => {
      applyFilter(root, options, searchInput.value);
    });
  }

  selectAllBtn?.addEventListener('click', () => {
    if (root.dataset.mode === 'list' && searchInput && searchInput.value.trim()) {
      const visible = options.filter((option) => !option.hasAttribute('hidden'));
      selectInScope(visible, true);
    } else {
      selectInScope(options, true);
    }
    if (live) {
      live.textContent = 'Все города выбраны';
    }
  });

  clearAllBtn?.addEventListener('click', () => {
    if (root.dataset.mode === 'list' && searchInput && searchInput.value.trim()) {
      const visible = options.filter((option) => !option.hasAttribute('hidden'));
      selectInScope(visible, false);
    } else {
      selectInScope(options, false);
    }
    if (live) {
      live.textContent = 'Выбор городов очищен';
    }
  });

  updateChips(root, options);
  if (searchInput) {
    applyFilter(root, options, searchInput.value);
  } else {
    updateEmptyState(root, options);
  }
}
