"""Импорт моделей MagicaVoxel (.vox) → блоки Minecraft.

Формат .vox: RIFF-подобный — "VOX " + version(i32) + чанки
(id 4 байта + content_n i32 + children_n i32 + content + children).
Читаются первые SIZE/XYZI/RGBA (первая модель файла); сцена (nTRN/nGRP/nSHP)
игнорируется.

Координаты: в MagicaVoxel ось z — «вверх», поэтому
vox(x, y, z) → mc(x, y'=z, z'=y).

Палитра .vox (255 цветов RGBA) → блоки Minecraft через Lab-метрику
(nearest по всей палитре или constrained k-means ≤ K); пустые воксели
и прозрачные цвета (a < 128) → air.
"""

import io
import struct
from dataclasses import dataclass

import numpy as np
from PIL import Image

import config
from colorutil import nearest_argmin, rgb_array_to_lab
from palette import AIR_CODE, AIR_NAME, PALETTE, block_rgb, palette_lab_array
from quantize import _adaptive_mapping

_BG = (26, 28, 32)  # фон превью — как тёмная тема UI


class VoxError(Exception):
    """Ошибка чтения .vox; code — машиночитаемый код для API."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class VoxResult:
    grid: list[int]              # блоки региона (x→z→y), индексы в `palette`
    palette: list[int]           # индексы PALETTE или AIR_CODE, по убыванию count
    counts: list[int]            # счётчики по позициям выходной палитры
    size: tuple[int, int, int]   # (sx, sy, sz) в Minecraft
    effective_k: int
    total_filled: int            # не-air блоков
    volume: int
    preview_png: bytes           # три ортогональные проекции
    preview_size: tuple[int, int]
    source_size: tuple[int, int, int]  # размеры в .vox


def parse_vox(data: bytes) -> tuple[np.ndarray, list[tuple[int, int, int, int]]]:
    """→ (массив вокселей (vx,vy,vz) int32 с индексами 0..255, RGBA-палитра 256)."""
    if len(data) < 12 or data[:4] != b"VOX ":
        raise VoxError("invalid_vox", "Не файл MagicaVoxel (нет заголовка VOX )")

    found: dict = {}

    def walk(pos: int, end: int) -> int:
        if pos + 12 > end:
            raise VoxError("invalid_vox", "Обрыв файла .vox")
        cid = data[pos : pos + 4]
        content_n = int.from_bytes(data[pos + 4 : pos + 8], "little")
        children_n = int.from_bytes(data[pos + 8 : pos + 12], "little")
        content = data[pos + 12 : pos + 12 + content_n]
        children_end = pos + 12 + content_n + children_n
        if children_end > end:
            raise VoxError("invalid_vox", "Обрыв файла .vox")
        if cid == b"SIZE" and "size" not in found:
            found["size"] = struct.unpack("<iii", content[:12])
        elif cid == b"XYZI" and "voxels" not in found:
            n = int.from_bytes(content[:4], "little")
            found["voxels"] = content[4 : 4 + 4 * n]
        elif cid == b"RGBA" and "rgba" not in found:
            found["rgba"] = content[:1024]
        cpos = pos + 12 + content_n
        while cpos < children_end:
            cpos = walk(cpos, children_end)
        return children_end

    walk(8, len(data))

    size = found.get("size")
    voxels = found.get("voxels")
    if size is None or voxels is None:
        raise VoxError("invalid_vox", "В файле нет SIZE/XYZI (модели)")
    if size[0] < 0 or size[1] < 0 or size[2] < 0 or max(size) > 256:
        raise VoxError("invalid_vox", f"Некорректный SIZE: {size}")

    arr = np.zeros(size, dtype=np.int32)
    for i in range(0, len(voxels), 4):
        x, y, z, ci = voxels[i], voxels[i + 1], voxels[i + 2], voxels[i + 3]
        if x >= size[0] or y >= size[1] or z >= size[2]:
            raise VoxError("invalid_vox", "Воксель за пределами SIZE")
        arr[x, y, z] = ci

    rgba = found.get("rgba", b"")
    if len(rgba) < 1024:
        rgba += bytes(1024 - len(rgba))
    palette = [tuple(rgba[i * 4 : i * 4 + 4]) for i in range(256)]
    return arr, palette


def build_vox(data: bytes, mode: str, k: int, seed: int = config.SEED) -> VoxResult:
    """Конвертирует .vox → VoxResult с блоками Minecraft."""
    arr, palette = parse_vox(data)
    vx, vy, vz = arr.shape
    volume = vx * vy * vz
    if volume > config.MAX_VOX_VOLUME:
        raise VoxError(
            "volume_too_large",
            f"Объём модели {vx}×{vy}×{vz} = {volume} блоков превышает лимит "
            f"({config.MAX_VOX_VOLUME})",
        )

    # Уникальные цвета вокселей → блоки Minecraft
    flat_vox = arr.ravel()
    counts_vox = np.bincount(flat_vox, minlength=256)
    solid_colors: list[tuple[int, int, int]] = []
    solid_idx: list[int] = []
    weights: list[int] = []
    color_map: dict[int, int] = {}
    for ci in range(1, 256):  # 0 — пусто
        if counts_vox[ci] == 0:
            continue
        r, g, b, a = palette[ci]
        if a < 128:
            color_map[ci] = AIR_CODE
        else:
            solid_colors.append((r, g, b))
            solid_idx.append(ci)
            weights.append(int(counts_vox[ci]))

    lab_b = palette_lab_array()
    if solid_colors:
        lab_u = rgb_array_to_lab(np.array(solid_colors, dtype=np.uint8))
        if mode == "palette":
            mapping = nearest_argmin(lab_u, lab_b)
        elif mode == "adaptive":
            mapping, _used = _adaptive_mapping(
                lab_u, np.array(weights, dtype=np.int64), lab_b, k, seed
            )
        else:
            raise VoxError("invalid_params", f"неизвестный режим: {mode!r}")
        for ci, m in zip(solid_idx, mapping):
            color_map[ci] = int(m)

    lut = np.full(256, AIR_CODE, dtype=np.int64)
    for ci, code in color_map.items():
        lut[ci] = code

    mc = arr.transpose(0, 2, 1)  # vox(x,y,z) → mc(x, y'=z, z'=y) — для превью
    codes = lut[mc]
    # порядок региона x→z→y: оси (y', z', x)
    flat = codes.transpose(1, 2, 0).ravel()
    binc = np.bincount(flat, minlength=len(PALETTE) + 1)
    used = sorted(
        (i for i in range(len(PALETTE) + 1) if binc[i] > 0),
        key=lambda i: (-binc[i], i),
    )
    order = {i: pos for pos, i in enumerate(used)}
    grid = [order[i] for i in flat.tolist()]
    preview_png = _render_preview(codes)
    img = Image.open(io.BytesIO(preview_png))
    return VoxResult(
        grid=grid,
        palette=used,
        counts=[int(binc[i]) for i in used],
        size=(vx, vz, vy),
        effective_k=len(used),
        total_filled=volume - int(binc[AIR_CODE]),
        volume=volume,
        preview_png=preview_png,
        preview_size=img.size,
        source_size=(vx, vy, vz),
    )


def _project(codes: np.ndarray, axis: int):
    """Первая не-air клетка вдоль оси (с ближней стороны).

    → (2D-массив кодов блоков, 2D-массив глубин, длина оси).
    """
    n = codes.shape[axis]
    m = np.moveaxis(codes != AIR_CODE, axis, -1)
    c = np.moveaxis(codes, axis, -1)
    m2 = m.reshape(-1, n)
    c2 = c.reshape(-1, n)
    first = np.argmax(m2, axis=1)
    has = m2.any(axis=1)
    colors = np.full(m2.shape[0], AIR_CODE, dtype=np.int64)
    depths = np.zeros(m2.shape[0], dtype=np.int64)
    colors[has] = c2[has, first[has]]
    depths[has] = first[has]
    return colors.reshape(m.shape[:-1]), depths.reshape(m.shape[:-1]), n


def _view(codes: np.ndarray, axis: int, from_far: bool = False,
          flipud: bool = False) -> Image.Image:
    """Одна ортогональная проекция с затенением по глубине."""
    if from_far:
        codes = np.flip(codes, axis=axis)
    colors, depths, n = _project(codes, axis)
    lut = np.array([b.rgb for b in PALETTE] + [_BG], dtype=np.float64)
    denom = max(n - 1, 1)
    shade = 0.55 + 0.45 * depths[..., None] / denom
    rgb = np.clip(lut[colors] * shade, 0, 255).astype(np.uint8)
    img = rgb.transpose(1, 0, 2)  # (первая ось → столбцы, вторая → строки)
    if flipud:
        img = img[::-1]
    return Image.fromarray(img, "RGB")


def _render_preview(codes: np.ndarray) -> bytes:
    """Три проекции: фронт (x-y) | сверху (x-z) | сбоку (y-z)."""
    front = _view(codes, 2, from_far=False, flipud=True)   # ось z, y вверх → flip
    top = _view(codes, 1, from_far=True, flipud=False)     # с неба (y дальний)
    side = _view(codes, 0, from_far=False, flipud=False)   # с запада
    gap = 4
    h = max(front.height, top.height, side.height)
    strip = Image.new(
        "RGB", (front.width + gap + top.width + gap + side.width, h), _BG
    )
    strip.paste(front, (0, 0))
    strip.paste(top, (front.width + gap, 0))
    strip.paste(side, (front.width + top.width + 2 * gap, 0))
    buf = io.BytesIO()
    strip.save(buf, format="PNG")
    return buf.getvalue()
