"""Shared storage primitives for the birthday-device server.

Path constants (FRAMES_DIR, SONGS_DIR, MANIFEST_PATH) intentionally live in
server.main so that monkeypatching ``main_module.<NAME>`` in the test suite
affects all call sites.  Route handlers import those values lazily (inside
function bodies) to avoid circular imports and to pick up any patched values.

This module owns everything else: the manifest lock, size limits, and the
atomic read/write helpers that every route uses.
"""

import datetime
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

EMPTY_MANIFEST: dict[str, Any] = {"frames": [], "songs": [], "updated_at": ""}
_manifest_lock = threading.Lock()

MAX_FRAME_BYTES = 1 * 1024 * 1024  # 1 MB — generous for a 128×160 PNG
MAX_SONG_BYTES = 64 * 1024  # 64 KB — ample for a text sheet
MAX_FRAMES = 6  # LittleFS practical limit for the ESP32 device


def _write_manifest_atomic(manifest: dict[str, Any], manifest_path: Path) -> None:
    """Write *manifest* to *manifest_path* via a temp-file rename (atomic on POSIX)."""
    tmp_fd, tmp_path = tempfile.mkstemp(dir=manifest_path.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(manifest, f, indent=2)
        os.replace(tmp_path, manifest_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_manifest(manifest_path: Path) -> dict[str, Any]:
    """Return the parsed manifest from *manifest_path*."""
    with manifest_path.open() as f:
        return json.load(f)


def _utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
