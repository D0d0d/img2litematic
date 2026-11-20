"""Константы конфигурации img2litematic."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Фиксированный сид k-means: превью == экспорт (детерминизм)
SEED = 20251119

# Метрика цвета: "lab" (CIELAB CIE76) или "redmean" (запасная)
DISTANCE_METRIC = "lab"

# Параметры конвертации
MIN_TARGET = 16
MAX_TARGET = 512
DEFAULT_TARGET = 128
MIN_K = 2
MAX_K = 64
DEFAULT_K = 16

# Лимиты входных данных
MAX_SOURCE_PIXELS = 40_000_000      # 40 Мп — защита от decompression bomb
MAX_CONTENT_LENGTH = 64 * 1024 * 1024

# Режим рельефа (3D)
MIN_MAX_HEIGHT = 1
MAX_MAX_HEIGHT = 64
DEFAULT_MAX_HEIGHT = 8
MAX_SMOOTHING = 16
DEFAULT_SMOOTHING = 2.0
DEFAULT_BASE_BLOCK = "minecraft:stone"
MAX_RELIEF_VOLUME = 8_000_000       # w·h·max_height — верхняя граница объёма

# Импорт .vox (MagicaVoxel)
MAX_VOX_VOLUME = 8_000_000          # вокселей в модели

# Композиция сцены (несколько объектов → одна схема)
MAX_COMPOSE_VOLUME = 8_000_000      # объём объединённой bounding box

# Данные для .litematic
MINECRAFT_DATA_VERSION = 3839       # Minecraft 1.21 (информационное поле)
REGION_NAME = "Image"
AUTHOR = "img2litematic"
PORT = 5000
