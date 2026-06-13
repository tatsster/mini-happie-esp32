---
wave: 1
depends_on: []
files_modified:
  - server/__init__.py
  - server/converters.py
  - server/requirements.txt
autonomous: true
requirements: [CONV-01, CONV-02, CONV-03, CONV-04]
---

# Plan 01a — server/converters.py module

## Goal
Create the standalone `server/converters.py` Python module with two public functions — `convert_png` and `convert_sheet` — plus the supporting `server/__init__.py` and `server/requirements.txt`.

## Artifacts this phase produces

| Symbol | Location | Description |
|---|---|---|
| `convert_png(data, width, height) -> bytes` | `server/converters.py` | PNG bytes → big-endian RGB565 raw bytes |
| `convert_sheet(text, bpm) -> list[dict]` | `server/converters.py` | Song sheet text → `[{"freq": int, "ms": int}]` |
| `_rgb565(r, g, b) -> int` | `server/converters.py` | Private pixel converter |
| `_note_to_freq(note_str) -> int` | `server/converters.py` | Private note → Hz |
| `_beats_to_ms(beats, bpm) -> int` | `server/converters.py` | Private beat → ms |
| `SEMITONES` | `server/converters.py` | Module-level dict, note name → semitone offset |
| `DURATION_BEATS` | `server/converters.py` | Module-level dict, duration code → float beats |
| `server/__init__.py` | `server/__init__.py` | Empty file enabling `from server.converters import …` |
| `server/requirements.txt` | `server/requirements.txt` | `Pillow>=10.0.0` pinned |

---

## Task 1 — Create server/ directory scaffolding

<task id="01a-T1">
<title>Create server/__init__.py and server/requirements.txt</title>

<read_first>
- scripts/png_to_rgb565.py (Pillow usage reference)
</read_first>

<action>
1. Create `server/` directory at the repo root if it does not exist.
2. Create `server/__init__.py` as an empty file (zero bytes — no content, no docstring).
3. Create `server/requirements.txt` with exactly this content:

```
Pillow>=10.0.0
```

No other dependencies. No version cap.
</action>

<acceptance_criteria>
- `server/__init__.py` exists and contains 0 bytes (or just a newline — no code).
- `server/requirements.txt` exists and contains exactly the line `Pillow>=10.0.0`.
- `python -c "from server.converters import convert_png"` does NOT raise ImportError once converters.py exists (init enables the package).
</acceptance_criteria>
</task>

---

## Task 2 — Implement `convert_png`

<task id="01a-T2">
<title>Implement convert_png in server/converters.py</title>

<read_first>
- scripts/png_to_rgb565.py — source of truth for RGB565 formula and transparency compositing logic
- .planning/phases/01-conversion-core/01-CONTEXT.md — D-01 (auto-resize), D-09 (no imports from scripts/)
- .planning/phases/01-conversion-core/01-RESEARCH.md — transparency compositing order, LANCZOS alias
</read_first>

<action>
Create `server/converters.py` (or append to it if T1 already created it). Implement the private helper `_rgb565(r, g, b) -> int` and the public function `convert_png(data, width=128, height=160) -> bytes` using the following algorithm:

- Import `io`, `struct`, and `PIL.Image` at the top of the file. Do NOT import anything from `scripts/`.
- `_rgb565`: apply the RGB565 formula `((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)` and return the result as an int.
- `convert_png`: wrap all PIL operations in a try/except that re-raises any exception as `ValueError("PNG conversion failed: ...")`.
  1. Open the input bytes via `io.BytesIO(data)` — accepts bytes, not a file path.
  2. If the image mode is RGBA, LA, or P: create a black RGBA background the same size, then composite the image onto it with `Image.alpha_composite(bg, img.convert("RGBA"))` — this must happen BEFORE `convert("RGB")`.
  3. Convert the composited result to RGB with `img.convert("RGB")`.
  4. Resize to `(width, height)` using `Image.LANCZOS` (never `Image.ANTIALIAS`, which was removed in Pillow 10).
  5. Iterate pixels row-major (y outer, x inner), compute each pixel's RGB565 value via `_rgb565`.
  6. Pack all pixel values as big-endian uint16 with `struct.pack(f">{width*height}H", *pixels)` and return the resulting bytes.
- Return type is `bytes`, length always equals `width * height * 2`.
</action>

<acceptance_criteria>
- `convert_png` is importable: `from server.converters import convert_png` succeeds.
- For a 1×1 solid-red PNG (255,0,0): `convert_png(data, 1, 1)` returns `b'\xf8\x00'` (0xF800 big-endian).
- For a 1×1 solid-green PNG (0,255,0): returns `b'\x07\xe0'` (0x07E0 big-endian).
- For a 1×1 solid-blue PNG (0,0,255): returns `b'\x00\x1f'` (0x001F big-endian).
- For a 128×160 PNG: `len(convert_png(data))` == 40960 (128*160*2).
- For a PNG with alpha (RGBA mode): no exception, transparent pixels composite to black (0x0000).
- Passing `b"not a png"` raises `ValueError`.
- No function in `server/converters.py` imports anything from `scripts/`.
- `Image.ANTIALIAS` is NOT referenced in the file (removed in Pillow 10).
</acceptance_criteria>
</task>

---

## Task 3 — Implement `convert_sheet`

<task id="01a-T3">
<title>Implement convert_sheet in server/converters.py</title>

<read_first>
- scripts/sheet_music_to_melody.py — source of truth for SEMITONES, DURATION_BEATS, note_to_freq, beats_to_ms, parse_sheet logic
- assets/happy_birthday.txt — canonical format: `<note> <duration>` per line, `#` comments, blank lines allowed
- .planning/phases/01-conversion-core/01-CONTEXT.md — D-06 (120 BPM default), D-09 (standalone, no imports from scripts/)
</read_first>

<action>
Append to `server/converters.py`. Copy `SEMITONES` and `DURATION_BEATS` verbatim from `scripts/sheet_music_to_melody.py` (20 entries and 9 entries respectively) as module-level dicts. Then implement the private helpers and public function as follows:

- `SEMITONES` and `DURATION_BEATS` must be at module level (not inside any function).
- `_note_to_freq(note_str: str) -> int`: private helper (underscore prefix). Strips the note string, returns 0 for "R"/"r". Splits trailing digits/minus to extract note name and octave string; raises `ValueError("Unknown note name: ...")` if not in SEMITONES, raises `ValueError("Missing octave in: ...")` if octave string is empty. Computes MIDI number as `(octave + 1) * 12 + SEMITONES[note_name]` and returns `round(440.0 * (2 ** ((midi - 69) / 12.0)))`.
- `_beats_to_ms(beats: float, bpm: float) -> int`: private helper. Returns `round((beats / bpm) * 60_000)`.
- `convert_sheet(text: str, bpm: float = 120.0) -> list[dict]`: public function. Accepts a `str` (not a `Path`). Default `bpm=120.0`. Iterates `text.splitlines()` with 1-based line numbers; skips blank lines and lines starting with `#`. For each non-skipped line: splits into exactly 2 parts, raises `ValueError(f"Line {lineno}: expected '<note> <duration>', got: ...")` if not 2 parts; looks up duration (lowercased) in `DURATION_BEATS`, raises `ValueError(f"Line {lineno}: unknown duration ...")` if missing; calls `_note_to_freq` and `_beats_to_ms`; appends `{"freq": int, "ms": int}` to result. Returns the accumulated list.
</action>

<acceptance_criteria>
- `convert_sheet` is importable: `from server.converters import convert_sheet` succeeds.
- `convert_sheet("D4 q\n")` at 120 BPM returns `[{"freq": 294, "ms": 500}]` (D4=293.66≈294 Hz, quarter at 120 BPM = 500ms).
- `convert_sheet("R e\n")` returns `[{"freq": 0, "ms": 250}]`.
- `convert_sheet("F#4 h.\n")` returns `[{"freq": 370, "ms": 1500}]` (F#4≈369.99≈370 Hz, dotted-half=3 beats at 120 BPM=1500ms).
- Parsing the full content of `assets/happy_birthday.txt` at default BPM returns a list of 25 dicts (25 notes, 7 comment/blank lines skipped).
- `convert_sheet("BADLINE\n")` raises `ValueError` with "Line 1" in the message.
- `convert_sheet("D4 z\n")` raises `ValueError` with "unknown duration" in the message.
- `convert_sheet("D q\n")` raises `ValueError` with "Missing octave" in the message.
- `_note_to_freq` and `_beats_to_ms` are NOT present in `dir(converters)` as public names (they start with `_`).
- `SEMITONES` and `DURATION_BEATS` are present at module level and have correct key counts (20 and 9 respectively).
</acceptance_criteria>
</task>

---

## Verification

```bash
cd /path/to/repo
pip install Pillow>=10.0.0
python -c "
from server.converters import convert_png, convert_sheet
# Smoke test convert_sheet with happy birthday
import pathlib
text = pathlib.Path('assets/happy_birthday.txt').read_text()
notes = convert_sheet(text)
assert len(notes) == 25, f'Expected 25 notes, got {len(notes)}'
assert notes[0] == {'freq': 294, 'ms': 500}
print('convert_sheet OK:', len(notes), 'notes')
"
```

## must_haves

- `convert_png` accepts `bytes`, opens via `io.BytesIO`, performs transparency compositing BEFORE `convert("RGB")`, resizes with `Image.LANCZOS`, packs as big-endian uint16, returns `bytes`.
- `convert_sheet` accepts `str`, returns `list[dict]` with `"freq"` and `"ms"` int keys, raises `ValueError` with line number for malformed input.
- No imports from `scripts/` package anywhere in `server/converters.py`.
- `server/__init__.py` exists (enables `from server.converters import …`).
- `server/requirements.txt` pins `Pillow>=10.0.0`.
- All non-public helpers are underscore-prefixed.
- `CONV-01` (PNG conversion), `CONV-02` (sheet parsing), `CONV-03` (RGB565 formula), `CONV-04` (standalone module, no scripts/ dependency) are satisfied.
