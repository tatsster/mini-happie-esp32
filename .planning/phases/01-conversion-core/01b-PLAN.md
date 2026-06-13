---
wave: 2
depends_on: [01a-PLAN.md]
files_modified:
  - tests/__init__.py
  - tests/conftest.py
  - tests/test_converters.py
autonomous: true
requirements: [CONV-01, CONV-02, CONV-03, CONV-04]
---

# Plan 01b — tests/test_converters.py

## Goal
Create a pytest test suite that validates `server/converters.py` using fully synthetic fixtures (no binary test assets checked in). All test inputs are generated programmatically in `conftest.py` using PIL `ImageDraw`.

## Artifacts this phase produces

| Symbol | Location | Description |
|---|---|---|
| `solid_red_1x1_png` | `tests/conftest.py` | pytest fixture — 1×1 solid-red PNG bytes |
| `solid_green_1x1_png` | `tests/conftest.py` | pytest fixture — 1×1 solid-green PNG bytes |
| `solid_blue_1x1_png` | `tests/conftest.py` | pytest fixture — 1×1 solid-blue PNG bytes |
| `transparent_1x1_png` | `tests/conftest.py` | pytest fixture — 1×1 fully-transparent RGBA PNG bytes |
| `solid_128x160_png` | `tests/conftest.py` | pytest fixture — 128×160 solid-white PNG bytes |
| `small_png` | `tests/conftest.py` | pytest fixture — 32×32 PNG bytes (for resize test) |
| `happy_birthday_text` | `tests/conftest.py` | pytest fixture — reads assets/happy_birthday.txt as str |
| `TestConvertPng` | `tests/test_converters.py` | Test class for convert_png |
| `TestConvertSheet` | `tests/test_converters.py` | Test class for convert_sheet |
| `tests/__init__.py` | `tests/__init__.py` | Empty file enabling pytest discovery |

---

## Task 1 — Create tests/ scaffolding and conftest.py

<task id="01b-T1">
<title>Create tests/__init__.py and tests/conftest.py with synthetic PNG fixtures</title>

<read_first>
- server/converters.py (must exist from wave 1 — verify it's present)
- .planning/phases/01-conversion-core/01-RESEARCH.md — section on synthetic test fixtures
</read_first>

<action>
1. Create `tests/__init__.py` as an empty file.
2. Create `tests/conftest.py` with the following 7 pytest fixtures, all using `PIL.Image` + `io.BytesIO` (no files on disk):

   - `_png_bytes(img)` — private module-level helper that saves a PIL Image to an in-memory `BytesIO` buffer and returns the bytes.
   - `solid_red_1x1_png` — 1×1 RGB image filled with (255, 0, 0).
   - `solid_green_1x1_png` — 1×1 RGB image filled with (0, 255, 0).
   - `solid_blue_1x1_png` — 1×1 RGB image filled with (0, 0, 255).
   - `transparent_1x1_png` — 1×1 RGBA image filled with (0, 0, 0, 0) (fully transparent).
   - `solid_128x160_png` — 128×160 RGB image filled with white (255, 255, 255).
   - `small_png` — 32×32 RGB image filled with (100, 150, 200) (for resize testing).
   - `happy_birthday_text` — reads `assets/happy_birthday.txt` relative to the repo root and returns its contents as a `str` with `encoding="utf-8"`.

   Each fixture is decorated with `@pytest.fixture` and returns `bytes` (via `_png_bytes`) except `happy_birthday_text` which returns `str`. No fixture creates any file on disk.
</action>

<acceptance_criteria>
- `tests/__init__.py` exists (may be empty).
- `tests/conftest.py` exists and is importable by pytest without errors.
- All 7 fixtures are defined with `@pytest.fixture` decorator.
- `solid_red_1x1_png`, `solid_green_1x1_png`, `solid_blue_1x1_png`, `transparent_1x1_png` each return `bytes` objects representing valid 1×1 PNGs.
- `solid_128x160_png` returns `bytes` for a valid 128×160 PNG.
- `small_png` returns `bytes` for a valid 32×32 PNG.
- `happy_birthday_text` fixture returns the file content as `str`.
- No fixture creates files in the repository; all data is in-memory.
- Running `pytest tests/conftest.py --collect-only` exits with code 0.
</acceptance_criteria>
</task>

---

## Task 2 — Implement TestConvertPng

<task id="01b-T2">
<title>Write TestConvertPng tests in tests/test_converters.py</title>

<read_first>
- server/converters.py — function signatures and docstrings
- tests/conftest.py — fixture names
- .planning/phases/01-conversion-core/01-RESEARCH.md — spot-check values (red=0xF800, green=0x07E0, blue=0x001F)
</read_first>

<action>
Create `tests/test_converters.py`. Import `struct`, `pytest`, `convert_png`, and `convert_sheet` from `server.converters`. Implement the `TestConvertPng` class with the following 10 test methods:

- `test_red_pixel_rgb565(solid_red_1x1_png)` — asserts `convert_png(..., 1, 1) == b'\xf8\x00'` (0xF800 big-endian).
- `test_green_pixel_rgb565(solid_green_1x1_png)` — asserts result `== b'\x07\xe0'` (0x07E0).
- `test_blue_pixel_rgb565(solid_blue_1x1_png)` — asserts result `== b'\x00\x1f'` (0x001F).
- `test_output_length_default(solid_128x160_png)` — asserts `len(result) == 128 * 160 * 2`.
- `test_output_length_custom_dimensions(solid_128x160_png)` — calls with `width=64, height=80`; asserts `len == 64 * 80 * 2`.
- `test_resize_small_to_default(small_png)` — passes 32×32 PNG with default dims; asserts `len == 128 * 160 * 2`.
- `test_transparent_composites_to_black(transparent_1x1_png)` — asserts result `== b'\x00\x00'`.
- `test_big_endian_packing(solid_red_1x1_png)` — unpacks with `struct.unpack(">H", result)[0]` and asserts `== 0xF800`.
- `test_invalid_bytes_raises_value_error()` — passes `b"not a png"`; asserts `pytest.raises(ValueError, match="PNG conversion failed")`.
- `test_returns_bytes(solid_red_1x1_png)` — asserts `isinstance(result, bytes)`.
</action>

<acceptance_criteria>
- `TestConvertPng` class contains exactly the 10 test methods listed above.
- `test_red_pixel_rgb565` asserts `result == b'\xf8\x00'`.
- `test_green_pixel_rgb565` asserts `result == b'\x07\xe0'`.
- `test_blue_pixel_rgb565` asserts `result == b'\x00\x1f'`.
- `test_output_length_default` asserts `len(result) == 40960`.
- `test_transparent_composites_to_black` asserts `result == b'\x00\x00'`.
- `test_big_endian_packing` unpacks with `struct.unpack(">H", …)` and checks `== 0xF800`.
- `test_invalid_bytes_raises_value_error` uses `pytest.raises(ValueError, match="PNG conversion failed")`.
- All tests use fixtures defined in conftest.py (no hardcoded binary data inside test methods).
- Running `pytest tests/test_converters.py::TestConvertPng -v` passes all 10 tests.
</acceptance_criteria>
</task>

---

## Task 3 — Implement TestConvertSheet

<task id="01b-T3">
<title>Write TestConvertSheet tests in tests/test_converters.py</title>

<read_first>
- server/converters.py — convert_sheet signature, SEMITONES, DURATION_BEATS
- assets/happy_birthday.txt — 25 non-blank non-comment lines
- .planning/phases/01-conversion-core/01-CONTEXT.md — D-06 (120 BPM default)
</read_first>

<action>
Append the `TestConvertSheet` class to `tests/test_converters.py` with the following 13 test methods:

- `test_d4_quarter_at_120bpm()` — asserts `convert_sheet("D4 q\n", bpm=120.0) == [{"freq": 294, "ms": 500}]`.
- `test_rest_returns_freq_zero()` — asserts `convert_sheet("R e\n", bpm=120.0) == [{"freq": 0, "ms": 250}]`.
- `test_dotted_half_fsharp4()` — asserts `convert_sheet("F#4 h.\n", bpm=120.0) == [{"freq": 370, "ms": 1500}]`.
- `test_comments_and_blank_lines_ignored()` — passes `"# comment\n\nD4 q\n"`; asserts `len(notes) == 1` and `notes[0]["freq"] == 294`.
- `test_happy_birthday_note_count(happy_birthday_text)` — asserts `len(notes) == 25`.
- `test_happy_birthday_first_note(happy_birthday_text)` — asserts `notes[0] == {"freq": 294, "ms": 500}`.
- `test_default_bpm_is_120()` — calls `convert_sheet("D4 q\n")` with and without explicit `bpm=120.0`; asserts results are equal.
- `test_invalid_line_raises_value_error_with_line_number()` — passes `"BADLINE\n"`; asserts `pytest.raises(ValueError, match="Line 1")`.
- `test_unknown_duration_raises_value_error()` — passes `"D4 z\n"`; asserts `pytest.raises(ValueError, match="unknown duration")`.
- `test_missing_octave_raises_value_error()` — passes `"D q\n"`; asserts `pytest.raises(ValueError, match="Missing octave")`.
- `test_returns_list_of_dicts()` — asserts result is `list`, element is `dict` with keys `{"freq", "ms"}`, both values are `int`.
- `test_rest_lowercase()` — passes `"r q\n"`; asserts `notes[0]["freq"] == 0`.
- `test_semitones_module_level()` — imports `SEMITONES` and `DURATION_BEATS` from `server.converters`; asserts `len(SEMITONES) == 20`, `len(DURATION_BEATS) == 9`, `SEMITONES["C"] == 0`, `SEMITONES["A"] == 9`, `DURATION_BEATS["w"] == 4.0`, `DURATION_BEATS["s"] == 0.25`.
</action>

<acceptance_criteria>
- `TestConvertSheet` class contains exactly the 13 test methods listed above.
- `test_d4_quarter_at_120bpm` asserts `notes == [{"freq": 294, "ms": 500}]`.
- `test_rest_returns_freq_zero` asserts `notes == [{"freq": 0, "ms": 250}]`.
- `test_dotted_half_fsharp4` asserts `notes == [{"freq": 370, "ms": 1500}]`.
- `test_happy_birthday_note_count` asserts `len(notes) == 25`.
- `test_invalid_line_raises_value_error_with_line_number` uses `pytest.raises(ValueError, match="Line 1")`.
- `test_unknown_duration_raises_value_error` uses `pytest.raises(ValueError, match="unknown duration")`.
- `test_missing_octave_raises_value_error` uses `pytest.raises(ValueError, match="Missing octave")`.
- `test_semitones_module_level` asserts `len(SEMITONES) == 20` and `len(DURATION_BEATS) == 9`.
- Running `pytest tests/test_converters.py::TestConvertSheet -v` passes all 13 tests.
</acceptance_criteria>
</task>

---

## Verification

```bash
cd /path/to/repo
pip install Pillow>=10.0.0 pytest
pytest tests/test_converters.py -v --tb=short
```

Expected output: all 23 tests pass (10 in TestConvertPng + 13 in TestConvertSheet), 0 failures.

```bash
# Verify no binary test assets were created
ls tests/  # should only show __init__.py, conftest.py, test_converters.py
```

## must_haves

- All 23 tests pass with `pytest tests/test_converters.py -v`.
- No binary PNG files exist under `tests/` — all fixtures generate data in-memory.
- `conftest.py` defines all 7 fixtures using only `PIL.Image`, `io.BytesIO`, and `pathlib.Path`.
- Spot-check pixel values are hardcoded: red=`b'\xf8\x00'`, green=`b'\x07\xe0'`, blue=`b'\x00\x1f'`.
- `test_happy_birthday_note_count` asserts exactly 25 notes (matching the 25 non-blank non-comment lines in `assets/happy_birthday.txt`).
- `CONV-01` (PNG bytes → RGB565), `CONV-02` (sheet text → melody list), `CONV-03` (RGB565 formula verified by spot checks), `CONV-04` (no scripts/ import — verifiable by test import path `from server.converters import …`) all have test coverage.
