# Phase 1: Conversion Core - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `01-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-06-13
**Phase:** 1-Conversion Core
**Areas discussed:** Image handling, BPM source, Code reuse

---

## Image Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Strict reject | Anything not exactly 128×160 gets an error message | |
| Auto-resize | Server rescales to 128×160 using PIL, no error | |
| Configurable dimensions with resize | Auto-resize to user-specified dimensions; default 128×160 | ✓ |

**User's choice:** Auto-resize to configurable dimensions — user noted that 2" screens use different resolutions, so the web UI should let users change the target size.

**Resize mode:**

| Option | Selected |
|--------|----------|
| Stretch to fill (distort if needed) | ✓ |
| Crop to fill (center-crop) | |
| Letterbox (black bars) | |

**User's choice:** Stretch — exact pixel count required for display.

**Default dimensions:** 128×160 (1.8" ST7735); overridable per upload.

---

## BPM Source

| Option | Description | Selected |
|--------|-------------|----------|
| BPM in file header (`# bpm: 94`) | Embedded in song sheet first line | |
| Upload form field | Separate BPM number input alongside file picker | |
| Fixed default 120 BPM | No user control, keep it simple | ✓ |

**User's choice:** Fixed 120 BPM — no user-facing BPM control for this milestone.

---

## Code Reuse

| Option | Description | Selected |
|--------|-------------|----------|
| Import from scripts/ directly | Server imports functions from existing CLI scripts | |
| Copy-and-adapt into server/converters.py | Independent module, no cross-folder imports | ✓ |
| Extract to shared lib/ | Both CLI and server import from lib/converters.py | |

**User's choice:** Standalone `server/converters.py` — clean server package with no dependency on `scripts/`.

---

## Claude's Discretion

- Testing setup (pytest structure, fixture location, parameterization)
- Internal helper structure within `server/converters.py`
- Error type: `ValueError` with descriptive messages for malformed input

## Deferred Ideas

- Custom BPM per upload (form field) — deferred to future iteration
- Resolution selector UI on upload form — Phase 3 concern; Phase 1 just needs parameterized `convert_png(data, width, height)` signature
- `# bpm: N` header embedded in song files — could be added later
