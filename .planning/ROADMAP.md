# Roadmap: happy-birthday-esp32

**Milestone:** v1.0 — Homelab Server
**Phases:** 4
**Requirements:** 21 total

## Phase Overview

| # | Phase | Goal | Requirements | Est. Effort |
|---|-------|------|--------------|-------------|
| 1 | Conversion Core | 2/2 | Complete   | 2026-06-13 |
| 2 | FastAPI Server | REST endpoints, file storage, and manifest management | API-01, API-02, API-03, API-04, API-05, API-06, API-07, API-08 | 3–4h |
| 3 | Web UI | Upload forms, thumbnail previews, delete actions, and error display | UI-01, UI-02, UI-03, UI-04, UI-05, UI-06 | 2–3h |
| 4 | Docker Packaging | Dockerfile, docker-compose, volume mounts, and env configuration | DEPLOY-01, DEPLOY-02, DEPLOY-03 | 1–2h |

## Phase Details

### Phase 1: Conversion Core ✓ Plan 01a complete

**Goal:** Extract and unit-test the PNG→RGB565 and sheet-music→melody conversion algorithms as importable Python modules, reusing the existing script logic.

**Requirements:**

- CONV-01: Server converts uploaded PNG (128×160) to raw big-endian RGB565 binary (40960 bytes)
- CONV-02: Server rejects PNG uploads that are not exactly 128×160 with a descriptive error
- CONV-03: Server converts uploaded song sheet text to a JSON melody array (`[{ "freq": N, "ms": N }, ...]`)
- CONV-04: Conversion logic reuses the algorithm from `scripts/png_to_rgb565.py` and `scripts/sheet_music_to_melody.py`

**Success criteria:**

1. `convert_png(bytes) -> bytes` returns exactly 40960 bytes for a valid 128×160 PNG input
2. `convert_png(bytes)` raises a descriptive `ValueError` for a PNG with any other dimensions
3. `convert_sheet(text) -> list[dict]` returns a list of `{"freq": int, "ms": int}` dicts for a valid sheet
4. All conversion functions are importable from a single `server/converters.py` module with no CLI dependency

**Effort estimate:** 2–3h

---

### Phase 2: FastAPI Server

**Goal:** Implement all REST API endpoints with file storage and manifest management using FastAPI.

**Requirements:**

- API-01: `GET /manifest.json` returns a JSON document listing available frame filenames, song filenames, and an `updated_at` ISO8601 timestamp
- API-02: `GET /frames/{name}.bin` returns the raw RGB565 binary for a frame
- API-03: `GET /songs/{name}.json` returns the melody JSON array for a song
- API-04: `POST /upload/frame` accepts a PNG, converts it, and stores the resulting binary
- API-05: `POST /upload/song` accepts a text song sheet, converts it, and stores the resulting JSON
- API-06: `DELETE /frames/{name}` removes a stored frame binary and updates the manifest
- API-07: `DELETE /songs/{name}` removes a stored song JSON and updates the manifest
- API-08: Binary responses include an `ETag` header so the ESP32 can skip unchanged downloads

**Success criteria:**

1. `curl localhost:8080/manifest.json` returns valid JSON with `frames`, `songs`, and `updated_at` fields
2. Uploading a 128×160 PNG via `POST /upload/frame` stores a 40960-byte `.bin` file and the name appears in the manifest
3. `GET /frames/{name}.bin` returns the binary with a matching `ETag` header; a second identical request returns the same ETag
4. `DELETE /frames/{name}` removes the file and the name no longer appears in the subsequent manifest

**Effort estimate:** 3–4h

---

### Phase 3: Web UI

**Goal:** Build a browser-based interface for uploading images and songs, previewing thumbnails, deleting assets, and seeing upload validation errors.

**Requirements:**

- UI-01: User can upload a PNG image file via the web interface
- UI-02: User can upload a plain-text song sheet via the web interface
- UI-03: User can preview uploaded frame images as thumbnails in the web UI
- UI-04: User can delete an individual frame from the server
- UI-05: User can delete an individual song from the server
- UI-06: User sees a clear error message when uploading a PNG that is not 128×160 pixels

**Success criteria:**

1. Uploading a valid 128×160 PNG via the browser results in its thumbnail appearing in the frames list without a page reload
2. Uploading a PNG with wrong dimensions shows a human-readable error message inline (no raw HTTP error)
3. Clicking delete on a frame or song removes it from the list immediately in the UI
4. Uploading a song sheet via the browser causes its name to appear in the songs list

**Effort estimate:** 2–3h

---

### Phase 4: Docker Packaging

**Goal:** Package the server and its dependencies into a Docker image, wired with docker-compose for single-command startup and persistent storage.

**Requirements:**

- DEPLOY-01: Server runs with a single `docker-compose up` command
- DEPLOY-02: Uploaded files persist across container restarts via a Docker volume mount
- DEPLOY-03: Server listens on port 8080 by default (configurable via environment variable)

**Success criteria:**

1. `docker-compose up` from a clean checkout starts the server with no manual steps
2. Files uploaded before `docker-compose restart` are still present and served after the restart
3. Setting `PORT=9090` in the environment causes the server to bind on port 9090 instead of 8080
4. `docker-compose down && docker-compose up` leaves no orphan data in the volume

**Effort estimate:** 1–2h
