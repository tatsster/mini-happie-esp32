"""Routes: GET /frames/{name}.bin, POST /upload/frame, DELETE /frames/{name}"""

import hashlib
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, HTTPException, Path as FPath, UploadFile
from fastapi.responses import Response

from server import storage
from server.converters import convert_png

router = APIRouter()


def _delete_frame(name: str, frames_dir: Path, manifest_path: Path) -> None:
    """Remove frame files and reorder remaining slots.

    Must be called inside ``storage._manifest_lock``.
    """
    manifest: dict[str, Any] = storage._read_manifest(manifest_path)
    if f"{name}.bin" not in manifest["frames"]:
        raise FileNotFoundError(name)

    idx = int(name.split("_")[1])
    total = len(manifest["frames"])

    (frames_dir / f"{name}.bin").unlink(missing_ok=True)
    (frames_dir / f"{name}.png").unlink(missing_ok=True)

    # Build the full rename plan before executing any rename so that a
    # partial failure mid-loop can be rolled back without leaving the
    # filesystem inconsistent with the manifest.
    plan = [
        (frames_dir / f"frame_{i}.bin", frames_dir / f"frame_{i - 1}.bin")
        for i in range(idx + 1, total)
    ] + [
        (frames_dir / f"frame_{i}.png", frames_dir / f"frame_{i - 1}.png")
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
    manifest["updated_at"] = storage._utc_now()
    storage._write_manifest_atomic(manifest, manifest_path)


@router.get("/frames/{name}.bin")
def get_frame_bin(name: Annotated[str, FPath(pattern=r"^frame_\d+$")]) -> Response:
    import server.main as _main

    path = _main.FRAMES_DIR / f"{name}.bin"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Frame '{name}' not found")
    data = path.read_bytes()
    etag = f'"{hashlib.md5(data, usedforsecurity=False).hexdigest()}"'
    return Response(content=data, media_type="application/octet-stream", headers={"ETag": etag})


@router.get("/frames/{name}.png")
def get_frame_png(name: Annotated[str, FPath(pattern=r"^frame_\d+$")]) -> Response:
    import server.main as _main

    path = _main.FRAMES_DIR / f"{name}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Frame '{name}' not found")
    data = path.read_bytes()
    return Response(content=data, media_type="image/png")


@router.post("/upload/frame", status_code=201)
async def upload_frame(file: Annotated[UploadFile, File()]) -> dict[str, str]:
    import server.main as _main

    raw = await file.read(storage.MAX_FRAME_BYTES + 1)
    if len(raw) > storage.MAX_FRAME_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 1 MB)")
    try:
        bin_bytes = convert_png(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    with storage._manifest_lock:
        manifest = storage._read_manifest(_main.MANIFEST_PATH)
        idx = len(manifest["frames"])
        name = f"frame_{idx}"
        (_main.FRAMES_DIR / f"{name}.bin").write_bytes(bin_bytes)
        (_main.FRAMES_DIR / f"{name}.png").write_bytes(raw)
        manifest["frames"].append(f"{name}.bin")
        manifest["updated_at"] = storage._utc_now()
        storage._write_manifest_atomic(manifest, _main.MANIFEST_PATH)

    return {"name": name}


@router.delete("/frames/{name}", status_code=204)
def delete_frame(name: Annotated[str, FPath(pattern=r"^frame_\d+$")]) -> None:
    import server.main as _main

    with storage._manifest_lock:
        try:
            _delete_frame(name, _main.FRAMES_DIR, _main.MANIFEST_PATH)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Frame '{name}' not found")
