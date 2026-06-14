# Phase 2: FastAPI Server - Research

**Researched:** 2026-06-14
**Domain:** FastAPI REST API, binary file serving, manifest JSON persistence, sequential slot management
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Manifest persisted as `data/manifest.json`. Updated atomically on every upload and delete.
- **D-02:** Manifest NOT auto-rebuilt on startup. Starts empty on fresh install. Manual file drops not reflected.
- **D-03:** `updated_at` set to current UTC ISO8601 on every write (upload, delete, reorder rename).
- **D-04:** Sequential slot names: `frame_0`, `frame_1`, ... and `song_0`, `song_1`, ...
- **D-05:** Upload takes next available index (next N after max existing index).
- **D-06:** Delete triggers reorder-rename: remaining slots fill the gap. All associated files renamed together (frame: `.bin` + `.png`; song: `.json`).
- **D-07:** Delete + reorder bumps `updated_at` so ESP32 knows to re-sync.
- **D-08:** `POST /upload/frame` writes both `data/frames/{name}.bin` AND `data/frames/{name}.png`. PNG stored but NOT served in Phase 2.
- **D-09:** ETag = MD5 hex digest of file content. Applied to `GET /frames/{name}.bin` and `GET /songs/{name}.json`.
- **D-10:** Storage layout: `data/frames/frame_N.bin`, `data/frames/frame_N.png`, `data/songs/song_N.json`
- **D-11:** Convert once at upload; serve pre-stored bytes on read.
- **D-12:** Files deleted explicitly via DELETE endpoints.
- **D-13:** Manifest format: `{ "frames": ["frame_0.bin", ...], "songs": ["song_0.json", ...], "updated_at": "ISO8601" }`
- **D-14:** Frame binary: raw big-endian uint16_t RGB565, exactly 40960 bytes (128×160×2)

### Claude's Discretion

- FastAPI app structure: single `server/main.py` or split into modules — Claude decides
- HTTP error response format: FastAPI default `{"detail": "..."}` is fine
- File I/O error handling: `FileNotFoundError` → 404; unexpected errors → 500
- Port: `8080` default, configurable via env var (Docker config is Phase 4)

### Deferred Ideas (OUT OF SCOPE)

- `GET /frames/{name}.png` thumbnail endpoint — Phase 3
- Custom BPM per song upload — still out of scope
- Manifest auto-rebuild on startup — decided against
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| API-01 | `GET /manifest.json` returns JSON with `frames`, `songs`, `updated_at` | Serve stored `data/manifest.json` via `JSONResponse`; initialize empty if missing on startup |
| API-02 | `GET /frames/{name}.bin` returns raw RGB565 binary | `Response(content=bytes, media_type="application/octet-stream")` with ETag header |
| API-03 | `GET /songs/{name}.json` returns melody JSON array | `FileResponse` or `JSONResponse` with ETag header |
| API-04 | `POST /upload/frame` accepts PNG, converts, stores `.bin` + `.png` | `UploadFile` → `await file.read()` → `convert_png()` → write both files → update manifest |
| API-05 | `POST /upload/song` accepts text sheet, converts, stores `.json` | `UploadFile` → decode text → `convert_sheet()` → `json.dump()` → write file → update manifest |
| API-06 | `DELETE /frames/{name}` removes frame and updates manifest | Delete `.bin` + `.png`, reorder remaining slots, rewrite manifest |
| API-07 | `DELETE /songs/{name}` removes song and updates manifest | Delete `.json`, reorder remaining slots, rewrite manifest |
| API-08 | Binary responses include ETag header | MD5 hex of file content; set `ETag` header on `GET /frames/{name}.bin` and `GET /songs/{name}.json` |
</phase_requirements>

---

## Summary

Phase 2 builds a FastAPI HTTP server that manages two asset types (frames and songs) stored on local disk, serving them to an ESP32 client. The server is purely synchronous file I/O wrapped in FastAPI's async handler layer — no database, no background tasks, no authentication. The complexity concentrates in three areas: (1) sequential slot management with reorder-on-delete across multiple file extensions per asset, (2) atomic manifest JSON persistence so a crash mid-write leaves the manifest uncorrupted, and (3) ETag computation from file content MD5 so the ESP32 can skip unchanged downloads.

FastAPI's `TestClient` (backed by httpx, already installed) supports full integration testing without a live server. Since all endpoints are synchronous file I/O, no async test infrastructure is needed — standard pytest with `def test_*` functions using `TestClient` is the right pattern. The converters from Phase 1 are already tested in isolation; Phase 2 tests focus on HTTP behavior, file storage, and manifest state.

The Phase 1 `server/converters.py` is the only integration point from prior work. `convert_png()` is called with the raw upload bytes and returns 40960 bytes to write as `.bin`; the original PNG bytes are stored separately as `.png`. `convert_sheet()` is called with the decoded upload text and returns a list of dicts to JSON-serialize as `.json`.

**Primary recommendation:** Single `server/main.py` file with a `pathlib.Path`-based `DATA_DIR` constant, a module-level manifest lock (`threading.Lock`) for concurrent-safe manifest writes, and `FileResponse`/`Response` for binary serving. Keep the module structure flat for Phase 2; split into router modules in Phase 3 only if warranted.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| REST endpoint routing | API / Backend | — | FastAPI handles HTTP routing and request parsing |
| File storage (frames, songs) | API / Backend | Database / Storage (local disk) | Files written to `data/` on the host filesystem |
| Manifest persistence | API / Backend | — | Single JSON file maintained by the server process |
| PNG-to-RGB565 conversion | API / Backend | — | `convert_png()` runs server-side at upload time |
| Sheet-to-melody conversion | API / Backend | — | `convert_sheet()` runs server-side at upload time |
| ETag computation | API / Backend | — | Server computes MD5; client decides whether to skip download |
| Sequential slot management | API / Backend | — | Server owns naming and reorder logic; ESP32 consumes manifest as-is |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | 0.136.3 | HTTP framework, routing, validation | [VERIFIED: PyPI] De facto Python async API framework; built-in OpenAPI, type-driven request parsing |
| `uvicorn` | 0.49.0 | ASGI server for running FastAPI | [VERIFIED: PyPI] FastAPI's official recommended server |
| `python-multipart` | 0.0.32 | Form data / file upload parsing | [VERIFIED: PyPI] Required by FastAPI for `UploadFile`; without it, file upload endpoints raise 422 |
| `Pillow` | >=10.0.0 | Already in `server/requirements.txt` for `convert_png()` | Inherited from Phase 1 |

### Supporting (tests only)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | 0.28.1 | HTTP client backing `TestClient` | Already installed; required by `fastapi.testclient.TestClient` |
| `pytest` | 9.0.2 | Test runner | Already installed; existing pattern in `tests/` |

### Not Needed

`pytest-asyncio` is available (1.4.0) but NOT required here. `TestClient` runs synchronous tests against async FastAPI apps without async fixtures. Only add `pytest-asyncio` if async test fixtures are needed (they are not in this phase).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `fastapi` | Flask | Flask lacks built-in async, type validation, and OpenAPI; FastAPI already decided in Phase 1 project stack |
| `uvicorn` | gunicorn+uvicorn | gunicorn adds complexity; uvicorn standalone is sufficient for homelab |
| `Response(bytes)` for binary | `FileResponse` | `FileResponse` streams from path; `Response(bytes)` reads file into memory first. For 40960-byte frames, memory approach is simpler and equally fast |

**Installation (add to `server/requirements.txt`):**
```bash
fastapi>=0.115.0
uvicorn>=0.30.0
python-multipart>=0.0.9
```

**Version verification:**
```
fastapi: 0.136.3 (PyPI, latest as of 2026-06-14) [VERIFIED: pip3 index versions]
uvicorn: 0.49.0 (PyPI, latest as of 2026-06-14) [VERIFIED: pip3 index versions]
python-multipart: 0.0.32 (PyPI, latest as of 2026-06-14) [VERIFIED: pip3 index versions]
httpx: 0.28.1 (already installed) [VERIFIED: pip3 show]
pytest: 9.0.2 (already installed) [VERIFIED: pip3 show]
```

---

## Package Legitimacy Audit

| Package | Registry | slopcheck | Disposition |
|---------|----------|-----------|-------------|
| `fastapi` | PyPI | [OK] | Approved |
| `uvicorn` | PyPI | [OK] | Approved |
| `python-multipart` | PyPI | [OK] — slopcheck noted "classic LLM naming pattern but package is established" | Approved |
| `httpx` | PyPI | [OK] | Approved |
| `pytest-asyncio` | PyPI | [OK] | Approved (not needed for this phase, listed for completeness) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
HTTP Client (ESP32 / curl / browser)
          |
          v
   FastAPI (server/main.py)
          |
    +-----+-----+
    |             |
    v             v
 Routing       UploadFile
 (GET/DELETE)  (POST upload)
    |             |
    |        +----+----+
    |        |         |
    |   convert_png()  convert_sheet()
    |   (converters)   (converters)
    |        |         |
    v        v         v
 data/              data/
 frames/             songs/
 frame_N.bin         song_N.json
 frame_N.png
          |
          v
   data/manifest.json
   (read on GET /manifest.json,
    written atomically on every
    upload + delete)
```

### Recommended Project Structure

```
server/
├── __init__.py          # already exists (empty)
├── converters.py        # already exists (Phase 1 output)
├── main.py              # Phase 2: FastAPI app + all endpoints
└── requirements.txt     # add fastapi, uvicorn, python-multipart

tests/
├── __init__.py          # already exists
├── conftest.py          # already exists (PNG/sheet fixtures) — extend with app fixture
├── test_converters.py   # already exists (Phase 1 tests — do not modify)
└── test_api.py          # Phase 2: new — all HTTP integration tests

data/                    # created by server on startup (mkdir if missing)
├── frames/              # frame_N.bin + frame_N.png
└── songs/               # song_N.json
```

### Pattern 1: FastAPI app initialization with data directory setup

**What:** Create `data/frames/` and `data/songs/` on startup; initialize empty manifest if `data/manifest.json` does not exist.
**When to use:** Startup lifespan — ensures first request never fails due to missing directories.

```python
# Source: https://fastapi.tiangolo.com/advanced/events/
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
FRAMES_DIR = DATA_DIR / "frames"
SONGS_DIR = DATA_DIR / "songs"
MANIFEST_PATH = DATA_DIR / "manifest.json"

EMPTY_MANIFEST = {"frames": [], "songs": [], "updated_at": ""}

@asynccontextmanager
async def lifespan(app: FastAPI):
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    SONGS_DIR.mkdir(parents=True, exist_ok=True)
    if not MANIFEST_PATH.exists():
        _write_manifest_atomic(EMPTY_MANIFEST)
    yield

app = FastAPI(lifespan=lifespan)
```

### Pattern 2: Atomic manifest write (write-then-rename)

**What:** Write manifest to a `.tmp` sibling, then `os.replace()` it over the real path. On POSIX, `os.replace()` is atomic — readers always see either the old or new manifest, never a partial write.
**When to use:** Every upload and delete operation.

```python
# Source: https://docs.python.org/3/library/os.html#os.replace (POSIX atomicity guarantee)
import json
import os
import tempfile
import threading

_manifest_lock = threading.Lock()

def _write_manifest_atomic(manifest: dict) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=MANIFEST_PATH.parent, suffix=".tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(manifest, f, indent=2)
        os.replace(tmp_path, MANIFEST_PATH)
    except Exception:
        os.unlink(tmp_path)
        raise

def _read_manifest() -> dict:
    with MANIFEST_PATH.open() as f:
        return json.load(f)
```

Key points:
- `tempfile.mkstemp(dir=MANIFEST_PATH.parent)` ensures temp file is on the same filesystem as the destination (required for `os.replace()` atomicity).
- `threading.Lock()` serializes concurrent uploads/deletes so two requests cannot interleave manifest reads and writes.
- `os.replace()` overwrites atomically; `os.rename()` may fail if destination exists on some systems.

### Pattern 3: File upload with UploadFile

**What:** Accept multipart form data, read bytes, call converter, write output file(s).
**When to use:** `POST /upload/frame` and `POST /upload/song`.

```python
# Source: https://fastapi.tiangolo.com/tutorial/request-files/
from fastapi import FastAPI, File, UploadFile, HTTPException
from typing import Annotated

@app.post("/upload/frame", status_code=201)
async def upload_frame(file: Annotated[UploadFile, File()]):
    data = await file.read()
    try:
        bin_bytes = convert_png(data)  # raises ValueError on bad input
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    with _manifest_lock:
        manifest = _read_manifest()
        idx = len(manifest["frames"])
        name = f"frame_{idx}"
        (FRAMES_DIR / f"{name}.bin").write_bytes(bin_bytes)
        (FRAMES_DIR / f"{name}.png").write_bytes(data)  # original PNG
        manifest["frames"].append(f"{name}.bin")
        manifest["updated_at"] = _utc_now()
        _write_manifest_atomic(manifest)

    return {"name": name}
```

Note: The entire manifest read-modify-write is inside `_manifest_lock` to prevent race conditions when two uploads arrive concurrently.

### Pattern 4: Binary response with ETag

**What:** Read file bytes, compute MD5, return as `Response` with `ETag` header and correct media type.
**When to use:** `GET /frames/{name}.bin` and `GET /songs/{name}.json`.

```python
# Source: https://fastapi.tiangolo.com/advanced/custom-response/
# Source: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag
import hashlib
from fastapi import Response
from fastapi.responses import FileResponse

@app.get("/frames/{name}.bin")
def get_frame(name: Annotated[str, Path(pattern=r"^frame_\d+$")]):
    path = FRAMES_DIR / f"{name}.bin"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Frame '{name}' not found")
    data = path.read_bytes()
    etag = f'"{hashlib.md5(data).hexdigest()}"'
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"ETag": etag},
    )
```

Note: The ETag value must be quoted per RFC 7232 (`"<hash>"`, not `<hash>`). [CITED: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/ETag]

### Pattern 5: Sequential reorder-on-delete

**What:** When slot `frame_K` is deleted, rename `frame_{K+1}` → `frame_K`, `frame_{K+2}` → `frame_{K+1}`, etc. Rename all associated files per slot atomically using `Path.rename()`.
**When to use:** `DELETE /frames/{name}` and `DELETE /songs/{name}`.

```python
def _delete_frame(name: str) -> None:
    """Must be called inside _manifest_lock."""
    manifest = _read_manifest()
    target_file = f"{name}.bin"
    if target_file not in manifest["frames"]:
        raise FileNotFoundError(name)

    idx = int(name.split("_")[1])
    total = len(manifest["frames"])

    # Delete target files
    (FRAMES_DIR / f"{name}.bin").unlink(missing_ok=True)
    (FRAMES_DIR / f"{name}.png").unlink(missing_ok=True)

    # Rename remaining slots to fill the gap
    for i in range(idx + 1, total):
        old = f"frame_{i}"
        new = f"frame_{i - 1}"
        (FRAMES_DIR / f"{old}.bin").rename(FRAMES_DIR / f"{new}.bin")
        (FRAMES_DIR / f"{old}.png").rename(FRAMES_DIR / f"{new}.png")

    # Rebuild the frames list from the new slot count
    new_total = total - 1
    manifest["frames"] = [f"frame_{i}.bin" for i in range(new_total)]
    manifest["updated_at"] = _utc_now()
    _write_manifest_atomic(manifest)
```

Key points:
- Rename loop runs in ascending order (`idx+1` to `total-1`) so no rename clobbers the next source.
- Both `.bin` and `.png` are renamed together — they are always co-located.
- The manifest `frames` list is rebuilt from scratch (not via string replacement) to avoid state drift.

### Pattern 6: Path parameter safety with Path() regex

**What:** Restrict `{name}` path parameters to the exact pattern `frame_N` or `song_N` to prevent path traversal (e.g., `../etc/passwd`).
**When to use:** All endpoints with `{name}` path parameters.

```python
# Source: FastAPI Path() validator with pattern kwarg
from typing import Annotated
from fastapi import Path

# In endpoint signature:
name: Annotated[str, Path(pattern=r"^frame_\d+$")]
name: Annotated[str, Path(pattern=r"^song_\d+$")]
```

FastAPI validates the pattern before the handler runs; an invalid name returns HTTP 422 automatically. [VERIFIED: FastAPI docs + confirmed via pattern kwarg behavior in Pydantic v2]

### Pattern 7: Dependency injection for DATA_DIR in tests

**What:** Make `DATA_DIR` injectable so tests can point the server at a `tmp_path` directory.
**When to use:** Integration test fixtures.

```python
# In server/main.py — expose a getter dependency:
def get_data_dir() -> Path:
    return DATA_DIR

# In tests/test_api.py:
from fastapi.testclient import TestClient
from server.main import app, get_data_dir

@pytest.fixture
def client(tmp_path):
    (tmp_path / "frames").mkdir()
    (tmp_path / "songs").mkdir()
    # Write empty manifest so startup does not need to create it
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"frames": [], "songs": [], "updated_at": ""}')

    app.dependency_overrides[get_data_dir] = lambda: tmp_path
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

Alternatively, set `DATA_DIR` as a module-level variable and patch it in tests using `monkeypatch`. The dependency override approach is cleaner for FastAPI. [ASSUMED — exact override wiring depends on how DATA_DIR is used in endpoint handlers]

### Anti-Patterns to Avoid

- **Rebuilding manifest on GET:** Scanning `data/frames/` on every `GET /manifest.json` creates a TOCTOU race and ignores the "never auto-rebuild" decision (D-02). Always read from `data/manifest.json`.
- **Deriving ETag from mtime:** `os.path.getmtime()` resets when the Docker volume is copied or the host FS is remounted. MD5 of content is stable (D-09).
- **Writing manifest without a lock:** Two concurrent uploads can interleave manifest reads, causing the second write to overwrite the first upload's entry.
- **Using `os.rename()` for atomic replace:** On macOS/Linux `os.rename()` is atomic, but `os.replace()` is the correct POSIX API for overwrite-if-exists semantics. Use `os.replace()`.
- **Ascending rename without checking order:** When renaming `frame_2` → `frame_1` then `frame_3` → `frame_2`, always rename in ascending index order. Descending order would clobber source files.
- **Accepting arbitrary `{name}` strings:** Without the `Path(pattern=...)` validator, a request for `/frames/../../etc/passwd.bin` would resolve to a path outside `data/frames/`. The regex gate is the only path traversal defense in this server.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multipart file upload parsing | Custom `Content-Type: multipart/form-data` parser | FastAPI `UploadFile` + `python-multipart` | Multipart boundary parsing has many edge cases; `python-multipart` is the FastAPI-blessed library |
| ETag computation | Custom hash or timestamp scheme | `hashlib.md5(data).hexdigest()` from stdlib | Standard library; no extra dependency needed |
| Atomic file write | Write directly to target path | `tempfile.mkstemp()` + `os.replace()` | Direct write leaves corrupted file on process crash; write-then-rename is the POSIX standard |
| HTTP test client | Raw `socket` or `requests` against live server | `fastapi.testclient.TestClient` | TestClient runs in-process, no port binding, no server startup needed |
| Path traversal protection | Manual `..` string checking | `Path(pattern=r"^frame_\d+$")` in FastAPI | Regex in `Path()` is validated by Pydantic before handler runs; string checking is error-prone |

**Key insight:** All the "interesting" problems in this phase (file upload parsing, atomic writes, ETag, path safety) have standard Python/FastAPI solutions. The only genuinely novel logic is the sequential reorder-on-delete algorithm, which must be hand-implemented.

---

## Common Pitfalls

### Pitfall 1: `python-multipart` missing at runtime

**What goes wrong:** FastAPI silently returns HTTP 422 with `"detail": "Field required"` on `POST /upload/frame` even when the file is present in the request.
**Why it happens:** `python-multipart` is not listed in FastAPI's hard dependencies; it is loaded lazily. If omitted from `requirements.txt`, the server starts fine but upload endpoints fail.
**How to avoid:** Add `python-multipart>=0.0.9` to `server/requirements.txt`. Verify with a smoke-test upload in CI.
**Warning signs:** 422 response on upload with `"msg": "field required"` and no log error about the file.

### Pitfall 2: Unquoted ETag value

**What goes wrong:** ESP32 `If-None-Match` matching fails; server always returns 200 instead of 304.
**Why it happens:** RFC 7232 requires ETag values to be quoted strings: `ETag: "d41d8cd..."`. An unquoted value is technically invalid.
**How to avoid:** Always format as `f'"{hashlib.md5(data).hexdigest()}"'` (with surrounding double quotes inside the string).
**Warning signs:** ESP32 always re-downloads files even when content has not changed.

### Pitfall 3: Rename in descending order on delete

**What goes wrong:** Renaming `frame_3` → `frame_2` before renaming `frame_2` → `frame_1` clobbers the original `frame_2` file. Data loss.
**Why it happens:** Naively iterating `range(total-1, idx, -1)`.
**How to avoid:** Always iterate in ascending order: `for i in range(idx+1, total): rename i → i-1`.
**Warning signs:** After deleting `frame_1` from `[frame_0, frame_1, frame_2, frame_3]`, the result is `[frame_0, frame_1, frame_2]` but `frame_1`/`frame_2` contain wrong data.

### Pitfall 4: Manifest written outside the lock

**What goes wrong:** Under concurrent uploads, one upload's manifest entry silently disappears.
**Why it happens:** Thread A reads manifest (0 frames), Thread B reads manifest (0 frames), both write 1 frame. The second write overwrites the first.
**How to avoid:** All code that reads + modifies + writes the manifest must hold `_manifest_lock`. The entire sequence is a critical section.
**Warning signs:** Uploading two frames in quick succession results in only one appearing in `/manifest.json`.

### Pitfall 5: `data/` directory not created before first request

**What goes wrong:** `FileNotFoundError` on the first upload if `data/frames/` does not exist.
**Why it happens:** `Path.write_bytes()` does not create parent directories.
**How to avoid:** Create `FRAMES_DIR` and `SONGS_DIR` in the lifespan startup handler with `mkdir(parents=True, exist_ok=True)`.
**Warning signs:** First upload returns HTTP 500; traceback shows `FileNotFoundError: [Errno 2]`.

### Pitfall 6: `asyncio_mode` not configured for pytest-asyncio (if added later)

**What goes wrong:** Tests using `async def test_*` are silently skipped or fail with a coroutine warning.
**Why it happens:** pytest-asyncio 1.x defaults to `strict` mode and requires explicit `@pytest.mark.asyncio` markers.
**How to avoid:** This phase uses synchronous `def test_*` functions with `TestClient`, so this pitfall does not apply. Document it for Phase 3 if async test fixtures become needed.
**Warning signs:** Async test functions appear as `PASSED` with zero assertions executed.

---

## Code Examples

Verified patterns from official sources:

### GET /manifest.json

```python
# Source: FastAPI docs — JSONResponse
from fastapi.responses import JSONResponse

@app.get("/manifest.json")
def get_manifest():
    data = json.loads(MANIFEST_PATH.read_text())
    return JSONResponse(content=data)
```

### GET /frames/{name}.bin with ETag

```python
# Source: https://fastapi.tiangolo.com/advanced/custom-response/
import hashlib
from fastapi import Path, Response, HTTPException
from typing import Annotated

@app.get("/frames/{name}.bin")
def get_frame_bin(name: Annotated[str, Path(pattern=r"^frame_\d+$")]):
    path = FRAMES_DIR / f"{name}.bin"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Frame '{name}' not found")
    data = path.read_bytes()
    etag = f'"{hashlib.md5(data).hexdigest()}"'
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"ETag": etag},
    )
```

### GET /songs/{name}.json with ETag

```python
@app.get("/songs/{name}.json")
def get_song_json(name: Annotated[str, Path(pattern=r"^song_\d+$")]):
    path = SONGS_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Song '{name}' not found")
    data = path.read_bytes()
    etag = f'"{hashlib.md5(data).hexdigest()}"'
    return Response(
        content=data,
        media_type="application/json",
        headers={"ETag": etag},
    )
```

### POST /upload/frame

```python
# Source: https://fastapi.tiangolo.com/tutorial/request-files/
from fastapi import UploadFile, File
from server.converters import convert_png
import datetime

def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

@app.post("/upload/frame", status_code=201)
async def upload_frame(file: Annotated[UploadFile, File()]):
    raw = await file.read()
    try:
        bin_bytes = convert_png(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    with _manifest_lock:
        manifest = _read_manifest()
        idx = len(manifest["frames"])
        name = f"frame_{idx}"
        (FRAMES_DIR / f"{name}.bin").write_bytes(bin_bytes)
        (FRAMES_DIR / f"{name}.png").write_bytes(raw)
        manifest["frames"].append(f"{name}.bin")
        manifest["updated_at"] = _utc_now()
        _write_manifest_atomic(manifest)

    return {"name": name}
```

### POST /upload/song

```python
from server.converters import convert_sheet

@app.post("/upload/song", status_code=201)
async def upload_song(file: Annotated[UploadFile, File()]):
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
        notes = convert_sheet(text)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    with _manifest_lock:
        manifest = _read_manifest()
        idx = len(manifest["songs"])
        name = f"song_{idx}"
        (SONGS_DIR / f"{name}.json").write_text(
            json.dumps(notes, indent=2), encoding="utf-8"
        )
        manifest["songs"].append(f"{name}.json")
        manifest["updated_at"] = _utc_now()
        _write_manifest_atomic(manifest)

    return {"name": name}
```

### DELETE /frames/{name}

```python
@app.delete("/frames/{name}", status_code=204)
def delete_frame(name: Annotated[str, Path(pattern=r"^frame_\d+$")]):
    with _manifest_lock:
        try:
            _delete_frame(name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Frame '{name}' not found")
```

### TestClient fixture with isolated tmp_path

```python
# Source: https://fastapi.tiangolo.com/tutorial/testing/
import pytest
from fastapi.testclient import TestClient
import server.main as main_module

@pytest.fixture
def client(tmp_path, monkeypatch):
    # Point module-level paths at tmp_path
    monkeypatch.setattr(main_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main_module, "FRAMES_DIR", tmp_path / "frames")
    monkeypatch.setattr(main_module, "SONGS_DIR", tmp_path / "songs")
    monkeypatch.setattr(main_module, "MANIFEST_PATH", tmp_path / "manifest.json")
    (tmp_path / "frames").mkdir()
    (tmp_path / "songs").mkdir()

    with TestClient(main_module.app) as c:
        yield c
```

Using `monkeypatch.setattr` on module-level `Path` constants is simpler than FastAPI dependency overrides for this use case, since all file I/O uses the module-level constants directly. [ASSUMED — actual approach may vary depending on final main.py structure]

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `@asynccontextmanager async def lifespan(app)` | FastAPI ~0.95 | `on_event` is deprecated; lifespan is the correct pattern |
| `pytest.mark.asyncio` on every async test | `asyncio_mode = auto` in pytest.ini | pytest-asyncio 0.19+ | Auto mode removes boilerplate; not needed here since we use sync TestClient |
| `File(...)` as parameter default | `Annotated[UploadFile, File()]` | FastAPI ~0.95 (Pydantic v2) | Annotated style is now preferred; old style still works |
| `os.rename()` for atomic replace | `os.replace()` | Python 3.3+ | `os.replace()` explicitly specifies overwrite semantics; `os.rename()` is ambiguous on non-POSIX |

**Deprecated/outdated:**
- `@app.on_event("startup")`: Works but deprecated since FastAPI 0.95. Use `lifespan` context manager. [CITED: FastAPI docs]
- Passing `File(...)` as a default (non-Annotated style): Still functional but the Annotated form is idiomatic in modern FastAPI.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `monkeypatch.setattr` on module-level Path constants is the cleanest test isolation approach | Code Examples (TestClient fixture) | If main.py uses constants inside closures, patching them after import may not affect running code; alternative is env var override |
| A2 | FastAPI `Path(pattern=...)` uses Pydantic v2 `pattern` kwarg (not `regex`) | Architecture Patterns #6 | In FastAPI < 0.100 with Pydantic v1, the kwarg was `regex=`; current FastAPI 0.136 uses Pydantic v2 so `pattern=` is correct |
| A3 | 40960-byte frame files reading into memory for MD5 computation is acceptable (not streaming) | Code Examples — ETag | For 40960 bytes this is fine; if frame size ever increases significantly, streaming MD5 would be needed |

---

## Open Questions

1. **How should `POST /upload/frame` behave if `convert_png()` is called with a non-128×160 PNG?**
   - What we know: `convert_png()` auto-resizes (Phase 1, D-01), so it never raises for wrong dimensions.
   - What's unclear: The API contract says "accepts a PNG" with no stated dimension restriction. REQUIREMENTS API-04 does not restrict. UI-06 mentions dimension validation but that is Phase 3's job.
   - Recommendation: Phase 2 accepts any valid PNG (convert_png resizes), no 422 for dimension mismatch. Phase 3 web UI adds client-side or server-side dimension validation per UI-06.

2. **Should `GET /manifest.json` return 200 with empty manifest on a fresh install, or 404?**
   - What we know: D-02 says manifest starts empty; D-01 says it is persisted on disk. Startup creates it if missing.
   - Recommendation: Always 200. An empty `{"frames": [], "songs": [], "updated_at": ""}` is a valid manifest. The ESP32 can handle an empty list.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | Server runtime | ✓ | 3.14.5 | — |
| pip | Package install | ✓ | 26.1.1 | — |
| pytest | Test runner | ✓ | 9.0.2 | — |
| httpx | TestClient backing | ✓ | 0.28.1 | — |
| fastapi | HTTP framework | ✗ (not yet installed) | — | Add to requirements.txt, install before dev |
| uvicorn | ASGI server | ✗ (not yet installed) | — | Add to requirements.txt, install before dev |
| python-multipart | File upload parsing | ✗ (not yet installed) | — | Add to requirements.txt; without it, uploads silently return 422 |
| Pillow | `convert_png()` | ✓ (in requirements.txt) | >=10.0.0 | — |

**Missing dependencies with no fallback:**
- `fastapi`, `uvicorn`, `python-multipart` — must be added to `server/requirements.txt` and installed. Wave 0 task.

**Missing dependencies with fallback:** none

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none — Wave 0 adds `pytest.ini` if needed |
| Quick run command | `pytest tests/test_api.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| API-01 | `GET /manifest.json` returns `frames`, `songs`, `updated_at` | integration | `pytest tests/test_api.py::test_get_manifest_empty -x` | ❌ Wave 0 |
| API-01 | Manifest reflects uploaded frames and songs | integration | `pytest tests/test_api.py::test_manifest_after_upload -x` | ❌ Wave 0 |
| API-02 | `GET /frames/{name}.bin` returns 40960 bytes | integration | `pytest tests/test_api.py::test_get_frame_bin -x` | ❌ Wave 0 |
| API-02 | `GET /frames/nonexistent.bin` returns 404 | integration | `pytest tests/test_api.py::test_get_frame_bin_not_found -x` | ❌ Wave 0 |
| API-03 | `GET /songs/{name}.json` returns JSON array | integration | `pytest tests/test_api.py::test_get_song_json -x` | ❌ Wave 0 |
| API-04 | `POST /upload/frame` stores `.bin` (40960 bytes) + `.png` | integration | `pytest tests/test_api.py::test_upload_frame_stores_files -x` | ❌ Wave 0 |
| API-04 | `POST /upload/frame` adds name to manifest | integration | `pytest tests/test_api.py::test_upload_frame_updates_manifest -x` | ❌ Wave 0 |
| API-04 | `POST /upload/frame` with invalid bytes returns 422 | integration | `pytest tests/test_api.py::test_upload_frame_invalid_png -x` | ❌ Wave 0 |
| API-05 | `POST /upload/song` stores `.json` and updates manifest | integration | `pytest tests/test_api.py::test_upload_song -x` | ❌ Wave 0 |
| API-05 | `POST /upload/song` with invalid sheet returns 422 | integration | `pytest tests/test_api.py::test_upload_song_invalid_sheet -x` | ❌ Wave 0 |
| API-06 | `DELETE /frames/{name}` removes files and updates manifest | integration | `pytest tests/test_api.py::test_delete_frame -x` | ❌ Wave 0 |
| API-06 | Delete reorders remaining slots and bumps `updated_at` | integration | `pytest tests/test_api.py::test_delete_frame_reorders_slots -x` | ❌ Wave 0 |
| API-07 | `DELETE /songs/{name}` removes file and updates manifest | integration | `pytest tests/test_api.py::test_delete_song -x` | ❌ Wave 0 |
| API-08 | `ETag` header present on binary response | integration | `pytest tests/test_api.py::test_etag_header_present -x` | ❌ Wave 0 |
| API-08 | Same file produces same ETag across two requests | integration | `pytest tests/test_api.py::test_etag_stable -x` | ❌ Wave 0 |
| — | Path traversal rejected (422 on `../foo`) | integration | `pytest tests/test_api.py::test_path_traversal_rejected -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_api.py -x -q`
- **Per wave merge:** `pytest tests/ -q` (includes Phase 1 converter tests)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_api.py` — all API integration tests (new file)
- [ ] `server/main.py` — FastAPI app (new file)
- [ ] `server/requirements.txt` — add `fastapi>=0.115.0`, `uvicorn>=0.30.0`, `python-multipart>=0.0.9`
- [ ] Install packages: `pip install fastapi uvicorn python-multipart`
- [ ] `data/frames/` and `data/songs/` directories — created by server lifespan startup (not pre-created in repo)

---

## Security Domain

`security_enforcement` not set in `.planning/config.json` — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Out of scope (homelab, single-owner, REQUIREMENTS.md explicitly excludes auth) |
| V3 Session Management | no | No sessions; stateless API |
| V4 Access Control | no | No roles; all endpoints open by design |
| V5 Input Validation | yes | `Path(pattern=r"^frame_\d+$")` on all name parameters; `convert_png`/`convert_sheet` raise `ValueError` on malformed input |
| V6 Cryptography | no | MD5 used for ETag only (cache fingerprint, not security hash); no authentication secrets |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `{name}` parameter | Tampering | `Path(pattern=r"^frame_\d+$")` regex — rejects any name with `/`, `..`, or non-digit characters |
| Oversized file upload exhausting disk | Denial of Service | [ASSUMED] FastAPI/python-multipart has no built-in upload size limit; for homelab this is acceptable. Could add `MAX_UPLOAD_BYTES` check on `len(raw)` if desired |
| Concurrent write race on manifest | Tampering / Integrity | `threading.Lock()` on all manifest read-modify-write sequences |

---

## Sources

### Primary (HIGH confidence)
- [FastAPI official docs — Request Files](https://fastapi.tiangolo.com/tutorial/request-files/) — UploadFile pattern, `await file.read()`, `python-multipart` requirement
- [FastAPI official docs — Custom Response](https://fastapi.tiangolo.com/advanced/custom-response/) — `Response(content, media_type, headers)`, `FileResponse`
- [FastAPI official docs — Response Headers](https://fastapi.tiangolo.com/advanced/response-headers/) — Setting `ETag` header
- [FastAPI official docs — Testing](https://fastapi.tiangolo.com/tutorial/testing/) — `TestClient`, file upload test pattern, `files={}` parameter
- [FastAPI official docs — Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) — `@asynccontextmanager` lifespan, startup directory creation
- [pytest-asyncio docs — Configuration](https://pytest-asyncio.readthedocs.io/en/stable/reference/configuration.html) — `asyncio_mode` defaults and config
- [MDN Web Docs — ETag](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/ETag) — quoted ETag format requirement
- [Python docs — os.replace](https://docs.python.org/3/library/os.html#os.replace) — POSIX atomic replace semantics
- PyPI registry — `pip3 index versions` for fastapi 0.136.3, uvicorn 0.49.0, python-multipart 0.0.32, httpx 0.28.1

### Secondary (MEDIUM confidence)
- [bswen.com — Atomic file writing in Python](https://docs.bswen.com/blog/2026-04-04-atomic-file-writing-python/) — `tempfile.mkstemp` + `os.replace` pattern confirmed
- [MDN — If-None-Match](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/If-None-Match) — conditional request behavior

### Tertiary (LOW confidence)
- none

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified via PyPI registry and slopcheck [OK]
- Architecture patterns: HIGH — all patterns sourced from FastAPI official documentation
- ETag/atomic write: HIGH — sourced from MDN RFC 7232 and Python stdlib docs
- Test patterns: HIGH — sourced from FastAPI testing docs; monkeypatch approach is ASSUMED (A1)
- Sequential reorder algorithm: HIGH — standard Python list/file operation; well-understood

**Research date:** 2026-06-14
**Valid until:** 2026-07-14 (FastAPI minor versions move fast; verify latest before install)
