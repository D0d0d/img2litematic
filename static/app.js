"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  file: null,
  fileUrl: null,
  voxFile: null,
  kind: "image",   // "image" | "vox" — что загружали последним
  result: null,    // ответ convert/vox
  scale: 1,
  viewer: null,    // интерактивный 3D-вьювер
  scene: [],       // объекты сцены (композиция)
};

const els = {
  file: $("file"),
  fileName: $("file-name"),
  voxfile: $("voxfile"),
  voxfileName: $("voxfile-name"),
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
  addtoscene: $("addtoscene"),
  clearscene: $("clearscene"),
  scenePanel: $("scene-panel"),
  sceneList: $("scene-list"),
  exportBtn: $("export"),
  stats: $("stats"),
  hover: $("hover"),
  error: $("error"),
  legend: $("legend"),
  original: $("original"),
  result: $("result"),
  viewer3d: $("viewer3d"),
  view3d: $("view3d"),
  view3dField: $("view3d-field"),
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
  if (state.kind === "vox") {
    fd.append("vox", state.voxFile);
    fd.append("params", JSON.stringify({ mode: params().mode, k: params().k }));
  } else {
    fd.append("image", state.file);
    fd.append("params", JSON.stringify(params()));
  }
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

function sceneObjects() {
  // Сцена (несколько объектов) или один свежий результат relief/vox
  if (state.scene.length > 0) return state.scene;
  const r = state.result;
  if (r && (r.relief || r.vox)) return [resultAsObject(r)];
  return null;
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
  };
}

function addToScene() {
  const r = state.result;
  if (!r || (!r.relief && !r.vox)) return;
  const o = resultAsObject(r);
  if (state.scene.length > 0) {
    // по умолчанию — рядом с существующими объектами по оси X
    const right = Math.max(...state.scene.map((s) => s.offset[0] + s.width));
    o.offset = [right + 1, 0, 0];
  }
  state.scene.push(o);
  renderScenePanel();
  renderLegend();
  renderResult();
}

function renderScenePanel() {
  els.scenePanel.hidden = state.scene.length === 0;
  els.sceneList.innerHTML = "";
  const axes = ["X", "Y", "Z"];
  state.scene.forEach((o, idx) => {
    const row = document.createElement("div");
    row.className = "scene-row";

    const name = document.createElement("span");
    name.className = "scene-name";
    name.textContent = o.name.length > 14 ? o.name.slice(0, 13) + "…" : o.name;
    row.appendChild(name);

    for (let a = 0; a < 3; a++) {
      const inp = document.createElement("input");
      inp.type = "number";
      inp.value = o.offset[a];
      inp.title = `Смещение по ${axes[a]}`;
      inp.addEventListener("change", () => {
        o.offset[a] = parseInt(inp.value, 10) || 0;
        renderResult();
      });
      row.appendChild(inp);
    }

    const lab = document.createElement("label");
    lab.className = "checkbox scene-overwrite";
    lab.title = "Вживление: air объекта не затирает блоки модели (иначе — затирает)";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !o.overwrite;
    cb.addEventListener("change", () => {
      o.overwrite = !cb.checked;
    });
    lab.append(cb, "вживить");
    row.appendChild(lab);

    const del = document.createElement("button");
    del.textContent = "✕";
    del.title = "Удалить из сцены";
    del.addEventListener("click", () => {
      state.scene.splice(idx, 1);
      renderScenePanel();
      renderLegend();
      renderResult();
    });
    row.appendChild(del);

    els.sceneList.appendChild(row);
  });
}

function renderResult() {
  const r = state.result;
  const c = els.result;

  // сброс старого 3D-вьювера
  if (state.viewer) {
    state.viewer.dispose();
    state.viewer = null;
  }
  els.viewer3d.replaceChildren();

  // 3D-вьювер: сцена целиком или один свежий результат relief/vox
  const objs = sceneObjects();
  if (objs && els.view3d.checked) {
    c.hidden = true;
    els.viewer3d.hidden = false;
    els.hover.textContent = "";
    state.viewer = Viewer3D(els.viewer3d, objs);
    if (state.viewer) return;
    if (state.scene.length > 0) {
      els.viewer3d.textContent = "WebGL недоступен — сцена не отображается";
      return;
    }
  }
  els.viewer3d.hidden = true;
  c.hidden = false;

  // масштаб отображения: целый множитель, без сглаживания
  const dispW = r.vox ? r.previewWidth : r.width;
  const dispH = r.vox ? r.previewHeight : r.height;
  const maxW = Math.min(760, window.innerWidth - 380);
  const maxH = Math.min(600, window.innerHeight - 190);
  const scale = Math.max(1, Math.floor(Math.min(maxW / dispW, maxH / dispH)));
  c.width = dispW * scale;
  c.height = dispH * scale;
  const ctx = c.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, c.width, c.height);
  state.scale = scale;

  const grid = r.vox ? null : r.relief ? r.surfaceGrid : r.grid;
  if (grid) {
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
  } else {
    c.onmousemove = null;
    els.hover.textContent = "";
  }

  if (r.relief || r.vox) {
    // превью — затенённая проекция от сервера
    const img = new Image();
    img.onload = () => {
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(img, 0, 0, c.width, c.height);
      if (!r.vox) drawGrid();
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
  if (state.scene.length > 0) {
    // агрегация палитр всех объектов сцены
    const byName = new Map();
    for (const o of state.scene) {
      for (const p of o.palette) {
        const e = byName.get(p.name) || { color: p.color, count: 0 };
        e.count += p.count;
        byName.set(p.name, e);
      }
    }
    const entries = [...byName.entries()].map(([name, e]) => ({ name, ...e }));
    entries.sort((a, b) => b.count - a.count);
    const total = entries.reduce((s, e) => s + e.count, 0);
    renderLegendItems(entries, total);
    els.stats.textContent = `Сцена: ${state.scene.length} объект(ов) · ${entries.length} типов блоков`;
    els.view3dField.hidden = false;
    els.exportBtn.disabled = false;
    return;
  }
  const r = state.result;
  const total = r.stats.totalBlocks;
  renderLegendItems(r.palette, total);
  const orient = r.vox ? "" : r.orientation === "vertical" ? "вертикальная · " : "ковёр · ";
  const mode = r.mode === "adaptive" ? `адаптивный (K=${r.kRequested})` : "полная палитра";
  const dith = r.dither ? " · дизеринг" : "";
  const rel = r.relief ? ` · рельеф H=${r.maxHeight}` : "";
  const vox = r.vox ? ` · vox ${r.width}×${r.height}×${r.depth}` : "";
  els.stats.textContent =
    `${r.width}×${r.height} · ${r.effectiveK} типов блоков · ${mode} · ${orient}${rel}${vox}${dith}`;
  els.view3dField.hidden = !(r.relief || r.vox);
  els.exportBtn.disabled = false;
}

async function generate() {
  if (state.kind === "vox" && !state.voxFile) {
    showError("Сначала выберите файл .vox.");
    return;
  }
  if (state.kind === "image" && !state.file) {
    showError("Сначала выберите изображение.");
    return;
  }
  clearError();
  els.generate.disabled = true;
  try {
    const url = state.kind === "vox" ? "/api/vox" : "/api/convert";
    const resp = await fetch(url, { method: "POST", body: formData() });
    const j = await resp.json();
    if (!resp.ok) throw new Error(j.error || `HTTP ${resp.status}`);
    state.result = j;
    els.addtoscene.disabled = !(j.relief || j.vox);
    renderResult();
    renderLegend();
  } catch (e) {
    showError(e.message || String(e));
  } finally {
    els.generate.disabled = false;
  }
}

async function exportScene() {
  clearError();
  els.exportBtn.disabled = true;
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
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "scene.litematic";
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    showError(e.message || String(e));
  } finally {
    els.exportBtn.disabled = false;
  }
}

async function exportFile() {
  if (!state.result) return;
  if (state.scene.length > 0) {
    await exportScene();
    return;
  }
  if (state.kind === "vox" && !state.voxFile) return;
  if (state.kind === "image" && !state.file) return;
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
    const srcName = state.kind === "vox" ? state.voxFile.name : state.file.name;
    a.download = (srcName.replace(/\.[^.]+$/, "") || "schematic") + ".litematic";
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
  if (!state.result) return;
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(generate, 300);
}

els.file.addEventListener("change", () => {
  const f = els.file.files[0];
  if (!f) return;
  state.kind = "image";
  state.file = f;
  els.fileName.textContent = f.name;
  if (state.fileUrl) URL.revokeObjectURL(state.fileUrl);
  state.fileUrl = URL.createObjectURL(f);
  drawOriginal();
  generate();
});

els.voxfile.addEventListener("change", () => {
  const f = els.voxfile.files[0];
  if (!f) return;
  state.kind = "vox";
  state.voxFile = f;
  els.voxfileName.textContent = f.name;
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
els.view3d.addEventListener("change", () => {
  if (state.result) renderResult();
});
els.addtoscene.addEventListener("click", addToScene);
els.clearscene.addEventListener("click", () => {
  state.scene = [];
  renderScenePanel();
  renderLegend();
  renderResult();
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
