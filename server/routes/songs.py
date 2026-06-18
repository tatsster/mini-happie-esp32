"""Routes: GET /songs/{name}.json, POST /upload/song, DELETE /songs/{name}"""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, HTTPException, Path as FPath, UploadFile
from fastapi.responses import Response

from server import storage
from server.converters import convert_audio

MAX_AUDIO_BYTES = 2 * 1024 * 1024  # 2 MB — ~46 s WAV / ~2 min MP3; leaves headroom for frames + firmware

router = APIRouter()


def _delete_song(name: str, songs_dir: Path, manifest_path: Path) -> None:
    """Remove song file and reorder remaining slots.

    Must be called inside ``storage._manifest_lock``.
    """
    manifest: dict[str, Any] = storage._read_manifest(manifest_path)
    if f"{name}.json" not in manifest["songs"]:
        raise FileNotFoundError(name)

    idx = int(name.split("_")[1])
    total = len(manifest["songs"])

    (songs_dir / f"{name}.json").unlink(missing_ok=True)

    # Build the full rename plan before executing any rename so that a
    # partial failure mid-loop can be rolled back without leaving the
    # filesystem inconsistent with the manifest.
    plan = [
        (songs_dir / f"song_{i}.json", songs_dir / f"song_{i - 1}.json")
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
    manifest["updated_at"] = storage._utc_now()
    storage._write_manifest_atomic(manifest, manifest_path)


@router.get("/songs/{name}.json")
def get_song_json(name: Annotated[str, FPath(pattern=r"^song_\d+$")]) -> Response:
    import server.main as _main

    path = _main.SONGS_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Song '{name}' not found")
    data = path.read_bytes()
    etag = f'"{hashlib.md5(data, usedforsecurity=False).hexdigest()}"'
    return Response(content=data, media_type="application/json", headers={"ETag": etag})


@router.post("/upload/song", status_code=201)
async def upload_song(file: Annotated[UploadFile, File()]) -> dict[str, Any]:
    import server.main as _main

    ct = file.content_type or ""
    extra: dict[str, Any] = {}

    if ct in ("audio/wav", "audio/x-wav", "audio/mpeg"):
        raw = await file.read(MAX_AUDIO_BYTES + 1)
        if len(raw) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="File too large (max 2 MB)")
        fmt = "mp3" if ct == "audio/mpeg" else "wav"
        try:
            notes, is_complex = convert_audio(raw, fmt=fmt)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        extra = {"notes": len(notes), "is_complex": is_complex}

    else:
        raise HTTPException(status_code=415, detail="Unsupported file type")

    # threading.Lock in an async handler blocks the event loop thread while waiting
    # for the lock.  Under concurrent load this would be a problem; for this
    # single-user homelab device the lock is almost never contested in practice.
    with storage._manifest_lock:
        manifest = storage._read_manifest(_main.MANIFEST_PATH)
        # Replace any existing song — only one song slot allowed at a time.
        for existing in manifest["songs"]:
            (_main.SONGS_DIR / existing).unlink(missing_ok=True)
        manifest["songs"] = []
        name = "song_0"
        (_main.SONGS_DIR / f"{name}.json").write_text(
            json.dumps(notes, indent=2), encoding="utf-8"
        )
        manifest["songs"].append(f"{name}.json")
        manifest["updated_at"] = storage._utc_now()
        storage._write_manifest_atomic(manifest, _main.MANIFEST_PATH)

    return {"name": name, **extra}


@router.delete("/songs/{name}", status_code=204)
def delete_song(name: Annotated[str, FPath(pattern=r"^song_\d+$")]) -> None:
    import server.main as _main

    with storage._manifest_lock:
        try:
            _delete_song(name, _main.SONGS_DIR, _main.MANIFEST_PATH)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Song '{name}' not found")
