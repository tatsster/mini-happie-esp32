# Phase 1: Conversion Core - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract the PNG→RGB565 and sheet-music→melody conversion logic into a standalone `server/converters.py` Python module with clean, importable function signatures. No HTTP, no UI — pure conversion logic with tests.

</domain>

<decisions>
## Implementation Decisions

### Image Conversion

- **D-01:** Auto-resize to target dimensions using PIL `Image.resize()` with `Image.LANCZOS` resampling — do NOT reject non-matching sizes
- **D-02:** Resize mode is **stretch to fill** — no letterbox, no crop; exact pixel count is required for the display
- **D-03:** Default target dimensions: `width=128, height=160` (1.8" ST7735); user can pass different values per upload for other screen sizes
- **D-04:** Transparent PNGs: composite onto black background before conversion (same behavior as existing `scripts/png_to_rgb565.py`)
- **D-05:** Function signature: `convert_png(data: bytes, width: int = 128, height: int = 160) -> bytes`
  - Input: raw PNG file bytes
  - Output: raw big-endian RGB565 binary (`width * height * 2` bytes)

### Song Conversion

- **D-06:** BPM is **fixed at 120** — no user-facing BPM control in this milestone (can be added to upload form in a future iteration)
- **D-07:** Function signature: `convert_sheet(text: str, bpm: float = 120.0) -> list[dict]`
  - Input: song sheet text content (same format as `assets/happy_birthday.txt`)
  - Output: `[{"freq": int, "ms": int}, ...]` — JSON-serializable list of note dicts
- **D-08:** Rest notes use `{"freq": 0, "ms": N}` (matches existing `note_to_freq()` behavior for "R")

### Code Structure

- **D-09:** `server/converters.py` is a **standalone module** — copy and adapt the conversion logic from `scripts/`, no cross-folder imports
- **D-10:** The existing CLI scripts in `scripts/` remain untouched — they serve a different purpose (generating C headers)
- **D-11:** `server/converters.py` exposes exactly two public functions: `convert_png()` and `convert_sheet()`; all helpers are module-private

### Claude's Discretion

- Testing setup: pytest, location of test fixtures, parameterization approach — Claude decides
- Internal helper structure within `server/converters.py` — Claude decides
- Error types: `ValueError` with descriptive messages for malformed input — standard, Claude decides

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing conversion scripts (adapt logic from these)
- `scripts/png_to_rgb565.py` — RGB565 pixel conversion formula (`rgb565(r,g,b)`), transparency compositing pattern, PIL usage
- `scripts/sheet_music_to_melody.py` — `SEMITONES` table, `DURATION_BEATS` table, `note_to_freq()`, `beats_to_ms()`, `parse_sheet()` — adapt these for string input instead of file path

### Requirements
- `.planning/REQUIREMENTS.md` — CONV-01 through CONV-04 define the acceptance criteria for this phase

### Sample assets (use as test fixtures)
- `assets/happy_birthday.txt` — canonical song sheet format; use as test input for `convert_sheet()`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/png_to_rgb565.py::rgb565(r, g, b) -> int` — exact formula to copy into converters.py: `((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)`
- `scripts/sheet_music_to_melody.py::SEMITONES` dict — complete semitone table including enharmonics; copy as-is
- `scripts/sheet_music_to_melody.py::DURATION_BEATS` dict — all duration codes (w, h, q, e, s + dotted variants); copy as-is
- `scripts/sheet_music_to_melody.py::note_to_freq()` and `beats_to_ms()` — pure functions, no file I/O; lift directly
- `scripts/sheet_music_to_melody.py::parse_sheet(path, bpm)` — adapt to `parse_sheet(text: str, bpm: float)` (take string instead of Path)

### Established Patterns
- PIL `Image.alpha_composite()` for transparent PNG handling — copy pattern from `scripts/png_to_rgb565.py` lines 20–23
- PIL `Image.open(io.BytesIO(data))` — standard pattern for opening PNG from bytes in memory (instead of file path)
- Row-major pixel iteration: `for y in range(h) for x in range(w)` — existing iteration order; preserve for correct display rendering

### Integration Points
- `server/converters.py` will be imported by `server/main.py` (Phase 2) at `POST /upload/frame` and `POST /upload/song` endpoints
- Output bytes from `convert_png()` will be written to disk as `.bin` files and served via `GET /frames/{name}.bin`
- Output list from `convert_sheet()` will be JSON-serialized and written as `.json` files

</code_context>

<specifics>
## Specific Ideas

- The `width` and `height` parameters on `convert_png()` anticipate Phase 3's "resolution selector" on the upload form — the server will pass user-chosen dimensions through to this function
- PIL `Image.LANCZOS` (formerly `Image.ANTIALIAS`) is the correct resampling filter for photo-quality downscaling; use it for `image.resize((width, height), Image.LANCZOS)`

</specifics>

<deferred>
## Deferred Ideas

- Custom BPM per song upload (form field) — deferred to future iteration; 120 BPM default covers the happy birthday use case
- Resolution selector on upload form (letting user pick 128×160 vs other sizes) — Phase 3 UI concern; Phase 1 just needs the parameterized `convert_png(data, width, height)` signature ready
- Support for `# bpm: N` header embedded in song files — could be added later without breaking the current interface

</deferred>

---

*Phase: 1-Conversion Core*
*Context gathered: 2026-06-13*
