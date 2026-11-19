"""Тесты квантования: детерминизм, гарантия K, корректность nearest-mode."""

import json
import subprocess
import sys

import numpy as np
import pytest
from PIL import Image

from imaging import downscale
from palette import PALETTE
from quantize import quantize

ROOT = str(__import__("pathlib").Path(__file__).resolve().parent.parent)


def _q(img, mode="adaptive", k=16):
    return quantize(img, mode, k)


class TestAdaptive:
    def test_solid_color_single_block(self):
        r = _q(Image.new("RGB", (8, 8), (200, 40, 40)), "adaptive", 16)
        assert r.effective_k == 1
        assert len(set(r.grid)) == 1

    def test_four_colors_k16(self):
        img = Image.new("RGB", (16, 16))
        px = img.load()
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        for y in range(16):
            for x in range(16):
                px[x, y] = colors[(x // 4 + y // 4) % 4]
        r = _q(img, "adaptive", 16)
        assert r.effective_k == 4

    def test_k_guarantee_k64(self, kregions_img):
        # 64 взаимно удалённых цветов палитры: почти все регионы восстанавливают
        # «свой» блок, но почти-дубликаты цветов палитры могут стоить 1-2 блоков
        # (гарантия «≤ K» при этом всегда соблюдается).
        r = _q(kregions_img, "adaptive", 64)
        assert 60 <= r.effective_k <= 64

    @pytest.mark.parametrize("k", [2, 5, 16])
    def test_k_guarantee_noise(self, noise_gradient_img, k):
        assert _q(noise_gradient_img, "adaptive", k).effective_k == k

    def test_effective_k_never_exceeds_k(self, noise_gradient_img):
        for k in (2, 7, 33, 64):
            assert _q(noise_gradient_img, "adaptive", k).effective_k <= k

    def test_determinism(self, noise_gradient_img):
        a = _q(noise_gradient_img, "adaptive", 16)
        b = _q(noise_gradient_img, "adaptive", 16)
        assert a.grid == b.grid and a.palette == b.palette

    def test_determinism_subprocess(self, noise_gradient_img, tmp_path):
        p = tmp_path / "noise.png"
        noise_gradient_img.save(p)
        script = (
            "import sys, json, hashlib\n"
            "from PIL import Image\n"
            "from imaging import downscale\n"
            "from quantize import quantize\n"
            "img = downscale(Image.open(sys.argv[1]).convert('RGB'), 64)\n"
            "r = quantize(img, 'adaptive', 16)\n"
            "h = hashlib.sha256(json.dumps([r.grid, r.palette]).encode()).hexdigest()\n"
            "print(h)\n"
        )
        outs = []
        for _ in range(2):
            proc = subprocess.run(
                [sys.executable, "-c", script, str(p)],
                capture_output=True, text=True, cwd=ROOT, timeout=120,
            )
            assert proc.returncode == 0, proc.stderr
            outs.append(proc.stdout.strip())
        assert outs[0] == outs[1]

    def test_1x1(self):
        for mode in ("adaptive", "palette"):
            r = _q(Image.new("RGB", (1, 1), (10, 20, 30)), mode, 16)
            assert r.effective_k == 1 and len(r.grid) == 1

    def test_palette_indices_valid(self, noise_gradient_img):
        r = _q(noise_gradient_img, "adaptive", 16)
        assert all(0 <= b < len(PALETTE) for b in r.palette)
        assert all(0 <= g < len(r.palette) for g in r.grid)


class TestPaletteMode:
    def test_nearest_bruteforce(self, noise_gradient_img):
        from colorutil import nearest_argmin, rgb_array_to_lab
        from conftest import scan_pixels
        from palette import palette_lab_array

        img = downscale(noise_gradient_img, 32)
        r = _q(img, "palette", 16)
        px = scan_pixels(img)
        uniq = list(dict.fromkeys(px))
        lab_u = rgb_array_to_lab(np.array(uniq, dtype=np.uint8))
        expect = nearest_argmin(lab_u, palette_lab_array())
        order = {b: i for i, b in enumerate(r.palette)}
        cmap = {c: i for i, c in enumerate(uniq)}
        brute = [order[expect[cmap[p]]] for p in px]
        assert brute == r.grid

    def test_uses_many_blocks(self, noise_gradient_img):
        r = _q(noise_gradient_img, "palette", 16)
        assert r.effective_k > 8  # полная палитра богаче адаптивного режима с малым K
