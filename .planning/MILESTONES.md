# Milestones

## Roadmap

| Milestone | Name | Status | Goal |
|-----------|------|--------|------|
| v1.0 | Homelab Server | 🔄 In Progress | Self-hosted web server for content upload, conversion, and serving |
| v1.1 | ESP32 WiFi + OTA | ⏳ Planned | ESP32 connects to WiFi, fetches assets from server, stores in LittleFS |
| v1.2 | Hardware Portability | ⏳ Planned | TP4056 + LiPo battery, power switch, auto-play loop |

---

## v0 — Baseline Device (Shipped)

**Completed:** 2026-06-13 (pre-planning baseline)

**What shipped:**
- TFT display renders 4 animated cake frames (128×160 RGB565)
- Passive buzzer plays Happy Birthday melody via `tone()`
- Button-triggered playback sequence (countdown → melody → cake animation)
- Sheet music parser script (`scripts/sheet_music_to_melody.py`)
- ST7735 display driver configured via `build_flags` in `platformio.ini`

**Key decisions locked in:**
- TFT_eSPI with big-endian RGB565 + `setSwapBytes(true)`
- Arduino framework on PlatformIO
- Passive buzzer on GPIO25 with `tone()`
