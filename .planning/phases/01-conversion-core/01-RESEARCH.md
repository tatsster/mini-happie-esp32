## RESEARCH COMPLETE

**Phase:** 1 — Conversion Core
**Research date:** 2026-06-13
**Sources:** existing scripts, planning context, Pillow 10.x API

---

### Stack

**Python:** 3.11+ recommended (matches modern FastAPI requirements in later phases; walrus operator, `list[dict]` return type hints native)

**Pillow:** Pin to `Pillow>=10.0.0`. Key API change in 10.0.0:
- `Image.ANTIALIAS` was **removed** (deprecated since 9.1.0) — use `Image.LANCZOS` or the enum form `Image.Resampling.LANCZOS`
- `Image.LANCZOS` (module-level alias) still works in Pillow 10.x and is the idiomatic short form
- `Image.Resampling.LANCZOS` is the enum form, more explicit for linting, same value

**No other dependencies** for `converters.py` — just `Pillow`. The sheet converter is pure Python.

---

### PIL Conversion Pattern

Exact pattern for `convert_png(data: bytes, width: int = 128, height: int = 160) -> bytes`:

```python
import io
import struct
from PIL import Image

def _rgb565(r: int, g: int, b: int) -> int:
    # Copied from scripts/png_to_rgb565.py — preserves exact bit layout
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def convert_png(data: bytes, width: int = 128, height: int = 160) -> bytes:
    try:
        img = Image.open(io.BytesIO(data))
    except Exception as exc:
        raise ValueError(f"Cannot decode PNG: {exc}") from exc

    # Step 1: handle transparency (composite onto black background)
    # Must happen BEFORE convert("RGB") so alpha channel is preserved
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
        img = Image.alpha_composite(bg, img.convert("RGBA"))

    # Step 2: normalize to RGB (drops alpha if still present)
    img = img.convert("RGB")

    # Step 3: resize AFTER RGB conversion — more efficient (3 channels vs 4)
    if img.size != (width, height):
        img = img.resize((width, height), Image.LANCZOS)

    # Step 4: emit big-endian RGB565 binary
    w, h = img.size
    pixels = [_rgb565(*img.getpixel((x, y))) for y in range(h) for x in range(w)]
    return struct.pack(f">{len(pixels)}H", *pixels)
```

**Why this order matters:**
- Composite BEFORE `convert("RGB")` — once you drop to RGB, alpha data is lost. Palette images ("P") may carry transparent index info that only survives through `convert("RGBA")`.
- Resize AFTER `convert("RGB")` — LANCZOS resampling on 3-channel RGB is faster than 4-channel RGBA and avoids re-handling any alpha artifacts post-resize.

**`getpixel` vs `getdata()` vs `tobytes()`:**
- `getpixel((x, y))` in a nested loop matches the existing script exactly; fine for 128×160 (20 480 calls)
- `list(img.getdata())` is faster (single call returns all (r,g,b) tuples) and equally readable:
  ```python
  pixels = [_rgb565(r, g, b) for r, g, b in img.getdata()]
  ```
  Either works; `getdata()` is ~3× faster for large images.

---

### RGB565 Byte Order

**Why big-endian for the binary file:**

The ESP32 (Xtensa LX6, little-endian) will read the binary file into a `uint8_t` buffer and cast/pass it to `tft.pushImage()`. TFT_eSPI with `setSwapBytes(true)` expects the pixel data to arrive in **display-wire order** (big-endian): MSB first (`RRRRRGG G` byte, then `GGGBBBBB` byte).

For a pure red pixel:
- RGB565 value: `0xF800`
- Big-endian bytes in file: `0xF8, 0x00` ← correct; display receives red
- Little-endian bytes in file: `0x00, 0xF8` ← display sees garbage color

**Packing with `struct`** (platform-independent):
```python
struct.pack(f">{len(pixels)}H", *pixels)
# ">" = big-endian, "H" = unsigned 16-bit
```

This is the same byte order as the existing C headers (values stored as `0xRRRR` hex literals, which the ESP32 reads with `setSwapBytes(true)` to produce correct colors).

**Output size assertion:** for default 128×160, output must be exactly `128 * 160 * 2 = 40 960` bytes. This is a good post-condition assertion in tests.

---

### Testing Approach

**Directory layout:**
```
server/
    __init__.py       # empty — makes server/ a package for clean imports
    converters.py
tests/
    conftest.py       # shared fixtures
    test_converters.py
requirements.txt      # Pillow>=10.0.0
requirements-dev.txt  # pytest>=8.0, pillow (inherited)
```

**Why `server/__init__.py`:** lets tests do `from server.converters import convert_png` when pytest is run from the repo root. Without it, you'd need `sys.path` hacks.

**conftest.py fixture strategy — synthetic generation (preferred over pre-baked binary files):**

Rationale: synthetic fixtures are self-describing, reproducible, editable, and have no binary diff noise in git.

```python
# tests/conftest.py
import io
import pytest
from PIL import Image

def _make_png(size=(128, 160), mode="RGB", color=(255, 0, 0)) -> bytes:
    img = Image.new(mode, size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

@pytest.fixture
def png_128x160_rgb():
    return _make_png()

@pytest.fixture
def png_200x200_rgb():
    return _make_png(size=(200, 200))

@pytest.fixture
def png_rgba():
    # Semi-transparent red — tests alpha compositing
    return _make_png(mode="RGBA", color=(255, 0, 0, 128))

@pytest.fixture
def png_palette():
    # Palette mode — tests "P" branch
    img = Image.new("RGB", (128, 160), color=(0, 255, 0))
    img = img.convert("P")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

@pytest.fixture
def happy_birthday_sheet():
    # Read the actual asset — canonical test fixture for convert_sheet()
    from pathlib import Path
    return Path("assets/happy_birthday.txt").read_text(encoding="utf-8")
```

**Parametrize pattern for mode coverage:**
```python
@pytest.mark.parametrize("mode,color", [
    ("RGB",  (255,   0,   0)),
    ("RGBA", (255,   0,   0, 200)),
    ("L",    128),
])
def test_convert_png_image_modes(mode, color):
    img = Image.new(mode, (128, 160), color=color)
    buf = io.BytesIO(); img.save(buf, format="PNG")
    result = convert_png(buf.getvalue())
    assert len(result) == 40960
```

---

### Edge Cases

#### `convert_png` edge cases

| Case | Expected behavior | How to test |
|---|---|---|
| Non-PNG bytes (e.g. `b"garbage"`) | `ValueError` with message | `pytest.raises(ValueError)` |
| Empty bytes `b""` | `ValueError` | same |
| PNG of wrong size (e.g. 200×200) | Auto-resize → still 40 960 bytes output | assert `len(result) == 128*160*2` |
| RGBA with partial transparency | Composited onto black, correct byte count | pixel-value spot check on known color |
| Palette mode "P" | Handled by `img.convert("RGBA")` path, no crash | assert `len(result) == 40960` |
| Grayscale "L" mode | `convert("RGB")` works directly (no alpha branch needed) | assert byte count |
| Already 128×160 | No resize called; fast path | assert byte count |
| 1×1 single pixel | Resize up; assert byte count = 40 960 | assert |
| Pixel value verification | Solid red 128×160 → first two bytes should be `0xF8, 0x00` | `assert result[:2] == bytes([0xF8, 0x00])` |

#### `convert_sheet` edge cases

| Case | Expected behavior | How to test |
|---|---|---|
| Valid `happy_birthday.txt` | Returns non-empty list of `{"freq": int, "ms": int}` | assert len, assert keys |
| Empty string `""` | Returns `[]` | direct assert |
| Comment-only input `"# comment\n"` | Returns `[]` | direct assert |
| Unknown note name `"X4 q"` | `ValueError` containing note name | `pytest.raises(ValueError, match="X4")` |
| Unknown duration `"D4 z"` | `ValueError` containing duration | `pytest.raises(ValueError, match="z")` |
| Missing octave `"D q"` | `ValueError` about missing octave | `pytest.raises(ValueError)` |
| Line with 3 parts `"D4 q extra"` | `ValueError` about wrong format | `pytest.raises(ValueError)` |
| Rest note `"R q"` | `{"freq": 0, "ms": 500}` at 120 BPM | spot check |
| Custom BPM `bpm=60` | `ms` values doubled vs `bpm=120` | compare with known calculation |
| Dotted duration `"D4 q."` | `ms` = 750 at 120 BPM (1.5 beats × 500 ms/beat) | assert value |
| All enharmonic equivalents | `Bb4`, `A#4` → same freq | assert equal |

**Regression: `"R"` vs `"R4"` — the existing `note_to_freq()` handles `"R"` without octave (returns 0). `"R4"` would fail because "R" is not in SEMITONES but note_str.upper() == "R" is checked first. Verify this path.**

---

### Implementation Notes

#### REQUIREMENTS.md vs CONTEXT.md conflict — MUST resolve before planning

`REQUIREMENTS.md` CONV-02 says: *"Server rejects PNG uploads that are not exactly 128×160 with a descriptive error"*

`CONTEXT.md` D-01/D-02 say: *"Auto-resize to target dimensions — do NOT reject non-matching sizes"*

`ROADMAP.md` Phase 1 success criterion #2 says: *"raises a descriptive ValueError for PNG with any other dimensions"*

**The task description (from the phase objective) says auto-resize.** The CONTEXT.md represents the latest decision made during discuss-phase and supersedes the original REQUIREMENTS.md. **The plan should implement auto-resize (CONTEXT.md wins), and should explicitly note that CONV-02 needs to be updated in REQUIREMENTS.md and ROADMAP.md to reflect the auto-resize decision.**

#### `io.BytesIO` is required

The existing `png_to_rgb565.py` uses `Image.open(src)` with a file path. The new `convert_png` receives `bytes` — use `Image.open(io.BytesIO(data))` to open from memory. This is the standard Pillow pattern.

#### `Image.LANCZOS` vs `Image.Resampling.LANCZOS`

Both work in Pillow 10.x. `Image.LANCZOS` is still the short form alias. Use it. If you want forward compatibility beyond Pillow 10, `Image.Resampling.LANCZOS` is the canonical enum.

#### `parse_sheet` API change: Path → str

`scripts/sheet_music_to_melody.py::parse_sheet(path: Path, bpm)` does `path.read_text(...)` and `path.read_text(...).splitlines()`. The new `convert_sheet(text: str, bpm: float)` receives the string directly. Adapt the inner loop to iterate over `text.splitlines()`.

#### `note_to_freq` is a pure function

It has no I/O or global state — lift it verbatim into `converters.py`. Same for `beats_to_ms`, `SEMITONES`, and `DURATION_BEATS`.

#### Error wrapping strategy

Wrap `Image.open()` errors in `ValueError` (not PIL exceptions) so callers (Phase 2 FastAPI handlers) get a consistent exception type they can map to HTTP 400. Same for all `parse_sheet` errors — already `ValueError` in the original.

#### `server/__init__.py` must exist

Without it, `from server.converters import convert_png` works only if `server/` is on `sys.path` directly. With `__init__.py`, the import works when pytest runs from the repo root (which adds `.` to sys.path automatically).

#### `requirements.txt` location

Place at `server/requirements.txt` (not repo root) since Phase 4 will Dockerize only the `server/` directory. Content:
```
Pillow>=10.0.0
```

Dev requirements at repo root `requirements-dev.txt`:
```
Pillow>=10.0.0
pytest>=8.0
```

#### `struct.pack` performance

For 128×160 = 20 480 pixels, `struct.pack(f">{n}H", *pixels)` with `n=20480` is fast (sub-millisecond). The list comprehension for pixel extraction is the bottleneck if it matters — `img.getdata()` is meaningfully faster than the loop + `getpixel()` approach. Either is fine for the test suite.

#### Happy birthday fixture

`assets/happy_birthday.txt` has 24 note lines + comment lines. The expected output from `convert_sheet()` at BPM=120 is 24 dicts. Use this as the canonical integration test for `convert_sheet()`: count = 24, all keys present, rest notes have freq=0.

The file uses `e` (eighth) and `q.` (dotted quarter) durations — good coverage of the non-trivial duration codes.

---

*Research status: complete — ready for planning*
