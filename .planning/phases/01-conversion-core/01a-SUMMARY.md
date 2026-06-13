---
plan: 01a
status: complete
key-files:
  created:
    - server/__init__.py
    - server/converters.py
    - server/requirements.txt
---

# Summary: Plan 01a — server/converters.py module

## What Was Built

Created the standalone `server/converters.py` module with:
- `convert_png(data, width=128, height=160) -> bytes`: PNG bytes → big-endian RGB565 raw bytes with transparency compositing
- `convert_sheet(text, bpm=120.0) -> list[dict]`: song sheet text → `[{"freq": int, "ms": int}]`
- Private helpers: `_rgb565`, `_note_to_freq`, `_beats_to_ms`
- Module-level dicts: `SEMITONES` (20 entries), `DURATION_BEATS` (9 entries)

Also created `server/__init__.py` (empty package init) and `server/requirements.txt` (`Pillow>=10.0.0`).

## Verification

All acceptance criteria met:
- `convert_png` returns 40960 bytes for 128×160 input
- Red/green/blue spot checks pass (0xF800, 0x07E0, 0x001F)
- Transparent pixels composite to black (0x0000)
- Invalid bytes raise ValueError
- `convert_sheet("D4 q\n")` → `[{"freq": 294, "ms": 500}]`
- `assets/happy_birthday.txt` parses to 25 notes
- No imports from `scripts/` anywhere in server/

## Self-Check: PASSED

Requirements satisfied: CONV-01, CONV-02, CONV-03, CONV-04

## Deviations

Tasks 2 and 3 were implemented in a single write to `server/converters.py` and committed together under the Task 2 commit message (`feat(01-01a): implement convert_png with RGB565 packing`). A separate Task 3 commit was not created since no additional diff existed. All functionality specified in both tasks is present and verified.
