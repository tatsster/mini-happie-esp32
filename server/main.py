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

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
FRAMES_DIR = DATA_DIR / "frames"
SONGS_DIR = DATA_DIR / "songs"
MANIFEST_PATH = DATA_DIR / "manifest.json"

EMPTY_MANIFEST: dict = {"frames": [], "songs": [], "updated_at": ""}
_manifest_lock = threading.Lock()

MAX_FRAME_BYTES = 1 * 1024 * 1024   # 1 MB — generous for a 128×160 PNG
MAX_SONG_BYTES = 64 * 1024           # 64 KB — ample for a text sheet


def _write_manifest_atomic(manifest: dict) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(dir=MANIFEST_PATH.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(manifest, f, indent=2)
        os.replace(tmp_path, MANIFEST_PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_manifest() -> dict:
    with MANIFEST_PATH.open() as f:
        return json.load(f)


def _utc_now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    SONGS_DIR.mkdir(parents=True, exist_ok=True)
    if not MANIFEST_PATH.exists():
        _write_manifest_atomic(EMPTY_MANIFEST)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/manifest.json")
def get_manifest():
    return JSONResponse(content=_read_manifest())


@app.post("/upload/frame", status_code=201)
async def upload_frame(file: Annotated[UploadFile, File()]):
    raw = await file.read(MAX_FRAME_BYTES + 1)
    if len(raw) > MAX_FRAME_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 1 MB)")
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


@app.post("/upload/song", status_code=201)
async def upload_song(file: Annotated[UploadFile, File()]):
    raw = await file.read(MAX_SONG_BYTES + 1)
    if len(raw) > MAX_SONG_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 64 KB)")
    try:
        text = raw.decode("utf-8")
        notes = convert_sheet(text)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    with _manifest_lock:
        manifest = _read_manifest()
        idx = len(manifest["songs"])
        name = f"song_{idx}"
        (SONGS_DIR / f"{name}.json").write_text(json.dumps(notes, indent=2), encoding="utf-8")
        manifest["songs"].append(f"{name}.json")
        manifest["updated_at"] = _utc_now()
        _write_manifest_atomic(manifest)

    return {"name": name}


@app.get("/frames/{name}.bin")
def get_frame_bin(name: Annotated[str, FPath(pattern=r"^frame_\d+$")]):
    path = FRAMES_DIR / f"{name}.bin"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Frame '{name}' not found")
    data = path.read_bytes()
    etag = f'"{hashlib.md5(data, usedforsecurity=False).hexdigest()}"'
    return Response(content=data, media_type="application/octet-stream", headers={"ETag": etag})


@app.get("/songs/{name}.json")
def get_song_json(name: Annotated[str, FPath(pattern=r"^song_\d+$")]):
    path = SONGS_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Song '{name}' not found")
    data = path.read_bytes()
    etag = f'"{hashlib.md5(data, usedforsecurity=False).hexdigest()}"'
    return Response(content=data, media_type="application/json", headers={"ETag": etag})


def _delete_frame(name: str) -> None:
    """Remove frame files and reorder remaining slots. Must be called inside _manifest_lock."""
    manifest = _read_manifest()
    if f"{name}.bin" not in manifest["frames"]:
        raise FileNotFoundError(name)

    idx = int(name.split("_")[1])
    total = len(manifest["frames"])

    (FRAMES_DIR / f"{name}.bin").unlink(missing_ok=True)
    (FRAMES_DIR / f"{name}.png").unlink(missing_ok=True)

    # Build the full rename plan before executing any rename so that a
    # partial failure mid-loop can be rolled back without leaving the
    # filesystem inconsistent with the manifest.
    plan = [
        (FRAMES_DIR / f"frame_{i}.bin", FRAMES_DIR / f"frame_{i - 1}.bin")
        for i in range(idx + 1, total)
    ] + [
        (FRAMES_DIR / f"frame_{i}.png", FRAMES_DIR / f"frame_{i - 1}.png")
        for i in range(idx + 1, total)
    ]

    completed: list[tuple[Path, Path]] = []
    try:
        for src, dst in plan:
            src.rename(dst)
            completed.append((dst, src))
    except OSError:
        for dst, src in reversed(completed):
            try:
                dst.rename(src)
            except OSError:
                pass
        raise

    manifest["frames"] = [f"frame_{i}.bin" for i in range(total - 1)]
    manifest["updated_at"] = _utc_now()
    _write_manifest_atomic(manifest)


def _delete_song(name: str) -> None:
    """Remove song file and reorder remaining slots. Must be called inside _manifest_lock."""
    manifest = _read_manifest()
    if f"{name}.json" not in manifest["songs"]:
        raise FileNotFoundError(name)

    idx = int(name.split("_")[1])
    total = len(manifest["songs"])

    (SONGS_DIR / f"{name}.json").unlink(missing_ok=True)

    # Build the full rename plan before executing any rename so that a
    # partial failure mid-loop can be rolled back without leaving the
    # filesystem inconsistent with the manifest.
    plan = [
        (SONGS_DIR / f"song_{i}.json", SONGS_DIR / f"song_{i - 1}.json")
        for i in range(idx + 1, total)
    ]

    completed: list[tuple[Path, Path]] = []
    try:
        for src, dst in plan:
            src.rename(dst)
            completed.append((dst, src))
    except OSError:
        for dst, src in reversed(completed):
            try:
                dst.rename(src)
            except OSError:
                pass
        raise

    manifest["songs"] = [f"song_{i}.json" for i in range(total - 1)]
    manifest["updated_at"] = _utc_now()
    _write_manifest_atomic(manifest)


@app.delete("/frames/{name}", status_code=204)
def delete_frame(name: Annotated[str, FPath(pattern=r"^frame_\d+$")]):
    with _manifest_lock:
        try:
            _delete_frame(name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Frame '{name}' not found")


@app.delete("/songs/{name}", status_code=204)
def delete_song(name: Annotated[str, FPath(pattern=r"^song_\d+$")]):
    with _manifest_lock:
        try:
            _delete_song(name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Song '{name}' not found")
