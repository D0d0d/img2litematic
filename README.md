# img2litematic

Локальное веб-приложение: картинки и воксельные модели → схемы Minecraft
Litematica (`.litematic`). 2D и 3D.

A local web app that turns images and voxel models into Minecraft Litematica
schematics (`.litematic`). 2D and 3D.

Документация: [🇷🇺 Русский](#-русский) · [🇬🇧 English](#-english)

---

## 🇷🇺 Русский

### Возможности

- **2D**: 1 пиксель = 1 блок, усреднение площади при масштабировании.
  Адаптивный constrained k-means (гарантированно ≤ K типов блоков) или
  полная палитра (81 блок), метрика CIELAB, дизеринг Floyd–Steinberg.
  Вертикальная картина или ковёр на полу.
- **Рельеф (3D)**: яркость → глубина/высота (сглаживание, инверсия), цветная
  поверхность из того же квантования, основание — выбранный блок, air в пустотах.
- **MagicaVoxel `.vox`**: воксельные модели → .litematic; палитра маппится
  на блоки через Lab-метрику (ближайший блок или ≤ K), пустые воксели → air.
- **Сцена-композиция**: рельеф и .vox как объекты одной сцены — смещения
  по X/Y/Z, режим «вживить» (air не затирает блоки модели — картинку можно
  поместить внутрь воксельной модели), экспорт одним .litematic.
- **Интерактивный 3D-превью** (three.js, офлайн-вендор): сцена занимает всё
  рабочее пространство; «Оригинал», «Пикселизация» и «Блоки» — перетаскиваемые
  окна. Детерминированная генерация: превью совпадает с файлом.
- **UI**: вкладки «Картинка» / «.vox» / «Сцена», языки RU/EN с автоопределением
  по системе.

### Установка и запуск

Требуется Python 3.14+.

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

Откройте http://127.0.0.1:5000.

### Загрузка схемы в Minecraft

1. Скачайте `.litematic` из приложения.
2. Положите в `%APPDATA%\.minecraft\schematics\` (Windows) или
   `~/.minecraft/schematics/` (Linux/macOS).
3. В игре с модом Litematica: `M` → Load Schematics → выберите файл,
   затем вставьте в мир (`M` → Schematic Placements).

Нюанс: Litematica по умолчанию не заменяет блоки на air при вставке —
включите соответствующую опцию, если нужны пустоты.

### Тесты

```bash
# Windows:
.venv\Scripts\python -m pytest
# Linux/macOS:
.venv/bin/python -m pytest
```

Round-trip тесты проверяют записанный NBT независимым декодером (упаковка
BlockStates для размеров палитры 1–129, порядок индексов x→z→y), перекрёстно —
библиотекой nbtlib (опционально); плюс детерминизм k-means и тесты API.

### Ограничения

- Полупрозрачные пиксели композитируются на белый фон.
- Картинки меньше целевого размера не увеличиваются.
- Часть палитры (deepslate, copper, amethyst) требует Minecraft ≥ 1.17.
- Из .vox берётся первая модель (сцена nTRN игнорируется).

### Планы

См. [ROADMAP.md](ROADMAP.md).

---

## 🇬🇧 English

### Features

- **2D**: 1 pixel = 1 block, area-averaged downscaling. Adaptive constrained
  k-means (guaranteed ≤ K block types) or the full palette (81 blocks),
  CIELAB color metric, Floyd–Steinberg dithering. Vertical picture or floor
  carpet orientation.
- **Relief (3D)**: brightness → depth/height (smoothing, invert), colored
  surface from the same quantization, a selectable base block, air in cavities.
- **MagicaVoxel `.vox`**: voxel models → .litematic; the palette is mapped to
  blocks via the Lab metric (nearest block or ≤ K), empty voxels → air.
- **Scene composition**: reliefs and .vox files as objects of one scene —
  X/Y/Z offsets, an «embed» mode (air doesn't erase model blocks, so a picture
  can be placed inside a voxel model), exported as a single .litematic.
- **Interactive 3D preview** (three.js, vendored for offline use): the scene
  fills the workspace; «Original», «Pixelization» and «Blocks» are draggable
  windows. Deterministic generation: the preview matches the file.
- **UI**: «Image» / «.vox» / «Scene» tabs, RU/EN languages auto-detected from
  the system locale.

### Setup and Run

Requires Python 3.14+.

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

Open http://127.0.0.1:5000.

### Loading a schematic in Minecraft

1. Download the `.litematic` from the app.
2. Put it into `%APPDATA%\.minecraft\schematics\` (Windows) or
   `~/.minecraft/schematics/` (Linux/macOS).
3. In-game with the Litematica mod: `M` → Load Schematics → choose the file,
   then paste it (`M` → Schematic Placements).

Note: Litematica does not replace blocks with air by default — enable that
option if you need the empty spaces.

### Tests

```bash
# Windows:
.venv\Scripts\python -m pytest
# Linux/macOS:
.venv/bin/python -m pytest
```

Round-trip tests validate the written NBT with an independent decoder
(BlockStates packing for palette sizes 1–129, x→z→y index order), cross-checked
with nbtlib (optional); plus k-means determinism and API tests.

### Limitations

- Semi-transparent pixels are composited onto a white background.
- Images smaller than the target size are not upscaled.
- Some palette blocks (deepslate, copper, amethyst) require Minecraft ≥ 1.17.
- The first model of a .vox file is used (the nTRN scene graph is ignored).

### Roadmap

See [ROADMAP.md](ROADMAP.md).
