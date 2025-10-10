const ready = (callback) => {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', callback, { once: true });
  } else {
    callback();
  }
};

ready(() => {
  const table = document.querySelector('[data-cities-table]');
  if (!table) return;

  const tbody = table.querySelector('tbody');
  const board = document.querySelector('[data-cities-board]');
  const searchInput = document.querySelector('[data-cities-search]');
  const clearSearchButton = document.querySelector('[data-clear-search]');
  const filterButtons = Array.from(document.querySelectorAll('[data-cities-filter]'));
  const sortButtons = Array.from(table.querySelectorAll('[data-sort]'));
  const visibleCountLabel = document.querySelector('[data-visible-count]');
  const emptyState = document.querySelector('[data-empty-state]');
  const columnToggles = Array.from(document.querySelectorAll('[data-toggle-column]'));
  const densityButtons = Array.from(document.querySelectorAll('[data-density-option]'));
  const densityStorageKey = 'cities-table-density';

  const rows = Array.from(tbody.querySelectorAll('[data-city-row]')).map((row) => {
    const name = (row.dataset.name || '').trim();
    const tz = (row.dataset.tz || '').trim();
    const owner = (row.dataset.owner || '').trim();
    return {
      row,
      name,
      tz,
      owner,
      ownerState: row.dataset.ownerState === '1',
      active: row.dataset.active === '1',
      searchName: name.toLowerCase(),
      searchTz: tz.toLowerCase(),
    };
  });

  let activeFilter = 'all';
  let sortKey = 'name';
  let sortDirection = 'asc';
  const virtualizationThreshold = 180;
  const chunkSize = 120;
  let pendingFrame = null;
  let pendingIdle = null;

  const collator = new Intl.Collator('ru', {
    sensitivity: 'base',
    numeric: false,
  });

  const cancelChunks = () => {
    if (pendingFrame !== null) {
      window.cancelAnimationFrame(pendingFrame);
      pendingFrame = null;
    }
    if (pendingIdle !== null && typeof window.cancelIdleCallback === 'function') {
      window.cancelIdleCallback(pendingIdle);
      pendingIdle = null;
    }
  };

  const openRow = (row) => {
    const href = row?.dataset?.href;
    if (href) {
      window.location.assign(href);
    }
  };

  const setFilter = (next) => {
    activeFilter = next;
    filterButtons.forEach((button) => {
      const isActive = button.dataset.citiesFilter === next;
      button.classList.toggle('is-active', isActive);
      button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
    apply();
  };

  const setSort = (key) => {
    if (sortKey === key) {
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      sortKey = key;
      sortDirection = 'asc';
    }
    sortButtons.forEach((button) => {
      const isCurrent = button.dataset.sort === sortKey;
      let ariaSort = 'none';
      if (isCurrent) {
        ariaSort = sortDirection === 'asc' ? 'ascending' : 'descending';
      }
      button.setAttribute('aria-sort', ariaSort);
      button.classList.toggle('is-sorted', isCurrent);
      button.dataset.sortDirection = isCurrent ? sortDirection : '';
    });
    apply();
  };

  const matchesFilter = (item) => {
    switch (activeFilter) {
      case 'assigned':
        return item.ownerState;
      case 'unassigned':
        return !item.ownerState;
      case 'active':
        return item.active;
      default:
        return true;
    }
  };

  const compareItems = (a, b) => {
    const direction = sortDirection === 'asc' ? 1 : -1;
    if (sortKey === 'owner') {
      const nameA = a.owner || (a.ownerState ? '' : '\uFFFF');
      const nameB = b.owner || (b.ownerState ? '' : '\uFFFF');
      return collator.compare(nameA, nameB) * direction;
    }
    return collator.compare(a.name, b.name) * direction;
  };

  const updateCount = (count) => {
    if (!visibleCountLabel) return;
    visibleCountLabel.textContent = `${count}`;
  };

  const updateEmptyState = (isEmpty) => {
    if (!emptyState) return;
    emptyState.hidden = !isEmpty;
  };

  const toggleColumns = (key, visible) => {
    const cells = table.querySelectorAll(`[data-col="${key}"]`);
    cells.forEach((cell) => {
      if (visible) {
        cell.classList.remove('hidden');
        cell.removeAttribute('aria-hidden');
      } else {
        cell.classList.add('hidden');
        cell.setAttribute('aria-hidden', 'true');
      }
    });
  };

  const applyDensity = (value, persist = true) => {
    const normalized = value === 'compact' ? 'compact' : 'standard';
    if (board) {
      board.dataset.density = normalized;
    }
    table.dataset.density = normalized;
    densityButtons.forEach((button) => {
      const isActive = button.dataset.densityOption === normalized;
      button.classList.toggle('is-active', isActive);
      button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
    if (persist) {
      try {
        window.localStorage.setItem(densityStorageKey, normalized);
      } catch (err) {
        /* noop */
      }
    }
  };

  const apply = () => {
    cancelChunks();
    const query = (searchInput?.value || '').trim().toLowerCase();
    const filtered = rows.filter((item) => {
      if (!matchesFilter(item)) return false;
      if (!query) return true;
      return item.searchName.includes(query) || item.searchTz.includes(query);
    });

    const sorted = filtered.slice().sort(compareItems);
    const visibleSet = new Set(sorted);

    rows.forEach((item) => {
      if (!visibleSet.has(item)) {
        item.row.hidden = true;
        item.row.tabIndex = -1;
      }
    });

    updateCount(sorted.length);
    updateEmptyState(sorted.length === 0);

    tbody.innerHTML = '';

    let index = 0;
    const needsChunking = sorted.length > virtualizationThreshold;

    const renderChunk = () => {
      const fragment = document.createDocumentFragment();
      const limit = needsChunking ? Math.min(index + chunkSize, sorted.length) : sorted.length;
      for (; index < limit; index += 1) {
        const item = sorted[index];
        item.row.hidden = false;
        item.row.tabIndex = 0;
        fragment.appendChild(item.row);
      }
      tbody.appendChild(fragment);
      if (needsChunking && index < sorted.length) {
        if (typeof window.requestIdleCallback === 'function') {
          pendingIdle = window.requestIdleCallback(() => {
            pendingIdle = null;
            renderChunk();
          });
        } else {
          pendingFrame = window.requestAnimationFrame(() => {
            pendingFrame = null;
            renderChunk();
          });
        }
      }
    };

    renderChunk();
  };

  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const hasQuery = Boolean(searchInput.value);
      if (clearSearchButton) {
        clearSearchButton.hidden = !hasQuery;
      }
      apply();
    });
  }

  if (clearSearchButton) {
    clearSearchButton.addEventListener('click', () => {
      if (!searchInput) return;
      searchInput.value = '';
      clearSearchButton.hidden = true;
      searchInput.focus();
      apply();
    });
  }

  filterButtons.forEach((button) => {
    button.type = 'button';
    button.addEventListener('click', () => {
      const { citiesFilter } = button.dataset;
      if (!citiesFilter) return;
      setFilter(citiesFilter);
    });
  });

  sortButtons.forEach((button) => {
    button.type = 'button';
    button.addEventListener('click', () => {
      const { sort } = button.dataset;
      if (!sort) return;
      setSort(sort);
    });
  });

  columnToggles.forEach((toggle) => {
    const key = toggle.dataset.toggleColumn;
    if (!key) return;
    toggle.addEventListener('change', () => {
      toggleColumns(key, toggle.checked);
    });
    toggleColumns(key, toggle.checked);
  });

  densityButtons.forEach((button) => {
    const value = button.dataset.densityOption || 'standard';
    button.addEventListener('click', () => {
      applyDensity(value);
    });
  });

  let storedDensity = null;
  try {
    storedDensity = window.localStorage.getItem(densityStorageKey);
  } catch (err) {
    storedDensity = null;
  }
  if (storedDensity) {
    applyDensity(storedDensity, false);
  } else if (board?.dataset?.density) {
    applyDensity(board.dataset.density, false);
  }

  const initialSortButton = sortButtons.find((button) => button.dataset.sort === sortKey);
  if (initialSortButton) {
    initialSortButton.dataset.sortDirection = sortDirection;
    initialSortButton.classList.add('is-sorted');
    initialSortButton.setAttribute('aria-sort', sortDirection === 'asc' ? 'ascending' : 'descending');
  }

  if (tbody) {
    tbody.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.closest('a, button')) return;
      const row = target.closest('[data-city-row]');
      if (!row) return;
      openRow(row);
    });

    tbody.addEventListener('keydown', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (!target.matches('[data-city-row]')) return;
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openRow(target);
        return;
      }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        const visibleRows = Array.from(tbody.querySelectorAll('[data-city-row]:not([hidden])'));
        const currentIndex = visibleRows.indexOf(target);
        if (currentIndex === -1) return;
        const delta = event.key === 'ArrowDown' ? 1 : -1;
        const nextIndex = currentIndex + delta;
        if (nextIndex >= 0 && nextIndex < visibleRows.length) {
          event.preventDefault();
          visibleRows[nextIndex].focus();
        }
      }
    });
  }

  setFilter(activeFilter);
});
