# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git commits

**Never commit anything.** The user handles all git commits manually. Do not run `git commit`, `git add`, or any GSD commit helpers (`gsd_run query commit`). Make file changes freely, but stop before staging or committing.

## Project overview

Two independent systems in one repo:

1. **ESP32 firmware** (`src/`) — Arduino/PlatformIO. Plays animated cake frames on a 128×160 ST7735 TFT and a Happy Birthday melody on a passive piezo buzzer. Button-triggered.
2. **Homelab web server** (`server/`) — FastAPI/Python. Accepts PNG and song-sheet uploads, converts them, and serves binary assets to the ESP32 over HTTP.

The server and firmware are developed independently — the server can be built and tested with no ESP32 hardware.

## Commands

### Firmware (PlatformIO)
```bash
pio run                  # build only
pio run -t upload        # build + flash
pio device monitor       # serial monitor at 115200
```
If upload fails with "No serial data received": hold BOOT button → start upload → release BOOT once "Writing at 0x..." appears.

### Server (Python)
```bash
# Install
pip install -r server/requirements.txt
pip install -r server/requirements-dev.txt   # adds pytest + httpx

# Run
uvicorn server.main:app --port 8080 --reload

# Test
python -m pytest tests/ -q            # all 47 tests
python -m pytest tests/test_api.py::TestUploadFrame -q   # single class
python -m pytest tests/ -q -k "etag"  # by keyword
```

### Asset conversion (Python, dev-time only)
```bash
python3 scripts/png_to_rgb565.py <in.png> <out.h> <array_name>   # PNG → C header
python3 scripts/sheet_music_to_melody.py <sheet.txt> --bpm 94    # sheet → C array
```
After regenerating headers, rebuild and flash with `pio run -t upload`.

## Server architecture

```
server/
  main.py       # app wiring only: FastAPI instance, lifespan, include_router calls
  storage.py    # manifest lock, atomic write, read helpers, size constants
  converters.py # convert_png(bytes) -> bytes, convert_sheet(str) -> list[Note]
  routes/
    frames.py   # GET /frames/{name}.bin, POST /upload/frame, DELETE /frames/{name}
    songs.py    # GET /songs/{name}.json, POST /upload/song,  DELETE /songs/{name}
    manifest.py # GET /manifest.json
```

**Critical import pattern — do not break it.** Path constants (`FRAMES_DIR`, `SONGS_DIR`, `MANIFEST_PATH`) live in `server.main`, not `server.storage`. Route handlers import them *lazily* (inside function bodies via `import server.main as _main`) to avoid a circular import and so that `monkeypatch.setattr(main_module, "FRAMES_DIR", ...)` in tests redirects all handlers at runtime. If you move constants or change import style, the 47 tests will break.

**Storage model:**
- Upload converts once → stores result on disk → serves pre-stored bytes (no re-conversion on read)
- Frames: `data/frames/frame_N.bin` (RGB565) + `data/frames/frame_N.png` (original, for future thumbnails)
- Songs: `data/songs/song_N.json` (melody array)
- Manifest: `data/manifest.json` — persisted JSON, updated on every upload/delete, never auto-rebuilt
- Slot naming: sequential (`frame_0`, `frame_1`, …); delete triggers ascending-order rename to keep slots contiguous and bumps `updated_at`
- ETag: `f'"{hashlib.md5(data, usedforsecurity=False).hexdigest()}"'` — quoted per RFC 7232

## TFT display configuration

Configured entirely via `build_flags` in `platformio.ini` — **no `User_Setup.h` file**. The relevant flags are `ST7735_BLACKTAB`, `TFTWIDTH=128`, `TFTHEIGHT=160`, and the SPI pin assignments. If the display shows shifted pixels or wrong colors, change the tab variant flag (`BLACKTAB` → `GREENTAB`/`REDTAB`).

`tft.setSwapBytes(true)` is required — generated RGB565 arrays are big-endian.

## RGB565 pixel format

Each pixel is 2 bytes, big-endian: `((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)`. A 128×160 frame is exactly 40,960 bytes. The conversion logic lives in `server/converters.py::convert_png()` and the original script `scripts/png_to_rgb565.py`.

## Song sheet format

Plain text, one note per line: `NOTE OCTAVE DURATION` (e.g. `G 4 q`). Durations: `w h q e s` (whole/half/quarter/eighth/sixteenth) plus dotted variants. Rests use `R`. BPM defaults to 120. See `assets/happy_birthday.txt` for the canonical example.
