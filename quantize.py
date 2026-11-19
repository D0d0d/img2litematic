"""Квантование изображения в блоки Minecraft.

Режимы:
- "palette":  каждый пиксель → ближайший блок всей курируемой палитры;
- "adaptive": ограниченный k-means (K кластеров), каждый кластер привязывается
  к реальному блоку → гарантированно ≤ K различных блоков.

Детерминизм: фиксированный сид, tie-break'и по индексу, einsum без BLAS.
"""

import random
from collections import Counter
from dataclasses import dataclass

import numpy as np

import config
from colorutil import nearest_argmin, rgb_array_to_lab
from imaging import pixels_scan_order
from palette import PALETTE, palette_lab_array


@dataclass(frozen=True)
class QuantResult:
    grid: list[int]      # w·h значений: индексы в `palette` (порядок сканирования)
    palette: list[int]   # индексы блоков в palette.PALETTE, по убыванию count
    effective_k: int     # число использованных типов блоков (≤ K)


def quantize(
    img, mode: str, k: int, seed: int = config.SEED, dither: bool = False
) -> QuantResult:
    """Квантует изображение в блоки; dither=True включает Флойда–Штейнберга.

    Кандидаты дизеринга: в режиме "palette" — все блоки палитры, в "adaptive" —
    только выбранные k-means'ом блоки (гарантия ≤ K сохраняется).
    """
    pixels, w, h = pixels_scan_order(img)
    counter = Counter(pixels)
    uniq = list(counter)  # порядок первого появления — детерминирован
    weights = np.array([counter[c] for c in uniq], dtype=np.int64)
    lab_u = rgb_array_to_lab(np.array(uniq, dtype=np.uint8))
    lab_b = palette_lab_array()

    if mode == "palette":
        mapping = nearest_argmin(lab_u, lab_b)  # uniq → индекс блока палитры
        cand_lab = lab_b
        cand_idx = np.arange(len(PALETTE), dtype=np.int64)
    elif mode == "adaptive":
        mapping, used = _adaptive_mapping(lab_u, weights, lab_b, k, seed)
        used_arr = np.array(used, dtype=np.int64)
        cand_lab = lab_b[used_arr]
        cand_idx = used_arr
    else:
        raise ValueError(f"неизвестный режим: {mode!r}")

    if dither:
        lab_img = rgb_array_to_lab(np.array(pixels, dtype=np.uint8)).reshape(h, w, 3)
        raw = _floyd_steinberg(lab_img, cand_lab, cand_idx).ravel().tolist()
    else:
        cmap = {c: i for i, c in enumerate(uniq)}
        raw = [mapping[cmap[p]] for p in pixels]

    # Выходная палитра: по убыванию count, tie → меньший индекс палитры
    counts = np.bincount(raw, minlength=len(PALETTE))
    used = sorted(
        (b for b in range(len(PALETTE)) if counts[b] > 0),
        key=lambda b: (-counts[b], b),
    )
    order = {b: i for i, b in enumerate(used)}
    grid = [order[b] for b in raw]
    return QuantResult(grid=grid, palette=used, effective_k=len(used))


def _nearest_block(p: np.ndarray, cand_lab: np.ndarray) -> int:
    """Индекс ближайшего блока-кандидата к точке p (3,) в Lab."""
    d = cand_lab - p
    return int(np.argmin(np.einsum("ij,ij->i", d, d)))


def _floyd_steinberg(
    lab_img: np.ndarray, cand_lab: np.ndarray, cand_idx: np.ndarray
) -> np.ndarray:
    """Флойд–Штейнберг (serpentine): (h,w,3) Lab → (h,w) индексов палитры.

    Веса ошибки: вправо 7/16, вниз-влево 3/16, вниз 5/16, вниз-вправо 1/16
    (зеркально для строк справа налево). Детерминирован по построению.
    """
    h, w, _ = lab_img.shape
    out = np.empty((h, w), dtype=np.int64)
    err = np.zeros((w + 2, 3))
    for y in range(h):
        row = lab_img[y]
        e = np.zeros((w + 2, 3))
        if y % 2 == 0:  # слева направо
            for x in range(w):
                p = row[x] + err[x + 1]
                bi = _nearest_block(p, cand_lab)
                out[y, x] = cand_idx[bi]
                d = p - cand_lab[bi]
                err[x + 2] += d * (7.0 / 16.0)
                e[x] += d * (3.0 / 16.0)
                e[x + 1] += d * (5.0 / 16.0)
                e[x + 2] += d * (1.0 / 16.0)
        else:  # справа налево (serpentine)
            for x in range(w - 1, -1, -1):
                p = row[x] + err[x + 1]
                bi = _nearest_block(p, cand_lab)
                out[y, x] = cand_idx[bi]
                d = p - cand_lab[bi]
                err[x] += d * (7.0 / 16.0)
                e[x + 2] += d * (3.0 / 16.0)
                e[x + 1] += d * (5.0 / 16.0)
                e[x] += d * (1.0 / 16.0)
        err = e
    return out


def _dist_to_nearest(lab_u: np.ndarray, centers: np.ndarray) -> np.ndarray:
    idx = nearest_argmin(lab_u, centers)
    return ((lab_u - centers[idx]) ** 2).sum(axis=1)


def _adaptive_mapping(lab_u, weights, lab_b, k, seed):
    """Ограниченный k-means: uniq-цвет → индекс блока палитры.

    Гарантия: число различных блоков ≤ K.
    """
    n = len(lab_u)
    p = len(lab_b)
    k = min(k, n, p)

    if k == 1:
        wmean = (lab_u * weights[:, None]).sum(axis=0) / float(weights.sum())
        b = int(nearest_argmin(wmean[None, :], lab_b)[0])
        return np.full(n, b, dtype=np.int64), [b]

    rng = random.Random(seed)

    # k-means++ инициализация (взвешенная по частотам цветов)
    first = rng.choices(range(n), weights=weights.tolist(), k=1)[0]
    centroids = [first]
    while len(centroids) < k:
        d2 = _dist_to_nearest(lab_u, lab_u[centroids])
        total = float((d2 * weights).sum())
        r = rng.random() * total
        cum = 0.0
        nxt = None
        for i in range(n):
            cum += d2[i] * weights[i]
            if cum >= r:
                nxt = i
                break
        if nxt is None:
            nxt = n - 1
        if nxt in centroids:
            nxt = next(i for i in range(n) if i not in centroids)
        centroids.append(nxt)

    # Итерации Ллойда (взвешенные)
    cent = lab_u[np.array(centroids)].copy()
    assign = nearest_argmin(lab_u, cent)
    for _ in range(50):
        new_cent = np.empty_like(cent)
        empty = []
        for j in range(k):
            mask = assign == j
            if mask.any():
                new_cent[j] = (lab_u[mask] * weights[mask][:, None]).sum(axis=0) / float(
                    weights[mask].sum()
                )
            else:
                empty.append(j)
        if empty:
            # пустые кластеры пересеваются самыми дальними от своих центров точками
            d_own = ((lab_u - cent[assign]) ** 2).sum(axis=1)
            order = np.argsort(-d_own, kind="stable")
            for t, j in enumerate(empty):
                new_cent[j] = lab_u[order[t]]
        new_assign = nearest_argmin(lab_u, new_cent)
        if np.array_equal(new_assign, assign):
            break
        assign, cent = new_assign, new_cent

    # Snap центров к реальным блокам; коллизии решаются жадным перебором
    nearest_block = nearest_argmin(cent, lab_b).astype(np.int64)
    cw = np.array([float(weights[assign == j].sum()) for j in range(k)])
    used_blocks: set[int] = set()
    for j in sorted(range(k), key=lambda jj: (-cw[jj], jj)):
        b = int(nearest_block[j])
        if b in used_blocks:
            d = ((lab_b - cent[j]) ** 2).sum(axis=1)
            for cand in np.argsort(d, kind="stable"):  # tie → меньший индекс палитры
                cand = int(cand)
                if cand not in used_blocks:
                    b = cand
                    break
        nearest_block[j] = b
        used_blocks.add(b)

    # Финальный Voronoi по выбранному множеству S (только улучшает, не выходит за S)
    S = np.unique(nearest_block)
    final = nearest_argmin(lab_u, lab_b[S])
    return S[final].astype(np.int64), S.tolist()
