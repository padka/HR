import { bindSubmitHotkey } from './form-hotkeys.js';

const DEFAULT_PREVIEW_FIELDS = {
  '{{candidate_fio}}': 'pv_fio',
  '{{city_name}}': 'pv_city',
  '{{slot_date_local}}': 'pv_date',
  '{{slot_time_local}}': 'pv_time',
  '{{recruiter_name}}': 'pv_rec',
  '{{recruiter_phone}}': 'pv_phone',
  '{{address}}': 'pv_addr',
  '{{whatsapp_link}}': 'pv_wa'
};

const DEFAULT_PREVIEW_VALUES = {
  '{{candidate_fio}}': 'Иван Иванов',
  '{{city_name}}': 'Москва',
  '{{slot_date_local}}': '21.09',
  '{{slot_time_local}}': '10:30',
  '{{recruiter_name}}': 'Михаил',
  '{{recruiter_phone}}': '+7 (900) 000-00-00',
  '{{address}}': 'ул. Пушкина, 10',
  '{{whatsapp_link}}': 'https://wa.me/79000000000'
};

function randomKey() {
  const stamp = Date.now().toString(36);
  const random = Math.random().toString(36).replace(/[^a-z0-9]/g, '').slice(0, 6);
  return `tmpl_${stamp}_${random}`;
}

export function initTemplateEditor(options = {}) {
  const {
    root = document,
    formId,
    textareaId = 'text',
    counterId,
    previewId,
    placeholderSelector,
    presets,
    presetSelectId,
    keyInputId,
    isGlobalCheckboxId,
    citySelectId,
    cityFilterId,
    charLimit = null,
    showLimit = false,
    submitHotkey,
    previewFields = {},
  } = options;

  const form = formId ? root.getElementById(formId) : null;
  const textarea = textareaId ? root.getElementById(textareaId) : null;
  const counter = counterId ? root.getElementById(counterId) : null;
  const preview = previewId ? root.getElementById(previewId) : null;
  const placeholderButtons = placeholderSelector ? Array.from(root.querySelectorAll(placeholderSelector)) : [];
  const presetSelect = presetSelectId ? root.getElementById(presetSelectId) : null;
  const keyInput = keyInputId ? root.getElementById(keyInputId) : null;
  const globalCheckbox = isGlobalCheckboxId ? root.getElementById(isGlobalCheckboxId) : null;
  const citySelect = citySelectId ? root.getElementById(citySelectId) : null;
  const cityFilter = cityFilterId ? root.getElementById(cityFilterId) : null;

  if (!textarea) {
    return;
  }

  const teardown = [];
  if (submitHotkey && form) {
    const off = bindSubmitHotkey(form, submitHotkey);
    teardown.push(off);
  }

  const previewMap = { ...DEFAULT_PREVIEW_FIELDS, ...previewFields };
  const previewTokens = Object.keys(previewMap);

  const cityOptionsData = citySelect
    ? Array.from(citySelect.options).map(opt => ({
        value: opt.value,
        text: opt.textContent,
        disabled: opt.disabled,
        selected: opt.selected,
      }))
    : [];

  if (citySelect) {
    citySelect.addEventListener('change', () => {
      const current = citySelect.value;
      cityOptionsData.forEach(item => {
        item.selected = item.value === current;
      });
    });
  }

  function rebuildCityOptions(filtered = null) {
    if (!citySelect) return;
    const list = filtered || cityOptionsData;
    citySelect.innerHTML = '';
    list.forEach(item => {
      const option = document.createElement('option');
      option.value = item.value;
      option.textContent = item.text;
      option.disabled = item.disabled;
      if (item.selected && !option.disabled) {
        option.selected = true;
      }
      citySelect.appendChild(option);
    });
  }

  function ensureKey(force = false) {
    if (!keyInput) return;
    if (force || !(keyInput.value || '').trim()) {
      keyInput.value = randomKey();
    }
  }

  function updateGlobalState() {
    if (!globalCheckbox || !citySelect) return;
    const global = globalCheckbox.checked;
    citySelect.disabled = global || !cityOptionsData.length;
    if (global) {
      citySelect.removeAttribute('required');
      citySelect.value = '';
    } else {
      citySelect.setAttribute('required', '');
    }
    if (cityFilter) {
      cityFilter.disabled = global || !cityOptionsData.length;
    }
  }

  function filterCities() {
    if (!citySelect || !cityFilter) return;
    const query = (cityFilter.value || '').toLowerCase().trim();
    if (!query) {
      rebuildCityOptions();
      return;
    }
    const filtered = cityOptionsData.filter(opt => !opt.value || opt.text.toLowerCase().includes(query));
    rebuildCityOptions(filtered);
    if (!citySelect.value && filtered.length) {
      const first = filtered.find(opt => opt.value);
      if (first) {
        citySelect.value = first.value;
      }
    }
  }

  function insertAtCursor(text) {
    const el = textarea;
    el.focus();
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    const before = el.value.slice(0, start);
    const after = el.value.slice(end);
    el.value = before + text + after;
    const pos = start + text.length;
    el.selectionStart = el.selectionEnd = pos;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }

  placeholderButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const value = btn.getAttribute('data-insert') || btn.getAttribute('data-ph') || '';
      insertAtCursor(value);
    });
  });

  if (presetSelect && presets) {
    presetSelect.addEventListener('change', () => {
      const key = presetSelect.value;
      if (!key) { return; }
      const preset = presets[key];
      if (preset) {
        textarea.value = preset;
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });
  }

  function getPreviewValue(token) {
    const inputId = previewMap[token];
    if (!inputId) {
      return DEFAULT_PREVIEW_VALUES[token] || '';
    }
    const node = root.getElementById(inputId);
    if (!node) {
      return DEFAULT_PREVIEW_VALUES[token] || '';
    }
    const value = node.value ?? node.textContent;
    return value && String(value).trim() ? String(value) : (DEFAULT_PREVIEW_VALUES[token] || '');
  }

  function renderPreview() {
    if (!preview) return;
    let content = textarea.value || '';
    previewTokens.forEach(token => {
      const value = getPreviewValue(token);
      content = content.split(token).join(value);
    });
    preview.textContent = content;
  }

  function updateCounter() {
    if (!counter) return;
    const len = textarea.value.length;
    counter.textContent = showLimit && charLimit ? `${len}` : String(len);
    if (charLimit) {
      const badge = counter.closest('.badge');
      if (badge) {
        badge.dataset.overflow = String(len > charLimit);
      }
    }
  }

  function updateMeta() {
    updateCounter();
    renderPreview();
  }

  textarea.addEventListener('input', updateMeta);
  previewTokens.forEach(token => {
    const id = previewMap[token];
    if (!id) return;
    const node = root.getElementById(id);
    if (node) {
      node.addEventListener('input', renderPreview);
    }
  });

  if (globalCheckbox) {
    globalCheckbox.addEventListener('change', updateGlobalState);
    updateGlobalState();
  }

  if (cityFilter) {
    cityFilter.addEventListener('input', filterCities);
  }

  ensureKey(true);
  updateMeta();
  filterCities();

  if (form) {
    form.addEventListener('submit', ensureKey);
  }

  return () => {
    teardown.forEach(fn => typeof fn === 'function' && fn());
  };
}
