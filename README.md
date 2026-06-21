# Mini Happie

An interactive birthday display built around an ESP32. A 2" SPI TFT shows animated graphics, a passive piezo buzzer plays any melody fetched from the web, and a push button triggers the full sequence.

The firmware connects to a **homelab web server** (FastAPI) over WiFi and pulls the latest display frames and songs via REST API — no reflashing needed to change the art or music. The server ("Mini Happie Manager") stores pre-converted assets and serves them on demand.

## Inspiration

This project inherits its core idea from [cupidbity/happy-birthday-esp32](https://github.com/cupidbity/happy-birthday-esp32) — an ESP32 birthday display with TFT animation and buzzer melody. Mini Happie extends that concept with:

- A **2" ST7789 240×320 display** (vs the original 1.8" ST7735 128×160)
- A **custom partition table** (`no_ota.csv`) that disables OTA firmware updates to reclaim space — 1920KB for the app (WiFi + TLS fit comfortably) and 2MB LittleFS for asset storage
- **WiFi-based asset updates** — the firmware fetches frames and songs from a REST API; no reflashing or filesystem upload required
- A **FastAPI web server** ("Mini Happie Manager") that manages and serves those assets
- **Docker-based deployment** for the server component

## Hardware

ESP32 Pin diagram reference: https://5.imimg.com/data5/SELLER/Doc/2025/4/501949387/EU/NR/MQ/1833510/nodemcu-esp32-cp2102-30pin.pdf

| Component  | ESP32 pin      | Notes                      |
|------------|----------------|----------------------------|
| TFT CS     | GPIO5          | SPI chip select            |
| TFT DC     | GPIO16 (RX2)   | data/command               |
| TFT RES    | GPIO17 (TX2)   |                            |
| TFT SCL    | GPIO18         | hardware SPI clock         |
| TFT SDA    | GPIO23         | hardware SPI MOSI          |
| TFT VDD    | 3V3            | 3.3V logic                 |
| TFT BLK    | 3V3            | backlight always-on        |
| Buzzer +   | GPIO25         | passive piezo              |
| Button     | GPIO14         | to GND, INPUT_PULLUP       |

All grounds tied together. ST7789 is write-only — no MISO connection needed.

## Bill of Materials

| Qty | Part | Notes |
|-----|------|-------|
| 1 | ESP32 dev board (CP2102 USB chip) | Any 30-pin ESP32 DevKit works |
| 1 | 2" SPI TFT, ST7789, 240×320 | Logic 3.3V; pins: GND VCC SCL SDA RST DC CS BLK |
| 1 | Passive piezo buzzer | Must be **passive** — active buzzers play only one fixed tone |
| 1 | Momentary push button | Optional — onboard BOOT (GPIO0) works for testing |
| — | Breadboard + jumper wires | Power rails for 3V3 / GND fanout |
| 1 | USB data cable | Charge-only cables cause upload failures |

## Quick Start — Firmware

### 1. Install tooling

- [PlatformIO](https://platformio.org/) — VS Code extension or `pip install platformio`
- Python 3 with Pillow for asset conversion: `pip3 install pillow`

### 2. Clone and build

```bash
git clone <this-repo>
cd happy-birthday-esp32
pio run -t upload
pio device monitor
```

Pin assignments and display driver settings live entirely in `platformio.ini` as `build_flags` — no `User_Setup.h` editing needed. PlatformIO installs `TFT_eSPI` automatically on first build.

### 3. Connect to WiFi (first boot only)

On first boot the TFT shows **"Setup WiFi:"** with an AP name and IP. On your phone:

1. Join the `MiniHappie-Setup` WiFi network
2. Open `192.168.4.1` in a browser (or wait for the captive portal redirect)
3. Enter your home WiFi credentials and save

Subsequent boots auto-connect — the portal never appears again unless credentials are erased. If no credentials are entered within 180 seconds, the device falls back to **Offline mode** and plays from cached assets on button press.

### 4. Wire it

Follow the Hardware table above. Tips:

- The ESP32 has one **3V3 pin** — jumper it to the breadboard + rail, then feed TFT VCC and BLK from there.
- GPIO16/17 may be silkscreened **RX2/TX2** on some boards — they still work as DC/RST.
- Seat TFT pins firmly. A loose joint shows as a white screen that flickers when touched.
- The passive buzzer has no polarity.

### 5. Tune the display

If colors look wrong after first flash:

- **Warm colors look blue / blue fills appear red** — your ST7789 panel uses BGR channel order. Add `-DTFT_RGB_ORDER=TFT_BGR` to the `build_flags` block in `platformio.ini`. This is the most common issue with ST7789 panels; it affects both solid fills (`fillScreen`) and pushed images.
- **All colors inverted / washed out** — toggle `-DTFT_INVERSION_ON` in `platformio.ini` (uncomment to enable, comment out to disable). Some ST7789 panels need this alongside `TFT_BGR`; try both combinations.
- **Byte-order garbage on images only** — `tft.setSwapBytes(true)` is already set in the firmware; generated RGB565 arrays are big-endian. This should not need changing.
- **Portrait vs landscape** — change `tft.setRotation(2)` (0–3) in `src/main.cpp`.

## Quick Start — Web Server (Mini Happie Manager)

The server runs on your homelab and serves pre-converted binary assets to the ESP32 over WiFi. It is independent of the firmware — you can run and test it with no hardware attached.

### Run with Docker (recommended)

```bash
docker-compose up
```

### Run locally

```bash
pip install -r requirements.txt
uvicorn server.main:app --port 8080 --reload
```

### API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/manifest.json` | Index of all available frames and songs (ESP32 polls this) |
| POST | `/upload/frame` | Upload a PNG (any size) → server resizes to 240×320, converts to RGB565, stores it |
| GET | `/frames/{name}.bin` | Download a frame as raw RGB565 binary |
| DELETE | `/frames/{name}` | Remove a frame |
| GET | `/songs/{name}.json` | Download a song as a JSON note array |
| DELETE | `/songs/{name}` | Remove a song |

Upload songs as WAV or MP3 files via `POST /upload/song` — the server converts them to a `{freq, ms}` note array automatically. A `is_complex: true` flag in the response indicates polyphonic audio that may not play cleanly on the passive buzzer.

Point `SERVER_URL` in `src/config.h` at your server before flashing:

```cpp
#define SERVER_URL "http://192.168.1.x:8080"   // local Caddy / uvicorn
// or
#define SERVER_URL "https://your-tunnel.trycloudflare.com"  // Cloudflare tunnel
```

### Run tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

## Build Reference

```bash
# Firmware
pio run                  # build only
pio run -t upload        # build + flash
pio device monitor       # serial at 115200
```

Upload note: CP2102-based boards have reliable auto-reset — no need to hold BOOT during upload. If upload fails anyway, try: hold BOOT → start upload → release once "Writing at 0x..." appears.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Upload: `No serial data received` | Charge-only USB cable or flaky reset | Swap cable; try manual BOOT hold during upload |
| Screen totally dark | No power to VCC/BLK | Verify VCC + BLK on 3V3 rail, GND on − rail |
| White screen, flickers when touched | Loose/cold joint | Reseat / reflow the pin |
| Cake image looks blue/cold; navy fills appear red | ST7789 BGR panel | Add `-DTFT_RGB_ORDER=TFT_BGR` to `build_flags` in `platformio.ini` |
| Colors inverted / washed out | ST7789 panel variant | Toggle `-DTFT_INVERSION_ON` in `platformio.ini`; try with and without `TFT_BGR` |
| Image colors look like static | Byte order | `tft.setSwapBytes(true)` (already set) |
| Buzzer plays one flat tone | Active buzzer | Replace with a **passive** piezo |
| Stuck on "Connecting..." at boot | Saved credentials bad or first boot | Wait for portal AP, or hold BOOT 3s to reset WiFi creds |
| No WiFi AP appears after "Connecting..." | Portal timeout waiting for you | Reflash to trigger first-boot flow again |
| Nothing happens after WiFi connects | Button-triggered by design | Press BOOT or GPIO14 button to play |
| Server: frame not updating | ETag cache | DELETE the old frame and re-upload |

## Project Layout

```
src/             ESP32 firmware source
include/         generated image/font C headers
partitions/      custom ESP32 partition table (no_ota.csv)
server/          FastAPI web server (Mini Happie Manager)
tests/           server test suite (pytest)
data/            server runtime data (frames, songs, manifest)
docs/            wiring diagrams, notes
```
