const cards = Array.from(document.querySelectorAll('[data-rec-card]'));
if (cards.length) {
  const liveRegion = document.createElement('div');
  liveRegion.setAttribute('aria-live', 'polite');
  liveRegion.className = 'sr-only';
  document.body.appendChild(liveRegion);

  const flashMessage = (message) => {
    liveRegion.textContent = '';
    window.requestAnimationFrame(() => {
      liveRegion.textContent = message;
    });
  };

  const openCard = (card) => {
    const url = card?.dataset.recUrl;
    if (url) {
      window.location.assign(url);
    }
  };

  cards.forEach((card) => {
    card.addEventListener('click', (event) => {
      const rawTarget = event.target;
      const quickAction = rawTarget instanceof Element ? rawTarget.closest('.quick-actions .btn') : null;
      if (quickAction) return;
      if (event.defaultPrevented) return;
      event.preventDefault();
      openCard(card);
    });

    card.addEventListener('keydown', (event) => {
      if (event.code === 'Enter' || event.code === 'Space') {
        const target = event.target;
        if (target instanceof HTMLElement && target.closest('.quick-actions')) {
          return;
        }
        event.preventDefault();
        openCard(card);
      }
    });

    const toggleBtn = card.querySelector('[data-action="toggle"]');
    const copyBtn = card.querySelector('[data-action="copy-link"]');
    const toggleForm = card.querySelector('[data-toggle-form]');
    const activeField = toggleForm?.querySelector('[data-active-field]');

    toggleBtn?.addEventListener('click', async (event) => {
      event.stopPropagation();
      if (!toggleForm || !activeField) return;
      const nextIsActive = toggleBtn.getAttribute('aria-pressed') !== 'true';
      activeField.value = nextIsActive ? '1' : '';
      const formData = new FormData(toggleForm);
      try {
        const response = await fetch(toggleForm.action, {
          method: 'POST',
          body: formData,
        });
        if (!response.ok) throw new Error('failed');
        toggleBtn.setAttribute('aria-pressed', nextIsActive ? 'true' : 'false');
        card.dataset.recActive = nextIsActive ? 'true' : 'false';
        const status = card.querySelector('.recruiter-status');
        if (status) {
          status.dataset.state = nextIsActive ? 'active' : 'inactive';
          status.textContent = nextIsActive ? 'Активен' : 'Неактивен';
        }
        flashMessage(nextIsActive ? 'Рекрутёр включён' : 'Рекрутёр выключен');
      } catch (err) {
        flashMessage('Не удалось обновить статус');
      }
    });

    copyBtn?.addEventListener('click', async (event) => {
      event.stopPropagation();
      const link = copyBtn.dataset.link || '';
      if (!link) {
        flashMessage('Ссылка на телемост не указана');
        copyBtn.classList.add('is-empty');
        window.setTimeout(() => copyBtn.classList.remove('is-empty'), 1600);
        return;
      }
      try {
        await navigator.clipboard.writeText(link);
        copyBtn.classList.add('is-success');
        flashMessage('Ссылка скопирована');
      } catch (err) {
        flashMessage('Скопируйте вручную: ' + link);
      } finally {
        window.setTimeout(() => copyBtn.classList.remove('is-success'), 1600);
      }
    });
  });
}
