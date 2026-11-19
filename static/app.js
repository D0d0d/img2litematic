"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  file: null,
  fileUrl: null,
  result: null,   // ответ /api/convert
  scale: 1,
};

const els = {
  file: $("file"),
  fileName: $("file-name"),
  mode: $("mode"),
  k: $("k"),
  kValue: $("k-value"),
  kField: $("k-field"),
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
  exportBtn: $("export"),
  stats: $("stats"),
  hover: $("hover"),
  error: $("error"),
  legend: $("legend"),
  original: $("original"),
  result: $("result"),
};

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

function showError(msg) {
  els.error.textContent = msg;
  els.error.hidden = false;
}

function clearError() {
  els.error.hidden = true;
}

function formData() {
  const fd = new FormData();
  fd.append("image", state.file);
  fd.append("params", JSON.stringify(params()));
  return fd;
}

function shortName(name) {
  return name.startsWith("minecraft:") ? name.slice("minecraft:".length) : name;
}

function drawOriginal() {
  const img = new Image();
  img.onload = () => {
    const c = els.original;
    const scale = Math.min(1, 360 / img.width, 220 / img.height);
    c.width = Math.max(1, Math.round(img.width * scale));
    c.height = Math.max(1, Math.round(img.height * scale));
    const ctx = c.getContext("2d");
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(img, 0, 0, c.width, c.height);
  };
  img.src = state.fileUrl;
}

function drawGrid() {
  const c = els.result;
  const r = state.result;
  const s = state.scale;
  if (s < 4) return;
  const ctx = c.getContext("2d");
  ctx.strokeStyle = "rgba(0,0,0,0.35)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let x = 0; x <= r.width; x++) {
    ctx.moveTo(x * s + 0.5, 0);
    ctx.lineTo(x * s + 0.5, r.height * s);
  }
  for (let y = 0; y <= r.height; y++) {
    ctx.moveTo(0, y * s + 0.5);
    ctx.lineTo(r.width * s, y * s + 0.5);
  }
  ctx.stroke();
}

function renderResult() {
  const r = state.result;
  const c = els.result;

  // масштаб отображения: целый множитель, без сглаживания
  const maxW = Math.min(760, window.innerWidth - 380);
  const maxH = Math.min(600, window.innerHeight - 190);
  const scale = Math.max(1, Math.floor(Math.min(maxW / r.width, maxH / r.height)));
  c.width = r.width * scale;
  c.height = r.height * scale;
  const ctx = c.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, c.width, c.height);
  state.scale = scale;

  const grid = r.relief ? r.surfaceGrid : r.grid;
  c.onmousemove = (e) => {
    const rect = c.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / (rect.width / r.width));
    const y = Math.floor((e.clientY - rect.top) / (rect.height / r.height));
    if (x < 0 || y < 0 || x >= r.width || y >= r.height) {
      els.hover.textContent = "";
      return;
    }
    const b = r.palette[grid[y * r.width + x]];
    els.hover.textContent = `${x}, ${y} → ${shortName(b.name)}`;
  };

  if (r.relief) {
    // превью рельефа — затенённая проекция от сервера
    const img = new Image();
    img.onload = () => {
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(img, 0, 0, c.width, c.height);
      drawGrid();
    };
    img.src = "data:image/png;base64," + r.preview;
  } else {
    // offscreen-канвас: 1 пиксель = 1 блок
    const off = document.createElement("canvas");
    off.width = r.width;
    off.height = r.height;
    const octx = off.getContext("2d");
    const imgData = octx.createImageData(r.width, r.height);
    const data = imgData.data;
    for (let i = 0; i < r.grid.length; i++) {
      const col = r.palette[r.grid[i]].color;
      data[i * 4] = col[0];
      data[i * 4 + 1] = col[1];
      data[i * 4 + 2] = col[2];
      data[i * 4 + 3] = 255;
    }
    octx.putImageData(imgData, 0, 0);
    ctx.drawImage(off, 0, 0, c.width, c.height);
    drawGrid();
  }
}

function renderLegend() {
  const r = state.result;
  const total = r.stats.totalBlocks;
  els.legend.innerHTML = "";
  for (const b of r.palette) {
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
  const orient = r.orientation === "vertical" ? "вертикальная" : "ковёр";
  const mode = r.mode === "adaptive" ? `адаптивный (K=${r.kRequested})` : "полная палитра";
  const dith = r.dither ? " · дизеринг" : "";
  const rel = r.relief ? ` · рельеф H=${r.maxHeight}` : "";
  els.stats.textContent =
    `${r.width}×${r.height} · ${r.effectiveK} типов блоков · ${mode} · ${orient}${rel}${dith}`;
  els.exportBtn.disabled = false;
}

async function generate() {
  if (!state.file) {
    showError("Сначала выберите изображение.");
    return;
  }
  clearError();
  els.generate.disabled = true;
  try {
    const resp = await fetch("/api/convert", { method: "POST", body: formData() });
    const j = await resp.json();
    if (!resp.ok) throw new Error(j.error || `HTTP ${resp.status}`);
    state.result = j;
    renderResult();
    renderLegend();
  } catch (e) {
    showError(e.message || String(e));
  } finally {
    els.generate.disabled = false;
  }
}

async function exportFile() {
  if (!state.file || !state.result) return;
  clearError();
  els.exportBtn.disabled = true;
  try {
    const resp = await fetch("/api/export", { method: "POST", body: formData() });
    if (!resp.ok) {
      const j = await resp.json().catch(() => ({}));
      throw new Error(j.error || `HTTP ${resp.status}`);
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = (state.file.name.replace(/\.[^.]+$/, "") || "schematic") + ".litematic";
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    showError(e.message || String(e));
  } finally {
    els.exportBtn.disabled = false;
  }
}

function updateKField() {
  const adaptive = els.mode.value === "adaptive";
  els.kField.style.opacity = adaptive ? 1 : 0.4;
  els.k.disabled = !adaptive;
}

let debounceTimer = null;
function autoGenerate() {
  if (!state.file) return;
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(generate, 300);
}

els.file.addEventListener("change", () => {
  const f = els.file.files[0];
  if (!f) return;
  state.file = f;
  els.fileName.textContent = f.name;
  if (state.fileUrl) URL.revokeObjectURL(state.fileUrl);
  state.fileUrl = URL.createObjectURL(f);
  drawOriginal();
  generate();
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
els.gridlines.addEventListener("change", () => {
  if (state.result) renderResult();
});
els.generate.addEventListener("click", generate);
els.exportBtn.addEventListener("click", exportFile);

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
    /* некритично: при пустом списке параметр проигнорируется */
  }
}

updateKField();
initBaseBlocks();
