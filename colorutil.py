"""Утилиты цвета: sRGB → CIELAB, попарные расстояния.

Все операции детерминированы (einsum без BLAS, tie-break по индексу).
"""

import numpy as np

# Константы CIELAB, иллюминант D65
_EPS = 216.0 / 24389.0
_KAPPA = 24389.0 / 27.0
_XN, _YN, _ZN = 0.95047, 1.0, 1.08883

_RGB2XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ]
)


def srgb_to_linear(c: float) -> float:
    """sRGB-компонента (0..1) → линейная (IEC 61966-2-1)."""
    c = min(max(c, 0.0), 1.0)
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lab_f(t: float) -> float:
    if t > _EPS:
        return t ** (1.0 / 3.0)
    return (_KAPPA * t + 16.0) / 116.0


def rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """RGB (0..255) → CIELAB (L, a, b), иллюминант D65."""
    r, g, b = (srgb_to_linear(c / 255.0) for c in rgb)
    x = _RGB2XYZ[0, 0] * r + _RGB2XYZ[0, 1] * g + _RGB2XYZ[0, 2] * b
    y = _RGB2XYZ[1, 0] * r + _RGB2XYZ[1, 1] * g + _RGB2XYZ[1, 2] * b
    z = _RGB2XYZ[2, 0] * r + _RGB2XYZ[2, 1] * g + _RGB2XYZ[2, 2] * b
    fx, fy, fz = _lab_f(x / _XN), _lab_f(y / _YN), _lab_f(z / _ZN)
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def rgb_array_to_lab(rgb: np.ndarray) -> np.ndarray:
    """(N,3) uint8 RGB → (N,3) float64 CIELAB."""
    rgb = rgb.astype(np.float64) / 255.0
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = lin @ _RGB2XYZ.T
    t = xyz / np.array([_XN, _YN, _ZN])
    f = np.where(t > _EPS, np.cbrt(t), (_KAPPA * t + 16.0) / 116.0)
    L = 116.0 * f[:, 1] - 16.0
    a = 500.0 * (f[:, 0] - f[:, 1])
    b = 200.0 * (f[:, 1] - f[:, 2])
    return np.stack([L, a, b], axis=1)


def _pairwise_sq(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Квадрат евклидова расстояния: (N,3) × (M,3) → (N,M).

    einsum не использует BLAS → одинаковый результат на всех платформах.
    """
    aa = np.einsum("ij,ij->i", a, a)[:, None]
    bb = np.einsum("ij,ij->i", b, b)[None, :]
    ab = np.einsum("ik,jk->ij", a, b)
    return aa + bb - 2.0 * ab


def nearest_argmin(points: np.ndarray, centers: np.ndarray, chunk: int = 16384) -> np.ndarray:
    """Для каждой строки points — индекс ближайшей строки centers.

    Tie-break: меньший индекс. Чанки ограничивают пик памяти.
    """
    n = points.shape[0]
    out = np.empty(n, dtype=np.int64)
    for s in range(0, n, chunk):
        d = _pairwise_sq(points[s : s + chunk], centers)
        out[s : s + chunk] = np.argmin(d, axis=1)
    return out


def lab_dist2(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Квадрат ΔE (CIE76) между наборами Lab-точек: (N,3) × (M,3) → (N,M)."""
    return _pairwise_sq(a, b)


def redmean_dist2(rgb1: np.ndarray, rgb2: np.ndarray) -> np.ndarray:
    """Запасная метрика: взвешенный redmean RGB (0..255): (N,3) × (M,3) → (N,M)."""
    rmean = (rgb1[:, 0:1] + rgb2[None, :, 0]) / 2.0
    dr = rgb1[:, 0:1] - rgb2[None, :, 0]
    dg = rgb1[:, 1:2] - rgb2[None, :, 1]
    db = rgb1[:, 2:3] - rgb2[None, :, 2]
    return (
        (2.0 + rmean / 256.0) * dr * dr
        + 4.0 * dg * dg
        + (2.0 + (255.0 - rmean) / 256.0) * db * db
    )
