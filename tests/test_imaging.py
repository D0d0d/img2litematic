"""Тесты загрузки, alpha-композита, BOX-даунскейла и PNG-превью."""

from io import BytesIO

import pytest
from PIL import Image

from imaging import ImageError, downscale, ensure_rgb, load_image, render_preview_png


class TestLoad:
    def test_valid(self):
        buf = BytesIO()
        Image.new("RGB", (8, 8)).save(buf, format="PNG")
        assert load_image(buf.getvalue()).size == (8, 8)

    def test_invalid(self):
        with pytest.raises(ImageError) as ei:
            load_image(b"not an image at all")
        assert ei.value.code == "invalid_image"


class TestEnsureRgb:
    def test_rgba_semialpha(self):
        img = Image.new("RGBA", (1, 1), (255, 0, 0, 128))
        out = ensure_rgb(img)
        assert out.mode == "RGB"
        assert out.getpixel((0, 0)) == (255, 127, 127)

    def test_rgba_transparent(self):
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        assert ensure_rgb(img).getpixel((0, 0)) == (255, 255, 255)

    def test_rgba_opaque(self):
        img = Image.new("RGBA", (1, 1), (255, 0, 0, 255))
        assert ensure_rgb(img).getpixel((0, 0)) == (255, 0, 0)

    @pytest.mark.parametrize("mode", ["L", "LA", "P", "CMYK"])
    def test_conversions(self, mode):
        img = Image.new("RGB", (2, 2), (128, 128, 128)).convert(mode)
        assert ensure_rgb(img).mode == "RGB"


class TestDownscale:
    def test_box_average(self, quadrants_img):
        out = downscale(quadrants_img, 2)
        assert out.size == (2, 2)
        assert out.getpixel((0, 0)) == (255, 0, 0)
        assert out.getpixel((1, 0)) == (0, 255, 0)
        assert out.getpixel((0, 1)) == (0, 0, 255)
        assert out.getpixel((1, 1)) == (255, 255, 0)

    def test_aspect_ratio(self):
        assert downscale(Image.new("RGB", (100, 50)), 64).size == (64, 32)

    def test_no_upscale(self):
        assert downscale(Image.new("RGB", (20, 10)), 128).size == (20, 10)

    def test_1x1(self):
        assert downscale(Image.new("RGB", (1, 1)), 16).size == (1, 1)

    def test_jpeg_draft(self):
        img = Image.new("RGB", (1600, 800))
        px = img.load()
        for y in range(0, 800, 50):
            for x in range(1600):
                px[x, y] = (255, 0, 0)
        buf = BytesIO()
        img.save(buf, format="JPEG")
        jpg = load_image(buf.getvalue())
        assert jpg.format == "JPEG"
        assert downscale(jpg, 64).size == (64, 32)


class TestPreviewPng:
    def test_preview(self):
        png = render_preview_png([0, 1, 1, 0], [(255, 0, 0), (0, 0, 255)], 2, 2)
        img = Image.open(BytesIO(png))
        assert img.size == (2, 2)
        assert img.getpixel((0, 0)) == (255, 0, 0)
        assert img.getpixel((1, 0)) == (0, 0, 255)
        assert img.getpixel((0, 1)) == (0, 0, 255)
        assert img.getpixel((1, 1)) == (255, 0, 0)
