"""FastAPI application entry point.

Path constants (DATA_DIR, FRAMES_DIR, SONGS_DIR, MANIFEST_PATH) live here so
that ``monkeypatch.setattr(main_module, "<NAME>", ...)`` in the test suite
redirects all route handlers to the temporary directory.  Route modules import
these values lazily (inside function bodies) to resolve them at call time and
avoid a circular import.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from server.storage import EMPTY_MANIFEST, _write_manifest_atomic
from server.routes import frames, manifest, songs

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
FRAMES_DIR = DATA_DIR / "frames"
SONGS_DIR = DATA_DIR / "songs"
MANIFEST_PATH = DATA_DIR / "manifest.json"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    SONGS_DIR.mkdir(parents=True, exist_ok=True)
    if not MANIFEST_PATH.exists():
        _write_manifest_atomic(EMPTY_MANIFEST, MANIFEST_PATH)
    yield


app = FastAPI(lifespan=lifespan)  # noqa: F841 — ASGI entry point, referenced by uvicorn server.main:app

app.include_router(manifest.router)
app.include_router(frames.router)
app.include_router(songs.router)
