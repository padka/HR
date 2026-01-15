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

async function postStatus(candidateId, status) {
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
    // ignore JSON parse errors
  }
  if (!response.ok) {
    const message = payload.message || 'Не удалось обновить статус кандидата.';
    window.alert(message);
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
        window.alert('Эту колонку нельзя трогать вручную.');
        return;
      }
      if (column === sourceColumn) {
        return;
      }

      const candidateId = draggedCard.dataset.candidateId;
      const status = column.dataset.status;
      if (!candidateId || !status) {
        return;
      }

      try {
        await postStatus(candidateId, status);
      } catch (err) {
        return;
      }

      const targetBody = column.querySelector('[data-kanban-column]') || column;
      const sourceBody = sourceColumn.querySelector('[data-kanban-column]') || sourceColumn;

      updateCounter(sourceColumn, -1);
      updateCounter(column, 1);

      targetBody.appendChild(draggedCard);
      draggedCard.dataset.status = status;
    });
  });
}
