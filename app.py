"""img2litematic — локальное веб-приложение: изображение → .litematic (2D).

Запуск: python app.py → http://127.0.0.1:5000
"""

import json
import re
import time
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

import config
from imaging import ImageError, downscale, ensure_rgb, load_image, render_preview_png
from litematic.writer import build_litematic_bytes
from palette import PALETTE, blocks_payload
from quantize import quantize

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH


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

    return {
        "mode": mode,
        "k": k,
        "orientation": orientation,
        "target": target,
        "timestamp_ms": ts,
        "dither": dither,
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


@app.post("/api/export")
def api_export():
    f = _get_file()
    params = _parse_params()
    try:
        result, img, _w0, _h0 = _convert(f.read(), params)
    except ImageError as e:
        raise ApiError(400, e.code, e.message)

    w, h = img.size
    if params["orientation"] == "vertical":
        size = (w, h, 1)
        # Строка 0 изображения — верх. В Minecraft Y растёт вверх, поэтому верхнюю
        # строку кладём на y = h−1, иначе Litematica вставит картинку вверх ногами.
        block_indices = [result.grid[(h - 1 - y) * w + x] for y in range(h) for x in range(w)]
    else:
        size = (w, 1, h)
        # grid построчно (x, y): строки изображения → ось z; индекс региона совпадает:
        # (0·h+z)·w + x = z·w + x
        block_indices = result.grid

    ts = params["timestamp_ms"] if params["timestamp_ms"] is not None else int(time.time() * 1000)
    stem = _sanitize_filename(Path(f.filename.replace("\\", "/")).stem)
    palette_names = [PALETTE[i].name for i in result.palette]
    preview = render_preview_png(
        result.grid, [PALETTE[i].rgb for i in result.palette], w, h
    )
    data = build_litematic_bytes(
        name=stem,
        description=(
            f"{w}×{h} mode={params['mode']} k={params['k']} "
            f"orientation={params['orientation']} dither={params['dither']} "
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
