const board = document.querySelector('[data-kanban-board]');
const csrfToken = window.__CSRF_TOKEN__ || '';
let draggedCard = null;
let sourceColumn = null;

function updateCounter(column, delta) {
  const counter = column.querySelector('.kanban-column__title span:last-child');
  if (!counter) return;
  const current = parseInt(counter.textContent || '0', 10);
  counter.textContent = String(Math.max(0, current + delta));
}

// Toast notification instead of blocking alert
function showToast(message, type = 'error') {
  const toast = document.createElement('div');
  toast.className = `kanban-toast kanban-toast--${type}`;
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 12px 20px;
    border-radius: 8px;
    background: ${type === 'error' ? '#ef4444' : '#22c55e'};
    color: white;
    font-size: 14px;
    z-index: 9999;
    animation: fadeIn 0.3s ease;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  `;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Map kanban column statuses to action keys for the new API
const STATUS_ACTION_MAP = {
  'hired': 'mark_hired',
  'not_hired': 'mark_not_hired',
  'interview_declined': 'reject',
  'test2_failed': 'reject',
  'intro_day_declined_day_of': 'decline_after_intro',
  'intro_day_declined_invitation': 'reject',
};

async function postStatus(candidateId, status) {
  // Use new actions API if action mapping exists, otherwise fall back to legacy
  const actionKey = STATUS_ACTION_MAP[status];

  if (actionKey) {
    // Use new API endpoint
    const response = await fetch(`/api/candidates/${candidateId}/actions/${actionKey}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-CSRFToken': csrfToken,
      },
      body: JSON.stringify({}),
    });
    let payload = {};
    try {
      payload = await response.json();
    } catch (err) {
      console.warn('candidates-board: JSON parse error', { status: response.status, candidateId });
    }
    if (!response.ok) {
      const message = payload.message || payload.detail?.message || 'Не удалось обновить статус кандидата.';
      showToast(message, 'error');
      throw new Error(message);
    }
    return payload;
  }

  // Fallback to legacy endpoint for unmapped statuses (should not happen with droppable columns)
  const response = await fetch(`/candidates/${candidateId}/status`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    body: JSON.stringify({ status }),
  });
  let payload = {};
  try {
    payload = await response.json();
  } catch (err) {
    console.warn('candidates-board: JSON parse error (legacy)', { status: response.status, candidateId });
  }
  if (!response.ok) {
    const message = payload.message || 'Не удалось обновить статус кандидата.';
    showToast(message, 'error');
    throw new Error(message);
  }
  return payload;
}

if (board) {
  board.querySelectorAll('.kanban-card').forEach((card) => {
    card.addEventListener('dragstart', (event) => {
      draggedCard = card;
      sourceColumn = card.closest('.kanban-column');
      card.classList.add('is-dragging');
      event.dataTransfer.effectAllowed = 'move';
    });
    card.addEventListener('dragend', () => {
      if (draggedCard) {
        draggedCard.classList.remove('is-dragging');
      }
      draggedCard = null;
      sourceColumn = null;
    });
  });

  board.querySelectorAll('.kanban-column').forEach((column) => {
    column.addEventListener('dragover', (event) => {
      if (!draggedCard) return;
      if (column.dataset.droppable !== 'true' || column === sourceColumn) {
        event.dataTransfer.dropEffect = 'none';
        return;
      }
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      column.classList.add('is-over');
    });

    column.addEventListener('dragleave', () => {
      column.classList.remove('is-over');
    });

    column.addEventListener('drop', async (event) => {
      event.preventDefault();
      column.classList.remove('is-over');

      if (!draggedCard || !sourceColumn) {
        return;
      }
      if (column.dataset.droppable !== 'true') {
        showToast('Эту колонку нельзя трогать вручную.', 'error');
        return;
      }
      if (column === sourceColumn) {
        return;
      }

      const candidateId = draggedCard.dataset.candidateId;
      const status = column.dataset.status;
      const previousStatus = draggedCard.dataset.status;
      if (!candidateId || !status) {
        return;
      }

      const targetBody = column.querySelector('[data-kanban-column]') || column;
      const sourceBody = sourceColumn.querySelector('[data-kanban-column]') || sourceColumn;

      // Optimistic UI update
      draggedCard.classList.add('is-loading');
      draggedCard.style.opacity = '0.6';
      targetBody.appendChild(draggedCard);
      updateCounter(sourceColumn, -1);
      updateCounter(column, 1);
      draggedCard.dataset.status = status;

      try {
        await postStatus(candidateId, status);
        // Success - finalize UI
        draggedCard.classList.remove('is-loading');
        draggedCard.style.opacity = '1';
      } catch (err) {
        // Rollback UI on error
        sourceBody.appendChild(draggedCard);
        updateCounter(column, -1);
        updateCounter(sourceColumn, 1);
        draggedCard.dataset.status = previousStatus;
        draggedCard.classList.remove('is-loading');
        draggedCard.style.opacity = '1';
      }
    });
  });
}
