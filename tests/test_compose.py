"""Тесты композиции сцены: объединение объектов, вживление, API."""

import base64
import gzip
import io
import json

import pytest

import config
from app import app
from compose import ComposeError, compose_litematic
from nbt_test_reader import NbtReader, decode_block_states

AIR = "minecraft:air"
STONE = "minecraft:stone"
RED = "minecraft:red_wool"


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _obj(values, size, offset, overwrite=False, palette=(AIR, STONE, RED), check=True):
    """values — список позиций палитры в порядке (y, z, x)."""
    if check:
        assert len(values) == size[0] * size[1] * size[2]
    return {
        "gridB64": base64.b64encode(bytes(values)).decode("ascii"),
        "palette": list(palette),
        "width": size[0],
        "height": size[1],
        "depth": size[2],
        "offset": list(offset),
        "overwrite": overwrite,
    }


def _counts(data: bytes):
    """Расшифровка .litematic → (size, {имя блока: счётчик})."""
    tag, _name, root = NbtReader(gzip.decompress(data)).named_tag()
    region = root["Regions"]["Image"]
    size = tuple(region["Size"].values())
    _eid, items = region["BlockStatePalette"]
    names = [next(iter(p.values())) for p in items]
    bits = max(2, (len(names) - 1).bit_length())
    decoded = decode_block_states(region["BlockStates"], bits, size[0] * size[1] * size[2])
    counts = {}
    for v in decoded:
        counts[v] = counts.get(v, 0) + 1
    return size, {names[i]: counts.get(i, 0) for i in range(len(names))}


class TestCompose:
    def test_side_by_side(self):
        a = _obj([1], (1, 1, 1), (0, 0, 0))           # камень
        b = _obj([2], (1, 1, 1), (2, 0, 0))           # красная шерсть
        size, nc = _counts(compose_litematic([a, b], 1, 1))
        assert size == (3, 1, 1)
        assert nc == {AIR: 1, STONE: 1, RED: 1}

    def test_overwrite_true_air_replaces(self):
        a = _obj([1], (1, 1, 1), (0, 0, 0))
        b = _obj([0], (1, 1, 1), (0, 0, 0), overwrite=True)  # air затирает камень
        _size, nc = _counts(compose_litematic([a, b], 1, 1))
        assert nc == {AIR: 1}

    def test_embed_air_skipped(self):
        a = _obj([1], (1, 1, 1), (0, 0, 0))
        b = _obj([0], (1, 1, 1), (0, 0, 0), overwrite=False)  # вживление: air пропущен
        _size, nc = _counts(compose_litematic([a, b], 1, 1))
        assert nc == {STONE: 1}

    def test_embed_fills_only_solid(self):
        a = _obj([1, 0], (2, 1, 1), (0, 0, 0))                      # [камень, air]
        b = _obj([0, 2], (2, 1, 1), (0, 0, 0), overwrite=False)     # [air, красный]
        _size, nc = _counts(compose_litematic([a, b], 1, 1))
        assert nc == {STONE: 1, RED: 1}

    def test_negative_offsets(self):
        a = _obj([1], (1, 1, 1), (-2, 0, 0))
        b = _obj([1], (1, 1, 1), (1, 0, 0))
        size, nc = _counts(compose_litematic([a, b], 1, 1))
        assert size == (4, 1, 1)   # bbox x ∈ [-2, 1]
        assert nc == {AIR: 2, STONE: 2}  # камень на x=-2 и x=1, air на x=-1 и x=0

    def test_3d_offset(self):
        a = _obj([1], (1, 1, 1), (0, 0, 0))
        b = _obj([2], (1, 1, 1), (0, 2, 1))
        size, nc = _counts(compose_litematic([a, b], 1, 1))
        assert size == (1, 3, 2)
        assert nc == {AIR: 4, STONE: 1, RED: 1}  # 6 ячеек, 2 заполнены

    def test_volume_cap(self, monkeypatch):
        monkeypatch.setattr(config, "MAX_COMPOSE_VOLUME", 2)
        a = _obj([1, 1, 1, 1], (2, 2, 1), (0, 0, 0))  # объём 4 > 2
        with pytest.raises(ComposeError) as ei:
            compose_litematic([a], 1, 1)
        assert ei.value.code == "volume_too_large"

    def test_invalid_base64(self):
        o = _obj([1], (1, 1, 1), (0, 0, 0))
        o["gridB64"] = "!!!not base64!!!"
        with pytest.raises(ComposeError) as ei:
            compose_litematic([o], 1, 1)
        assert ei.value.code == "invalid_params"

    def test_unknown_block(self):
        o = _obj([0], (1, 1, 1), (0, 0, 0), palette=["minecraft:bedrock"])
        with pytest.raises(ComposeError) as ei:
            compose_litematic([o], 1, 1)
        assert ei.value.code == "invalid_params"

    def test_wrong_grid_length(self):
        o = _obj([1, 2], (1, 1, 1), (0, 0, 0), check=False)  # 2 байта вместо 1
        with pytest.raises(ComposeError) as ei:
            compose_litematic([o], 1, 1)
        assert ei.value.code == "invalid_params"

    def test_determinism(self):
        objs = [_obj([1, 2], (2, 1, 1), (0, 0, 0)), _obj([0, 2], (2, 1, 1), (1, 0, 1), overwrite=False)]
        assert compose_litematic(objs, 5, 5) == compose_litematic(objs, 5, 5)


class TestComposeApi:
    def test_compose_endpoint(self, client):
        objs = [_obj([1], (1, 1, 1), (0, 0, 0)), _obj([2], (1, 1, 1), (1, 0, 0))]
        r = client.post(
            "/api/compose",
            data=json.dumps({"objects": objs, "timestamp_ms": 9}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert 'filename="scene.litematic"' in r.headers["Content-Disposition"]
        size, nc = _counts(r.data)
        assert size == (2, 1, 1)
        assert nc == {STONE: 1, RED: 1}

    def test_empty_objects(self, client):
        r = client.post("/api/compose", data=json.dumps({"objects": []}),
                        content_type="application/json")
        assert r.status_code == 400
        assert r.get_json()["code"] == "invalid_params"

    def test_not_json(self, client):
        r = client.post("/api/compose", data="oops", content_type="application/json")
        assert r.status_code == 400
        assert r.get_json()["code"] == "invalid_params"
