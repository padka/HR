/*
 * UX Telemetry helper (demo-only)
 * Captures filter, click, scroll and search interactions when DEBUG_UX=1.
 * Logs are stored in window.__UX_LOG and can be persisted as JSON files
 * under previews/ux_logs/ for offline analysis.
 */
(function () {
  'use strict';

  var global = window;
  var debugFlag = String(global.DEBUG_UX || document.documentElement.dataset.debugUx || '0');
  var debugEnabled = debugFlag === '1' || debugFlag.toLowerCase() === 'true';

  if (!debugEnabled) {
    global.__uxTelemetry = {
      enabled: false,
      record: function () {},
      flush: function () {},
    };
    return;
  }

  var LOG_KEY = '__UX_LOG';
  var CACHE_KEY = '__UX_LOG_CACHE__';
  var log = Array.isArray(global[LOG_KEY]) ? global[LOG_KEY] : [];
  global[LOG_KEY] = log;

  var lastScrollY = global.scrollY;
  var saveTimer = null;
  var saveDelay = 1500;

  function nowISO() {
    return new Date().toISOString();
  }

  function sanitizeText(text) {
    if (!text) return '';
    return text.replace(/\s+/g, ' ').trim().slice(0, 80);
  }

  function elementDescriptor(el) {
    if (!el) return {};
    var descriptor = {
      tag: el.tagName ? el.tagName.toLowerCase() : undefined,
      id: el.id || undefined,
      name: el.name || undefined,
      classes: el.classList ? Array.prototype.slice.call(el.classList) : undefined,
      label: el.dataset ? el.dataset.uxLabel || el.getAttribute('aria-label') : null,
    };
    if (!descriptor.label && typeof el.innerText === 'string') {
      descriptor.label = sanitizeText(el.innerText);
    }
    if (el.dataset) {
      descriptor.dataset = {};
      Object.keys(el.dataset).forEach(function (key) {
        if (key.indexOf('ux') === 0 || key.indexOf('track') >= 0) {
          descriptor.dataset[key] = el.dataset[key];
        }
      });
    }
    return descriptor;
  }

  function record(eventType, payload) {
    var entry = {
      ts: nowISO(),
      type: eventType,
      url: global.location ? global.location.pathname + global.location.search : undefined,
      payload: payload || {},
    };
    log.push(entry);
    scheduleSave();
  }

  function handleClick(event) {
    var target = event.target.closest('[data-ux-track], [data-ux-label], button, a');
    if (!target) return;
    record('click', {
      element: elementDescriptor(target),
      x: event.clientX,
      y: event.clientY,
    });
  }

  function handleFilterChange(event) {
    var target = event.target;
    if (!target) return;
    if (target.matches('[data-ux-filter], select, input[type="checkbox"], input[type="radio"]')) {
      var value = target.type === 'checkbox' ? target.checked : target.value;
      record('filter', {
        element: elementDescriptor(target),
        value: value,
      });
    }
  }

  var searchTimer = null;
  function handleSearch(event) {
    var target = event.target;
    if (!target) return;
    if (!target.matches('[data-ux-search], input[type="search"], input[data-role="search"]')) {
      return;
    }
    if (searchTimer) {
      clearTimeout(searchTimer);
    }
    searchTimer = setTimeout(function () {
      record('search', {
        element: elementDescriptor(target),
        valueLength: target.value ? target.value.length : 0,
        sample: sanitizeText(target.value).slice(0, 20),
      });
      searchTimer = null;
    }, 400);
  }

  var scrollScheduled = false;
  function handleScroll() {
    if (scrollScheduled) return;
    scrollScheduled = true;
    global.requestAnimationFrame(function () {
      scrollScheduled = false;
      var direction = global.scrollY > lastScrollY ? 'down' : 'up';
      lastScrollY = global.scrollY;
      var doc = document.documentElement;
      var scrollHeight = doc ? doc.scrollHeight : 0;
      var viewportHeight = global.innerHeight;
      var depth = scrollHeight > 0 ? Math.min(1, (global.scrollY + viewportHeight) / scrollHeight) : 0;
      record('scroll', {
        y: global.scrollY,
        direction: direction,
        depth: Math.round(depth * 100) / 100,
      });
    });
  }

  function scheduleSave() {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(function () {
      persistLog(false);
    }, saveDelay);
  }

  function defaultWriter(fileName, payload) {
    try {
      if (global.showSaveFilePicker) {
        var opts = {
          suggestedName: fileName,
          types: [
            {
              description: 'UX log',
              accept: { 'application/json': ['.json'] },
            },
          ],
        };
        return global
          .showSaveFilePicker(opts)
          .then(function (handle) {
            return handle.createWritable();
          })
          .then(function (writable) {
            return writable.write(payload).then(function () {
              return writable.close();
            });
          });
      }
    } catch (err) {
      console.warn('UX telemetry: File picker unavailable', err);
    }

    var blob = new Blob([payload], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    return Promise.resolve();
  }

  function persistLog(forceDownload) {
    saveTimer = null;
    if (!log.length) return;
    var payload = JSON.stringify(
      {
        generatedAt: nowISO(),
        entries: log,
      },
      null,
      2
    );
    var fileName = 'previews-ux_logs-' + nowISO().replace(/[:.]/g, '-') + '.json';

    if (typeof global.__UX_LOG_WRITER__ === 'function') {
      global.__UX_LOG_WRITER__(fileName, payload).catch(function (error) {
        console.warn('UX telemetry: failed to persist log', error);
      });
      return;
    }

    try {
      global.localStorage.setItem(CACHE_KEY, payload);
    } catch (storageErr) {
      console.warn('UX telemetry: unable to cache log', storageErr);
    }

    if (forceDownload) {
      defaultWriter(fileName, payload).catch(function (error) {
        console.warn('UX telemetry: failed to save log', error);
      });
    }
  }

  function flush(forceDownload) {
    persistLog(forceDownload === true);
  }

  function restoreCachedLog() {
    try {
      var cached = global.localStorage.getItem(CACHE_KEY);
      if (cached) {
        var parsed = JSON.parse(cached);
        if (parsed && Array.isArray(parsed.entries)) {
          Array.prototype.push.apply(log, parsed.entries);
        }
        global.localStorage.removeItem(CACHE_KEY);
      }
    } catch (err) {
      console.warn('UX telemetry: unable to restore cache', err);
    }
  }

  restoreCachedLog();

  document.addEventListener('click', handleClick, true);
  document.addEventListener('change', handleFilterChange, true);
  document.addEventListener('input', handleSearch, true);
  global.addEventListener('scroll', handleScroll, { passive: true });
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') {
      persistLog(false);
    }
  });
  global.addEventListener('beforeunload', function () {
    persistLog(false);
  });

  global.__uxTelemetry = {
    enabled: true,
    record: record,
    flush: flush,
    log: log,
  };
})();
