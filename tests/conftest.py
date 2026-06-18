import io
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from PIL import Image


def _png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _wav_bytes(y: "np.ndarray", sr: int = 22050) -> bytes:
    """Write a float32 numpy array to WAV bytes via soundfile."""
    buf = io.BytesIO()
    sf.write(buf, y, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


@pytest.fixture
def sine_wav():
    """2-second 440 Hz sine wave — is_complex: false (flatness ~0.0)."""
    sr = 22050
    t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
    return _wav_bytes(np.sin(2 * np.pi * 440 * t).astype(np.float32), sr)


@pytest.fixture
def noise_wav():
    """2-second white noise — is_complex: true (flatness ~0.56 >> threshold 0.15). Seeded for reproducibility."""
    sr = 22050
    rng = np.random.default_rng(42)
    return _wav_bytes((rng.standard_normal(int(sr * 2.0)) * 0.5).astype(np.float32), sr)


@pytest.fixture
def short_wav():
    """0.1-second 440 Hz sine — below the 1.0 s minimum duration threshold."""
    sr = 22050
    t = np.linspace(0, 0.1, int(sr * 0.1), endpoint=False)
    return _wav_bytes(np.sin(2 * np.pi * 440 * t).astype(np.float32), sr)


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


