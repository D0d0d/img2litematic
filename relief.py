"""Рельеф из изображения (барельеф/террейн).

Яркость пикселя → высота (сглаживание, инверсия). Поверхность — блоки из
обычного квантования (оба режима + дизеринг), внутренности — блок основания,
пустоты bounding box — air.

Геометрия:
- vertical: картина в плоскости x-y, рельеф вглубь по z; строки переворачиваются
  (верх картинки → y = h−1, как в 2D);
- floor: картина в плоскости x-z (строки → z), рельеф вверх по y.
"""

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter

from palette import PALETTE
from quantize import quantize

AIR_NAME = "minecraft:air"
AIR_CODE = len(PALETTE)  # служебный индекс «воздуха» — вне палитры цветов
AIR_RGB = (205, 213, 219)  # цвет для легенды/превью


def relief_name(i: int) -> str:
    return AIR_NAME if i == AIR_CODE else PALETTE[i].name


def relief_rgb(i: int) -> tuple[int, int, int]:
    return AIR_RGB if i == AIR_CODE else PALETTE[i].rgb


@dataclass(frozen=True)
class ReliefResult:
    grid: list[int]          # блоки региона (x→z→y), индексы в `palette`
    palette: list[int]       # индексы PALETTE или AIR_CODE, по убыванию count
    counts: list[int]        # счётчики по позициям выходной палитры
    surface_grid: list[int]  # w·h индексов в `palette` — блоки поверхности
    size: tuple[int, int, int]
    depth: int               # фактическая глубина/высота (≤ max_height)
    effective_k: int
    total_filled: int        # заполненных (не air) блоков
    volume: int              # w·h·depth, включая air
    preview_png: bytes       # затенённая проекция (1 px = 1 блок)


def luminance_array(img: Image.Image) -> np.ndarray:
    """(h,w) float64 яркость 0..255 (Rec. 601)."""
    arr = np.asarray(img, dtype=np.float64)
    return 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]


def heights_from_luminance(lum: np.ndarray, max_height: int) -> np.ndarray:
    """(h,w) int64 высоты 1..max_height."""
    norm = np.clip(lum, 0.0, 255.0) / 255.0
    return (1 + np.round(norm * (max_height - 1))).astype(np.int64)


def build_relief(
    img: Image.Image,
    mode: str,
    k: int,
    dither: bool,
    max_height: int,
    smoothing: float,
    invert: bool,
    base_block: str,
    orientation: str,
) -> ReliefResult:
    """Собирает рельеф: поверхность — quantize(), высоты — из яркости."""
    w, h = img.size
    surface = quantize(img, mode, k, dither=dither)

    lum = luminance_array(img)
    if invert:
        lum = 255.0 - lum
    if smoothing > 0:
        blur = Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8), "L")
        lum = np.asarray(blur.filter(ImageFilter.GaussianBlur(smoothing)), dtype=np.float64)
    heights = heights_from_luminance(lum, max_height)  # (h,w) 1..max_height
    depth = int(heights.max())

    base_code = next(i for i, b in enumerate(PALETTE) if b.name == base_block)
    surf_pal = np.array(surface.palette, dtype=np.int64)
    surf = surf_pal[np.array(surface.grid, dtype=np.int64)].reshape(h, w)  # (h,w)

    if orientation == "vertical":
        size = (w, h, depth)
        ht = heights[::-1]  # переворот строк: верх картинки → y = h−1
        s = surf[::-1]
        z = np.arange(depth)[None, :, None]
        H = ht[:, None, :]
        filled = z < H
        top = z == (H - 1)
        arr = np.full((h, depth, w), AIR_CODE, dtype=np.int64)
        arr[filled] = base_code
        arr[top] = np.broadcast_to(s[:, None, :], (h, depth, w))[top]
    else:  # floor
        size = (w, depth, h)
        y = np.arange(depth)[:, None, None]
        H = heights[None, :, :]
        filled = y < H
        top = y == (H - 1)
        arr = np.full((depth, h, w), AIR_CODE, dtype=np.int64)
        arr[filled] = base_code
        arr[top] = np.broadcast_to(surf[None, :, :], (depth, h, w))[top]

    # Выходная палитра: по убыванию count, tie → меньший индекс
    flat = arr.ravel()
    binc = np.bincount(flat, minlength=len(PALETTE) + 1)
    used = sorted(
        (i for i in range(len(PALETTE) + 1) if binc[i] > 0),
        key=lambda i: (-binc[i], i),
    )
    order = {i: pos for pos, i in enumerate(used)}
    grid = [order[i] for i in flat.tolist()]
    surface_grid = [order[i] for i in surf.ravel().tolist()]
    volume = w * h * depth
    return ReliefResult(
        grid=grid,
        palette=used,
        counts=[int(binc[i]) for i in used],
        surface_grid=surface_grid,
        size=size,
        depth=depth,
        effective_k=len(used),
        total_filled=volume - int(binc[AIR_CODE]),
        volume=volume,
        preview_png=_render_preview(surf, heights, depth),
    )


def _render_preview(surf: np.ndarray, heights: np.ndarray, depth: int) -> bytes:
    """Проекция рельефа (как загружена картинка) с затенением по глубине:
    выше/глубже — светлее."""
    denom = max(depth - 1, 1)
    shade = 0.55 + 0.45 * (heights - 1) / denom
    pal_rgb = np.array([b.rgb for b in PALETTE], dtype=np.float64)
    rgb = pal_rgb[surf] * shade[..., None]
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
