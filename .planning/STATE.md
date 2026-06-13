---
milestone: v1.0
name: Homelab Server
status: planning
progress:
  phases_total: 4
  phases_complete: 0
  requirements_total: 21
  requirements_complete: 0
---

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-13)

**Core value:** The device always plays correctly — images and melody work with or without WiFi.
**Current focus:** Defining requirements for v1.0 Homelab Server

## Current Position

Phase: Not started
Plan: 4 phases defined (see ROADMAP.md)
Status: Ready to plan Phase 1
Last activity: 2026-06-13 — Roadmap created, 21 requirements mapped across 4 phases

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
