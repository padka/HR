/**
 * Shared utility functions for RecruitSmart Admin UI.
 * Import these instead of duplicating code in each module.
 */

/**
 * Escape HTML special characters to prevent XSS.
 * @param {string} str - String to escape
 * @returns {string} Escaped string
 */
export function escapeHTML(str) {
  if (str == null) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

/**
 * Show a toast notification.
 * @param {string} message - Message to display
 * @param {'success' | 'error' | 'warning' | 'info'} type - Toast type
 * @param {number} duration - Duration in ms (default 4000)
 */
export function showToast(message, type = 'info', duration = 4000) {
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.textContent = message;
  toast.setAttribute('role', 'alert');
  toast.setAttribute('aria-live', 'polite');

  const colors = {
    success: '#22c55e',
    error: '#ef4444',
    warning: '#f59e0b',
    info: '#3b82f6',
  };

  toast.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 12px 20px;
    border-radius: 8px;
    background: ${colors[type] || colors.info};
    color: white;
    font-size: 14px;
    font-weight: 500;
    z-index: 9999;
    max-width: 400px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    animation: toastSlideIn 0.3s ease;
  `;

  // Add animation keyframes if not already present
  if (!document.getElementById('toast-styles')) {
    const style = document.createElement('style');
    style.id = 'toast-styles';
    style.textContent = `
      @keyframes toastSlideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
      }
    `;
    document.head.appendChild(style);
  }

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

/**
 * Build URL search params from an object, skipping null/undefined/empty values.
 * @param {Object} params - Key-value pairs
 * @returns {URLSearchParams}
 */
export function buildSearchParams(params) {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value != null && value !== '') {
      searchParams.set(key, String(value));
    }
  }
  return searchParams;
}

/**
 * Get CSRF token from page meta tag or cookie.
 * @returns {string|null}
 */
export function getCSRFToken() {
  // Try meta tag first
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta) {
    return meta.getAttribute('content');
  }
  // Try hidden input
  const input = document.querySelector('input[name="csrf_token"]');
  if (input) {
    return input.value;
  }
  // Try cookie
  const match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : null;
}

/**
 * Make a fetch request with common defaults (JSON, CSRF).
 * @param {string} url - Request URL
 * @param {Object} options - Fetch options
 * @returns {Promise<{ok: boolean, status: number, data: any}>}
 */
export async function fetchJSON(url, options = {}) {
  const csrfToken = getCSRFToken();
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    ...(csrfToken && { 'X-CSRFToken': csrfToken }),
    ...options.headers,
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    let data = {};
    try {
      data = await response.json();
    } catch (parseError) {
      console.warn('fetchJSON: JSON parse error', { url, status: response.status });
    }

    return {
      ok: response.ok,
      status: response.status,
      data,
    };
  } catch (networkError) {
    console.error('fetchJSON: Network error', { url, error: networkError });
    return {
      ok: false,
      status: 0,
      data: { message: 'Ошибка сети. Проверьте подключение.' },
    };
  }
}

/**
 * Set loading state on a button.
 * @param {HTMLButtonElement} button - Button element
 * @param {boolean} loading - Whether loading
 * @param {string} loadingText - Text to show while loading
 */
export function setButtonLoading(button, loading, loadingText = 'Загрузка...') {
  if (!button) return;

  if (loading) {
    button.dataset.originalText = button.textContent;
    button.textContent = loadingText;
    button.disabled = true;
    button.classList.add('is-loading');
  } else {
    button.textContent = button.dataset.originalText || button.textContent;
    button.disabled = false;
    button.classList.remove('is-loading');
    delete button.dataset.originalText;
  }
}

/**
 * Debounce a function.
 * @param {Function} fn - Function to debounce
 * @param {number} delay - Delay in ms
 * @returns {Function}
 */
export function debounce(fn, delay = 300) {
  let timeoutId;
  return function (...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * Format a date for display.
 * @param {string|Date} date - Date to format
 * @param {Object} options - Intl.DateTimeFormat options
 * @returns {string}
 */
export function formatDate(date, options = {}) {
  if (!date) return '';
  const d = typeof date === 'string' ? new Date(date) : date;
  if (isNaN(d.getTime())) return '';

  const defaultOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...options,
  };

  return new Intl.DateTimeFormat('ru-RU', defaultOptions).format(d);
}

/**
 * Format a date with time.
 * @param {string|Date} date - Date to format
 * @returns {string}
 */
export function formatDateTime(date) {
  return formatDate(date, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
