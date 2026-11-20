# img2litematic

Локальное веб-приложение: изображения и воксельные модели → схемы Minecraft
формата Litematica (`.litematic`). 2D и 3D.

A local web app: images and voxel models → Minecraft Litematica schematics
(`.litematic`). 2D and 3D.

---

## Возможности / Features

- **2D**: 1 пиксель = 1 блок, box-усреднение при масштабировании.
  Адаптивный constrained k-means (гарантированно ≤ K типов блоков) или
  полная палитра (81 блок), метрика CIELAB, дизеринг Floyd–Steinberg.
  Вертикальная картина или ковёр на полу.
- **Рельеф (3D)**: яркость → глубина/высота (сглаживание, инверсия), цветная
  поверхность из того же квантования, основание — выбранный блок, air в пустотах.
- **MagicaVoxel `.vox`**: воксельные модели → .litematic; палитра маппится
  на блоки через Lab-метрику (nearest или ≤ K), пустые воксели → air.
- **Сцена-композиция**: рельеф и .vox как объекты одной сцены — смещения
  X/Y/Z, режим «вживить» (air не затирает блоки модели — картинку можно
  поместить внутрь воксельной модели), экспорт одним .litematic.
- **Интерактивный 3D-превью** (three.js, офлайн-вендор): сцена на всё
  рабочее пространство, перетаскиваемые окна «Оригинал» и «Пикселизация»,
  сворачиваемое окно «Блоки». Детерминированная генерация (превью == файл).
- **UI**: RU/EN (автоопределение по языку системы), вкладки
  «Картинка» / «.vox» / «Сцена».

## Установка и запуск / Setup and Run

Требуется Python 3.14+ (проверено на 3.14). / Requires Python 3.14+ (tested on 3.14).

```bash
cd img2litematic
python -m venv .venv

# Windows:
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app.py

# Linux/macOS:
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Откройте http://127.0.0.1:5000 / Open http://127.0.0.1:5000.

### Как загрузить схему в Minecraft / Loading a schematic in Minecraft

1. Скачайте `.litematic` из приложения. / Download the `.litematic` from the app.
2. Положите в `%APPDATA%\.minecraft\schematics\` (Windows) или
   `~/.minecraft/schematics/` (Linux/macOS).
3. В игре с модом Litematica: `M` → Load Schematics → выбрать файл, вставить
   в мир (`M` → Schematic Placements). / In-game with Litematica: `M` →
   Load Schematics → choose the file, then paste it (`M` → Schematic Placements).

Нюанс: Litematica по умолчанию не заменяет блоки на air при вставке — включите
соответствующую опцию, если нужны пустоты. / Note: Litematica doesn't replace
blocks with air by default — enable that option if you need the empty spaces.

## Тесты / Tests

```bash
# Windows:
.venv\Scripts\python -m pytest
# Linux/macOS:
.venv/bin/python -m pytest
```

Round-trip тесты проверяют NBT независимым декодером (упаковка BlockStates для
размеров палитры 1–129, порядок индексов x→z→y), перекрёстно — nbtlib
(опционально), детерминизм k-means, API. / Round-trip tests validate the NBT
with an independent decoder (BlockStates packing for palette sizes 1–129,
x→z→y index order), cross-checked with nbtlib (optional), k-means determinism, API.

## Ограничения / Limitations

- Полупрозрачные пиксели композитируются на белый фон. / Semi-transparent
  pixels are composited onto a white background.
- Картинки меньше целевого размера не увеличиваются. / Images smaller than
  the target size are not upscaled.
- Часть палитры (deepslate, copper, amethyst) требует Minecraft ≥ 1.17. /
  Some palette blocks (deepslate, copper, amethyst) require Minecraft ≥ 1.17.
- Из .vox берётся первая модель (сцена nTRN игнорируется). / The first model
  of a .vox file is used (nTRN scene graph is ignored).

## Roadmap

См. / See [ROADMAP.md](ROADMAP.md) — экструзия, превью срезами, сцена nTRN.
