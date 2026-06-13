---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
last_updated: "2026-06-13T11:09:00.000Z"
last_activity: 2026-06-13 -- Plan 01a complete (server/converters.py implemented and verified)
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 2
  completed_plans: 1
  percent: 25
---

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-13)

**Core value:** The device always plays correctly — images and melody work with or without WiFi.
**Current focus:** Phase 01 — conversion-core

## Current Position

Phase: 01 (conversion-core) — EXECUTING
Plan: 2 of 2
Status: 01a complete, starting 01b
Last activity: 2026-06-13 -- Plan 01a complete (server/converters.py implemented and verified)

## Accumulated Context

### Decisions

- Server stack: Python FastAPI + Docker — reuses existing `scripts/png_to_rgb565.py` conversion logic
- Manifest format agreed: `{ "frames": [...], "songs": [...], "updated_at": "ISO8601" }`
- Frame binary format: raw uint16_t big-endian RGB565, 40960 bytes (128×160×2)
- Song data: JSON array of `{ freq, ms }` objects — ESP32 parses with ArduinoJson

### Blockers

(none)

### Todos

- [ ] Build and test server before connecting ESP32
