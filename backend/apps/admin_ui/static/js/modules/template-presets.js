const PRESETS_DATA_ELEMENT_ID = "template-presets-data";

function readPresetData() {
  const holder = document.getElementById(PRESETS_DATA_ELEMENT_ID);
  if (!holder) {
    return {};
  }

  const raw = holder.textContent || "{}";
  try {
    return JSON.parse(raw);
  } catch (error) {
    console.warn("Не удалось прочитать пресеты шаблонов", error);
    return {};
  }
}

export function getTemplatePresets() {
  return readPresetData();
}
