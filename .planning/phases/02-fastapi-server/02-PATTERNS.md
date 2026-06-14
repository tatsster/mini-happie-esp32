# Phase 2: FastAPI Server - Pattern Map

**Mapped:** 2026-06-14
**Files analyzed:** 4 (server/main.py, server/requirements.txt, tests/test_api.py, data/manifest.json)
**Analogs found:** 3 / 4 (data/manifest.json is runtime-only; no analog needed)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `server/main.py` | controller + service | request-response + file-I/O | `server/converters.py` | partial (same package, different role) |
| `server/requirements.txt` | config | — | `server/requirements.txt` (itself, modify) | exact |
| `tests/test_api.py` | test | request-response | `tests/test_converters.py` | role-match |
| `data/manifest.json` | — | — | none (runtime artifact, not in repo) | none |

---

## Pattern Assignments

### `server/main.py` (controller + service, request-response + file-I/O)

**Analog:** `server/converters.py` (same package; import style and error-handling conventions)

**Imports pattern** (`server/converters.py` lines 1–4):
```python
import io
import struct

from PIL import Image
```
Apply the same convention to `server/main.py`: stdlib imports first, blank line, then third-party/local. For main.py the block will be:
```python
import datetime
import hashlib
import json
import os
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Path as FPath, UploadFile
from fastapi.responses import JSONResponse, Response

from server.converters import convert_png, convert_sheet
```

**Module-level constants pattern** (RESEARCH.md Pattern 1):
```python
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
FRAMES_DIR = DATA_DIR / "frames"
SONGS_DIR = DATA_DIR / "songs"
MANIFEST_PATH = DATA_DIR / "manifest.json"

EMPTY_MANIFEST: dict = {"frames": [], "songs": [], "updated_at": ""}
_manifest_lock = threading.Lock()
```
All file I/O uses these module-level `Path` constants — this enables `monkeypatch.setattr` in tests without dependency injection wiring.

**Lifespan startup pattern** (RESEARCH.md Pattern 1):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    SONGS_DIR.mkdir(parents=True, exist_ok=True)
    if not MANIFEST_PATH.exists():
        _write_manifest_atomic(EMPTY_MANIFEST)
    yield

app = FastAPI(lifespan=lifespan)
```
Note: `@app.on_event("startup")` is deprecated since FastAPI 0.95 — use lifespan only.

**Atomic manifest write pattern** (RESEARCH.md Pattern 2):
```python
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

def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
```
`tempfile.mkstemp(dir=MANIFEST_PATH.parent)` keeps temp file on same filesystem. Use `os.replace()` not `os.rename()`.

**Error handling pattern** (`server/converters.py` lines 43–46):
```python
    except (ValueError, TypeError) as exc:
        raise exc
    except Exception as exc:
        raise ValueError(f"PNG conversion failed: {exc}") from exc
```
Apply the same two-tier pattern in endpoint handlers: known domain errors (`ValueError`) → HTTP 422; `FileNotFoundError` → HTTP 404; all other exceptions propagate as HTTP 500 (FastAPI default).

**Core endpoint patterns** (RESEARCH.md Code Examples):

GET manifest:
```python
@app.get("/manifest.json")
def get_manifest():
    data = json.loads(MANIFEST_PATH.read_text())
    return JSONResponse(content=data)
```

GET binary with ETag — copy this pattern for both `/frames/{name}.bin` and `/songs/{name}.json`:
```python
@app.get("/frames/{name}.bin")
def get_frame_bin(name: Annotated[str, FPath(pattern=r"^frame_\d+$")]):
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
ETag must be quoted: `'"<hash>"'` not `'<hash>'` (RFC 7232 requirement).

POST upload with lock-guarded manifest write:
```python
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
Entire manifest read-modify-write must be inside `_manifest_lock`.

DELETE with reorder (RESEARCH.md Pattern 5):
```python
def _delete_frame(name: str) -> None:
    """Must be called inside _manifest_lock."""
    manifest = _read_manifest()
    target_file = f"{name}.bin"
    if target_file not in manifest["frames"]:
        raise FileNotFoundError(name)

    idx = int(name.split("_")[1])
    total = len(manifest["frames"])

    (FRAMES_DIR / f"{name}.bin").unlink(missing_ok=True)
    (FRAMES_DIR / f"{name}.png").unlink(missing_ok=True)

    for i in range(idx + 1, total):          # ascending order — critical
        old, new = f"frame_{i}", f"frame_{i - 1}"
        (FRAMES_DIR / f"{old}.bin").rename(FRAMES_DIR / f"{new}.bin")
        (FRAMES_DIR / f"{old}.png").rename(FRAMES_DIR / f"{new}.png")

    manifest["frames"] = [f"frame_{i}.bin" for i in range(total - 1)]
    manifest["updated_at"] = _utc_now()
    _write_manifest_atomic(manifest)

@app.delete("/frames/{name}", status_code=204)
def delete_frame(name: Annotated[str, FPath(pattern=r"^frame_\d+$")]):
    with _manifest_lock:
        try:
            _delete_frame(name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Frame '{name}' not found")
```

**Path parameter safety pattern** (RESEARCH.md Pattern 6):
```python
name: Annotated[str, FPath(pattern=r"^frame_\d+$")]
name: Annotated[str, FPath(pattern=r"^song_\d+$")]
```
Apply to ALL endpoints with `{name}` parameters. FastAPI validates before handler runs; invalid names auto-return 422.

---

### `server/requirements.txt` (config, modify)

**Analog:** `server/requirements.txt` itself (lines 1, current content)
```
Pillow>=10.0.0
```

**Modified content — append these three lines:**
```
fastapi>=0.115.0
uvicorn>=0.30.0
python-multipart>=0.0.9
```
`python-multipart` must be present or `POST /upload/*` endpoints silently return 422 even when the file is in the request.

---

### `tests/test_api.py` (test, request-response)

**Analog:** `tests/test_converters.py` (same test directory, same pytest conventions)

**Imports pattern** (`tests/test_converters.py` lines 1–3):
```python
import struct
import pytest
from server.converters import convert_png, convert_sheet
```
Apply the same convention to `tests/test_api.py`:
```python
import io
import json
import pytest
from PIL import Image
from fastapi.testclient import TestClient
import server.main as main_module
```

**Fixture pattern** (`tests/conftest.py` lines 13–17 — PNG fixture style):
```python
@pytest.fixture
def solid_red_1x1_png():
    img = Image.new("RGB", (1, 1), color=(255, 0, 0))
    return _png_bytes(img)
```
Apply same factory style for the `client` fixture in `tests/test_api.py`. Use `monkeypatch.setattr` (not FastAPI dependency overrides) to redirect module-level Path constants to `tmp_path`:
```python
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main_module, "FRAMES_DIR", tmp_path / "frames")
    monkeypatch.setattr(main_module, "SONGS_DIR", tmp_path / "songs")
    monkeypatch.setattr(main_module, "MANIFEST_PATH", tmp_path / "manifest.json")
    (tmp_path / "frames").mkdir()
    (tmp_path / "songs").mkdir()

    with TestClient(main_module.app) as c:
        yield c
```
Note: `monkeypatch` is a pytest built-in — no import needed.

**Test class organization pattern** (`tests/test_converters.py` lines 6–7):
```python
class TestConvertPng:
    def test_red_pixel_rgb565(self, solid_red_1x1_png):
```
Group tests by endpoint using the same class-per-feature pattern:
- `class TestGetManifest` — API-01
- `class TestGetFrameBin` — API-02
- `class TestGetSongJson` — API-03
- `class TestUploadFrame` — API-04
- `class TestUploadSong` — API-05
- `class TestDeleteFrame` — API-06
- `class TestDeleteSong` — API-07
- `class TestETag` — API-08
- `class TestPathTraversal` — security

**Test assertion pattern** (`tests/test_converters.py` lines 9, 39–41):
```python
assert result == b'\xf8\x00'
# ...
with pytest.raises(ValueError, match="PNG conversion failed"):
    convert_png(b"not a png")
```
For HTTP tests, match on `response.status_code` and `response.json()` keys:
```python
def test_get_manifest_empty(self, client):
    r = client.get("/manifest.json")
    assert r.status_code == 200
    body = r.json()
    assert "frames" in body
    assert "songs" in body
    assert "updated_at" in body

def test_upload_frame_invalid_png(self, client, solid_128x160_png):
    r = client.post("/upload/frame", files={"file": ("bad.png", b"not a png", "image/png")})
    assert r.status_code == 422
```

**File upload test pattern** (RESEARCH.md Code Examples — TestClient fixture):
```python
# files= kwarg: {"field_name": (filename, bytes_or_file, content_type)}
r = client.post("/upload/frame", files={"file": ("frame.png", png_bytes, "image/png")})
assert r.status_code == 201
assert r.json()["name"] == "frame_0"
```

**Shared fixture: PNG bytes** — reuse `conftest.py` fixtures (`solid_128x160_png`, `small_png`) already defined there. Do not duplicate them in `test_api.py`.

---

## Shared Patterns

### Module-level Path constants (monkeypatch target)
**Source:** `server/main.py` (to be created)
**Apply to:** `tests/test_api.py` client fixture
```python
# In server/main.py — these names must match exactly for monkeypatch to work:
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
FRAMES_DIR = DATA_DIR / "frames"
SONGS_DIR = DATA_DIR / "songs"
MANIFEST_PATH = DATA_DIR / "manifest.json"

# In tests/test_api.py — patch by name:
monkeypatch.setattr(main_module, "FRAMES_DIR", tmp_path / "frames")
```

### ValueError → HTTPException 422
**Source:** `server/converters.py` lines 43–46 (error origin); apply in `server/main.py` handlers
**Apply to:** `POST /upload/frame`, `POST /upload/song`
```python
try:
    bin_bytes = convert_png(raw)
except ValueError as exc:
    raise HTTPException(status_code=422, detail=str(exc))
```

### FileNotFoundError → HTTPException 404
**Apply to:** `GET /frames/{name}.bin`, `GET /songs/{name}.json`, `DELETE /frames/{name}`, `DELETE /songs/{name}`
```python
if not path.exists():
    raise HTTPException(status_code=404, detail=f"Frame '{name}' not found")
# — or for delete helpers —
except FileNotFoundError:
    raise HTTPException(status_code=404, detail=f"Frame '{name}' not found")
```

### Manifest lock scope
**Apply to:** All endpoints that write to the manifest (upload, delete)
- Lock must wrap the full read-modify-write sequence, not just the write call.
- Helper functions (`_delete_frame`, `_delete_song`) must be called inside an active `_manifest_lock` block.

### pytest fixture sharing via conftest.py
**Source:** `tests/conftest.py` lines 13–52
**Apply to:** `tests/test_api.py`
Fixtures `solid_128x160_png`, `small_png`, `solid_red_1x1_png`, and `happy_birthday_text` are already available to all test files through `conftest.py` — import them by parameter name, do not redefine.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `data/manifest.json` | runtime artifact | — | Created at server startup; not a code file; no analog needed. Content schema is fully specified in D-13. |

---

## Metadata

**Analog search scope:** `server/`, `tests/`
**Files scanned:** 4 (converters.py, requirements.txt, conftest.py, test_converters.py)
**Pattern extraction date:** 2026-06-14
**Key anti-patterns documented in RESEARCH.md:** unquoted ETag, descending rename order, manifest write outside lock, manifest auto-rebuild on GET, `os.rename()` instead of `os.replace()`
