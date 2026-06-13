---
phase: "01"
status: passed
must_haves_verified: 8/8
---

# Phase 01 Verification: Conversion Core

## Summary

All 8 must-haves verified against the implementation. The full 23-test suite passes with exit code 0; `server/converters.py` is a clean standalone module with no dependency on `scripts/`.

## Must-Haves Check

| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| 1 | `convert_png` accepts bytes, BytesIO, transparency compositing BEFORE `convert("RGB")`, LANCZOS resize, big-endian uint16 packing, returns bytes | ✓ PASS | `server/converters.py` lines 33-46: `Image.open(io.BytesIO(data))`, `Image.alpha_composite` before `.convert("RGB")`, `img.resize((width, height), Image.LANCZOS)`, `struct.pack(f">{width*height}H", *pixels)` |
| 2 | `convert_sheet` accepts str, returns `list[dict]` with `"freq"` and `"ms"` int keys, raises `ValueError` with line number for malformed input | ✓ PASS | `server/converters.py` lines 70-86: iterates `text.splitlines()` with 1-based `lineno`, raises `ValueError(f"Line {lineno}: ...")` for bad format/duration |
| 3 | No imports from `scripts/` in `server/converters.py` | ✓ PASS | `grep -r "from scripts" server/ tests/` returned nothing; top of `converters.py` imports only `io`, `struct`, `PIL.Image` |
| 4 | `server/__init__.py` exists | ✓ PASS | File present, 0 bytes — enables `from server.converters import …` |
| 5 | `server/requirements.txt` pins `Pillow>=10.0.0` | ✓ PASS | File contains exactly `Pillow>=10.0.0`; `Image.ANTIALIAS` not referenced (removed in Pillow 10) |
| 6 | All non-public helpers underscore-prefixed | ✓ PASS | `_rgb565`, `_note_to_freq`, `_beats_to_ms` — all helpers prefixed with `_`; only `convert_png`, `convert_sheet`, `SEMITONES`, `DURATION_BEATS` are public |
| 7 | All 23 tests pass | ✓ PASS | `python -m pytest tests/test_converters.py -v --tb=short` → exit 0, 23 passed (10 `TestConvertPng` + 13 `TestConvertSheet`) |
| 8 | No binary PNG files in `tests/` | ✓ PASS | `ls tests/` shows only `__init__.py`, `conftest.py`, `test_converters.py`; all fixtures generated in-memory via `PIL.Image` + `io.BytesIO` |

## Requirements Traceability

| Requirement | Status |
|-------------|--------|
| CONV-01 | ✓ Satisfied — `convert_png(data, 128, 160)` returns 40960 bytes of big-endian RGB565; verified by `test_output_length_default` and pixel spot-checks |
| CONV-02 | ✓ Satisfied (resize strategy, API layer enforces size) — per CONTEXT.md D-01, auto-resize replaces rejection; `convert_png` accepts any size and resizes to target; size enforcement deferred to Phase 2 API layer |
| CONV-03 | ✓ Satisfied — `convert_sheet(text)` returns `[{"freq": int, "ms": int}, ...]`; verified by `test_d4_quarter_at_120bpm`, `test_happy_birthday_note_count` (25 notes), and `test_returns_list_of_dicts` |
| CONV-04 | ✓ Satisfied — algorithm ported verbatim from `scripts/png_to_rgb565.py` (RGB565 formula, alpha compositing) and `scripts/sheet_music_to_melody.py` (SEMITONES, DURATION_BEATS, note/beat helpers); no cross-folder imports (standalone copy) |

## Test Results

```
23 passed  (exit code 0)

TestConvertPng (10 tests):
  test_red_pixel_rgb565               PASSED
  test_green_pixel_rgb565             PASSED
  test_blue_pixel_rgb565              PASSED
  test_output_length_default          PASSED
  test_output_length_custom_dimensions PASSED
  test_resize_small_to_default        PASSED
  test_transparent_composites_to_black PASSED
  test_big_endian_packing             PASSED
  test_invalid_bytes_raises_value_error PASSED
  test_returns_bytes                  PASSED

TestConvertSheet (13 tests):
  test_d4_quarter_at_120bpm           PASSED
  test_rest_returns_freq_zero         PASSED
  test_dotted_half_fsharp4            PASSED
  test_comments_and_blank_lines_ignored PASSED
  test_happy_birthday_note_count      PASSED
  test_happy_birthday_first_note      PASSED
  test_default_bpm_is_120             PASSED
  test_invalid_line_raises_value_error_with_line_number PASSED
  test_unknown_duration_raises_value_error PASSED
  test_missing_octave_raises_value_error PASSED
  test_returns_list_of_dicts          PASSED
  test_rest_lowercase                 PASSED
  test_semitones_module_level         PASSED
```

## Issues

None.
