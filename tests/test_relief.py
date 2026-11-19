"""Тесты режима рельефа: высоты, геометрия, сглаживание, API, экспорт."""

import base64
import gzip
import io
import json

import numpy as np
import pytest
from PIL import Image

import config
from app import app
from conftest import png_bytes
from nbt_test_reader import NbtReader, decode_block_states
from relief import (
    AIR_NAME,
    build_relief,
    heights_from_luminance,
    luminance_array,
    relief_name,
)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post(client, path, img, params):
    return client.post(
        path,
        data={"image": (io.BytesIO(png_bytes(img)), "test.png"),
              "params": json.dumps(params)},
        content_type="multipart/form-data",
    )


def _relief_params(**over):
    p = {
        "mode": "palette",
        "k": 16,
        "orientation": "vertical",
        "target": 32,
        "relief": True,
        "max_height": 4,
        "smoothing": 0,
        "invert": False,
        "base_block": "minecraft:stone",
    }
    p.update(over)
    return p


def _two_row_img():
    """1×2: верх — белый (H=max), низ — чёрный (H=1)."""
    img = Image.new("RGB", (1, 2))
    img.putpixel((0, 0), (255, 255, 255))
    img.putpixel((0, 1), (0, 0, 0))
    return img


class TestHeights:
    def test_uniform_gray(self):
        img = Image.new("RGB", (4, 4), (128, 128, 128))
        h = heights_from_luminance(luminance_array(img), 8)
        # 128/255*7 = 3.5137 → np.round → 4 → высота 5
        assert (h == 5).all()

    def test_extremes(self):
        h = heights_from_luminance(luminance_array(Image.new("RGB", (2, 2), (255, 255, 255))), 64)
        assert (h == 64).all()
        h = heights_from_luminance(luminance_array(Image.new("RGB", (2, 2), (0, 0, 0))), 64)
        assert (h == 1).all()

    def test_max_height_one(self):
        h = heights_from_luminance(luminance_array(Image.new("RGB", (2, 2), (200, 100, 50))), 1)
        assert (h == 1).all()


class TestGeometry:
    def test_vertical_fill(self):
        r = build_relief(
            _two_row_img(), "palette", 16, dither=False, max_height=4, smoothing=0,
            invert=False, base_block="minecraft:stone", orientation="vertical",
        )
        assert r.size == (1, 2, 4)
        assert r.volume == 8
        assert r.total_filled == 5  # белая колонка 4 + чёрная 1
        names = [relief_name(i) for i in r.palette]
        assert AIR_NAME in names and "minecraft:stone" in names
        assert len(r.surface_grid) == 2

        w, h, D = 1, 2, 4

        def at(y, z, x):
            return r.grid[(y * D + z) * w + x]

        def name_at(y, z, x):
            return relief_name(r.palette[at(y, z, x)])

        # переворот строк: y_world=1 ↔ строка 0 (белая): z=0..2 камень, z=3 поверхность
        assert name_at(1, 3, 0) not in (AIR_NAME, "minecraft:stone")
        assert name_at(1, 2, 0) == "minecraft:stone"
        assert name_at(1, 0, 0) == "minecraft:stone"
        # y_world=0 ↔ строка 1 (чёрная): z=0 поверхность, выше — air
        assert name_at(0, 0, 0) not in (AIR_NAME, "minecraft:stone")
        assert name_at(0, 1, 0) == AIR_NAME

    def test_floor_fill(self):
        r = build_relief(
            _two_row_img(), "palette", 16, dither=False, max_height=4, smoothing=0,
            invert=False, base_block="minecraft:stone", orientation="floor",
        )
        assert r.size == (1, 4, 2)

        w, D, h = 1, 4, 2

        def name_at(y, z, x):
            return relief_name(r.palette[r.grid[(y * h + z) * w + x]])

        # z=0 ↔ строка 0 (белая): y=0..2 камень, y=3 поверхность
        assert name_at(3, 0, 0) not in (AIR_NAME, "minecraft:stone")
        assert name_at(2, 0, 0) == "minecraft:stone"
        # z=1 ↔ строка 1 (чёрная): y=0 поверхность, выше — air
        assert name_at(0, 1, 0) not in (AIR_NAME, "minecraft:stone")
        assert name_at(1, 1, 0) == AIR_NAME

    def test_invert(self):
        img = _two_row_img()
        r = build_relief(
            img, "palette", 16, dither=False, max_height=4, smoothing=0,
            invert=True, base_block="minecraft:stone", orientation="vertical",
        )
        # инверсия меняет только высоты: белая строка H=1, чёрная H=4;
        # цвет поверхности остаётся цветом картинки

        def name_at(y, z, x):
            return relief_name(r.palette[r.grid[(y * 4 + z) * 1 + x]])

        # y_world=1 (белая): z=0 — белая поверхность, выше пусто
        assert name_at(1, 0, 0) not in (AIR_NAME, "minecraft:stone")
        assert name_at(1, 1, 0) == AIR_NAME
        # y_world=0 (чёрная): z=0..2 камень, z=3 — чёрная поверхность
        assert name_at(0, 2, 0) == "minecraft:stone"
        assert name_at(0, 3, 0) not in (AIR_NAME, "minecraft:stone")

    def test_smoothing_reduces_variance(self):
        from PIL import ImageFilter

        arr = np.zeros((8, 8), dtype=np.uint8)
        arr[::2, ::2] = 255
        arr[1::2, 1::2] = 255
        img = Image.fromarray(np.stack([arr] * 3, axis=-1), "RGB")
        h_sharp = heights_from_luminance(luminance_array(img), 16)
        blurred = img.filter(ImageFilter.GaussianBlur(3))
        h_blur = heights_from_luminance(luminance_array(blurred), 16)
        assert h_blur.var() < h_sharp.var() / 2

    def test_determinism(self):
        img = _two_row_img().resize((4, 8))
        a = build_relief(img, "adaptive", 8, dither=True, max_height=8, smoothing=1.5,
                         invert=True, base_block="minecraft:stone", orientation="floor")
        b = build_relief(img, "adaptive", 8, dither=True, max_height=8, smoothing=1.5,
                         invert=True, base_block="minecraft:stone", orientation="floor")
        assert a.grid == b.grid and a.palette == b.palette
        assert a.surface_grid == b.surface_grid
        assert a.preview_png == b.preview_png

    def test_preview_png(self):
        img = _two_row_img().resize((4, 8))
        r = build_relief(img, "palette", 16, dither=False, max_height=4, smoothing=0,
                         invert=False, base_block="minecraft:stone", orientation="vertical")
        prev = Image.open(io.BytesIO(r.preview_png))
        assert prev.size == (4, 8)


class TestReliefApi:
    def test_convert_response(self, client, noise_gradient_img):
        r = _post(client, "/api/convert", noise_gradient_img,
                  _relief_params(target=32, mode="adaptive", k=4))
        assert r.status_code == 200
        j = r.get_json()
        assert j["relief"] is True
        assert 1 <= j["maxHeight"] <= 4
        assert len(j["surfaceGrid"]) == j["width"] * j["height"]
        assert sum(b["count"] for b in j["palette"]) == j["stats"]["totalBlocks"]
        assert j["stats"]["totalBlocks"] >= j["stats"]["filledBlocks"]
        assert j["effectiveK"] <= 4 + 2  # поверхности (≤ K) + air + base
        prev = Image.open(io.BytesIO(base64.b64decode(j["preview"])))
        assert prev.size == (j["width"], j["height"])

    def test_volume_cap(self, client, noise_gradient_img, monkeypatch):
        monkeypatch.setattr(config, "MAX_RELIEF_VOLUME", 100)
        r = _post(client, "/api/convert", noise_gradient_img, _relief_params(target=32))
        assert r.status_code == 400
        assert r.get_json()["code"] == "volume_too_large"

    def test_invalid_base_block(self, client, noise_gradient_img):
        r = _post(client, "/api/convert", noise_gradient_img,
                  _relief_params(base_block="minecraft:bedrock"))
        assert r.status_code == 400
        assert r.get_json()["code"] == "invalid_params"

    @pytest.mark.parametrize(
        "over",
        [
            {"max_height": 0},
            {"max_height": 65},
            {"smoothing": -1},
            {"smoothing": 17},
            {"invert": "yes"},
            {"relief": "yes"},
        ],
    )
    def test_invalid_relief_params(self, client, noise_gradient_img, over):
        r = _post(client, "/api/convert", noise_gradient_img, _relief_params(**over))
        assert r.status_code == 400
        assert r.get_json()["code"] == "invalid_params"

    def test_export_roundtrip(self, client, noise_gradient_img):
        params = _relief_params(target=32, timestamp_ms=777)
        j = _post(client, "/api/convert", noise_gradient_img, params).get_json()
        exp = _post(client, "/api/export", noise_gradient_img, params)
        assert exp.status_code == 200
        assert exp.data[:2] == b"\x1f\x8b"
        tag, _name, root = NbtReader(gzip.decompress(exp.data)).named_tag()
        region = root["Regions"]["Image"]
        assert tuple(region["Size"].values()) == (j["width"], j["height"], j["maxHeight"])
        elem_id, items = region["BlockStatePalette"]
        names = [next(iter(p.values())) for p in items]
        assert names == [p["name"] for p in j["palette"]]
        bits = max(2, (len(names) - 1).bit_length())
        volume = j["stats"]["totalBlocks"]
        decoded = decode_block_states(region["BlockStates"], bits, volume)
        # счётчики блоков в файле совпадают со счётчиками convert
        counts = {}
        for v in decoded:
            counts[v] = counts.get(v, 0) + 1
        assert [counts.get(i, 0) for i in range(len(names))] == [p["count"] for p in j["palette"]]

    def test_export_deterministic(self, client, noise_gradient_img):
        params = _relief_params(target=32, timestamp_ms=42)
        a = _post(client, "/api/export", noise_gradient_img, params).data
        b = _post(client, "/api/export", noise_gradient_img, params).data
        assert a == b

    def test_floor_size(self, client, noise_gradient_img):
        params = _relief_params(target=32, orientation="floor", timestamp_ms=1)
        exp = _post(client, "/api/export", noise_gradient_img, params)
        root = NbtReader(gzip.decompress(exp.data)).named_tag()[2]
        size = root["Regions"]["Image"]["Size"]
        assert size["y"] > 1 and size["z"] == 32