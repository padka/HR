const searchInput = document.querySelector('[data-search-input]');
const searchForm = document.querySelector('[data-search-form]');
const perPageSelect = document.querySelector('[data-per-page]');

function updateQuery(changes = {}) {
  const url = new URL(window.location.href);
  Object.entries(changes).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      url.searchParams.delete(key);
    } else {
      url.searchParams.set(key, value);
    }
  });
  window.location.assign(url.toString());
}

if (searchInput) {
  let timer = null;
  const delay = 350;

  const triggerSearch = () => {
    const value = searchInput.value.trim();
    updateQuery({ search: value, page: 1 });
  };

  searchInput.addEventListener('input', () => {
    clearTimeout(timer);
    timer = window.setTimeout(triggerSearch, delay);
  });

  searchForm?.addEventListener('submit', (event) => {
    event.preventDefault();
    triggerSearch();
  });
}

if (perPageSelect) {
  perPageSelect.addEventListener('change', () => {
    updateQuery({ per_page: perPageSelect.value, page: 1 });
  });
}
