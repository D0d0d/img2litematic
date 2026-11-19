"""Фикстуры тестов: синтетические изображения (Pillow) и общие хелперы."""

import io
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def scan_pixels(img: Image.Image) -> list:
    if hasattr(img, "get_flattened_data"):
        return list(img.get_flattened_data())
    return list(img.getdata())


@pytest.fixture
def quadrants_img():
    """4×4: 4 квадранта 2×2 сплошных цветов (для проверки box-average)."""
    img = Image.new("RGB", (4, 4))
    px = img.load()
    colors = {
        (0, 0): (255, 0, 0),
        (1, 0): (0, 255, 0),
        (0, 1): (0, 0, 255),
        (1, 1): (255, 255, 0),
    }
    for y in range(4):
        for x in range(4):
            px[x, y] = colors[(x // 2, y // 2)]
    return img


@pytest.fixture
def noise_gradient_img():
    """64×64: шумный градиент — тысячи уникальных цветов."""
    import numpy as np

    rng = np.random.default_rng(42)
    y, x = np.mgrid[0:64, 0:64]
    arr = np.stack(
        [
            x * 3 + rng.integers(0, 30, (64, 64)),
            y * 3 + rng.integers(0, 30, (64, 64)),
            (x + y) // 2 + rng.integers(0, 30, (64, 64)),
        ],
        axis=-1,
    )
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


@pytest.fixture
def kregions_img():
    """64×64: 64 регионов 8×8 цветов 64 взаимно удалённых блоков палитры + лёгкий шум.

    Цвета выбираются жадным farthest-point по Lab из реальной палитры,
    поэтому k-means c K=64 обязан восстановить ровно эти 64 блока.
    """
    import numpy as np

    from palette import PALETTE, palette_lab_array

    labs = palette_lab_array()
    chosen = [0]
    dist = ((labs - labs[0]) ** 2).sum(axis=1)
    while len(chosen) < 64:
        nxt = int(np.argmax(dist))
        chosen.append(nxt)
        d = ((labs - labs[nxt]) ** 2).sum(axis=1)
        dist = np.minimum(dist, d)

    arr = np.zeros((64, 64, 3), dtype=np.uint8)
    rng = np.random.default_rng(7)
    for i, b in enumerate(chosen):
        base = np.array(PALETTE[b].rgb)
        row, col = divmod(i, 8)
        arr[row * 8 : (row + 1) * 8, col * 8 : (col + 1) * 8] = np.clip(
            base + rng.integers(-4, 5, (8, 8, 3)), 0, 255
        )
    return Image.fromarray(arr, "RGB")
