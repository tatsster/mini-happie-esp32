# Requirements: happy-birthday-esp32

**Milestone:** v1.0 — Homelab Server
**Defined:** 2026-06-13
**Core Value:** The device always plays correctly — images and melody work with or without WiFi.

## v1.0 Requirements

### Web UI

- [ ] **UI-01**: User can upload a PNG image file via the web interface
- [ ] **UI-02**: User can upload a plain-text song sheet via the web interface
- [ ] **UI-03**: User can preview uploaded frame images as thumbnails in the web UI
- [ ] **UI-04**: User can delete an individual frame from the server
- [ ] **UI-05**: User can delete an individual song from the server
- [ ] **UI-06**: User sees a clear error message when uploading a PNG that is not 128×160 pixels

### Conversion

- [ ] **CONV-01**: Server converts uploaded PNG (128×160) to raw big-endian RGB565 binary (40960 bytes)
- [ ] **CONV-02**: Server rejects PNG uploads that are not exactly 128×160 with a descriptive error
- [ ] **CONV-03**: Server converts uploaded song sheet text to a JSON melody array (`[{ "freq": N, "ms": N }, ...]`)
- [ ] **CONV-04**: Conversion logic reuses the algorithm from `scripts/png_to_rgb565.py` and `scripts/sheet_music_to_melody.py`

### API

- [ ] **API-01**: `GET /manifest.json` returns a JSON document listing available frame filenames, song filenames, and an `updated_at` ISO8601 timestamp
- [ ] **API-02**: `GET /frames/{name}.bin` returns the raw RGB565 binary for a frame
- [ ] **API-03**: `GET /songs/{name}.json` returns the melody JSON array for a song
- [ ] **API-04**: `POST /upload/frame` accepts a PNG, converts it, and stores the resulting binary
- [ ] **API-05**: `POST /upload/song` accepts a text song sheet, converts it, and stores the resulting JSON
- [ ] **API-06**: `DELETE /frames/{name}` removes a stored frame binary and updates the manifest
- [ ] **API-07**: `DELETE /songs/{name}` removes a stored song JSON and updates the manifest
- [ ] **API-08**: Binary responses include an `ETag` header so ESP32 can skip unchanged downloads

### Deployment

- [ ] **DEPLOY-01**: Server runs with a single `docker-compose up` command
- [ ] **DEPLOY-02**: Uploaded files persist across container restarts via a Docker volume mount
- [ ] **DEPLOY-03**: Server listens on port 8080 by default (configurable via environment variable)

## v1.1 Requirements (Planned — not in current roadmap)

### WiFi

- **WIFI-01**: ESP32 launches a WiFiManager captive portal on first boot for WiFi credential entry
- **WIFI-02**: ESP32 auto-connects to saved WiFi credentials on subsequent boots
- **WIFI-03**: ESP32 falls back to offline playback if WiFi connection fails within timeout

### OTA Sync

- **OTA-01**: ESP32 fetches `/manifest.json` from the configured server URL on boot
- **OTA-02**: ESP32 compares manifest `updated_at` against locally cached timestamp
- **OTA-03**: ESP32 downloads only changed frame binaries to LittleFS
- **OTA-04**: ESP32 downloads only changed song JSONs to LittleFS
- **OTA-05**: ESP32 falls back to built-in PROGMEM frames if LittleFS is empty

## v1.2 Requirements (Planned — not in current roadmap)

### Hardware

- **HW-01**: Device operates on 3.7V LiPo battery via TP4056 USB-C charger module
- **HW-02**: Physical switch on VIN line provides hard power on/off
- **HW-03**: Device auto-plays the full animation + melody loop on boot without button press
- **HW-04**: Device charges battery via USB-C while switch is in the off position

## Out of Scope

| Feature | Reason |
|---------|--------|
| OTA firmware updates | Security risk, complexity; content-only via LittleFS is sufficient |
| HTTPS / TLS | Local LAN only; certificate management adds friction for homelab |
| User authentication | Single-owner private homelab; no public access |
| Cloud hosting | By design: homelab self-hosted only |
| Mobile app | Web UI is sufficient for single-owner use |
| Video / animated GIF | ESP32 memory constraints; static frame animation is sufficient |
| Multiple device support | Single device; multi-device sync out of scope for v1 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| UI-01 | Phase 3: Web UI | Pending |
| UI-02 | Phase 3: Web UI | Pending |
| UI-03 | Phase 3: Web UI | Pending |
| UI-04 | Phase 3: Web UI | Pending |
| UI-05 | Phase 3: Web UI | Pending |
| UI-06 | Phase 3: Web UI | Pending |
| CONV-01 | Phase 1: Conversion Core | Pending |
| CONV-02 | Phase 1: Conversion Core | Pending |
| CONV-03 | Phase 1: Conversion Core | Pending |
| CONV-04 | Phase 1: Conversion Core | Pending |
| API-01 | Phase 2: FastAPI Server | Pending |
| API-02 | Phase 2: FastAPI Server | Pending |
| API-03 | Phase 2: FastAPI Server | Pending |
| API-04 | Phase 2: FastAPI Server | Pending |
| API-05 | Phase 2: FastAPI Server | Pending |
| API-06 | Phase 2: FastAPI Server | Pending |
| API-07 | Phase 2: FastAPI Server | Pending |
| API-08 | Phase 2: FastAPI Server | Pending |
| DEPLOY-01 | Phase 4: Docker Packaging | Pending |
| DEPLOY-02 | Phase 4: Docker Packaging | Pending |
| DEPLOY-03 | Phase 4: Docker Packaging | Pending |

**Coverage:**
- v1.0 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-13*
*Last updated: 2026-06-13 — initial definition*
