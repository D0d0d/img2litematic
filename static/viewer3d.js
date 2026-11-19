"use strict";

/**
 * Интерактивный 3D-превью воксельной схемы (three.js, офлайн-вендор).
 *
 * r — ответ /api/convert (relief) или /api/vox: gridB64 (1 байт = блок,
 * порядок региона: index = (y·depth + z)·width + x), width/height/depth, palette.
 * Управление: левая кнопка/тач — вращение, колесо — зум, правая — контекст-меню.
 * Возвращает {dispose()} или null, если WebGL недоступен.
 */
function Viewer3D(container, r) {
  if (typeof THREE === "undefined") return null;

  const maxW = () => Math.min(760, window.innerWidth - 380);
  const maxH = () => Math.min(600, window.innerHeight - 190);

  let renderer;
  try {
    // preserveDrawingBuffer: кадр остаётся доступен для readPixels/скриншотов
    renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  } catch (e) {
    return null;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(maxW(), maxH());
  const canvas = renderer.domElement;
  canvas.style.cursor = "grab";
  container.appendChild(canvas);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1b1d21);
  scene.add(new THREE.AmbientLight(0xffffff, 0.65));
  const sun = new THREE.DirectionalLight(0xffffff, 1.0);
  sun.position.set(1.5, 2.5, 1.5);
  scene.add(sun);

  // Сетка блоков: bytes[(y·depth + z)·width + x], air пропускается
  const bytes = Uint8Array.from(atob(r.gridB64), (c) => c.charCodeAt(0));
  const airIdx = r.palette.findIndex((p) => p.name === "minecraft:air");
  const w = r.width, h = r.height, d = r.depth;
  const pos = [];
  const col = [];
  for (let y = 0; y < h; y++) {
    for (let z = 0; z < d; z++) {
      for (let x = 0; x < w; x++) {
        const p = bytes[(y * d + z) * w + x];
        if (airIdx >= 0 && p === airIdx) continue;
        pos.push(x - w / 2, y - h / 2, z - d / 2);
        const c = r.palette[p].color;
        col.push(c[0] / 255, c[1] / 255, c[2] / 255);
      }
    }
  }

  if (pos.length > 0) {
    const mesh = new THREE.InstancedMesh(
      new THREE.BoxGeometry(1, 1, 1),
      new THREE.MeshLambertMaterial(),
      pos.length / 3
    );
    const m4 = new THREE.Matrix4();
    const c3 = new THREE.Color();
    for (let i = 0; i < pos.length / 3; i++) {
      m4.setPosition(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]);
      mesh.setMatrixAt(i, m4);
      c3.setRGB(col[i * 3], col[i * 3 + 1], col[i * 3 + 2]);
      mesh.setColorAt(i, c3);
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    scene.add(mesh);
  }

  // Камера: сферические координаты вокруг центра модели
  const maxDim = Math.max(w, h, d, 1);
  const camera = new THREE.PerspectiveCamera(50, maxW() / maxH(), 0.1, maxDim * 50);
  let yaw = Math.PI / 4;
  let pitch = Math.PI / 6;
  let dist = maxDim * 1.7;

  function applyCamera() {
    camera.position.set(
      dist * Math.cos(pitch) * Math.sin(yaw),
      dist * Math.sin(pitch),
      dist * Math.cos(pitch) * Math.cos(yaw)
    );
    camera.lookAt(0, 0, 0);
  }
  applyCamera();

  let dragging = null;
  canvas.addEventListener("pointerdown", (e) => {
    canvas.setPointerCapture(e.pointerId);
    dragging = { x: e.clientX, y: e.clientY, yaw, pitch };
    canvas.style.cursor = "grabbing";
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    yaw = dragging.yaw + (e.clientX - dragging.x) * 0.008;
    pitch = Math.min(1.45, Math.max(0.05, dragging.pitch + (e.clientY - dragging.y) * 0.008));
    applyCamera();
  });
  canvas.addEventListener("pointerup", () => {
    dragging = null;
    canvas.style.cursor = "grab";
  });
  canvas.addEventListener("contextmenu", (e) => e.preventDefault());
  canvas.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      dist = Math.min(maxDim * 8, Math.max(4, dist * Math.exp(e.deltaY * 0.0012)));
      applyCamera();
    },
    { passive: false }
  );

  const onResize = () => {
    camera.aspect = maxW() / maxH();
    camera.updateProjectionMatrix();
    renderer.setSize(maxW(), maxH());
  };
  window.addEventListener("resize", onResize);

  let disposed = false;
  function animate() {
    if (disposed) return;
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
  }
  animate();

  return {
    dispose() {
      disposed = true;
      window.removeEventListener("resize", onResize);
      renderer.dispose();
      canvas.remove();
    },
  };
}
