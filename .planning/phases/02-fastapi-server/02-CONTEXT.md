# Phase 2: FastAPI Server - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement all REST API endpoints (`API-01` through `API-08`) with file storage and manifest management using FastAPI. No web UI (Phase 3), no Docker packaging (Phase 4) — pure API server backed by local disk storage.

</domain>

<decisions>
## Implementation Decisions

### Manifest Management

- **D-01:** Manifest is persisted as `data/manifest.json` on disk. Updated atomically on every upload and delete operation.
- **D-02:** Manifest is NOT auto-rebuilt on startup. It starts empty on a fresh install. If files are manually dropped into the volume outside the API, they will not appear in the manifest.
- **D-03:** `updated_at` is set to the current UTC ISO8601 timestamp on every write operation (upload, delete, or reorder rename). This is the signal the ESP32 uses to decide whether to re-sync.

### File Naming

- **D-04:** Frames use sequential slot names: `frame_0`, `frame_1`, `frame_2`, ... Songs use sequential slot names: `song_0`, `song_1`, ...
- **D-05:** On upload, the new asset takes the next available index (e.g., if `frame_0` and `frame_1` exist, upload creates `frame_2`).
- **D-06:** On delete, remaining assets are renamed to fill the gap (e.g., deleting `frame_1` renames `frame_2` → `frame_1`, `frame_3` → `frame_2`, etc.). All associated files are renamed together:
  - Frame: `data/frames/frame_N.bin` + `data/frames/frame_N.png`
  - Song: `data/songs/song_N.json`
- **D-07:** Any delete + reorder operation bumps `updated_at` in the manifest so the ESP32 knows to re-sync affected frames.

### Thumbnail Storage

- **D-08:** `POST /upload/frame` writes both `data/frames/{name}.bin` (for ESP32) and `data/frames/{name}.png` (original upload, for future thumbnail serving). The `.png` file is stored but NOT served by Phase 2 — `GET /frames/{name}.png` is deferred to Phase 3.

### ETag

- **D-09:** `GET /frames/{name}.bin` and `GET /songs/{name}.json` include `ETag: "{md5_hex}"` headers where the value is the MD5 hash of the file content. Stable across server restarts and Docker volume migrations — same file bytes always produce the same ETag. ESP32 can use `If-None-Match` to skip unchanged downloads.

### Carried Forward from Phase 1

- **D-10:** Storage layout: `data/frames/frame_N.bin`, `data/frames/frame_N.png`, `data/songs/song_N.json`
- **D-11:** Convert once at upload time; serve pre-stored bytes on read. No re-conversion per request.
- **D-12:** Files live until explicitly deleted via `DELETE /frames/{name}` or `DELETE /songs/{name}`
- **D-13:** Manifest format: `{ "frames": ["frame_0.bin", ...], "songs": ["song_0.json", ...], "updated_at": "ISO8601" }`
- **D-14:** Frame binary: raw big-endian uint16_t RGB565, exactly 40960 bytes (128×160×2)

### Claude's Discretion

- FastAPI app structure: single `server/main.py` or split into modules — Claude decides based on complexity
- HTTP error response format: FastAPI default `{"detail": "..."}` is fine for this homelab use case
- File I/O error handling: standard Python `FileNotFoundError` → 404; unexpected errors → 500
- Port: `8080` (from DEPLOY-03, configurable via env var — but Docker config is Phase 4)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Conversion module (integrate at upload endpoints)
- `server/converters.py` — `convert_png(data: bytes, width: int = 128, height: int = 160) -> bytes` and `convert_sheet(text: str, bpm: float = 120.0) -> list[dict]`; import these at `POST /upload/frame` and `POST /upload/song`

### Requirements
- `.planning/REQUIREMENTS.md` — `API-01` through `API-08` define the acceptance criteria for this phase
- `.planning/ROADMAP.md` — Phase 2 success criteria (curl tests, ETag behavior, delete behavior)

### Prior phase decisions (integration contract)
- `.planning/phases/01-conversion-core/01-CONTEXT.md` — D-15, D-16 define the dual-file storage contract (`.bin` + `.png` per frame) that Phase 2 must implement

### Existing scripts (for reference only — do not import)
- `scripts/png_to_rgb565.py` — source of conversion algorithm (already ported to `server/converters.py`)
- `scripts/sheet_music_to_melody.py` — source of melody parser (already ported to `server/converters.py`)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `server/converters.py::convert_png(data, width=128, height=160) -> bytes` — call at `POST /upload/frame`; returns raw RGB565 binary bytes to write as `.bin`
- `server/converters.py::convert_sheet(text, bpm=120.0) -> list[dict]` — call at `POST /upload/song`; returns `[{"freq": int, "ms": int}, ...]` to JSON-serialize as `.json`

### Established Patterns
- Phase 1 tests in `tests/` use pytest — maintain the same test structure for Phase 2 integration tests
- `server/requirements.txt` currently has `Pillow>=10.0.0` — FastAPI and uvicorn need to be added

### Integration Points
- `server/converters.py` is the only existing server module; `server/main.py` does not exist yet
- `data/` directory (for stored frames and songs) does not exist yet — server must create it on startup
- Phase 3 (Web UI) will call the same endpoints defined here; Phase 4 (Docker) will package the server

</code_context>

<specifics>
## Specific Ideas

- Sequential slot naming (`frame_0`, `frame_1`, ...) is intentional — the ESP32 firmware references frames by predictable names; arbitrary UUIDs would require manifest-driven name lookup on the device
- The reorder-on-delete behavior keeps the slot sequence contiguous, which simplifies ESP32 logic (no gaps to handle)

</specifics>

<deferred>
## Deferred Ideas

- `GET /frames/{name}.png` thumbnail endpoint — deferred to Phase 3 (Web UI); the PNG is stored by Phase 2 but not served until the UI needs it
- Custom BPM per song upload (upload form field) — already deferred in Phase 1; still out of scope
- Manifest auto-rebuild on startup — decided against; kept simple (empty manifest on fresh install)

</deferred>

---

*Phase: 2-FastAPI Server*
*Context gathered: 2026-06-14*
