"""img2litematic — локальное веб-приложение: изображение → .litematic (2D).

Запуск: python app.py → http://127.0.0.1:5000
"""

import base64
import json
import re
import time
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

import config
from imaging import ImageError, downscale, ensure_rgb, load_image, render_preview_png
from litematic.writer import build_litematic_bytes
from palette import PALETTE, block_name, block_rgb, blocks_payload
from quantize import quantize
from relief import build_relief
from vox import VoxError, build_vox

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

_PALETTE_NAMES = {b.name for b in PALETTE}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


@app.errorhandler(ApiError)
def _handle_api_error(e: ApiError):
    return jsonify(error=e.message, code=e.code), e.status


@app.errorhandler(413)
def _handle_413(e):
    return jsonify(error="Файл слишком большой", code="image_too_large"), 413


@app.errorhandler(500)
def _handle_500(e):
    return jsonify(error="Внутренняя ошибка сервера", code="internal"), 500


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/blocks")
def api_blocks():
    return jsonify(blocks=blocks_payload())


def _parse_params() -> dict:
    raw = request.form.get("params", "")
    try:
        p = json.loads(raw)
        if not isinstance(p, dict):
            raise ValueError
    except ValueError:
        raise ApiError(400, "invalid_params", "params должен быть JSON-объектом")

    mode = p.get("mode")
    if mode not in ("adaptive", "palette"):
        raise ApiError(400, "invalid_params", "mode должен быть adaptive или palette")

    k = p.get("k", config.DEFAULT_K)
    if not isinstance(k, int) or isinstance(k, bool) or not (config.MIN_K <= k <= config.MAX_K):
        raise ApiError(
            400, "invalid_params", f"k должен быть целым в диапазоне {config.MIN_K}..{config.MAX_K}"
        )

    orientation = p.get("orientation", "vertical")
    if orientation not in ("vertical", "floor"):
        raise ApiError(400, "invalid_params", "orientation должен быть vertical или floor")

    target = p.get("target", config.DEFAULT_TARGET)
    if not isinstance(target, int) or isinstance(target, bool) or not (
        config.MIN_TARGET <= target <= config.MAX_TARGET
    ):
        raise ApiError(
            400,
            "invalid_params",
            f"target должен быть целым в диапазоне {config.MIN_TARGET}..{config.MAX_TARGET}",
        )

    ts = p.get("timestamp_ms")
    if ts is not None and (not isinstance(ts, int) or isinstance(ts, bool) or ts < 0):
        raise ApiError(400, "invalid_params", "timestamp_ms должен быть целым ≥ 0 или отсутствовать")

    dither = p.get("dither", False)
    if not isinstance(dither, bool):
        raise ApiError(400, "invalid_params", "dither должен быть true или false")

    relief = p.get("relief", False)
    if not isinstance(relief, bool):
        raise ApiError(400, "invalid_params", "relief должен быть true или false")

    max_height = p.get("max_height", config.DEFAULT_MAX_HEIGHT)
    if not isinstance(max_height, int) or isinstance(max_height, bool) or not (
        config.MIN_MAX_HEIGHT <= max_height <= config.MAX_MAX_HEIGHT
    ):
        raise ApiError(
            400,
            "invalid_params",
            f"max_height должен быть целым в диапазоне {config.MIN_MAX_HEIGHT}..{config.MAX_MAX_HEIGHT}",
        )

    smoothing = p.get("smoothing", config.DEFAULT_SMOOTHING)
    if (
        not isinstance(smoothing, (int, float))
        or isinstance(smoothing, bool)
        or not (0 <= smoothing <= config.MAX_SMOOTHING)
    ):
        raise ApiError(
            400, "invalid_params", f"smoothing должен быть числом 0..{config.MAX_SMOOTHING}"
        )

    invert = p.get("invert", False)
    if not isinstance(invert, bool):
        raise ApiError(400, "invalid_params", "invert должен быть true или false")

    base_block = p.get("base_block", config.DEFAULT_BASE_BLOCK)
    if base_block not in _PALETTE_NAMES:
        raise ApiError(400, "invalid_params", f"неизвестный base_block: {base_block}")

    return {
        "mode": mode,
        "k": k,
        "orientation": orientation,
        "target": target,
        "timestamp_ms": ts,
        "dither": dither,
        "relief": relief,
        "max_height": max_height,
        "smoothing": smoothing,
        "invert": invert,
        "base_block": base_block,
    }


def _convert(file_bytes: bytes, params: dict):
    """Общий пайплайн обоих POST-эндпоинтов: load → RGB → лимит → downscale → quantize.

    Возвращает (result, img, source_w, source_h).
    """
    img = load_image(file_bytes)
    w0, h0 = img.size
    if w0 * h0 > config.MAX_SOURCE_PIXELS:
        raise ApiError(
            400, "image_too_large", f"Изображение слишком большое ({w0}×{h0}, максимум 40 Мп)"
        )
    img = ensure_rgb(img)
    img = downscale(img, params["target"])
    if params["relief"]:
        w, h = img.size
        if w * h * params["max_height"] > config.MAX_RELIEF_VOLUME:
            raise ApiError(
                400,
                "volume_too_large",
                f"Объём рельефа {w}×{h}×{params['max_height']} превышает лимит "
                f"({config.MAX_RELIEF_VOLUME} блоков)",
            )
        result = build_relief(
            img,
            params["mode"],
            params["k"],
            dither=params["dither"],
            max_height=params["max_height"],
            smoothing=params["smoothing"],
            invert=params["invert"],
            base_block=params["base_block"],
            orientation=params["orientation"],
        )
    else:
        result = quantize(img, params["mode"], params["k"], dither=params["dither"])
    return result, img, w0, h0


def _sanitize_filename(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9 _.\-]", "", s).strip(" .")
    return s or "schematic"


def _get_file():
    f = request.files.get("image")
    if f is None or f.filename == "":
        raise ApiError(400, "missing_file", "Не передан файл изображения (поле image)")
    return f


@app.post("/api/convert")
def api_convert():
    f = _get_file()
    params = _parse_params()
    try:
        result, img, w0, h0 = _convert(f.read(), params)
    except ImageError as e:
        raise ApiError(400, e.code, e.message)
    w, h = img.size
    if params["relief"]:
        palette = [
            {
                "name": block_name(result.palette[i]),
                "color": list(block_rgb(result.palette[i])),
                "count": result.counts[i],
            }
            for i in range(len(result.palette))
        ]
        return jsonify(
            relief=True,
            width=w,
            height=h,
            maxHeight=result.depth,
            orientation=params["orientation"],
            mode=params["mode"],
            kRequested=params["k"],
            dither=params["dither"],
            effectiveK=result.effective_k,
            surfaceGrid=result.surface_grid,
            palette=palette,
            preview=base64.b64encode(result.preview_png).decode("ascii"),
            stats={"totalBlocks": result.volume, "filledBlocks": result.total_filled,
                   "distinctBlocks": result.effective_k, "sourceSize": [w0, h0]},
        )
    counts = {}
    for g in result.grid:
        counts[g] = counts.get(g, 0) + 1
    palette = [
        {
            "name": PALETTE[result.palette[i]].name,
            "color": list(PALETTE[result.palette[i]].rgb),
            "count": counts[i],
        }
        for i in range(len(result.palette))
    ]
    return jsonify(
        width=w,
        height=h,
        orientation=params["orientation"],
        mode=params["mode"],
        kRequested=params["k"],
        dither=params["dither"],
        effectiveK=result.effective_k,
        grid=result.grid,
        palette=palette,
        stats={"totalBlocks": len(result.grid), "distinctBlocks": result.effective_k,
               "sourceSize": [w0, h0]},
    )


@app.post("/api/vox")
def api_vox():
    """Конвертация MagicaVoxel .vox → превью (экспорт — через /api/export)."""
    f = request.files.get("vox")
    if f is None or f.filename == "":
        raise ApiError(400, "missing_file", "Не передан файл .vox (поле vox)")
    params = _parse_params()
    try:
        result = build_vox(f.read(), params["mode"], params["k"])
    except VoxError as e:
        raise ApiError(400, e.code, e.message)
    palette = [
        {
            "name": block_name(result.palette[i]),
            "color": list(block_rgb(result.palette[i])),
            "count": result.counts[i],
        }
        for i in range(len(result.palette))
    ]
    return jsonify(
        vox=True,
        width=result.size[0],
        height=result.size[1],
        depth=result.size[2],
        mode=params["mode"],
        kRequested=params["k"],
        effectiveK=result.effective_k,
        palette=palette,
        preview=base64.b64encode(result.preview_png).decode("ascii"),
        previewWidth=result.preview_size[0],
        previewHeight=result.preview_size[1],
        stats={"totalBlocks": result.volume, "filledBlocks": result.total_filled,
               "distinctBlocks": result.effective_k, "sourceSize": list(result.source_size)},
    )


@app.post("/api/export")
def api_export():
    vox_file = request.files.get("vox")
    if vox_file is not None and vox_file.filename != "":
        params = _parse_params()
        try:
            result = build_vox(vox_file.read(), params["mode"], params["k"])
        except VoxError as e:
            raise ApiError(400, e.code, e.message)
        ts = params["timestamp_ms"] if params["timestamp_ms"] is not None else int(time.time() * 1000)
        stem = _sanitize_filename(Path(vox_file.filename.replace("\\", "/")).stem)
        data = build_litematic_bytes(
            name=stem,
            description=(
                f"vox {result.source_size[0]}×{result.source_size[1]}×{result.source_size[2]} "
                f"mode={params['mode']} k={params['k']} — generated by img2litematic"
            ),
            author=config.AUTHOR,
            size=result.size,
            palette_names=[block_name(i) for i in result.palette],
            block_indices=result.grid,
            created_ms=ts,
            modified_ms=ts,
            preview_png=result.preview_png,
            region_name=config.REGION_NAME,
            data_version=config.MINECRAFT_DATA_VERSION,
        )
        return Response(
            data,
            mimetype="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{stem}.litematic"'},
        )
    f = _get_file()
    params = _parse_params()
    try:
        result, img, _w0, _h0 = _convert(f.read(), params)
    except ImageError as e:
        raise ApiError(400, e.code, e.message)

    w, h = img.size
    if params["relief"]:
        size = result.size
        block_indices = result.grid
        palette_names = [block_name(i) for i in result.palette]
        preview = result.preview_png
    elif params["orientation"] == "vertical":
        size = (w, h, 1)
        # Строка 0 изображения — верх. В Minecraft Y растёт вверх, поэтому верхнюю
        # строку кладём на y = h−1, иначе Litematica вставит картинку вверх ногами.
        block_indices = [result.grid[(h - 1 - y) * w + x] for y in range(h) for x in range(w)]
        palette_names = [PALETTE[i].name for i in result.palette]
        preview = render_preview_png(
            result.grid, [PALETTE[i].rgb for i in result.palette], w, h
        )
    else:
        size = (w, 1, h)
        # grid построчно (x, y): строки изображения → ось z; индекс региона совпадает:
        # (0·h+z)·w + x = z·w + x
        block_indices = result.grid
        palette_names = [PALETTE[i].name for i in result.palette]
        preview = render_preview_png(
            result.grid, [PALETTE[i].rgb for i in result.palette], w, h
        )

    ts = params["timestamp_ms"] if params["timestamp_ms"] is not None else int(time.time() * 1000)
    stem = _sanitize_filename(Path(f.filename.replace("\\", "/")).stem)
    relief_desc = ""
    if params["relief"]:
        relief_desc = (
            f" relief max_height={params['max_height']} smoothing={params['smoothing']} "
            f"invert={params['invert']} base={params['base_block']}"
        )
    data = build_litematic_bytes(
        name=stem,
        description=(
            f"{w}×{h} mode={params['mode']} k={params['k']} "
            f"orientation={params['orientation']} dither={params['dither']}{relief_desc} "
            f"— generated by img2litematic"
        ),
        author=config.AUTHOR,
        size=size,
        palette_names=palette_names,
        block_indices=block_indices,
        created_ms=ts,
        modified_ms=ts,
        preview_png=preview,
        region_name=config.REGION_NAME,
        data_version=config.MINECRAFT_DATA_VERSION,
    )
    return Response(
        data,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{stem}.litematic"'},
    )


if __name__ == "__main__":
    print(f"img2litematic: http://127.0.0.1:{config.PORT}")
    app.run(host="127.0.0.1", port=config.PORT, threaded=True)
