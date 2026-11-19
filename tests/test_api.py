"""Тесты Flask API: валидация, коды ошибок, интеграционный детерминизм export."""

import gzip
import io
import json

import pytest

import config
from app import app
from conftest import png_bytes
from nbt_test_reader import NbtReader, decode_block_states


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _params(**over):
    p = {"mode": "adaptive", "k": 8, "orientation": "vertical", "target": 32}
    p.update(over)
    return p


def _post(client, path, img, params):
    return client.post(
        path,
        data={"image": (io.BytesIO(png_bytes(img)), "test.png"),
              "params": json.dumps(params)},
        content_type="multipart/form-data",
    )


class TestBlocks:
    def test_blocks(self, client):
        r = client.get("/api/blocks")
        assert r.status_code == 200
        blocks = r.get_json()["blocks"]
        assert len(blocks) >= 60
        names = [b["name"] for b in blocks]
        assert len(set(names)) == len(names)
        assert all(n.startswith("minecraft:") for n in names)
        assert all(
            len(b["color"]) == 3 and all(0 <= c <= 255 for c in b["color"]) for b in blocks
        )


class TestConvert:
    def test_happy(self, client, noise_gradient_img):
        r = _post(client, "/api/convert", noise_gradient_img, _params())
        assert r.status_code == 200
        j = r.get_json()
        assert j["width"] * j["height"] == len(j["grid"])
        assert j["effectiveK"] == 8
        assert j["stats"]["totalBlocks"] == j["width"] * j["height"]
        assert sum(b["count"] for b in j["palette"]) == j["stats"]["totalBlocks"]
        assert all(0 <= g < len(j["palette"]) for g in j["grid"])
        assert len({g for g in j["grid"]}) == j["effectiveK"]

    def test_missing_file(self, client):
        r = client.post("/api/convert", data={"params": json.dumps(_params())})
        assert r.status_code == 400
        assert r.get_json()["code"] == "missing_file"

    @pytest.mark.parametrize(
        "over",
        [
            {"mode": "bad"},
            {"k": 0},
            {"k": 65},
            {"k": "16"},
            {"target": 9999},
            {"target": 1},
            {"orientation": "diagonal"},
            {"timestamp_ms": -1},
        ],
    )
    def test_invalid_params(self, client, noise_gradient_img, over):
        r = _post(client, "/api/convert", noise_gradient_img, _params(**over))
        assert r.status_code == 400
        assert r.get_json()["code"] == "invalid_params"

    def test_invalid_json_params(self, client, noise_gradient_img):
        r = client.post(
            "/api/convert",
            data={
                "image": (io.BytesIO(png_bytes(noise_gradient_img)), "test.png"),
                "params": "{oops}",
            },
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert r.get_json()["code"] == "invalid_params"

    def test_not_an_image(self, client):
        r = client.post(
            "/api/convert",
            data={
                "image": (io.BytesIO(b"hello world"), "fake.png"),
                "params": json.dumps(_params()),
            },
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert r.get_json()["code"] == "invalid_image"

    def test_too_large(self, client, noise_gradient_img, monkeypatch):
        monkeypatch.setattr(config, "MAX_SOURCE_PIXELS", 100)
        r = _post(client, "/api/convert", noise_gradient_img, _params())
        assert r.status_code == 400
        assert r.get_json()["code"] == "image_too_large"


class TestExportIntegration:
    def test_export_matches_convert(self, client, noise_gradient_img):
        params = _params(timestamp_ms=1234567890)
        j = _post(client, "/api/convert", noise_gradient_img, params).get_json()
        exp = _post(client, "/api/export", noise_gradient_img, params)
        assert exp.status_code == 200
        assert exp.headers["Content-Type"] == "application/octet-stream"
        assert 'filename="test.litematic"' in exp.headers["Content-Disposition"]
        assert exp.data[:2] == b"\x1f\x8b"

        root = NbtReader(gzip.decompress(exp.data)).named_tag()
        tag, name, root = root
        assert tag == 10
        meta = root["Metadata"]
        assert meta["TimeCreated"] == 1234567890
        assert meta["TotalBlocks"] == j["stats"]["totalBlocks"]
        region = root["Regions"]["Image"]
        assert region["Size"] == {"x": j["width"], "y": j["height"], "z": 1}
        elem_id, items = region["BlockStatePalette"]
        names = [next(iter(p.values())) for p in items]
        assert names == [p["name"] for p in j["palette"]]
        bits = max(2, (len(names) - 1).bit_length())
        volume = j["width"] * j["height"]
        # vertical: строки инвертированы, чтобы верх картинки был сверху в мире
        w, h = j["width"], j["height"]
        expected = [j["grid"][(h - 1 - y) * w + x] for y in range(h) for x in range(w)]
        assert decode_block_states(region["BlockStates"], bits, volume) == expected

    def test_export_deterministic(self, client, noise_gradient_img):
        params = _params(timestamp_ms=42)
        a = _post(client, "/api/export", noise_gradient_img, params).data
        b = _post(client, "/api/export", noise_gradient_img, params).data
        assert a == b

    def test_floor_orientation(self, client, noise_gradient_img):
        params = _params(orientation="floor", timestamp_ms=1)
        j = _post(client, "/api/convert", noise_gradient_img, params).get_json()
        exp = _post(client, "/api/export", noise_gradient_img, params)
        root = NbtReader(gzip.decompress(exp.data)).named_tag()[2]
        region = root["Regions"]["Image"]
        assert region["Size"] == {"x": 32, "y": 1, "z": 32}
        # floor: строки изображения → ось z, порядок индексов не меняется
        bits = max(2, (len(region["BlockStatePalette"][1]) - 1).bit_length())
        assert decode_block_states(region["BlockStates"], bits, 32 * 32) == j["grid"]

    def test_vertical_not_upside_down(self, client):
        # 1×2: верх — красный, низ — синий. В регионе y=0 (низ) должен быть
        # нижний (синий) блок, y=1 (верх) — верхний (красный).
        from PIL import Image

        img = Image.new("RGB", (1, 2))
        img.putpixel((0, 0), (255, 0, 0))
        img.putpixel((0, 1), (0, 0, 255))
        params = _params(mode="palette", timestamp_ms=1)
        j = _post(client, "/api/convert", img, params).get_json()
        exp = _post(client, "/api/export", img, params)
        root = NbtReader(gzip.decompress(exp.data)).named_tag()[2]
        region = root["Regions"]["Image"]
        bits = max(2, (len(region["BlockStatePalette"][1]) - 1).bit_length())
        decoded = decode_block_states(region["BlockStates"], bits, 2)
        assert decoded[0] == j["grid"][1]  # y=0 ← нижняя строка изображения
        assert decoded[1] == j["grid"][0]  # y=1 ← верхняя строка

    def test_preview_embedded(self, client, noise_gradient_img):
        params = _params(timestamp_ms=1)
        exp = _post(client, "/api/export", noise_gradient_img, params)
        root = NbtReader(gzip.decompress(exp.data)).named_tag()[2]
        p = root["Metadata"]["PreviewImageData"]
        assert p["Width"] == 32 and p["Height"] == 32
        from PIL import Image

        img = Image.open(io.BytesIO(bytes(p["Data"])))
        assert img.size == (32, 32)
