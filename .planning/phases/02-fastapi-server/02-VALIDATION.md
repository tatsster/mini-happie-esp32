---
phase: 2
slug: fastapi-server
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-14
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | none — Wave 0 installs if needed |
| **Quick run command** | `pytest tests/test_api.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_api.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| manifest-read | — | 1 | API-01 | — | N/A | integration | `pytest tests/test_api.py::test_get_manifest_empty -x` | ❌ W0 | ⬜ pending |
| manifest-after-upload | — | 2 | API-01 | — | N/A | integration | `pytest tests/test_api.py::test_manifest_after_upload -x` | ❌ W0 | ⬜ pending |
| frame-bin-read | — | 2 | API-02 | — | N/A | integration | `pytest tests/test_api.py::test_get_frame_bin -x` | ❌ W0 | ⬜ pending |
| frame-bin-404 | — | 2 | API-02 | — | 404 on missing | integration | `pytest tests/test_api.py::test_get_frame_bin_not_found -x` | ❌ W0 | ⬜ pending |
| song-json-read | — | 2 | API-03 | — | N/A | integration | `pytest tests/test_api.py::test_get_song_json -x` | ❌ W0 | ⬜ pending |
| upload-frame-files | — | 2 | API-04 | — | N/A | integration | `pytest tests/test_api.py::test_upload_frame_stores_files -x` | ❌ W0 | ⬜ pending |
| upload-frame-manifest | — | 2 | API-04 | — | N/A | integration | `pytest tests/test_api.py::test_upload_frame_updates_manifest -x` | ❌ W0 | ⬜ pending |
| upload-frame-invalid | — | 2 | API-04 | — | 422 on bad bytes | integration | `pytest tests/test_api.py::test_upload_frame_invalid_png -x` | ❌ W0 | ⬜ pending |
| upload-song | — | 2 | API-05 | — | N/A | integration | `pytest tests/test_api.py::test_upload_song -x` | ❌ W0 | ⬜ pending |
| upload-song-invalid | — | 2 | API-05 | — | 422 on bad sheet | integration | `pytest tests/test_api.py::test_upload_song_invalid_sheet -x` | ❌ W0 | ⬜ pending |
| delete-frame | — | 2 | API-06 | — | N/A | integration | `pytest tests/test_api.py::test_delete_frame -x` | ❌ W0 | ⬜ pending |
| delete-frame-reorder | — | 2 | API-06 | — | N/A | integration | `pytest tests/test_api.py::test_delete_frame_reorders_slots -x` | ❌ W0 | ⬜ pending |
| delete-song | — | 2 | API-07 | — | N/A | integration | `pytest tests/test_api.py::test_delete_song -x` | ❌ W0 | ⬜ pending |
| etag-present | — | 2 | API-08 | — | ETag quoted per RFC 7232 | integration | `pytest tests/test_api.py::test_etag_header_present -x` | ❌ W0 | ⬜ pending |
| etag-stable | — | 2 | API-08 | — | Same file → same ETag | integration | `pytest tests/test_api.py::test_etag_stable -x` | ❌ W0 | ⬜ pending |
| path-traversal | — | 2 | — | security | 422 on ../foo names | integration | `pytest tests/test_api.py::test_path_traversal_rejected -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_api.py` — all API integration tests (new file, all tests initially stub/fail)
- [ ] `server/main.py` — FastAPI app (new file)
- [ ] `server/requirements.txt` — add `fastapi>=0.115.0`, `uvicorn>=0.30.0`, `python-multipart>=0.0.9`
- [ ] Install packages: `pip install fastapi uvicorn python-multipart`
- [ ] `data/frames/` and `data/songs/` — created by server lifespan startup (not pre-created in repo)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Server starts with `uvicorn server.main:app --port 8080` | — | Process lifecycle | Run `uvicorn server.main:app --port 8080` and confirm startup message |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
