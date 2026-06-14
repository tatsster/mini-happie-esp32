---
phase: 02-fastapi-server
verified: 2026-06-14T12:00:00Z
status: passed
score: 13/13
overrides_applied: 0
---

# Phase 2: FastAPI Server Verification Report

**Phase Goal:** Implement all REST API endpoints with file storage and manifest management using FastAPI.
**Verified:** 2026-06-14T12:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

All truths sourced from 02-01-PLAN.md `must_haves.truths` (Plans 01 and 02) and ROADMAP.md success criteria.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Server creates data/frames/ and data/songs/ on startup and an empty manifest if none exists | VERIFIED | `lifespan()` at lines 46-51 of main.py calls `mkdir(parents=True, exist_ok=True)` on FRAMES_DIR and SONGS_DIR; calls `_write_manifest_atomic(EMPTY_MANIFEST)` if `not MANIFEST_PATH.exists()` |
| 2 | GET /manifest.json returns JSON with frames, songs, and updated_at fields | VERIFIED | `get_manifest()` at line 57-60 reads MANIFEST_PATH and returns `JSONResponse(content=data)`; test `test_get_manifest_empty` asserts all three keys; 24 tests pass |
| 3 | POST /upload/frame converts a PNG and stores both a 40960-byte .bin and the original .png | VERIFIED | Lines 63-81 of main.py: calls `convert_png(raw)` → writes `.bin` and `.png` to FRAMES_DIR; `test_upload_frame_stores_files` asserts `st_size==40960` and `.png` exists |
| 4 | POST /upload/song converts a text sheet and stores a .json melody array | VERIFIED | Lines 84-102: calls `convert_sheet(text)` → writes `.json` via `json.dumps`; `test_upload_song` passes |
| 5 | Every upload appends the new slot name to the manifest and bumps updated_at | VERIFIED | Both upload handlers: `manifest[...].append(...)` then `manifest["updated_at"] = _utc_now()` then `_write_manifest_atomic(manifest)` under lock; `test_upload_frame_updates_manifest` and `test_upload_song` verify this |
| 6 | Manifest writes are atomic (temp file + os.replace) and serialized by a lock | VERIFIED | `_write_manifest_atomic` at lines 25-33: `tempfile.mkstemp` + `os.replace`; grep confirms `os.replace` present (1 occurrence) and `os.rename` absent (0 occurrences); `_manifest_lock` acquired in 4 locations (lines 71, 93, 167, 176) |
| 7 | GET /frames/{name}.bin returns the raw RGB565 binary with a quoted MD5 ETag header | VERIFIED | Lines 105-112: `etag = f'"{hashlib.md5(data).hexdigest()}"'`; `test_etag_header_present` asserts `startswith('"')` and `endswith('"')` |
| 8 | GET /songs/{name}.json returns the melody JSON with a quoted MD5 ETag header | VERIFIED | Lines 115-122: identical quoted-MD5 pattern; `test_etag_song` asserts quoting |
| 9 | The same file content always produces the same ETag across repeated requests | VERIFIED | `test_etag_stable` GETs frame_0.bin twice and asserts `etag1 == etag2`; MD5 of content is deterministic |
| 10 | DELETE /frames/{name} removes the .bin and .png, reorders remaining slots to fill the gap, and bumps updated_at | VERIFIED | `_delete_frame` at lines 125-143: unlinks `.bin` + `.png` with `missing_ok=True`; ascending `range(idx+1, total)` renames; rebuilds `manifest["frames"]` from scratch; bumps `_utc_now()`; `test_delete_frame_reorders_slots` asserts `manifest["frames"] == ["frame_0.bin","frame_1.bin"]` after deleting frame_1 from 3-frame set |
| 11 | DELETE /songs/{name} removes the .json, reorders remaining slots, and bumps updated_at | VERIFIED | `_delete_song` at lines 146-162: same ascending reorder pattern; `test_delete_song` passes |
| 12 | Path parameters not matching ^frame_\d+$ / ^song_\d+$ are rejected with 422 (path traversal defense) | VERIFIED | `FPath(pattern=r"^frame_\d+$")` on 2 endpoints; `FPath(pattern=r"^song_\d+$")` on 2 endpoints (4 total, confirmed by grep); `test_path_traversal_rejected` asserts 422 for `frame_x.bin`; `test_delete_path_traversal_rejected` and `test_song_path_traversal_rejected` also pass |
| 13 | tests/test_api.py covers all eight API requirements plus path-traversal rejection and passes | VERIFIED | 9 test classes (TestGetManifest, TestGetFrameBin, TestGetSongJson, TestUploadFrame, TestUploadSong, TestDeleteFrame, TestDeleteSong, TestETag, TestPathTraversal); `pytest tests/test_api.py -q` — 24 passed; `pytest tests/ -q` — 47 passed |

**Score:** 13/13 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `server/main.py` | FastAPI app, manifest helpers, all 8 endpoints | VERIFIED | 180 lines; exports all required symbols confirmed via import check; no stubs, no placeholders |
| `server/requirements.txt` | fastapi, uvicorn, python-multipart, Pillow | VERIFIED | All 4 packages present: `Pillow>=10.0.0`, `fastapi>=0.115.0`, `uvicorn>=0.30.0`, `python-multipart>=0.0.9` |
| `tests/test_api.py` | Full integration test suite, min 80 lines, contains TestClient | VERIFIED | 279 lines; contains `TestClient`; 9 test classes; 24 tests; all passing |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `server/main.py` | `server.converters.convert_png` | import + call in upload_frame | VERIFIED | Line 14: `from server.converters import convert_png, convert_sheet`; line 67: `bin_bytes = convert_png(raw)` |
| `server/main.py` | `server.converters.convert_sheet` | import + call in upload_song | VERIFIED | Same import; line 89: `notes = convert_sheet(text)` |
| `POST /upload/frame` | `data/manifest.json` | `_write_manifest_atomic` under `_manifest_lock` | VERIFIED | Lines 71-79: `with _manifest_lock:` wraps entire read-modify-write; `_write_manifest_atomic(manifest)` called at line 79 |
| `GET /frames/{name}.bin` | ETag header | `hashlib.md5(data).hexdigest()` quoted per RFC 7232 | VERIFIED | Line 111: `etag = f'"{hashlib.md5(data).hexdigest()}"'` — surrounding double-quotes present |
| `DELETE /frames/{name}` | reorder rename loop | ascending `range(idx+1, total)` rename i -> i-1 | VERIFIED | Line 137: `for i in range(idx + 1, total):` — ascending order confirmed |
| `tests/test_api.py` | `server.main` | `monkeypatch.setattr` on module-level Path constants + TestClient | VERIFIED | 4 `monkeypatch.setattr` calls in `client` fixture (lines 25-28); `with TestClient(main_module.app) as c: yield c` at line 32 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `GET /manifest.json` | `data` | `MANIFEST_PATH.read_text()` | Yes — reads disk file written by upload handlers | FLOWING |
| `GET /frames/{name}.bin` | `data` | `path.read_bytes()` on FRAMES_DIR file | Yes — reads `.bin` written by `convert_png` at upload | FLOWING |
| `GET /songs/{name}.json` | `data` | `path.read_bytes()` on SONGS_DIR file | Yes — reads `.json` written by `convert_sheet` at upload | FLOWING |
| `POST /upload/frame` | `bin_bytes` | `convert_png(raw)` — real PNG→RGB565 conversion | Yes — Phase 1 converter called with upload bytes | FLOWING |
| `POST /upload/song` | `notes` | `convert_sheet(text)` — real sheet text parser | Yes — Phase 1 converter called with upload bytes | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All Phase 2 tests pass | `pytest tests/test_api.py -q` | 24 passed | PASS |
| Full suite (Phase 1 + Phase 2) passes | `pytest tests/ -q` | 47 passed | PASS |
| All required symbols exported from server.main | `python -c "import server.main; ..."` | ALL EXPORTS OK | PASS |
| `os.replace` used (not `os.rename`) | grep on main.py | 1 `os.replace`, 0 `os.rename` | PASS |
| `on_event` deprecated hook absent | grep on main.py | 0 occurrences | PASS |
| FPath path-traversal validators present | grep on main.py | 4 `FPath(pattern=` occurrences | PASS |
| Quoted MD5 ETag on both GET endpoints | grep on main.py | 2 `hashlib.md5` occurrences with surrounding `"` | PASS |

---

### Probe Execution

No `probe-*.sh` files declared or found for this phase.

---

### Requirements Coverage

All 8 API requirements assigned to Phase 2 are accounted for across the two plans.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| API-01 | 02-01-PLAN.md | GET /manifest.json returns frames, songs, updated_at | SATISFIED | `get_manifest()` endpoint; 2 tests in TestGetManifest |
| API-02 | 02-02-PLAN.md | GET /frames/{name}.bin returns raw RGB565 binary | SATISFIED | `get_frame_bin()` endpoint; TestGetFrameBin passes |
| API-03 | 02-02-PLAN.md | GET /songs/{name}.json returns melody JSON array | SATISFIED | `get_song_json()` endpoint; TestGetSongJson passes |
| API-04 | 02-01-PLAN.md | POST /upload/frame accepts PNG, converts, stores binary | SATISFIED | `upload_frame()` endpoint; TestUploadFrame — 4 tests pass |
| API-05 | 02-01-PLAN.md | POST /upload/song accepts sheet, converts, stores JSON | SATISFIED | `upload_song()` endpoint; TestUploadSong — 2 tests pass |
| API-06 | 02-02-PLAN.md | DELETE /frames/{name} removes binary, updates manifest | SATISFIED | `delete_frame()` + `_delete_frame()`; TestDeleteFrame — 3 tests pass |
| API-07 | 02-02-PLAN.md | DELETE /songs/{name} removes JSON, updates manifest | SATISFIED | `delete_song()` + `_delete_song()`; TestDeleteSong — 2 tests pass |
| API-08 | 02-02-PLAN.md | Binary responses include ETag header for ESP32 caching | SATISFIED | Quoted MD5 ETag on both GET endpoints; TestETag — 3 tests pass |

**No orphaned requirements:** REQUIREMENTS.md maps API-01 through API-08 to Phase 2 and all 8 are covered.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No `TBD`, `FIXME`, or `XXX` markers. No stub returns (`return null`, `return {}`, `return []`). No placeholder comments. No hardcoded empty props. `EMPTY_MANIFEST = {"frames": [], "songs": [], "updated_at": ""}` at line 21 is a legitimate initial-state constant (not a stub — it is only written to disk when the manifest does not exist, and is immediately overwritten by real data upon uploads).

---

### Human Verification Required

None. All truths are programmatically verifiable and the test suite confirms behavioral correctness.

---

### Gaps Summary

No gaps. All 13 must-have truths verified, all 3 required artifacts exist and are wired, all 8 API requirements satisfied, test suite passes 47/47. Phase goal achieved.

---

_Verified: 2026-06-14T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
