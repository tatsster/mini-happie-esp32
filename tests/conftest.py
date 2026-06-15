import io
from pathlib import Path

import pytest
from PIL import Image


def _png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def solid_red_1x1_png():
    img = Image.new("RGB", (1, 1), color=(255, 0, 0))
    return _png_bytes(img)


@pytest.fixture
def solid_green_1x1_png():
    img = Image.new("RGB", (1, 1), color=(0, 255, 0))
    return _png_bytes(img)


@pytest.fixture
def solid_blue_1x1_png():
    img = Image.new("RGB", (1, 1), color=(0, 0, 255))
    return _png_bytes(img)


@pytest.fixture
def transparent_1x1_png():
    img = Image.new("RGBA", (1, 1), color=(0, 0, 0, 0))
    return _png_bytes(img)


@pytest.fixture
def solid_128x160_png():
    img = Image.new("RGB", (128, 160), color=(255, 255, 255))
    return _png_bytes(img)


@pytest.fixture
def solid_jpeg():
    """A 300×400 JPEG — larger than 128×160 to exercise auto-resize."""
    img = Image.new("RGB", (300, 400), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def small_png():
    img = Image.new("RGB", (32, 32), color=(100, 150, 200))
    return _png_bytes(img)


@pytest.fixture
def happy_birthday_text():
    root = Path(__file__).parent.parent
    return (root / "assets" / "happy_birthday.txt").read_text(encoding="utf-8")
