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


def quantize(img, mode: str, k: int, seed: int = config.SEED) -> QuantResult:
    pixels, _w, _h = pixels_scan_order(img)
    counter = Counter(pixels)
    uniq = list(counter)  # порядок первого появления — детерминирован
    weights = np.array([counter[c] for c in uniq], dtype=np.int64)
    lab_u = rgb_array_to_lab(np.array(uniq, dtype=np.uint8))
    lab_b = palette_lab_array()

    if mode == "palette":
        mapping = nearest_argmin(lab_u, lab_b)  # uniq → индекс блока палитры
    elif mode == "adaptive":
        mapping, _used = _adaptive_mapping(lab_u, weights, lab_b, k, seed)
    else:
        raise ValueError(f"неизвестный режим: {mode!r}")

    # Выходная палитра: по убыванию count, tie → меньший индекс палитры
    counts = np.bincount(mapping, weights=weights.astype(np.float64), minlength=len(PALETTE))
    counts = counts.astype(np.int64)
    used = sorted(
        (b for b in range(len(PALETTE)) if counts[b] > 0),
        key=lambda b: (-counts[b], b),
    )
    order = {b: i for i, b in enumerate(used)}
    cmap = {c: i for i, c in enumerate(uniq)}
    grid = [order[mapping[cmap[p]]] for p in pixels]
    return QuantResult(grid=grid, palette=used, effective_k=len(used))


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
