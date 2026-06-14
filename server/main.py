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


def _write_manifest_atomic(manifest: dict) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(dir=MANIFEST_PATH.parent, suffix=".tmp")
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
    data = json.loads(MANIFEST_PATH.read_text())
    return JSONResponse(content=data)


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
        (SONGS_DIR / f"{name}.json").write_text(json.dumps(notes, indent=2), encoding="utf-8")
        manifest["songs"].append(f"{name}.json")
        manifest["updated_at"] = _utc_now()
        _write_manifest_atomic(manifest)

    return {"name": name}
