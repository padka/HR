const scriptForm = document.querySelector('[data-interview-form]');
if (scriptForm) {
  const checkboxes = Array.from(scriptForm.querySelectorAll('input[name="checklist[]"]'));
  const progressEl = scriptForm.querySelector('[data-interview-progress]');
  const total = Number(progressEl?.textContent.split('/')[1]) || checkboxes.length;

  const updateProgress = () => {
    const completed = checkboxes.filter((box) => box.checked).length;
    if (progressEl) {
      progressEl.textContent = `${completed}/${total}`;
    }
    checkboxes.forEach((box) => {
      box.closest('.interview-step')?.classList.toggle('is-complete', box.checked);
    });
  };

  checkboxes.forEach((box) => {
    box.addEventListener('change', updateProgress);
  });

  updateProgress();
}
