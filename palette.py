"""Курируемая палитра блоков Minecraft (имена 1.13+) со средними цветами текстур.

80 блоков: 16 шерстей + 16 бетонов + 17 терракот + 31 дополнительный.
Цвета — усреднённые по текстурам; легко править вручную.
"""

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from colorutil import rgb_array_to_lab


@dataclass(frozen=True)
class Block:
    name: str  # полное имя 1.13+, напр. "minecraft:white_wool"
    rgb: tuple[int, int, int]


WOOLS = (
    Block("minecraft:white_wool", (233, 236, 236)),
    Block("minecraft:orange_wool", (240, 118, 19)),
    Block("minecraft:magenta_wool", (189, 68, 179)),
    Block("minecraft:light_blue_wool", (58, 175, 217)),
    Block("minecraft:yellow_wool", (248, 198, 39)),
    Block("minecraft:lime_wool", (112, 185, 25)),
    Block("minecraft:pink_wool", (237, 141, 172)),
    Block("minecraft:gray_wool", (62, 68, 71)),
    Block("minecraft:light_gray_wool", (142, 142, 134)),
    Block("minecraft:cyan_wool", (21, 137, 145)),
    Block("minecraft:purple_wool", (121, 42, 172)),
    Block("minecraft:blue_wool", (53, 57, 157)),
    Block("minecraft:brown_wool", (114, 71, 40)),
    Block("minecraft:green_wool", (84, 109, 27)),
    Block("minecraft:red_wool", (161, 39, 34)),
    Block("minecraft:black_wool", (20, 21, 25)),
)

CONCRETES = (
    Block("minecraft:white_concrete", (207, 213, 214)),
    Block("minecraft:orange_concrete", (224, 97, 1)),
    Block("minecraft:magenta_concrete", (169, 48, 159)),
    Block("minecraft:light_blue_concrete", (36, 137, 199)),
    Block("minecraft:yellow_concrete", (241, 175, 21)),
    Block("minecraft:lime_concrete", (94, 168, 24)),
    Block("minecraft:pink_concrete", (214, 101, 143)),
    Block("minecraft:gray_concrete", (55, 58, 62)),
    Block("minecraft:light_gray_concrete", (125, 125, 115)),
    Block("minecraft:cyan_concrete", (21, 119, 136)),
    Block("minecraft:purple_concrete", (100, 32, 156)),
    Block("minecraft:blue_concrete", (44, 46, 143)),
    Block("minecraft:brown_concrete", (96, 59, 32)),
    Block("minecraft:green_concrete", (73, 91, 36)),
    Block("minecraft:red_concrete", (142, 33, 33)),
    Block("minecraft:black_concrete", (8, 10, 15)),
)

TERRACOTTAS = (
    Block("minecraft:white_terracotta", (210, 179, 161)),
    Block("minecraft:orange_terracotta", (162, 84, 34)),
    Block("minecraft:magenta_terracotta", (149, 87, 108)),
    Block("minecraft:light_blue_terracotta", (112, 108, 138)),
    Block("minecraft:yellow_terracotta", (186, 133, 36)),
    Block("minecraft:lime_terracotta", (103, 117, 52)),
    Block("minecraft:pink_terracotta", (160, 77, 78)),
    Block("minecraft:gray_terracotta", (57, 42, 35)),
    Block("minecraft:light_gray_terracotta", (135, 107, 98)),
    Block("minecraft:cyan_terracotta", (87, 91, 91)),
    Block("minecraft:purple_terracotta", (118, 69, 86)),
    Block("minecraft:blue_terracotta", (76, 62, 92)),
    Block("minecraft:brown_terracotta", (77, 51, 35)),
    Block("minecraft:green_terracotta", (76, 82, 42)),
    Block("minecraft:red_terracotta", (143, 61, 46)),
    Block("minecraft:black_terracotta", (37, 22, 16)),
    Block("minecraft:terracotta", (152, 95, 68)),
)

EXTRAS = (
    Block("minecraft:stone", (127, 127, 127)),
    Block("minecraft:cobblestone", (109, 109, 109)),
    Block("minecraft:andesite", (133, 135, 133)),
    Block("minecraft:diorite", (188, 188, 188)),
    Block("minecraft:granite", (157, 107, 92)),
    Block("minecraft:deepslate", (79, 79, 85)),
    Block("minecraft:calcite", (223, 223, 220)),
    Block("minecraft:quartz_block", (234, 229, 222)),
    Block("minecraft:snow_block", (244, 252, 252)),
    Block("minecraft:end_stone", (219, 222, 162)),
    Block("minecraft:sandstone", (216, 210, 167)),
    Block("minecraft:sand", (219, 211, 160)),
    Block("minecraft:obsidian", (23, 19, 30)),
    Block("minecraft:iron_block", (216, 216, 216)),
    Block("minecraft:gold_block", (248, 209, 56)),
    Block("minecraft:copper_block", (189, 107, 79)),
    Block("minecraft:diamond_block", (98, 229, 232)),
    Block("minecraft:emerald_block", (46, 208, 111)),
    Block("minecraft:lapis_block", (31, 73, 168)),
    Block("minecraft:redstone_block", (177, 28, 18)),
    Block("minecraft:amethyst_block", (150, 106, 180)),
    Block("minecraft:oak_planks", (184, 148, 95)),
    Block("minecraft:spruce_planks", (129, 94, 60)),
    Block("minecraft:birch_planks", (200, 178, 115)),
    Block("minecraft:dark_oak_planks", (75, 50, 25)),
    Block("minecraft:acacia_planks", (179, 95, 47)),
    Block("minecraft:oak_log", (110, 86, 50)),
    Block("minecraft:nether_bricks", (44, 21, 24)),
    Block("minecraft:purpur_block", (169, 125, 171)),
    Block("minecraft:prismarine", (99, 150, 142)),
    Block("minecraft:warped_planks", (43, 122, 120)),
    Block("minecraft:sea_lantern", (181, 198, 186)),
)

PALETTE = WOOLS + CONCRETES + TERRACOTTAS + EXTRAS

# Fail fast: целостность данных палитры проверяется при импорте
assert len(PALETTE) >= 60, f"палитра слишком мала: {len(PALETTE)}"
_names = [b.name for b in PALETTE]
assert len(set(_names)) == len(_names), "дублирующиеся имена блоков"
for _b in PALETTE:
    assert _b.name.startswith("minecraft:"), _b.name
    assert len(_b.rgb) == 3 and all(0 <= c <= 255 for c in _b.rgb), _b


@lru_cache(maxsize=1)
def palette_rgb_array() -> np.ndarray:
    return np.array([b.rgb for b in PALETTE], dtype=np.uint8)


@lru_cache(maxsize=1)
def palette_lab_array() -> np.ndarray:
    return rgb_array_to_lab(palette_rgb_array())


def blocks_payload() -> list[dict]:
    """JSON-представление палитры для GET /api/blocks."""
    return [{"name": b.name, "color": list(b.rgb)} for b in PALETTE]


# Воздух: служебный «блок» вне цветовой палитры (используется в 3D-режимах)
AIR_NAME = "minecraft:air"
AIR_CODE = len(PALETTE)  # индекс за пределами PALETTE
AIR_RGB = (205, 213, 219)  # цвет для легенды/превью


def block_name(i: int) -> str:
    """Имя для индекса палитры или AIR_CODE."""
    return AIR_NAME if i == AIR_CODE else PALETTE[i].name


def block_rgb(i: int) -> tuple[int, int, int]:
    """Цвет для индекса палитры или AIR_CODE."""
    return AIR_RGB if i == AIR_CODE else PALETTE[i].rgb
