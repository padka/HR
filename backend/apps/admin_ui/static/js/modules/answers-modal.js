const modal = document.querySelector('[data-answer-modal]');
if (modal) {
  const dialog = modal.querySelector('.modal__dialog');
  const titleEl = modal.querySelector('[data-answer-modal-title]');
  const metaEl = modal.querySelector('[data-answer-modal-meta]');
  const bodyEl = modal.querySelector('[data-answer-modal-body]');
  const closeButtons = modal.querySelectorAll('[data-answer-modal-close]');
  let lastTrigger = null;

  const renderAnswers = (payload) => {
    if (!bodyEl) return;
    bodyEl.innerHTML = '';
    const list = document.createElement('ol');
    list.className = 'answers-list';
    list.setAttribute('role', 'list');

    (payload.questions || []).forEach((item, index) => {
      const entry = document.createElement('li');
      entry.className = 'answers-list__item surface';
      const header = document.createElement('div');
      header.className = 'answers-list__header';

      const title = document.createElement('span');
      title.className = 'answers-list__question';
      title.textContent = `Вопрос ${index + 1}: ${item.question_text || ''}`;
      header.appendChild(title);

      const badges = document.createElement('span');
      badges.className = 'answers-list__badges';
      const statusBadge = document.createElement('span');
      statusBadge.className = item.is_correct ? 'badge badge--success' : 'badge badge--muted';
      statusBadge.textContent = item.is_correct ? 'Верно' : 'Неверно';
      badges.appendChild(statusBadge);
      if (item.overtime) {
        const overtime = document.createElement('span');
        overtime.className = 'badge badge--soft';
        overtime.textContent = 'Просрочено';
        badges.appendChild(overtime);
      }
      header.appendChild(badges);
      entry.appendChild(header);

      const answer = document.createElement('p');
      answer.innerHTML = `Ответ кандидата: <strong>${item.user_answer || '—'}</strong>`;
      entry.appendChild(answer);

      if (!item.is_correct && item.correct_answer) {
        const correct = document.createElement('p');
        correct.innerHTML = `Правильный ответ: <strong>${item.correct_answer}</strong>`;
        entry.appendChild(correct);
      }

      const meta = document.createElement('p');
      meta.className = 'muted text-sm';
      meta.textContent = `Время: ${item.time_spent || '—'} сек · Попытки: ${item.attempts_count || '—'}`;
      entry.appendChild(meta);

      list.appendChild(entry);
    });

    bodyEl.appendChild(list);
  };

  const openModal = (payload, trigger) => {
    if (titleEl) {
      titleEl.textContent = payload.title || 'Ответы теста';
    }
    if (metaEl) {
      const { stats } = payload;
      if (stats) {
        const overtime = stats.overtime ? `, просрочено: ${stats.overtime}` : '';
        metaEl.textContent = `Правильных: ${stats.correct || 0} из ${stats.total || 0}${overtime}`;
      } else {
        metaEl.textContent = '';
      }
    }
    renderAnswers(payload);
    modal.removeAttribute('hidden');
    document.body.style.overflow = 'hidden';
    lastTrigger = trigger;
    setTimeout(() => {
      dialog?.focus();
    }, 0);
  };

  const closeModal = () => {
    modal.setAttribute('hidden', '');
    document.body.style.overflow = '';
    if (lastTrigger) {
      lastTrigger.focus();
    }
  };

  modal.addEventListener('click', (event) => {
    if (event.target === modal) {
      closeModal();
    }
  });

  closeButtons.forEach((btn) => {
    btn.addEventListener('click', () => closeModal());
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modal.hasAttribute('hidden')) {
      event.preventDefault();
      closeModal();
    }
  });

  document.querySelectorAll('[data-answer-modal-trigger]').forEach((trigger) => {
    trigger.addEventListener('click', () => {
      const payloadRaw = trigger.getAttribute('data-answer-modal-payload');
      if (!payloadRaw) return;
      try {
        const payload = JSON.parse(payloadRaw);
        openModal(payload, trigger);
      } catch (err) {
        console.error('answers-modal.parse-error', err);
      }
    });
  });
}
