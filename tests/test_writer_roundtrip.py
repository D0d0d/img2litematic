"""Round-trip тесты сборки .litematic через независимый декодер."""

import gzip
import io
from math import ceil

import pytest
from PIL import Image

from litematic.writer import build_litematic_bytes, pack_block_states
from nbt_test_reader import NbtReader, decode_block_states, read_compound_root


def _build(size=(4, 2, 1), palette_size=4, indices=None, **extra) -> bytes:
    volume = size[0] * size[1] * size[2]
    if indices is None:
        indices = [i % palette_size for i in range(volume)]
    kw = dict(
        name="тест",
        description="описание",
        author="tester",
        size=size,
        palette_names=[f"minecraft:b{i}" for i in range(palette_size)],
        block_indices=indices,
        created_ms=1700000000000,
        modified_ms=1700000000001,
    )
    kw.update(extra)
    return build_litematic_bytes(**kw)


def _load(data: bytes) -> dict:
    return read_compound_root(gzip.decompress(data))


class TestPackBits:
    @pytest.mark.parametrize(
        "palette_size,bits",
        [
            (1, 2), (2, 2), (3, 2), (4, 2), (5, 3), (16, 4), (17, 5),
            (64, 6), (65, 7), (128, 7), (129, 8),
        ],
    )
    def test_roundtrip_cycles(self, palette_size, bits):
        volume = 24  # 24*3=72 бита для bits=3 — пересекает 64-битную границу
        indices = [i % palette_size for i in range(volume)]
        packed_bits, longs = pack_block_states(indices, palette_size, volume)
        assert packed_bits == bits
        assert len(longs) == ceil(bits * volume / 64)
        assert decode_block_states(longs, packed_bits, volume) == indices

    def test_random_long_volume(self):
        volume = 1000
        indices = [i % 7 for i in range(volume)]
        bits, longs = pack_block_states(indices, 7, volume)
        assert decode_block_states(longs, bits, volume) == indices

    def test_invalid_indices(self):
        with pytest.raises(ValueError):
            pack_block_states([3], 3, 1)
        with pytest.raises(ValueError):
            pack_block_states([0, 1], 4, 3)


class TestWriterRoundtrip:
    def test_metadata(self):
        root = _load(_build())
        meta = root["Metadata"]
        assert meta["Name"] == "тест"
        assert meta["Description"] == "описание"
        assert meta["Author"] == "tester"
        assert meta["RegionCount"] == 1
        assert meta["TotalBlocks"] == 8
        assert meta["TotalVolume"] == 8
        assert meta["EnclosingSize"] == {"x": 4, "y": 2, "z": 1}
        assert meta["TimeCreated"] == 1700000000000
        assert meta["TimeModified"] == 1700000000001

    def test_region(self):
        root = _load(_build())
        region = root["Regions"]["Image"]
        assert region["Position"] == {"x": 0, "y": 0, "z": 0}
        assert region["Size"] == {"x": 4, "y": 2, "z": 1}
        elem_id, items = region["BlockStatePalette"]
        assert elem_id == 10
        assert [next(iter(p.values())) for p in items] == [
            "minecraft:b0", "minecraft:b1", "minecraft:b2", "minecraft:b3",
        ]
        for name in ("Entities", "TileEntities", "PendingBlockTicks", "PendingFluidTicks"):
            elem, entries = region[name]
            assert entries == []
        assert region["MinecraftDataVersion"] == 3839

    def test_blockstates_order_2d(self):
        # 2×3×1: индекс = y·2 + x
        indices = list(range(6))
        root = _load(_build(size=(2, 3, 1), palette_size=8, indices=indices))
        longs = root["Regions"]["Image"]["BlockStates"]
        assert decode_block_states(longs, 3, 6) == indices

    def test_blockstates_order_3d(self):
        # 2×2×2: индекс = (y·2 + z)·2 + x
        indices = list(range(8))
        root = _load(_build(size=(2, 2, 2), palette_size=8, indices=indices))
        longs = root["Regions"]["Image"]["BlockStates"]
        assert decode_block_states(longs, 3, 8) == indices

    def test_custom_region_and_version(self):
        root = _load(_build(region_name="Pic", data_version=3000))
        assert "Pic" in root["Regions"]
        assert root["Regions"]["Pic"]["MinecraftDataVersion"] == 3000

    def test_no_preview_by_default(self):
        assert "PreviewImageData" not in _load(_build())["Metadata"]

    def test_preview_image(self):
        buf = io.BytesIO()
        Image.new("RGB", (4, 2), (1, 2, 3)).save(buf, format="PNG")
        meta = _load(_build(preview_png=buf.getvalue()))["Metadata"]
        p = meta["PreviewImageData"]
        assert p["Width"] == 4 and p["Height"] == 2
        img = Image.open(io.BytesIO(bytes(p["Data"])))
        assert img.size == (4, 2)
        assert img.getpixel((0, 0)) == (1, 2, 3)

    def test_nbtlib_crosscheck(self):
        nbtlib = pytest.importorskip("nbtlib")
        f = nbtlib.load(io.BytesIO(_build()), gzipped=True)
        assert str(f["Metadata"]["Name"]) == "тест"
        region = f["Regions"]["Image"]
        assert len(region["BlockStatePalette"]) == 4
        assert len(region["BlockStates"]) == ceil(2 * 8 / 64)
