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

# Данные для .litematic
MINECRAFT_DATA_VERSION = 3839       # Minecraft 1.21 (информационное поле)
REGION_NAME = "Image"
AUTHOR = "img2litematic"
PORT = 5000
