---
phase: 02-fastapi-server
reviewed: 2026-06-14T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - server/main.py
  - server/requirements.txt
  - tests/test_api.py
findings:
  critical: 1
  warning: 5
  info: 1
  total: 7
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-06-14
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Three files reviewed: the FastAPI server (`server/main.py`), its dependency manifest (`server/requirements.txt`), and the integration test suite (`tests/test_api.py`). The server converters module (`server/converters.py`) was read as supporting context because `main.py` imports from it directly.

The implementation is structurally sound: atomic manifest writes via `os.replace`, path-traversal rejection via regex-validated `FPath` parameters, a threading lock protecting all manifest mutations. The one **critical** finding is a data-integrity gap in the delete-and-reorder logic: a mid-loop rename failure leaves the filesystem in a state that is inconsistent with the manifest in a way that silently corrupts existing frame/song data. Five warnings cover exception-handling robustness, missing upload size caps, a FIPS-incompatible MD5 call, an incomplete `requirements.txt`, and a traceback-destroying re-raise pattern in the converter. One info item covers an enharmonic edge case in note parsing.

---

## Critical Issues

### CR-01: Delete-reorder rename loop leaves filesystem inconsistent on partial failure

**File:** `server/main.py:137-143` (frame); `server/main.py:157-162` (song)

**Issue:** `_delete_frame` deletes the target file with `unlink(missing_ok=True)`, then renames every subsequent slot one position lower in a plain loop. If any `rename` call in that loop raises (disk full, permission error, cross-device link), the function raises before reaching the manifest write at line 141. The manifest is therefore left showing the **original** slot names, but the filesystem already has some files renamed. On the next request the manifest references files that no longer exist at their listed paths and points to other files that now contain the wrong content.

Concrete example with three frames:
- `DELETE /frames/frame_0` — unlink succeeds; `frame_1 -> frame_0` rename succeeds; `frame_2 -> frame_1` rename **fails** (disk full).
- Manifest still reads `["frame_0.bin", "frame_1.bin", "frame_2.bin"]`.
- Filesystem now has `frame_0.bin` (content of old `frame_1`), `frame_2.bin` (original). `frame_1.bin` is gone.
- `GET /frames/frame_0.bin` returns silently wrong data; `GET /frames/frame_1.bin` returns 404 despite manifest claiming it exists.

`_delete_song` at lines 157-162 has the identical structure and the identical risk.

**Fix:** Build a complete rename plan first, then execute it inside a try/except that attempts a rollback. If rollback also fails, at minimum raise with a clear error so the caller gets a 500 rather than silent corruption. A simpler alternative that avoids the rename loop entirely is to stop reordering files on delete and instead store slot entries as a sparse list or use stable UUIDs as file names; the manifest can reflect gaps without any file renaming.

Minimal defensive wrapper:

```python
def _delete_frame(name: str) -> None:
    manifest = _read_manifest()
    if f"{name}.bin" not in manifest["frames"]:
        raise FileNotFoundError(name)

    idx = int(name.split("_")[1])
    total = len(manifest["frames"])

    (FRAMES_DIR / f"{name}.bin").unlink(missing_ok=True)
    (FRAMES_DIR / f"{name}.png").unlink(missing_ok=True)

    # Build the rename plan before executing any rename.
    plan = [
        (FRAMES_DIR / f"frame_{i}.bin", FRAMES_DIR / f"frame_{i - 1}.bin")
        for i in range(idx + 1, total)
    ] + [
        (FRAMES_DIR / f"frame_{i}.png", FRAMES_DIR / f"frame_{i - 1}.png")
        for i in range(idx + 1, total)
    ]

    completed = []
    try:
        for src, dst in plan:
            src.rename(dst)
            completed.append((dst, src))
    except OSError:
        # Attempt rollback of completed renames before re-raising.
        for dst, src in reversed(completed):
            try:
                dst.rename(src)
            except OSError:
                pass
        raise

    manifest["frames"] = [f"frame_{i}.bin" for i in range(total - 1)]
    manifest["updated_at"] = _utc_now()
    _write_manifest_atomic(manifest)
```

---

## Warnings

### WR-01: Exception cleanup in `_write_manifest_atomic` can swallow the original error

**File:** `server/main.py:31-33`

**Issue:** The `except` block calls `os.unlink(tmp_path)` before `raise`. If `os.unlink` itself raises (for example, because another process already removed the temp file, or a permissions error), that new exception propagates and the original exception — the one that triggered the cleanup — is silently lost. Callers see a misleading `OSError` from the unlink instead of the true failure.

```python
except Exception:
    os.unlink(tmp_path)   # if THIS raises, the original exception is gone
    raise
```

**Fix:** Wrap the cleanup in a nested `try/except` so the original exception always propagates:

```python
except Exception:
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
    raise
```

---

### WR-02: No upload body size limit — unbounded memory consumption

**File:** `server/main.py:65` (frame); `server/main.py:86` (song)

**Issue:** Both upload endpoints call `await file.read()` with no size cap. A request body of arbitrary size is read entirely into memory before processing begins. On a machine with limited RAM (e.g. a Raspberry Pi acting as the bridge server), a sufficiently large upload exhausts memory and crashes the process.

```python
raw = await file.read()   # no limit — full body in memory
```

**Fix:** Enforce a reasonable maximum. For frames the expected payload is a PNG that converts to 128×160 px; a 1 MB cap is generous. For songs a 64 KB cap is more than sufficient.

```python
MAX_FRAME_BYTES = 1 * 1024 * 1024   # 1 MB
raw = await file.read(MAX_FRAME_BYTES + 1)
if len(raw) > MAX_FRAME_BYTES:
    raise HTTPException(status_code=413, detail="File too large")
```

---

### WR-03: `hashlib.md5()` fails on FIPS-enabled systems

**File:** `server/main.py:111` and `server/main.py:121`

**Issue:** `hashlib.md5(data)` raises `ValueError: [digital envelope routines] unsupported` on systems with FIPS mode enabled (common in government/enterprise Linux deployments). Python 3.9 introduced `usedforsecurity=False` specifically to allow MD5 in non-security contexts such as ETags.

```python
etag = f'"{hashlib.md5(data).hexdigest()}"'  # crashes on FIPS hosts
```

**Fix:**

```python
etag = f'"{hashlib.md5(data, usedforsecurity=False).hexdigest()}"'
```

---

### WR-04: `requirements.txt` is incomplete — test dependencies not declared

**File:** `server/requirements.txt`

**Issue:** The test suite (`tests/test_api.py`) requires `pytest`, `httpx` (Starlette's `TestClient` backend since FastAPI 0.99+), and `Pillow` at test time. None of `pytest` or `httpx` appear in `requirements.txt`. Running `pip install -r server/requirements.txt && pytest` in a fresh environment will fail with `ModuleNotFoundError: No module named 'httpx'`.

**Fix:** Either add a separate `requirements-dev.txt` / `requirements-test.txt` at the repo root:

```
pytest>=8.0
httpx>=0.27
```

or add an `[project.optional-dependencies]` `test` group if the project adopts `pyproject.toml`. At minimum, document the missing dependencies in the README so the next developer can run the tests without guessing.

---

### WR-05: `raise exc` in `convert_png` discards the original traceback

**File:** `server/converters.py:43-44`

**Issue:** The `except (ValueError, TypeError) as exc: raise exc` pattern creates a new exception object at the point of `raise exc`, replacing the original traceback with a synthetic one that points at line 44 instead of the actual failure site inside `Image.open` or `img.convert`. This makes debugging significantly harder.

```python
except (ValueError, TypeError) as exc:
    raise exc   # traceback now starts here, hiding the real source
```

**Fix:** Use a bare `raise` to re-raise with the original traceback intact:

```python
except (ValueError, TypeError):
    raise
```

---

## Info

### IN-01: `B#` enharmonic mapped to same octave instead of octave + 1

**File:** `server/converters.py:13`

**Issue:** `SEMITONES["B#"] = 0` maps B-sharp to semitone 0 (C), which is correct in isolation, but the frequency formula `(octave + 1) * 12 + semitone` then computes B#4 as MIDI 60 (C4 = 261.6 Hz) rather than the musically correct MIDI 72 (C5 = 523.3 Hz). B#N is enharmonically equivalent to C(N+1), not CN. For a birthday-song tool the in-use sheet files likely never use B#, but any song that does will play the note an octave too low.

**Fix:** Add an octave correction for the B# case:

```python
midi_semitone = SEMITONES[note_name]
octave_offset = 1 if note_name == "B#" else 0
midi = (int(octave_str) + 1 + octave_offset) * 12 + midi_semitone
```

---

_Reviewed: 2026-06-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
