---
phase: 02-fastapi-server
plan: "02"
subsystem: api
tags: [fastapi, etag, md5, delete, reorder, path-traversal, integration-tests, pytest]

# Dependency graph
requires:
  - phase: 02-fastapi-server
    plan: "01"
    provides: "server/main.py with app, FRAMES_DIR, SONGS_DIR, MANIFEST_PATH, _manifest_lock, _write_manifest_atomic, _read_manifest, _utc_now, upload endpoints"
provides:
  - "GET /frames/{name}.bin — raw RGB565 binary with quoted MD5 ETag (API-02 + API-08)"
  - "GET /songs/{name}.json — melody JSON with quoted MD5 ETag (API-03 + API-08)"
  - "DELETE /frames/{name} — removes .bin + .png, ascending reorder, bumps updated_at (API-06)"
  - "DELETE /songs/{name} — removes .json, ascending reorder, bumps updated_at (API-07)"
  - "_delete_frame() / _delete_song() helpers (must be called inside _manifest_lock)"
  - "FPath(pattern=) on all four new endpoints as path-traversal defense"
  - "Full integration test suite: 9 test classes, 24 tests, all passing (tests/test_api.py)"
affects: [03-web-ui, 04-docker]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Quoted MD5 ETag: etag = f'\"{ hashlib.md5(data).hexdigest() }\"' per RFC 7232"
    - "Response(content=bytes, media_type=..., headers={'ETag': etag}) for binary and JSON serves"
    - "Ascending reorder-on-delete: range(idx+1, total) rename i->i-1 avoids clobber"
    - "Manifest list rebuilt from range(total-1) after delete — no string replacement"
    - "FPath(pattern=r'^frame_\\d+$') / '^song_\\d+$' as sole path-traversal defense"
    - "client fixture: monkeypatch.setattr on 4 Path constants + with TestClient(app) as c: yield c"

key-files:
  created:
    - tests/test_api.py
  modified:
    - server/main.py

key-decisions:
  - "ETag uses quoted MD5 of file content — RFC 7232 requires surrounding double quotes; ESP32 If-None-Match depends on this"
  - "Ascending rename loop (range(idx+1, total)) prevents source clobber; descending would overwrite i-1 before reading i"
  - "Manifest list rebuilt from scratch after delete — prevents state drift between disk and manifest"
  - "All four new endpoints carry FPath(pattern=) — this is the server's only path-traversal defense"
  - "client fixture uses lifespan-based manifest init (with TestClient(app) as c:) not manual _write_manifest_atomic"

# Metrics
duration: 20min
completed: 2026-06-14
---

# Phase 02 Plan 02: Serve + Delete Endpoints with ETag Summary

**GET/DELETE endpoints for frames and songs with quoted MD5 ETags, ascending reorder-on-delete keeping slots contiguous, and 9-class 24-test integration suite — all 47 tests (Phase 1 + Phase 2) passing**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-06-14T08:38:00Z
- **Completed:** 2026-06-14T08:58:00Z
- **Tasks:** 2
- **Files modified:** 2 (server/main.py extended, tests/test_api.py rewritten)

## Accomplishments

- Extended `server/main.py` with 4 endpoints and 2 helpers:
  - `GET /frames/{name}.bin` — 200 + raw binary + quoted MD5 ETag; 404 on missing
  - `GET /songs/{name}.json` — 200 + JSON + quoted MD5 ETag; 404 on missing
  - `_delete_frame(name)` — ascending reorder of .bin + .png, manifest rebuild, updated_at bump
  - `_delete_song(name)` — same pattern for .json files
  - `DELETE /frames/{name}` — 204 / 404; delegates to `_delete_frame` inside `_manifest_lock`
  - `DELETE /songs/{name}` — 204 / 404; delegates to `_delete_song` inside `_manifest_lock`
- Rewrote `tests/test_api.py` with 9 test classes covering all API requirements:
  - TestGetManifest (API-01), TestGetFrameBin (API-02), TestGetSongJson (API-03)
  - TestUploadFrame (API-04), TestUploadSong (API-05)
  - TestDeleteFrame (API-06), TestDeleteSong (API-07), TestETag (API-08)
  - TestPathTraversal (security)
- All 47 tests pass: 23 Phase 1 + 24 new API integration tests

## Task Commits

1. **Task 1: Serve endpoints + delete endpoints** — `2feea16` (feat)
2. **Task 2: Full integration test suite** — `cbc6041` (feat)

## Files Created/Modified

- `server/main.py` — Added `get_frame_bin`, `get_song_json`, `_delete_frame`, `_delete_song`, `delete_frame`, `delete_song` (78 lines added)
- `tests/test_api.py` — Replaced Wave 1 partial suite with full 9-class 24-test suite; `client` fixture uses lifespan context manager + 4 monkeypatches; reuses `solid_128x160_png` and `happy_birthday_text` from `conftest.py`

## Decisions Made

- RFC 7232 requires ETag value to be a quoted string (`"<hash>"`), not a bare hash. The surrounding double quotes are written as `f'"{hashlib.md5(data).hexdigest()}"'`. ESP32 `If-None-Match` comparison depends on this quoting.
- Ascending rename order (`range(idx+1, total)`) is mandatory — descending would overwrite `frame_{i-1}` before reading `frame_{i}`, corrupting data.
- Manifest `frames` / `songs` lists are rebuilt from `[f"frame_{i}.bin" for i in range(total-1)]` after every delete — string-replacement patching can leave state drift between disk and manifest.
- The `client` fixture uses `with TestClient(main_module.app) as c: yield c` to trigger lifespan startup, which writes the empty manifest. No manual `_write_manifest_atomic` call in the fixture.

## Deviations from Plan

None — plan executed exactly as written.

Both tasks followed TDD ordering: Task 1 implemented the endpoints (GREEN state), Task 2 wrote the tests (all passing). Because the plan specifies both tasks as `tdd="true"` but Task 1 is the implementation and Task 2 is the test suite, strict RED/GREEN sequencing is not applicable across tasks — Task 2 tests were written against the already-implemented endpoints from Task 1 and passed immediately. This matches the pattern established in Plan 02-01 (see 02-01-SUMMARY.md).

## Threat Surface Scan

All threat mitigations from the plan's `<threat_model>` are implemented:

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-02-05 path traversal | `FPath(pattern=r"^frame_\d+$")` / `"^song_\d+$"` on all 4 endpoints | Satisfied — grep confirms 4 occurrences |
| T-02-06 ETag content hash | MD5 of file content (cache fingerprint, not security hash) | Satisfied |
| T-02-07 reorder clobber | Ascending `range(idx+1, total)` rename | Satisfied — grep confirms 2 occurrences |
| T-02-08 manifest drift | Lists rebuilt from slot count, not patched | Satisfied |

No new threat surface introduced beyond what is documented in the plan's `<threat_model>`.

## Known Stubs

None — all endpoints are fully wired and return real file content.

## Self-Check: PASSED

- server/main.py: exists, contains get_frame_bin, get_song_json, _delete_frame, _delete_song, delete_frame, delete_song
- tests/test_api.py: exists, 9 test classes, 24 tests all passing
- Commit 2feea16: verified in git log
- Commit cbc6041: verified in git log
- `pytest tests/ -q`: 47 passed

---
*Phase: 02-fastapi-server*
*Completed: 2026-06-14*
