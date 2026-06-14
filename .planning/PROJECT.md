# happy-birthday-esp32

## What This Is

A personal ESP32-based birthday gift device that plays animated cake frames on a 1.8" TFT display and a Happy Birthday melody on a passive buzzer. The project is evolving from a standalone device toward a WiFi-connected system with a self-hosted web server for remote content updates and a battery-powered portable form factor.

## Core Value

The device delights the recipient by playing a personalized birthday experience — images and melody must always play correctly, with or without WiFi.

## Requirements

### Validated

- ✓ TFT display renders 4 animated cake frames (128×160 RGB565) — v0 baseline
- ✓ Passive buzzer plays Happy Birthday melody via `tone()` — v0 baseline
- ✓ Button-triggered playback sequence — v0 baseline
- ✓ Sheet music parser script (`scripts/sheet_music_to_melody.py`) converts text notation to C array — v0 baseline
- ✓ PNG→RGB565 and sheet-music→melody conversion modules (`server/converters.py`) — Validated in Phase 1: Conversion Core
- ✓ REST API endpoints for frame/song upload, serve, delete, and manifest — Validated in Phase 2: FastAPI Server

### Active

**Milestone v1.0 — Homelab Server:**
- [x] User can upload a PNG image and it is converted to RGB565 binary for ESP32 (Phase 1 + Phase 2)
- [x] User can upload a song sheet and it is converted to melody data for ESP32 (Phase 1 + Phase 2)
- [ ] User can manage (preview, delete) uploaded frames via web UI
- [x] ESP32 can fetch a manifest listing available images and songs (Phase 2)
- [x] ESP32 can download individual frame binaries and song data via HTTP (Phase 2)
- [ ] Server is containerized and self-hostable via docker-compose

**Planned v1.1 — ESP32 WiFi + OTA:**
- [ ] ESP32 connects to home WiFi via WiFiManager captive portal
- [ ] ESP32 fetches manifest from server and downloads updated assets to LittleFS
- [ ] ESP32 falls back to built-in PROGMEM frames when offline or server unreachable

**Planned v1.2 — Hardware Portability:**
- [ ] Device runs on 3.7V LiPo via TP4056 USB-C charger circuit
- [ ] Physical power switch on VIN line controls device on/off
- [ ] Device auto-plays animation + melody loop on boot (no button needed)

### Out of Scope

| Feature | Reason |
|---------|--------|
| OTA firmware updates | Security risk, complexity out of scope — content-only updates via LittleFS |
| User accounts / auth | Single-owner homelab device, no public access needed |
| Video playback | ESP32 memory constraints; 128×160 static frames are sufficient |
| Cloud hosting | Homelab self-hosted only by design |
| Mobile app | Web UI sufficient for single-owner use |

## Context

- **Hardware:** ESP32 DevKit V1, ST7735 1.8" SPI TFT (128×160), passive piezo buzzer on GPIO25
- **Framework:** Arduino on ESP32 via PlatformIO — not ESP-IDF
- **Display driver:** `TFT_eSPI` configured entirely via `build_flags` in `platformio.ini` (no `User_Setup.h`)
- **Asset pipeline:** PNGs must be 128×160; `scripts/png_to_rgb565.py` converts to big-endian RGB565 C headers; `tft.setSwapBytes(true)` required
- **Flash budget:** current firmware ~460KB; with WiFi libs ~810KB; LittleFS partition ~1.5MB available for OTA assets
- **Memory model:** load one frame at a time into RAM (~40KB), push to display, free — never hold all frames simultaneously
- **Prior PLAN.md:** detailed implementation notes exist in `PLAN.md` at repo root — reference for technical decisions

## Constraints

- **Hardware**: Images must be exactly 128×160 pixels — reject anything else
- **Protocol**: ESP32 uses plain HTTP (not HTTPS) — server must be on local LAN, no TLS required for v1.1
- **Stack**: Arduino framework only — no ESP-IDF, no FreeRTOS tasks beyond what Arduino provides
- **Storage**: LittleFS partition ~1.5MB — max ~37 frames of 40KB each; practical limit 8–10 frames
- **Deployment**: Server must run via `docker-compose up` with no additional setup steps

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| TFT_eSPI build_flags instead of User_Setup.h | Version-stable, no file to manage per-developer | ✓ Good |
| RGB565 big-endian with setSwapBytes(true) | Matches TFT_eSPI pushImage expectation | ✓ Good |
| FastAPI + Docker for server | Reuses Python conversion logic, easy homelab deploy | — Pending |
| WiFiManager for WiFi onboarding | Captive portal UX — no hardcoded credentials | — Pending |
| ArduinoJson for manifest parsing | Mature, memory-safe, widely used in Arduino ecosystem | — Pending |
| LittleFS over SPIFFS | SPIFFS deprecated in Arduino ESP32 core | — Pending |
| Separate milestones per feature area | Server can be built/tested before hardware is available | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-14 — Phase 2 complete: FastAPI server with all REST endpoints, 47 tests passing*
