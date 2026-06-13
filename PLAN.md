# PLAN.md — happy-birthday-esp32 improvements

> This file tracks planned features for new sessions to pick up from.
> Status: PENDING | IN_PROGRESS | DONE

---

## Feature 1 — Flip switch + auto-play loop

**Goal:** replace momentary button with a physical power switch. Device auto-plays
animation + melody on boot and loops continuously. Saves battery since the switch
fully cuts power when off.

**Status:** PENDING

**Files to change:**
- `src/main.cpp`

**Changes:**
- Remove button pin declarations (`PIN_BUTTON`, `PIN_BOOT_BTN`)
- Remove `pinMode` calls for buttons
- Move sequence into `loop()` — `countdown()` → `playMelody()` → `drawCake(0)` → `delay(3000)` → repeat
- Remove button-polling logic from `loop()`

**Hardware change:**
- Remove external button wiring on GPIO14
- Add physical SPDT/DPDT toggle switch on VIN/battery+ line (no code needed)

---

## Feature 2 — Sheet music parser (DONE)

**Goal:** Python script to convert human-readable sheet music text → `melody[]` C array.

**Status:** DONE

**Files created:**
- `scripts/sheet_music_to_melody.py` — parser, supports all note names, octaves, dotted durations, rests
- `assets/happy_birthday.txt` — sample Happy Birthday sheet music in G, 94 BPM

**Usage:**
```bash
python3 scripts/sheet_music_to_melody.py assets/happy_birthday.txt --bpm 94
python3 scripts/sheet_music_to_melody.py assets/my_song.txt --bpm 120 --var my_melody
```

Output is ready to paste into `src/main.cpp` as the `melody[]` array.

---

## Feature 3 — Battery + power switch hardware design

**Goal:** make device portable using a LiPo battery + USB charger module.

**Status:** PENDING (hardware design only, no code changes)

**Bill of materials to add:**
| Qty | Part | Notes |
|-----|------|-------|
| 1 | 3.7V LiPo (e.g. 1000mAh flat pack or 18650) | capacity depends on desired runtime |
| 1 | TP4056 USB-C module with protection (DW01 chip) | protects against over-charge + over-discharge |
| 1 | SPDT or DPDT slide/toggle switch | rated ≥ 1A |

**Wiring:**
```
LiPo+ → TP4056 BAT+ → TP4056 OUT+ → Switch → ESP32 VIN
LiPo− → TP4056 BAT− → TP4056 OUT− → ESP32 GND
```

**Notes:**
- Switch sits between TP4056 output and ESP32 VIN → can charge with switch OFF
- LiPo 3.7V (4.2V fresh) provides enough headroom for AMS1117 regulator on DevKit
- No code changes needed for this feature alone

---

## Feature 4 — Self-hosted web UI + OTA image updates

**Goal:** friend can upload new PNG images via a self-hosted web page; ESP32 fetches
them over WiFi automatically. No ESP32 knowledge needed on friend's side.

**Status:** PENDING

### Memory analysis (safe to proceed)

| | Before | After | ESP32 limit |
|---|---|---|---|
| Firmware flash | ~460KB | ~810KB | 4096KB |
| LittleFS storage | 0 | ~320KB (8 frames) | ~1500KB |
| RAM peak | ~40KB | ~120KB | 520KB |

Images move from PROGMEM (firmware flash) → LittleFS (separate flash partition).
Load one frame at a time into RAM (~40KB), push to display, free before loading next.

---

### 4a — ESP32 firmware changes

#### Task esp32-wifi: WiFiManager + connect on boot
**Lib to add to `platformio.ini`:** `tzapu/WiFiManager`

```cpp
#include <WiFiManager.h>
void connectWifi() {
    WiFiManager wm;
    wm.autoConnect("BirthdayDevice-Setup");
    // first boot: creates hotspot, friend configures via phone captive portal
    // subsequent boots: auto-connects from saved credentials
}
```

#### Task esp32-http: fetch manifest then frames
- GET `http://<server>/images/manifest.json` → parse frame list (ArduinoJson)
- Compare `updated_at` timestamp against value stored in LittleFS
- If changed: download each listed `.bin` file, save to LittleFS
- Frame count is dynamic (1–8), not hardcoded

**Manifest format:**
```json
{
  "frames": ["frame_0.bin", "frame_1.bin", "frame_2.bin"],
  "updated_at": "2026-06-12T11:00:00Z"
}
```

**Libs to add:** `bblanchon/ArduinoJson`

#### Task esp32-littlefs: LittleFS storage
- Add LittleFS partition to `platformio.ini` (use `min_spiffs.csv` or custom)
- Save frames as `/frame_0.bin`, `/frame_1.bin`, etc.
- Save manifest timestamp as `/manifest_ts.txt`
- On display: open file → read 40KB chunk → `tft.pushImage()` → close file

#### Task esp32-fallback: offline fallback
- If WiFi fails or server unreachable: check if LittleFS has frames from previous fetch
- If LittleFS empty too: fall back to built-in PROGMEM frames (keep existing headers)
- Never show a blank screen

**`platformio.ini` additions needed:**
```ini
lib_deps =
    bodmer/TFT_eSPI@^2.5.43
    tzapu/WiFiManager
    bblanchon/ArduinoJson

board_build.filesystem = littlefs
```

---

### 4b — Homelab server

**Language/framework:** Python + FastAPI
**Deployment:** Docker + docker-compose

#### Task server-app: web UI
- Single-page HTML form: select frame slot (0–7), upload PNG
- Shows current uploaded frames with preview thumbnails
- Delete button per frame

#### Task server-convert: PNG → RGB565 binary
- Reuse logic from `scripts/png_to_rgb565.py`
- Validate: must be exactly 128×160, reject with message otherwise
- Output: raw `uint16_t` binary (not C header), 40960 bytes per frame

#### Task server-serve: HTTP endpoints
```
GET  /images/manifest.json     → current frame list + updated_at
GET  /images/frame_{n}.bin     → raw RGB565 binary for frame n
POST /upload                   → upload PNG for slot n
DELETE /images/frame_{n}.bin   → remove a frame
```
- Include `ETag` on binary responses so ESP32 skips unchanged downloads

#### Task server-docker: containerise
```yaml
# docker-compose.yml sketch
services:
  birthday-server:
    build: ./server
    ports:
      - "8080:8080"
    volumes:
      - ./server/images:/app/images
```

**Project layout for server code:**
```
server/
  main.py          FastAPI app
  convert.py       PNG → RGB565 logic (extracted from scripts/)
  Dockerfile
docker-compose.yml
```

---

## Suggested implementation order

```
[ ] Feature 1 (flip switch)        — 30 min, main.cpp only
[ ] Feature 3 (battery design)     — hardware only, no code
[ ] Feature 4b server-app          — homelab side, independent
[ ] Feature 4b server-convert      — depends on server-app
[ ] Feature 4b server-serve        — depends on server-convert
[ ] Feature 4b server-docker       — depends on server-serve
[ ] Feature 4a esp32-wifi          — needs WiFiManager
[ ] Feature 4a esp32-http          — depends on esp32-wifi + server running
[ ] Feature 4a esp32-littlefs      — depends on esp32-http
[ ] Feature 4a esp32-fallback      — depends on esp32-littlefs
[ ] README update                  — last, after all features done
```

Server and ESP32 sides can be developed in parallel once the manifest format is agreed.
