"use strict";

/**
 * Лёгкая i18n: русский и английский.
 * Язык: localStorage → язык системы (ru → русский, иначе — английский).
 * Статические строки — атрибуты data-i18n / data-i18n-title,
 * динамические — t("key", {vars}).
 */

const I18N = {
  ru: {
    "tab.image": "Картинка",
    "tab.vox": ".vox",
    "tab.scene": "Сцена",
    "file.choose": "Выберите изображение…",
    "voxfile.choose": "Выберите модель .vox (MagicaVoxel)…",
    "mode.label": "Режим подбора блоков",
    "mode.adaptive": "Адаптивный (k-means)",
    "mode.palette": "Полная палитра",
    "k.label": "Число блоков K:",
    "orientation.label": "Ориентация",
    "orientation.vertical": "Вертикальная картина",
    "orientation.floor": "Ковёр на полу",
    "target.label": "Макс. сторона (блоки)",
    "dither": "Дизеринг (Floyd–Steinberg)",
    "relief": "Рельеф (3D)",
    "maxheight.label": "Макс. глубина/высота:",
    "smoothing.label": "Сглаживание:",
    "invert": "Инвертировать яркость",
    "baseblock.label": "Блок основания",
    "gridlines": "Сетка на превью (2D)",
    "generate": "Сгенерировать",
    "addtoscene": "Добавить в сцену",
    "download": "Скачать .litematic",
    "scene.objects": "Объекты сцены (клик — выбрать)",
    "scene.edit.offset": "Смещение",
    "scene.embed": "Вживить (air не затирает блоки модели)",
    "scene.reconfigure": "Перенастроить (рельеф)",
    "scene.delete": "Удалить объект",
    "scene.clear": "Очистить сцену",
    "scene.download": "Скачать сцену (.litematic)",
    "scene.empty.hint": "Сцена пуста — добавьте объекты из вкладок «Картинка» или «.vox»",
    "win.original": "Оригинал",
    "win.result": "Пикселизация",
    "win.blocks": "Блоки",
    "win.close": "Закрыть",
    "gen.progress": "Генерация…",
    "webgl.unavailable": "WebGL недоступен — 3D-вид не отображается",
    "scene.too_big": "Сцена слишком большая для превью",
    "scene.mode.embed": "вживление",
    "scene.mode.overwrite": "затирает",
    "scene.edit.title": "Объект {n}: {name}",
    "scene.stats": "Сцена: {n} объект(ов) · {w}×{h}×{d} · {b} типов блоков",
    "stats.blocks.count": "{k} типов блоков",
    "stats.orient.vertical": "вертикальная",
    "stats.orient.floor": "ковёр",
    "stats.mode.adaptive": "адаптивный (K={k})",
    "stats.mode.palette": "полная палитра",
    "stats.dither": " · дизеринг",
    "stats.relief": " · рельеф H={h}",
    "stats.vox": " · vox {w}×{h}×{d}",
    "reconfigure.hint": "Настройки загружены из сцены — измените их и нажмите «Сгенерировать», объект обновится",
    "err.no_image": "Сначала выберите изображение (вкладка «Картинка»).",
    "err.no_vox": "Сначала выберите файл .vox (вкладка «.vox»).",
    "err.missing_file": "Не передан файл",
    "err.invalid_params": "Некорректные параметры",
    "err.invalid_image": "Не удалось прочитать изображение",
    "err.image_too_large": "Изображение слишком большое",
    "err.volume_too_large": "Превышен лимит объёма",
    "err.invalid_vox": "Не удалось прочитать файл .vox",
    "err.internal": "Внутренняя ошибка сервера",
  },
  en: {
    "tab.image": "Image",
    "tab.vox": ".vox",
    "tab.scene": "Scene",
    "file.choose": "Choose an image…",
    "voxfile.choose": "Choose a MagicaVoxel .vox model…",
    "mode.label": "Block selection mode",
    "mode.adaptive": "Adaptive (k-means)",
    "mode.palette": "Full palette",
    "k.label": "Number of blocks K:",
    "orientation.label": "Orientation",
    "orientation.vertical": "Vertical picture",
    "orientation.floor": "Floor carpet",
    "target.label": "Max side (blocks)",
    "dither": "Dithering (Floyd–Steinberg)",
    "relief": "Relief (3D)",
    "maxheight.label": "Max depth/height:",
    "smoothing.label": "Smoothing:",
    "invert": "Invert brightness",
    "baseblock.label": "Base block",
    "gridlines": "Grid on preview (2D)",
    "generate": "Generate",
    "addtoscene": "Add to scene",
    "download": "Download .litematic",
    "scene.objects": "Scene objects (click to select)",
    "scene.edit.offset": "Offset",
    "scene.embed": "Embed (air doesn't erase model blocks)",
    "scene.reconfigure": "Reconfigure (relief)",
    "scene.delete": "Delete object",
    "scene.clear": "Clear scene",
    "scene.download": "Download scene (.litematic)",
    "scene.empty.hint": "Scene is empty — add objects from the Image or .vox tabs",
    "win.original": "Original",
    "win.result": "Pixelization",
    "win.blocks": "Blocks",
    "win.close": "Close",
    "gen.progress": "Generating…",
    "webgl.unavailable": "WebGL unavailable — 3D view is not displayed",
    "scene.too_big": "Scene too large for preview",
    "scene.mode.embed": "embed",
    "scene.mode.overwrite": "overwrites",
    "scene.edit.title": "Object {n}: {name}",
    "scene.stats": "Scene: {n} object(s) · {w}×{h}×{d} · {b} block types",
    "stats.blocks.count": "{k} block types",
    "stats.orient.vertical": "vertical",
    "stats.orient.floor": "carpet",
    "stats.mode.adaptive": "adaptive (K={k})",
    "stats.mode.palette": "full palette",
    "stats.dither": " · dithering",
    "stats.relief": " · relief H={h}",
    "stats.vox": " · vox {w}×{h}×{d}",
    "reconfigure.hint": "Settings loaded from the scene — adjust them and press Generate to update the object",
    "err.no_image": "Choose an image first (Image tab).",
    "err.no_vox": "Choose a .vox file first (.vox tab).",
    "err.missing_file": "No file provided",
    "err.invalid_params": "Invalid parameters",
    "err.invalid_image": "Could not read the image",
    "err.image_too_large": "Image too large",
    "err.volume_too_large": "Volume limit exceeded",
    "err.invalid_vox": "Could not read the .vox file",
    "err.internal": "Internal server error",
  },
};

const API_ERR = {
  missing_file: "err.missing_file",
  invalid_params: "err.invalid_params",
  invalid_image: "err.invalid_image",
  image_too_large: "err.image_too_large",
  volume_too_large: "err.volume_too_large",
  invalid_vox: "err.invalid_vox",
  internal: "err.internal",
};

let LANG = localStorage.getItem("lang");
if (!LANG) {
  LANG = (navigator.language || "").toLowerCase().startsWith("ru") ? "ru" : "en";
}

function t(key, vars) {
  let s = (I18N[LANG] && I18N[LANG][key]) ?? I18N.en[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replaceAll("{" + k + "}", v);
    }
  }
  return s;
}

function apiErrorText(j) {
  if (j && j.code && API_ERR[j.code]) return t(API_ERR[j.code]);
  if (j && j.error) return j.error;
  return `HTTP ${(j && j.status) || "?"}`;
}

function applyLanguage() {
  document.documentElement.lang = LANG;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.title = t(el.dataset.i18nTitle);
  });
  const sel = document.getElementById("lang");
  if (sel) sel.value = LANG;
  if (typeof refreshDynamicUi === "function") refreshDynamicUi();
}

function setLang(lang) {
  LANG = lang;
  localStorage.setItem("lang", lang);
  applyLanguage();
}
