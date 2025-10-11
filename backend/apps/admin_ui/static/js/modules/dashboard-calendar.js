const root = document.querySelector('[data-calendar-root]');

if (root) {
  const endpoint = root.dataset.calendarEndpoint || '/api/dashboard/calendar';
  const daysContainer = root.querySelector('[data-calendar-days]');
  const eventsContainer = root.querySelector('[data-calendar-events]');
  const feedbackEl = root.querySelector('[data-calendar-feedback]');
  const dateInput = root.querySelector('[data-calendar-input]');
  const refreshBtn = root.querySelector('[data-calendar-refresh]');
  const summaryLabel = document.querySelector('[data-calendar-label]');
  const summaryTotal = document.querySelector('[data-calendar-total]');
  const summaryMeta = document.querySelector('[data-calendar-meta]');
  const summaryUpdated = document.querySelector('[data-calendar-updated]');
  const statusBlock = root.querySelector('[data-calendar-status]');
  const statusConfirmed = root.querySelector('[data-calendar-status-confirmed]');
  const statusBooked = root.querySelector('[data-calendar-status-booked]');
  const statusPending = root.querySelector('[data-calendar-status-pending]');
  const statusCanceled = root.querySelector('[data-calendar-status-canceled]');

  const REFRESH_INTERVAL = 30000;
  let refreshTimer = null;
  let controller = null;
  let currentDate = null;
  let windowDays = null;

  function safeParseInitial() {
    const raw = root.dataset.calendarInitial;
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw);
    } catch (err) {
      console.warn('Failed to parse calendar initial payload', err);
      return null;
    }
  }

  function setLoading(isLoading) {
    root.dataset.loading = isLoading ? 'true' : 'false';
  }

  function setError(message) {
    if (!feedbackEl) {
      return;
    }
    if (!message) {
      feedbackEl.textContent = '';
      feedbackEl.dataset.state = 'idle';
      return;
    }
    feedbackEl.textContent = message;
    feedbackEl.dataset.state = 'error';
  }

  function renderDays(days) {
    if (!daysContainer) {
      return;
    }
    daysContainer.innerHTML = '';
    (days || []).forEach((day) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'calendar-day pill focus-ring';
      if (day.is_selected) {
        button.classList.add('is-active');
      }
      if (day.is_today) {
        button.classList.add('is-today');
      }
      button.dataset.calendarDay = day.date;

      const weekday = document.createElement('span');
      weekday.className = 'calendar-day__weekday';
      weekday.textContent = day.weekday;
      button.appendChild(weekday);

      const date = document.createElement('span');
      date.className = 'calendar-day__date';
      date.textContent = day.label;
      button.appendChild(date);

      const count = document.createElement('span');
      count.className = 'calendar-day__count';
      count.textContent = String(day.count || 0);
      button.appendChild(count);

      button.addEventListener('click', () => {
        if (day.date !== currentDate) {
          selectDate(day.date);
        }
      });

      daysContainer.appendChild(button);
    });
  }

  function renderEvent(event) {
    const wrapper = document.createElement('article');
    wrapper.className = 'calendar-event surface';
    wrapper.dataset.calendarEventId = String(event.id);

    const clock = document.createElement('div');
    clock.className = 'calendar-event__clock';
    const start = document.createElement('span');
    start.className = 'calendar-event__start';
    start.textContent = event.start_time;
    const end = document.createElement('span');
    end.className = 'calendar-event__end';
    end.textContent = `до ${event.end_time}`;
    clock.appendChild(start);
    clock.appendChild(end);
    wrapper.appendChild(clock);

    const details = document.createElement('div');
    details.className = 'calendar-event__details';

    const header = document.createElement('div');
    header.className = 'calendar-event__header';

    const title = document.createElement('h3');
    title.className = 'calendar-event__title';
    if (event.candidate && event.candidate.profile_url) {
      const link = document.createElement('a');
      link.href = event.candidate.profile_url;
      link.className = 'calendar-event__candidate';
      link.textContent = event.candidate.name || 'Кандидат';
      title.appendChild(link);
    } else {
      title.textContent = event.candidate?.name || 'Кандидат';
    }
    header.appendChild(title);

    if (event.status_label) {
      const badge = document.createElement('span');
      badge.className = `badge badge--${event.status_variant || 'muted'}`;
      badge.textContent = event.status_label;
      header.appendChild(badge);
    }

    details.appendChild(header);

    const meta = document.createElement('p');
    meta.className = 'calendar-event__meta';
    const recruiterName = event.recruiter?.name || 'Без рекрутёра';
    const cityName = event.city?.name ? ` · ${event.city.name}` : '';
    meta.textContent = `${recruiterName}${cityName}`;
    details.appendChild(meta);

    if (event.candidate?.telegram_id) {
      const tg = document.createElement('p');
      tg.className = 'calendar-event__meta muted';
      tg.textContent = `tg: ${event.candidate.telegram_id}`;
      details.appendChild(tg);
    }

    wrapper.appendChild(details);
    return wrapper;
  }

  function renderEvents(events) {
    if (!eventsContainer) {
      return;
    }
    eventsContainer.innerHTML = '';
    if (!events || events.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'calendar-empty';
      empty.textContent = 'На выбранную дату интервью не запланировано.';
      eventsContainer.appendChild(empty);
      return;
    }
    events.forEach((event) => {
      eventsContainer.appendChild(renderEvent(event));
    });
  }

  function updateStatusSummary(summary) {
    if (statusConfirmed) {
      statusConfirmed.textContent = String(summary?.CONFIRMED_BY_CANDIDATE || 0);
    }
    if (statusBooked) {
      statusBooked.textContent = String(summary?.BOOKED || 0);
    }
    if (statusPending) {
      statusPending.textContent = String(summary?.PENDING || 0);
    }
    if (statusCanceled) {
      statusCanceled.textContent = String(summary?.CANCELED || 0);
    }
    if (statusBlock) {
      statusBlock.dataset.state = summary ? 'ready' : 'empty';
    }
  }

  function applySnapshot(snapshot) {
    if (!snapshot || snapshot.ok === false) {
      return;
    }
    currentDate = snapshot.selected_date || currentDate;
    windowDays = snapshot.window_days || snapshot.days?.length || windowDays;

    renderDays(snapshot.days);
    renderEvents(snapshot.events);
    updateStatusSummary(snapshot.status_summary);

    if (dateInput && snapshot.selected_date) {
      dateInput.value = snapshot.selected_date;
    }
    if (summaryLabel) {
      summaryLabel.textContent = snapshot.selected_label || '';
    }
    if (summaryTotal) {
      summaryTotal.textContent = String(snapshot.events_total ?? 0);
    }
    if (summaryMeta) {
      summaryMeta.textContent = snapshot.meta || 'Нет назначенных интервью';
    }
    if (summaryUpdated) {
      summaryUpdated.textContent = snapshot.updated_label || '';
    }

    setError('');
    setLoading(false);
  }

  async function fetchSnapshot(dateValue, { silent = false } = {}) {
    if (!endpoint) {
      return null;
    }

    if (controller) {
      controller.abort();
    }
    controller = new AbortController();

    if (!silent) {
      setLoading(true);
    }

    const url = new URL(endpoint, window.location.origin);
    if (dateValue) {
      url.searchParams.set('date', dateValue);
    }
    if (windowDays) {
      url.searchParams.set('days', String(windowDays));
    }

    const response = await fetch(url.toString(), {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    const payload = await response.json();
    return payload;
  }

  async function selectDate(dateValue) {
    try {
      const snapshot = await fetchSnapshot(dateValue);
      applySnapshot(snapshot);
    } catch (err) {
      if (err.name === 'AbortError') {
        return;
      }
      console.error('Failed to load calendar data', err);
      setLoading(false);
      setError('Не удалось обновить календарь. Попробуйте ещё раз.');
    }
  }

  async function silentRefresh() {
    if (!currentDate) {
      return;
    }
    try {
      const snapshot = await fetchSnapshot(currentDate, { silent: true });
      applySnapshot(snapshot);
    } catch (err) {
      if (err.name === 'AbortError') {
        return;
      }
      console.warn('Silent refresh failed', err);
    }
  }

  const initial = safeParseInitial();
  if (initial) {
    currentDate = initial.selected_date || null;
    windowDays = initial.window_days || initial.days?.length || null;
    applySnapshot(initial);
  }

  if (dateInput) {
    dateInput.addEventListener('change', (event) => {
      const value = event.target.value;
      if (value) {
        selectDate(value);
      }
    });
  }

  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      if (currentDate) {
        selectDate(currentDate);
      }
    });
  }

  if (REFRESH_INTERVAL > 0) {
    refreshTimer = window.setInterval(silentRefresh, REFRESH_INTERVAL);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        if (refreshTimer) {
          window.clearInterval(refreshTimer);
          refreshTimer = null;
        }
      } else if (!refreshTimer) {
        silentRefresh();
        refreshTimer = window.setInterval(silentRefresh, REFRESH_INTERVAL);
      }
    });
  }

  window.addEventListener('beforeunload', () => {
    if (controller) {
      controller.abort();
    }
    if (refreshTimer) {
      window.clearInterval(refreshTimer);
    }
  });
}
