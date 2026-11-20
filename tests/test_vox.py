"""Тесты импорта MagicaVoxel .vox: парсер, маппинг, API, экспорт."""

import base64
import gzip
import io
import json
import struct

import numpy as np
import pytest
from PIL import Image

import config
from app import app
from nbt_test_reader import NbtReader, decode_block_states
from palette import AIR_NAME, block_name
from vox import VoxError, build_vox, parse_vox


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def make_vox(size, voxels, rgba=None, version=150):
    """Собирает минимальный .vox: MAIN → SIZE, XYZI, RGBA.

    voxels: список (x, y, z, color_index); rgba: 256 записей (r,g,b,a).
    """
    body = b""
    content = struct.pack("<iii", *size)
    body += b"SIZE" + struct.pack("<ii", len(content), 0) + content
    content = struct.pack("<i", len(voxels)) + b"".join(
        struct.pack("<BBBB", *v) for v in voxels
    )
    body += b"XYZI" + struct.pack("<ii", len(content), 0) + content
    if rgba is None:
        rgba = [(i % 256, (i * 7) % 256, (i * 13) % 256, 255) for i in range(256)]
    content = b"".join(struct.pack("<BBBB", *c) for c in rgba)
    body += b"RGBA" + struct.pack("<ii", len(content), 0) + content
    main = b"MAIN" + struct.pack("<ii", 0, len(body)) + body
    return b"VOX " + struct.pack("<i", version) + main


def _red_rgba():
    # индекс 1 — красный, индекс 2 — синий (0 — пусто)
    return [(0, 0, 0, 0), (255, 0, 0, 255), (0, 0, 255, 255)] + [(0, 0, 0, 0)] * 253


class TestParse:
    def test_roundtrip(self):
        arr, palette = parse_vox(make_vox((2, 2, 2), [(0, 0, 0, 1), (1, 1, 1, 2)], _red_rgba()))
        assert arr.shape == (2, 2, 2)
        assert arr[0, 0, 0] == 1
        assert arr[1, 1, 1] == 2
        assert arr[1, 0, 0] == 0
        assert palette[1] == (255, 0, 0, 255)
        assert palette[2] == (0, 0, 255, 255)
        assert len(palette) == 256

    def test_not_vox(self):
        with pytest.raises(VoxError) as ei:
            parse_vox(b"hello world, not a vox file")
        assert ei.value.code == "invalid_vox"

    def test_missing_model(self):
        with pytest.raises(VoxError) as ei:
            parse_vox(b"VOX " + struct.pack("<i", 150) + b"MAIN" + struct.pack("<ii", 0, 0))
        assert ei.value.code == "invalid_vox"

    def test_voxel_out_of_size(self):
        with pytest.raises(VoxError) as ei:
            parse_vox(make_vox((2, 2, 2), [(5, 0, 0, 1)], _red_rgba()))
        assert ei.value.code == "invalid_vox"


class TestBuild:
    def test_transpose_vox_z_up(self):
        # воксель vox(0,1,0) → mc(x=0, y=0, z=1): индекс (0·2 + 1)·2 + 0 = 2
        r = build_vox(make_vox((2, 2, 2), [(0, 1, 0, 1)], _red_rgba()), "palette", 16)
        assert r.size == (2, 2, 2)
        assert r.source_size == (2, 2, 2)
        assert r.total_filled == 1
        air_pos = {block_name(i): pos for pos, i in enumerate(r.palette)}[AIR_NAME]
        assert all(r.grid[i] == air_pos for i in range(8) if i != 2)
        assert block_name(r.palette[r.grid[2]]) != AIR_NAME

    def test_transparent_is_air(self):
        rgba = [(0, 0, 0, 0), (255, 0, 0, 0)] + [(0, 0, 0, 0)] * 254  # индекс 1 прозрачный
        r = build_vox(make_vox((2, 2, 2), [(0, 0, 0, 1)], rgba), "palette", 16)
        assert r.total_filled == 0
        assert r.effective_k == 1
        assert block_name(r.palette[0]) == AIR_NAME

    def test_color_mapping(self):
        from colorutil import nearest_argmin, rgb_array_to_lab
        from palette import PALETTE, palette_lab_array

        rgba = [(0, 0, 0, 0), (255, 0, 0, 255)] + [(0, 0, 0, 0)] * 254
        r = build_vox(make_vox((1, 1, 1), [(0, 0, 0, 1)], rgba), "palette", 16)
        name = block_name(r.palette[r.grid[0]])
        assert name != AIR_NAME
        # маппинг совпадает с независимым brute-force ближайшего блока по Lab
        b = int(nearest_argmin(
            rgb_array_to_lab(np.array([[255, 0, 0]], dtype=np.uint8)),
            palette_lab_array(),
        )[0])
        assert name == PALETTE[b].name

    def test_volume_cap(self, monkeypatch):
        monkeypatch.setattr(config, "MAX_VOX_VOLUME", 4)  # 2×2×2 = 8 > 4
        with pytest.raises(VoxError) as ei:
            build_vox(make_vox((2, 2, 2), [(0, 0, 0, 1)], _red_rgba()), "palette", 16)
        assert ei.value.code == "volume_too_large"

    def test_adaptive_k_guarantee(self):
        # 8 разных цветов, K=4 → ≤ 4 блоков + air
        rgba = [((i * 30) % 256, (i * 17) % 256, (i * 41) % 256, 255) for i in range(256)]
        voxels = [(x, y, z, x + 2 * y + 4 * z + 1) for x in range(2) for y in range(2) for z in range(2)]
        r = build_vox(make_vox((2, 2, 2), voxels, rgba), "adaptive", 4)
        assert r.effective_k <= 5
        assert r.total_filled == 8

    def test_determinism(self):
        voxels = [(x, y, z, x + 2 * y + 4 * z + 1) for x in range(4) for y in range(4) for z in range(4)]
        data = make_vox((4, 4, 4), voxels)
        a = build_vox(data, "adaptive", 8)
        b = build_vox(data, "adaptive", 8)
        assert a.grid == b.grid and a.palette == b.palette
        assert a.preview_png == b.preview_png

    def test_preview(self):
        data = make_vox((4, 4, 4), [(1, 1, 1, 1)], _red_rgba())
        r = build_vox(data, "palette", 16)
        img = Image.open(io.BytesIO(r.preview_png))
        assert img.size == r.preview_size  # полоса из трёх проекций
        assert img.width > r.size[0] * 2


def _vox_params(**over):
    p = {"mode": "adaptive", "k": 8}
    p.update(over)
    return p


def _post_vox(client, path, data, params):
    return client.post(
        path,
        data={"vox": (io.BytesIO(data), "model.vox"), "params": json.dumps(params)},
        content_type="multipart/form-data",
    )


class TestVoxApi:
    def test_convert(self, client):
        data = make_vox((4, 4, 4), [(1, 1, 1, 1)], _red_rgba())
        r = _post_vox(client, "/api/vox", data, _vox_params())
        assert r.status_code == 200
        j = r.get_json()
        assert j["vox"] is True
        assert (j["width"], j["height"], j["depth"]) == (4, 4, 4)
        assert sum(b["count"] for b in j["palette"]) == j["stats"]["totalBlocks"] == 64
        assert j["stats"]["filledBlocks"] == 1
        prev = Image.open(io.BytesIO(base64.b64decode(j["preview"])))
        assert prev.size == (j["previewWidth"], j["previewHeight"])
        # gridB64: 1 байт = блок, порядок региона (x→z→y), счётчики совпадают
        raw = base64.b64decode(j["gridB64"])
        assert len(raw) == j["stats"]["totalBlocks"]
        assert max(raw) < len(j["palette"])
        counts = {}
        for v in raw:
            counts[v] = counts.get(v, 0) + 1
        assert [counts.get(i, 0) for i in range(len(j["palette"]))] == [
            p["count"] for p in j["palette"]
        ]

    def test_missing_file(self, client):
        r = client.post("/api/vox", data={"params": json.dumps(_vox_params())})
        assert r.status_code == 400
        assert r.get_json()["code"] == "missing_file"

    def test_invalid_file(self, client):
        r = _post_vox(client, "/api/vox", b"not vox", _vox_params())
        assert r.status_code == 400
        assert r.get_json()["code"] == "invalid_vox"

    def test_volume_cap_api(self, client, monkeypatch):
        monkeypatch.setattr(config, "MAX_VOX_VOLUME", 4)
        r = _post_vox(client, "/api/vox", make_vox((2, 2, 2), [(0, 0, 0, 1)], _red_rgba()),
                      _vox_params())
        assert r.status_code == 400
        assert r.get_json()["code"] == "volume_too_large"

    def test_export_roundtrip(self, client):
        data = make_vox((2, 2, 2), [(0, 0, 0, 1), (1, 1, 1, 2)], _red_rgba())
        params = _vox_params(mode="palette", timestamp_ms=555)
        j = _post_vox(client, "/api/vox", data, params).get_json()
        exp = _post_vox(client, "/api/export", data, params)
        assert exp.status_code == 200
        assert 'filename="model.litematic"' in exp.headers["Content-Disposition"]
        assert exp.data[:2] == b"\x1f\x8b"
        tag, _name, root = NbtReader(gzip.decompress(exp.data)).named_tag()
        region = root["Regions"]["Image"]
        assert tuple(region["Size"].values()) == (2, 2, 2)
        elem_id, items = region["BlockStatePalette"]
        names = [next(iter(p.values())) for p in items]
        assert names == [p["name"] for p in j["palette"]]
        bits = max(2, (len(names) - 1).bit_length())
        decoded = decode_block_states(region["BlockStates"], bits, 8)
        counts = {}
        for v in decoded:
            counts[v] = counts.get(v, 0) + 1
        assert [counts.get(i, 0) for i in range(len(names))] == [p["count"] for p in j["palette"]]

    def test_export_deterministic(self, client):
        data = make_vox((4, 4, 4), [(x, x, x, x + 1) for x in range(4)])
        params = _vox_params(timestamp_ms=42)
        a = _post_vox(client, "/api/export", data, params).data
        b = _post_vox(client, "/api/export", data, params).data
        assert a == b

    def test_image_flow_untouched(self, client, noise_gradient_img):
        # обычный image-export продолжает работать, когда vox не передан
        from conftest import png_bytes

        r = client.post(
            "/api/export",
            data={"image": (io.BytesIO(png_bytes(noise_gradient_img)), "test.png"),
                  "params": json.dumps({"mode": "adaptive", "k": 8, "target": 32,
                                        "timestamp_ms": 1})},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        assert r.data[:2] == b"\x1f\x8b"
