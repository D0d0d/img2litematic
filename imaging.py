"""Загрузка и подготовка изображений: alpha → белый фон, BOX-даунскейл, превью."""

from io import BytesIO

from PIL import Image


class ImageError(Exception):
    """Ошибка чтения изображения; code — машиночитаемый код для API."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def load_image(file_bytes: bytes) -> Image.Image:
    try:
        probe = Image.open(BytesIO(file_bytes))
        probe.verify()
        img = Image.open(BytesIO(file_bytes))
    except Exception:
        raise ImageError("invalid_image", "Не удалось прочитать изображение") from None
    return img


def ensure_rgb(img: Image.Image) -> Image.Image:
    """Приводит к RGB; полупрозрачные пиксели композитируются на белый фон."""
    if img.mode in ("RGBA", "LA", "PA", "P"):
        rgba = img.convert("RGBA")
        if rgba.getextrema()[3][0] < 255:  # есть прозрачность
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            rgba = Image.alpha_composite(bg, rgba)
        return rgba.convert("RGB")
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def downscale(img: Image.Image, target: int) -> Image.Image:
    """Уменьшает до target по большей стороне (BOX = средний цвет по группе пикселей).

    Изображения, не превышающие target, не увеличиваются.
    Может изменять img на месте (thumbnail) — caller использует возвращённый объект.
    """
    if max(img.size) <= target:
        return img
    if img.format == "JPEG" and max(img.size) > 4 * target:
        # черновой декодер: читаем JPEG сразу в уменьшенном виде
        img.draft("RGB", (4 * target, 4 * target))
        img = img.convert("RGB")
    img.thumbnail((target, target), Image.Resampling.BOX)
    return img


def pixels_scan_order(img: Image.Image) -> tuple[list[tuple[int, int, int]], int, int]:
    """Пиксели в порядке сканирования (row-major) + размеры."""
    w, h = img.size
    if hasattr(img, "get_flattened_data"):  # Pillow ≥ 12; getdata помечен deprecated
        return list(img.get_flattened_data()), w, h
    return list(img.getdata()), w, h


def render_preview_png(grid, palette_rgb, w: int, h: int) -> bytes:
    """PNG-превью результата (1 пиксель = 1 блок) для PreviewImageData."""
    img = Image.new("RGB", (w, h))
    img.putdata([palette_rgb[i] for i in grid])
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
