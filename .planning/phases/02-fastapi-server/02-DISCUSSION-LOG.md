# Phase 2: FastAPI Server - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-14
**Phase:** 2-FastAPI Server
**Areas discussed:** Manifest management, File naming, Thumbnail endpoint, ETag

---

## Manifest management

| Option | Description | Selected |
|--------|-------------|----------|
| Dynamic from filesystem | Generate manifest on every GET request by scanning disk | |
| Persisted JSON file | Write data/manifest.json on every upload/delete, serve directly | ✓ |

**User's choice:** Persisted JSON file

| Option | Description | Selected |
|--------|-------------|----------|
| On startup if missing | Scan filesystem and rebuild if manifest.json doesn't exist | |
| Never auto-rebuild | Manifest starts empty; only updated via upload/delete | ✓ |

**User's choice:** Never auto-rebuild

| Option | Description | Selected |
|--------|-------------|----------|
| Update on every upload/delete | Set updated_at to current UTC ISO8601 on every write | ✓ |
| You decide | Claude picks standard approach | |

**User's choice:** Update updated_at on every upload/delete

---

## File naming

| Option | Description | Selected |
|--------|-------------|----------|
| Original filename (sanitized) | Slugify upload filename, 409 on collision | |
| Sequential slots | frame_0, frame_1, ... as in PLAN.md | |
| UUID | Guaranteed unique, opaque names | |
| Other (freeform) | Sequential slots but reorder (rename) remaining slots after delete | ✓ |

**User's choice:** Sequential slots (`frame_0`, `frame_1`, ...) with reorder-on-delete — when a slot is deleted, remaining slots are renamed to fill the gap.

**Notes:** Follow-up clarified that the reorder operation bumps `updated_at` so the ESP32 knows to re-sync affected frames.

---

## Thumbnail endpoint

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 2 — complete storage contract now | Add GET /frames/{name}.png alongside GET /frames/{name}.bin | |
| Phase 3 — add with web UI | Thumbnail endpoint deferred; PNG stored but not served in Phase 2 | ✓ |

**User's choice:** Deferred to Phase 3

---

## ETag implementation

| Option | Description | Selected |
|--------|-------------|----------|
| MD5 hash of file content | ETag = MD5(file bytes), stable across restarts | ✓ |
| File mtime-based | ETag = mtime_ns, resets on Docker volume copy | |
| You decide | Claude picks implementation detail | |

**User's choice:** MD5 hash of file content

---

## Claude's Discretion

- FastAPI app structure (single file vs. modules) — Claude decides
- HTTP error response format — FastAPI default `{"detail": "..."}` assumed
- File I/O error handling — standard Python exceptions → appropriate HTTP status codes
- Port configuration — 8080 default, env-var override (Docker phase handles containerization)

## Deferred Ideas

- `GET /frames/{name}.png` thumbnail endpoint — Phase 3
- Custom BPM per song upload — already deferred in Phase 1, still out of scope
- Manifest auto-rebuild on startup — decided against (keep it simple)
