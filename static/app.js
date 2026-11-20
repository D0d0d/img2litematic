"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  file: null,
  fileUrl: null,
  voxFile: null,
  kind: "image",      // "image" | "vox" — что загружали последним
  result: null,       // ответ convert/vox
  viewer: null,       // 3D-вьювер сцены
  scene: [],          // объекты сцены (композиция)
  selected: null,     // индекс выбранного объекта сцены
  activeTab: "image",
  winClosed: { original: false, result: false },
};

const els = {
  tabs: [...document.querySelectorAll(".tab")],
  contents: { image: $("tab-image"), vox: $("tab-vox"), scene: $("tab-scene") },
  workspace: $("workspace"),
  stage: $("stage"),
  winOriginal: $("win-original"),
  winResult: $("win-result"),
  workspaceHint: $("workspace-hint"),

  file: $("file"),
  fileName: $("file-name"),
  voxfile: $("voxfile"),
  voxfileName: $("voxfile-name"),

  mode: $("mode"),
  k: $("k"),
  kValue: $("k-value"),
  kField: $("k-field"),
  modeVox: $("mode-vox"),
  kVox: $("k-vox"),
  kValueVox: $("k-value-vox"),
  kFieldVox: $("k-field-vox"),

  target: $("target"),
  dither: $("dither"),
  relief: $("relief"),
  reliefFields: $("relief-fields"),
  maxheight: $("maxheight"),
  maxheightValue: $("maxheight-value"),
  smoothing: $("smoothing"),
  smoothingValue: $("smoothing-value"),
  invert: $("invert"),
  baseblock: $("baseblock"),
  gridlines: $("gridlines"),

  generate: $("generate"),
  addtoscene: $("addtoscene"),
  exportBtn: $("export"),
  generateVox: $("generate-vox"),
  addtosceneVox: $("addtoscene-vox"),
  exportVox: $("export-vox"),

  sceneList: $("scene-list"),
  sceneEdit: $("scene-edit"),
  sceneEditName: $("scene-edit-name"),
  selX: $("sel-x"),
  selY: $("sel-y"),
  selZ: $("sel-z"),
  selOverwrite: $("sel-overwrite"),
  sceneDelete: $("scene-delete"),
  clearscene: $("clearscene"),
  exportscene: $("exportscene"),

  stats: $("stats"),
  hover: $("hover"),
  error: $("error"),
  legend: $("legend"),
  original: $("original"),
  result: $("result"),
  winBlocks: $("win-blocks"),
};

// ---------- Вкладки ----------

function switchTab(name) {
  state.activeTab = name;
  for (const t of els.tabs) t.classList.toggle("active", t.dataset.tab === name);
  for (const [k, el] of Object.entries(els.contents)) el.hidden = k !== name;
  resetWindows();
  renderWorkspace();
  renderLegend();
}

els.tabs.forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));

// ---------- Параметры и данные ----------

function params() {
  return {
    mode: els.mode.value,
    k: parseInt(els.k.value, 10),
    orientation: document.querySelector('input[name="orientation"]:checked').value,
    target: parseInt(els.target.value, 10),
    dither: els.dither.checked,
    relief: els.relief.checked,
    max_height: parseInt(els.maxheight.value, 10),
    smoothing: parseFloat(els.smoothing.value),
    invert: els.invert.checked,
    base_block: els.baseblock.value,
  };
}

function voxParams() {
  return { mode: els.modeVox.value, k: parseInt(els.kVox.value, 10) };
}

function imageFormData() {
  const fd = new FormData();
  fd.append("image", state.file);
  fd.append("params", JSON.stringify(params()));
  return fd;
}

function voxFormData() {
  const fd = new FormData();
  fd.append("vox", state.voxFile);
  fd.append("params", JSON.stringify(voxParams()));
  return fd;
}

function shortName(name) {
  return name.startsWith("minecraft:") ? name.slice("minecraft:".length) : name;
}

function showError(msg) {
  els.error.textContent = msg;
  els.error.hidden = false;
}

function clearError() {
  els.error.hidden = true;
}

// ---------- Окна рабочей области ----------

function resetWindows() {
  state.winClosed = { original: false, result: false };
  for (const w of [els.winOriginal, els.winResult]) {
    delete w.dataset.placed;
  }
}

function placeWin(win, x, y) {
  if (win.dataset.placed) return; // пользователь уже двигал/окно стоит на месте
  const ws = els.workspace.getBoundingClientRect();
  const r = win.getBoundingClientRect();
  win.style.left = Math.min(Math.max(0, x), Math.max(0, ws.width - r.width - 8)) + "px";
  win.style.top = Math.min(Math.max(0, y), Math.max(0, ws.height - r.height - 8)) + "px";
  win.dataset.placed = "1";
}

function setupWindowDrag(win, onHeaderClick) {
  const header = win.querySelector(".win-header");
  let moved = false;
  header.addEventListener("pointerdown", (e) => {
    if (e.target.classList.contains("win-close")) return;
    moved = false;
    try {
      header.setPointerCapture(e.pointerId);
    } catch (err) {
      /* синтетические события/старые браузеры — продолжаем без захвата */
    }
    const rect = win.getBoundingClientRect();
    const wsRect = els.workspace.getBoundingClientRect();
    const offX = e.clientX - rect.left;
    const offY = e.clientY - rect.top;
    const move = (ev) => {
      moved = true;
      const x = Math.min(Math.max(0, ev.clientX - wsRect.left - offX), wsRect.width - rect.width);
      const y = Math.min(Math.max(0, ev.clientY - wsRect.top - offY), wsRect.height - 44);
      win.style.right = "";
      win.style.bottom = "";
      win.style.left = x + "px";
      win.style.top = y + "px";
      win.dataset.placed = "1";
    };
    const up = () => {
      header.removeEventListener("pointermove", move);
      header.removeEventListener("pointerup", up);
    };
    header.addEventListener("pointermove", move);
    header.addEventListener("pointerup", up);
  });
  if (onHeaderClick) {
    header.addEventListener("click", (e) => {
      if (e.target.classList.contains("win-close")) return;
      if (moved) return; // это был драг, не клик
      onHeaderClick();
    });
  }
}

setupWindowDrag(els.winOriginal);
setupWindowDrag(els.winResult);
setupWindowDrag(els.winBlocks, () => els.winBlocks.classList.toggle("collapsed"));

for (const w of [els.winOriginal, els.winResult]) {
  w.querySelector(".win-close").addEventListener("click", () => {
    const isOriginal = w.id === "win-original";
    state.winClosed[isOriginal ? "original" : "result"] = true;
    w.hidden = true;
  });
}

function drawOriginalInto(canvas, url) {
  const img = new Image();
  img.onload = () => {
    const scale = Math.min(1, 380 / img.width, 300 / img.height);
    canvas.width = Math.max(1, Math.round(img.width * scale));
    canvas.height = Math.max(1, Math.round(img.height * scale));
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  };
  img.src = url;
}

function drawResultInto(canvas, data) {
  // data: {width, height, preview?, previewW?, previewH?, grid?, surfaceGrid?, palette?, isVox}
  canvas.onmousemove = null;
  els.hover.textContent = "";
  const dispW = data.previewW || data.width;
  const dispH = data.previewH || data.height;
  const scale = Math.max(1, Math.floor(Math.min(400 / dispW, 320 / dispH)));
  canvas.width = dispW * scale;
  canvas.height = dispH * scale;
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const grid = data.vox ? null : data.surfaceGrid || data.grid || null;
  if (grid && data.palette) {
    canvas.onmousemove = (e) => {
      const rect = canvas.getBoundingClientRect();
      const x = Math.floor((e.clientX - rect.left) / (rect.width / data.width));
      const y = Math.floor((e.clientY - rect.top) / (rect.height / data.height));
      if (x < 0 || y < 0 || x >= data.width || y >= data.height) {
        els.hover.textContent = "";
        return;
      }
      const b = data.palette[grid[y * data.width + x]];
      els.hover.textContent = `${x}, ${y} → ${shortName(b.name)}`;
    };
  }

  const drawGridOver = () => {
    if (!data.gridlines || scale < 4) return;
    ctx.strokeStyle = "rgba(0,0,0,0.35)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = 0; x <= data.width; x++) {
      ctx.moveTo(x * scale + 0.5, 0);
      ctx.lineTo(x * scale + 0.5, data.height * scale);
    }
    for (let y = 0; y <= data.height; y++) {
      ctx.moveTo(0, y * scale + 0.5);
      ctx.lineTo(data.width * scale, y * scale + 0.5);
    }
    ctx.stroke();
  };

  if (data.preview) {
    const img = new Image();
    img.onload = () => {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      drawGridOver();
    };
    img.src = "data:image/png;base64," + data.preview;
  } else {
    const off = document.createElement("canvas");
    off.width = data.width;
    off.height = data.height;
    const octx = off.getContext("2d");
    const imgData = octx.createImageData(data.width, data.height);
    const px = imgData.data;
    for (let i = 0; i < grid.length; i++) {
      const col = data.palette[grid[i]].color;
      px[i * 4] = col[0];
      px[i * 4 + 1] = col[1];
      px[i * 4 + 2] = col[2];
      px[i * 4 + 3] = 255;
    }
    octx.putImageData(imgData, 0, 0);
    ctx.drawImage(off, 0, 0, canvas.width, canvas.height);
    drawGridOver();
  }
}

function currentResultData() {
  if (state.activeTab === "scene") {
    // В режиме сцены окно показывает только выбранный объект —
    // без выбора ничего не показываем (не «висит» старый результат)
    if (state.scene.length === 0 || state.selected === null) return null;
    const o = state.scene[state.selected];
    return {
      width: o.width,
      height: o.height,
      preview: o.preview,
      previewW: o.previewW,
      previewH: o.previewH,
      surfaceGrid: o.surfaceGrid,
      palette: o.palette,
      isVox: o.isVox,
      gridlines: els.gridlines.checked && !o.isVox,
    };
  }
  const r = state.result;
  if (!r) return null;
  if (r.vox) {
    return {
      width: r.width, height: r.height,
      preview: r.preview, previewW: r.previewWidth, previewH: r.previewHeight,
      isVox: true, gridlines: false,
    };
  }
  if (r.relief) {
    return {
      width: r.width, height: r.height,
      preview: r.preview, previewW: r.width, previewH: r.height,
      surfaceGrid: r.surfaceGrid, palette: r.palette,
      isVox: false, gridlines: els.gridlines.checked,
    };
  }
  return { ...r, isVox: false, gridlines: els.gridlines.checked };
}

function currentOriginalUrl() {
  if (state.activeTab === "scene") {
    // как и для пикселизации: только выбранный объект, иначе ничего
    if (state.scene.length === 0 || state.selected === null) return null;
    return state.scene[state.selected].originalUrl || null;
  }
  if (state.activeTab === "image") return state.fileUrl;
  return null;
}

// ---------- Рабочая область: сцена + окна ----------

function renderStage(objs) {
  if (state.viewer) {
    state.viewer.dispose();
    state.viewer = null;
  }
  els.stage.replaceChildren();
  if (!objs) {
    els.stage.hidden = true;
    return;
  }
  els.stage.hidden = false;
  state.viewer = Viewer3D(els.stage, objs);
  if (!state.viewer) {
    els.stage.textContent = "WebGL недоступен — 3D-вид не отображается";
  }
}

function renderWorkspace() {
  // Сцена на всё пространство зависит от вкладки:
  // «Сцена» — объединённая композиция, «Картинка»/«.vox» — свежий 3D-результат
  let objs = null;
  if (state.activeTab === "scene") {
    if (state.scene.length > 0) {
      const m = mergedScene();
      if (m && !m.error) objs = [m];
    }
  } else if (state.result && (state.result.relief || state.result.vox)) {
    objs = [resultAsObject(state.result)];
  }
  renderStage(objs);

  // Окно «Пикселизация»
  const resultData = currentResultData();
  const showResult = resultData && !state.winClosed.result;
  els.winResult.hidden = !showResult;
  if (showResult) {
    drawResultInto(els.result, resultData);
    placeWin(els.winResult, 16, 16);
  }

  // Окно «Оригинал»
  const origUrl = currentOriginalUrl();
  const showOriginal = origUrl && !state.winClosed.original;
  els.winOriginal.hidden = !showOriginal;
  if (showOriginal) {
    drawOriginalInto(els.original, origUrl);
    const x = 16;
    const y = els.winResult.hidden ? 16 : els.winResult.getBoundingClientRect().bottom -
      els.workspace.getBoundingClientRect().top + 8;
    placeWin(els.winOriginal, x, y);
  }

  // Подсказка — только на пустой вкладке «Сцена» (когда стадия пуста)
  els.workspaceHint.hidden = !(
    state.activeTab === "scene" &&
    state.scene.length === 0 &&
    objs === null
  );
}

// ---------- Сцена ----------

let mergedCache = null;

function invalidateMerged() {
  mergedCache = null;
}

function decodeGrid(o) {
  if (!o._bytes) {
    o._bytes = Uint8Array.from(atob(o.gridB64), (c) => c.charCodeAt(0));
  }
  return o._bytes;
}

function buildMerged() {
  if (state.scene.length === 0) return null;
  const minx = Math.min(...state.scene.map((o) => o.offset[0]));
  const miny = Math.min(...state.scene.map((o) => o.offset[1]));
  const minz = Math.min(...state.scene.map((o) => o.offset[2]));
  const maxx = Math.max(...state.scene.map((o) => o.offset[0] + o.width));
  const maxy = Math.max(...state.scene.map((o) => o.offset[1] + o.height));
  const maxz = Math.max(...state.scene.map((o) => o.offset[2] + o.depth));
  const sx = maxx - minx;
  const sy = maxy - miny;
  const sz = maxz - minz;
  const volume = sx * sy * sz;
  if (volume > 16_000_000) return { error: "Сцена слишком большая для превью" };

  const palette = [{ name: "minecraft:air", color: [205, 213, 219] }];
  const byName = new Map([["minecraft:air", 0]]);
  for (const o of state.scene) {
    for (const p of o.palette) {
      if (!byName.has(p.name)) {
        byName.set(p.name, palette.length);
        palette.push({ name: p.name, color: p.color });
      }
    }
  }

  const merged = new Uint8Array(volume).fill(0);
  for (const o of state.scene) {
    const bytes = decodeGrid(o);
    const objAir = o.palette.findIndex((p) => p.name === "minecraft:air");
    const map = o.palette.map((p) => byName.get(p.name));
    for (let y = 0; y < o.height; y++) {
      for (let z = 0; z < o.depth; z++) {
        for (let x = 0; x < o.width; x++) {
          const v = bytes[(y * o.depth + z) * o.width + x];
          if (!o.overwrite && objAir >= 0 && v === objAir) continue; // вживление
          const gx = x + o.offset[0] - minx;
          const gy = y + o.offset[1] - miny;
          const gz = z + o.offset[2] - minz;
          merged[(gy * sz + gz) * sx + gx] = map[v];
        }
      }
    }
  }
  return { gridBytes: merged, palette, width: sx, height: sy, depth: sz };
}

function mergedScene() {
  if (mergedCache === null) mergedCache = buildMerged();
  return mergedCache;
}

function resultAsObject(r) {
  let sx, sy, sz;
  if (r.vox) {
    sx = r.width; sy = r.height; sz = r.depth;
  } else if (r.orientation === "vertical") {
    sx = r.width; sy = r.height; sz = r.maxHeight;
  } else {
    sx = r.width; sy = r.maxHeight; sz = r.height;
  }
  const srcName = state.kind === "vox" ? state.voxFile.name : state.file.name;
  return {
    name: srcName,
    gridB64: r.gridB64,
    palette: r.palette,
    width: sx,
    height: sy,
    depth: sz,
    offset: [0, 0, 0],
    overwrite: false,
    preview: r.preview || null,
    previewW: r.vox ? r.previewWidth : r.width,
    previewH: r.vox ? r.previewHeight : r.height,
    surfaceGrid: r.surfaceGrid || null,
    originalUrl: state.kind === "image" ? state.fileUrl : null,
    isVox: !!r.vox,
  };
}

function addToScene() {
  const r = state.result;
  if (!r || (!r.relief && !r.vox)) return;
  const o = resultAsObject(r);
  if (state.scene.length > 0) {
    const right = Math.max(...state.scene.map((s) => s.offset[0] + s.width));
    o.offset = [right + 1, 0, 0];
  }
  state.scene.push(o);
  state.selected = state.scene.length - 1;
  invalidateMerged();
  renderSceneUI();
  renderWorkspace();
  renderLegend();
  switchTab("scene");
}

function selectedObject() {
  return state.selected !== null ? state.scene[state.selected] : null;
}

function renderSceneUI() {
  const has = state.scene.length > 0;
  els.sceneList.innerHTML = "";
  els.sceneEdit.hidden = !has || state.selected === null;
  els.clearscene.disabled = !has;
  els.exportscene.disabled = !has;

  state.scene.forEach((o, idx) => {
    const row = document.createElement("div");
    row.className = "scene-row" + (idx === state.selected ? " selected" : "");
    const name = document.createElement("span");
    name.className = "scene-name";
    name.textContent = `${idx + 1}. ${o.name}`;
    name.title = o.name;
    const dims = document.createElement("span");
    dims.className = "scene-dims";
    dims.textContent = `${o.width}×${o.height}×${o.depth}`;
    const mode_ = document.createElement("span");
    mode_.className = "scene-mode";
    mode_.textContent = o.overwrite ? "затирает" : "вживление";
    row.append(name, dims, mode_);
    row.addEventListener("click", () => {
      state.selected = idx;
      resetWindows();
      renderSceneUI();
      renderWorkspace();
    });
    els.sceneList.appendChild(row);
  });

  const o = selectedObject();
  if (o) {
    els.sceneEditName.textContent = `Объект ${state.selected + 1}: ${o.name}`;
    els.selX.value = o.offset[0];
    els.selY.value = o.offset[1];
    els.selZ.value = o.offset[2];
    els.selOverwrite.checked = !o.overwrite;
  }
}

// ---------- Легенда и статистика ----------

function renderLegendItems(entries, total) {
  els.legend.innerHTML = "";
  for (const b of entries) {
    const li = document.createElement("li");
    const sw = document.createElement("span");
    sw.className = "swatch";
    sw.style.background = `rgb(${b.color.join(",")})`;
    const name = document.createElement("span");
    name.className = "bname";
    name.textContent = shortName(b.name);
    const cnt = document.createElement("span");
    cnt.className = "bcount";
    cnt.textContent = `${b.count} (${(100 * b.count / total).toFixed(1)}%)`;
    li.append(sw, name, cnt);
    els.legend.appendChild(li);
  }
}

function renderLegend() {
  if (state.activeTab === "scene" && state.scene.length > 0) {
    const m = mergedScene();
    if (m && !m.error) {
      const counts = new Array(m.palette.length).fill(0);
      for (let i = 0; i < m.gridBytes.length; i++) counts[m.gridBytes[i]]++;
      const entries = m.palette
        .map((p, i) => ({ ...p, count: counts[i] }))
        .filter((e) => e.count > 0)
        .sort((a, b) => b.count - a.count);
      const total = entries.reduce((s, e) => s + e.count, 0);
      renderLegendItems(entries, total);
      els.stats.textContent =
        `Сцена: ${state.scene.length} объект(ов) · ${m.width}×${m.height}×${m.depth} · ` +
        `${entries.length} типов блоков`;
    } else {
      els.legend.innerHTML = "";
      els.stats.textContent = `Сцена: ${state.scene.length} объект(ов)`;
    }
    els.exportscene.disabled = false;
    return;
  }
  const r = state.result;
  if (!r) {
    els.legend.innerHTML = "";
    els.stats.textContent = "";
    return;
  }
  const total = r.stats.totalBlocks;
  renderLegendItems(r.palette, total);
  const orient = r.vox ? "" : r.orientation === "vertical" ? "вертикальная · " : "ковёр · ";
  const mode = r.mode === "adaptive" ? `адаптивный (K=${r.kRequested})` : "полная палитра";
  const dith = r.dither ? " · дизеринг" : "";
  const rel = r.relief ? ` · рельеф H=${r.maxHeight}` : "";
  const vox = r.vox ? ` · vox ${r.width}×${r.height}×${r.depth}` : "";
  els.stats.textContent =
    `${r.width}×${r.height} · ${r.effectiveK} типов блоков · ${mode} · ${orient}${rel}${vox}${dith}`;
}

// ---------- Генерация ----------

function clearResult() {
  state.result = null;
  if (state.viewer) {
    state.viewer.dispose();
    state.viewer = null;
  }
  els.stage.replaceChildren();
  els.stage.hidden = true;
  els.winOriginal.hidden = true;
  els.winResult.hidden = true;
  els.legend.innerHTML = "";
  els.stats.textContent = "";
  els.hover.textContent = "";
  els.addtoscene.disabled = true;
  els.addtosceneVox.disabled = true;
  els.exportBtn.disabled = true;
  els.exportVox.disabled = true;
  els.workspaceHint.hidden = true;
}

async function generateImage() {
  if (!state.file) {
    showError("Сначала выберите изображение (вкладка «Картинка»).");
    return;
  }
  clearError();
  els.generate.disabled = true;
  els.stats.textContent = "Генерация…";
  try {
    const resp = await fetch("/api/convert", { method: "POST", body: imageFormData() });
    const j = await resp.json();
    if (!resp.ok) throw new Error(j.error || `HTTP ${resp.status}`);
    state.result = j;
    els.addtoscene.disabled = !(j.relief || j.vox);
    els.exportBtn.disabled = false;
    resetWindows();
    renderWorkspace();
    renderLegend();
  } catch (e) {
    showError(e.message || String(e));
  } finally {
    els.generate.disabled = false;
  }
}

async function generateVox() {
  if (!state.voxFile) {
    showError("Сначала выберите файл .vox (вкладка «.vox»).");
    return;
  }
  clearError();
  els.generateVox.disabled = true;
  els.stats.textContent = "Генерация…";
  try {
    const resp = await fetch("/api/vox", { method: "POST", body: voxFormData() });
    const j = await resp.json();
    if (!resp.ok) throw new Error(j.error || `HTTP ${resp.status}`);
    state.result = j;
    els.addtosceneVox.disabled = false;
    els.exportVox.disabled = false;
    resetWindows();
    renderWorkspace();
    renderLegend();
  } catch (e) {
    showError(e.message || String(e));
  } finally {
    els.generateVox.disabled = false;
  }
}

// ---------- Экспорт ----------

async function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

async function exportFile() {
  if (!state.result) return;
  clearError();
  if (state.kind === "vox") {
    els.exportVox.disabled = true;
    try {
      const resp = await fetch("/api/export", { method: "POST", body: voxFormData() });
      if (!resp.ok) {
        const j = await resp.json().catch(() => ({}));
        throw new Error(j.error || `HTTP ${resp.status}`);
      }
      await downloadBlob(
        await resp.blob(),
        (state.voxFile.name.replace(/\.[^.]+$/, "") || "model") + ".litematic"
      );
    } catch (e) {
      showError(e.message || String(e));
    } finally {
      els.exportVox.disabled = false;
    }
  } else {
    els.exportBtn.disabled = true;
    try {
      const resp = await fetch("/api/export", { method: "POST", body: imageFormData() });
      if (!resp.ok) {
        const j = await resp.json().catch(() => ({}));
        throw new Error(j.error || `HTTP ${resp.status}`);
      }
      await downloadBlob(
        await resp.blob(),
        (state.file.name.replace(/\.[^.]+$/, "") || "schematic") + ".litematic"
      );
    } catch (e) {
      showError(e.message || String(e));
    } finally {
      els.exportBtn.disabled = false;
    }
  }
}

async function exportScene() {
  if (state.scene.length === 0) return;
  clearError();
  els.exportscene.disabled = true;
  try {
    const body = {
      objects: state.scene.map((o) => ({
        gridB64: o.gridB64,
        width: o.width,
        height: o.height,
        depth: o.depth,
        offset: o.offset,
        palette: o.palette.map((p) => p.name),
        overwrite: o.overwrite,
      })),
    };
    const resp = await fetch("/api/compose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const j = await resp.json().catch(() => ({}));
      throw new Error(j.error || `HTTP ${resp.status}`);
    }
    await downloadBlob(await resp.blob(), "scene.litematic");
  } catch (e) {
    showError(e.message || String(e));
  } finally {
    els.exportscene.disabled = false;
  }
}

// ---------- Слушатели ----------

let debounceTimer = null;
function autoGenerate() {
  if (state.kind === "vox" && state.voxFile) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(generateVox, 300);
  } else if (state.kind === "image" && state.file) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(generateImage, 300);
  }
}

els.file.addEventListener("change", () => {
  const f = els.file.files[0];
  if (!f) return;
  state.kind = "image";
  state.file = f;
  els.fileName.textContent = f.name;
  if (state.fileUrl) URL.revokeObjectURL(state.fileUrl);
  state.fileUrl = URL.createObjectURL(f);
  clearResult();
  resetWindows();
  generateImage();
});

els.voxfile.addEventListener("change", () => {
  const f = els.voxfile.files[0];
  if (!f) return;
  state.kind = "vox";
  state.voxFile = f;
  els.voxfileName.textContent = f.name;
  clearResult();
  resetWindows();
  generateVox();
});

els.mode.addEventListener("change", () => {
  updateKField();
  autoGenerate();
});
els.k.addEventListener("input", () => {
  els.kValue.textContent = els.k.value;
  autoGenerate();
});
els.target.addEventListener("change", autoGenerate);
els.dither.addEventListener("change", autoGenerate);
els.relief.addEventListener("change", () => {
  els.reliefFields.hidden = !els.relief.checked;
  autoGenerate();
});
els.maxheight.addEventListener("input", () => {
  els.maxheightValue.textContent = els.maxheight.value;
  autoGenerate();
});
els.smoothing.addEventListener("input", () => {
  els.smoothingValue.textContent = els.smoothing.value;
  autoGenerate();
});
els.invert.addEventListener("change", autoGenerate);
els.baseblock.addEventListener("change", autoGenerate);
for (const radio of document.querySelectorAll('input[name="orientation"]')) {
  radio.addEventListener("change", autoGenerate);
}

els.modeVox.addEventListener("change", () => {
  updateKField();
  autoGenerate();
});
els.kVox.addEventListener("input", () => {
  els.kValueVox.textContent = els.kVox.value;
  autoGenerate();
});

els.gridlines.addEventListener("change", () => {
  renderWorkspace();
});

els.generate.addEventListener("click", generateImage);
els.generateVox.addEventListener("click", generateVox);
els.addtoscene.addEventListener("click", addToScene);
els.addtosceneVox.addEventListener("click", addToScene);
els.exportBtn.addEventListener("click", exportFile);
els.exportVox.addEventListener("click", exportFile);
els.exportscene.addEventListener("click", exportScene);

for (const [el, axis] of [[els.selX, 0], [els.selY, 1], [els.selZ, 2]]) {
  el.addEventListener("change", () => {
    const o = selectedObject();
    if (!o) return;
    o.offset[axis] = parseInt(el.value, 10) || 0;
    invalidateMerged();
    renderSceneUI();
    renderWorkspace();
    renderLegend();
  });
}
els.selOverwrite.addEventListener("change", () => {
  const o = selectedObject();
  if (!o) return;
  o.overwrite = !els.selOverwrite.checked;
  invalidateMerged();
  renderSceneUI();
  renderWorkspace();
  renderLegend();
});
els.sceneDelete.addEventListener("click", () => {
  if (state.selected === null) return;
  state.scene.splice(state.selected, 1);
  state.selected = state.scene.length ? Math.min(state.selected, state.scene.length - 1) : null;
  invalidateMerged();
  renderSceneUI();
  renderWorkspace();
  renderLegend();
});
els.clearscene.addEventListener("click", () => {
  state.scene = [];
  state.selected = null;
  invalidateMerged();
  renderSceneUI();
  renderWorkspace();
  renderLegend();
});

function updateKField() {
  const adaptive = els.mode.value === "adaptive";
  els.kField.style.opacity = adaptive ? 1 : 0.4;
  els.k.disabled = !adaptive;
  const adaptiveVox = els.modeVox.value === "adaptive";
  els.kFieldVox.style.opacity = adaptiveVox ? 1 : 0.4;
  els.kVox.disabled = !adaptiveVox;
}

async function initBaseBlocks() {
  try {
    const resp = await fetch("/api/blocks");
    const j = await resp.json();
    for (const b of j.blocks) {
      const opt = document.createElement("option");
      opt.value = b.name;
      opt.textContent = shortName(b.name);
      els.baseblock.appendChild(opt);
    }
    els.baseblock.value = "minecraft:stone";
  } catch (e) {
    /* некритично */
  }
}

updateKField();
initBaseBlocks();
