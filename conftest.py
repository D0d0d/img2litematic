"""Корневой conftest: добавляет корень проекта в sys.path для импорта модулей из тестов."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
