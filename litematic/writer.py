"""Сборка файла .litematic: упаковка BlockStates и структура схемы.

Спецификация (Litematica):
- gzip-сжатый NBT, корень — compound с пустым именем;
- BlockStates: LSB-first упаковка индексов палитры, bits = max(2,
  ceil(log2(palette_size))), элемент i занимает биты [i*bits, (i+1)*bits);
- порядок элементов: x быстрее всего, затем z, затем y:
  index = (y * sizeZ + z) * sizeX + x.
"""

import io
from math import ceil

from . import nbt

MASK64 = 0xFFFFFFFFFFFFFFFF


def pack_block_states(indices, palette_size: int, volume: int) -> tuple[int, list[int]]:
    """Упаковка индексов в 64-битные long (LSB-first).

    Возвращает (bits, longs).
    """
    if palette_size < 1:
        raise ValueError("palette_size должен быть ≥ 1")
    if len(indices) != volume:
        raise ValueError(f"ожидалось {volume} индексов, получено {len(indices)}")
    bits = max(2, (palette_size - 1).bit_length())
    longs = [0] * ceil(bits * volume / 64)
    for i, v in enumerate(indices):
        if not 0 <= v < palette_size:
            raise ValueError(f"индекс {v} вне палитры размера {palette_size}")
        bitpos = i * bits
        li, off = divmod(bitpos, 64)
        longs[li] |= (v << off) & MASK64
        if off + bits > 64:
            longs[li + 1] |= v >> (64 - off)
    return bits, longs


def build_litematic_bytes(
    *,
    name: str,
    description: str,
    author: str,
    size: tuple[int, int, int],
    palette_names,
    block_indices,
    created_ms: int,
    modified_ms: int,
    preview_png: bytes | None = None,
    region_name: str = "Image",
    data_version: int = 3839,
) -> bytes:
    """Собирает .litematic (gzip-NBT байты).

    block_indices — volume = sx·sy·sz записей в порядке x → z → y.
    """
    sx, sy, sz = size
    volume = sx * sy * sz
    if volume != len(block_indices):
        raise ValueError(f"size {size} требует {volume} индексов, получено {len(block_indices)}")
    if not palette_names:
        raise ValueError("пустая палитра блоков")
    _bits, longs = pack_block_states(block_indices, len(palette_names), volume)

    def int3():
        return [("x", nbt.TAG_INT, sx), ("y", nbt.TAG_INT, sy), ("z", nbt.TAG_INT, sz)]

    metadata = [
        ("Author", nbt.TAG_STRING, author),
        ("Description", nbt.TAG_STRING, description),
        ("Name", nbt.TAG_STRING, name),
        ("RegionCount", nbt.TAG_INT, 1),
        ("TotalBlocks", nbt.TAG_INT, volume),
        ("TotalVolume", nbt.TAG_INT, volume),
        ("EnclosingSize", nbt.TAG_COMPOUND, int3()),
        ("TimeCreated", nbt.TAG_LONG, created_ms),
        ("TimeModified", nbt.TAG_LONG, modified_ms),
    ]
    if preview_png is not None:
        metadata.append(
            (
                "PreviewImageData",
                nbt.TAG_COMPOUND,
                [
                    ("Data", nbt.TAG_BYTE_ARRAY, preview_png),
                    ("Width", nbt.TAG_INT, sx),
                    ("Height", nbt.TAG_INT, sy),
                ],
            )
        )

    empty_list = (nbt.TAG_COMPOUND, [])
    region = [
        (
            "Position",
            nbt.TAG_COMPOUND,
            [("x", nbt.TAG_INT, 0), ("y", nbt.TAG_INT, 0), ("z", nbt.TAG_INT, 0)],
        ),
        ("Size", nbt.TAG_COMPOUND, int3()),
        (
            "BlockStatePalette",
            nbt.TAG_LIST,
            (nbt.TAG_COMPOUND, [[("Name", nbt.TAG_STRING, nm)] for nm in palette_names]),
        ),
        ("TileEntities", nbt.TAG_LIST, empty_list),
        ("Entities", nbt.TAG_LIST, empty_list),
        ("PendingBlockTicks", nbt.TAG_LIST, empty_list),
        ("PendingFluidTicks", nbt.TAG_LIST, empty_list),
        ("BlockStates", nbt.TAG_LONG_ARRAY, longs),
        ("MinecraftDataVersion", nbt.TAG_INT, data_version),
    ]
    root = [
        ("Metadata", nbt.TAG_COMPOUND, metadata),
        ("Regions", nbt.TAG_COMPOUND, [(region_name, nbt.TAG_COMPOUND, region)]),
    ]

    buf = io.BytesIO()
    nbt.write_named_tag(buf, nbt.TAG_COMPOUND, "", root)
    return nbt.gzip_compress(buf.getvalue())


def save_litematic(path, **kwargs) -> None:
    path.write_bytes(build_litematic_bytes(**kwargs))
