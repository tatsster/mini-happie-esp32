"""Full HTTP integration test suite for the Phase 2 FastAPI server.

Covers all eight API requirements (API-01..API-08) plus path-traversal rejection.
Each test class maps to one API requirement or security concern.
"""

import io
import json

import pytest
from PIL import Image
from fastapi.testclient import TestClient

import server.main as main_module


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Redirect all server Path constants to a temp dir; lifespan writes empty manifest."""
    monkeypatch.setattr(main_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main_module, "FRAMES_DIR", tmp_path / "frames")
    monkeypatch.setattr(main_module, "SONGS_DIR", tmp_path / "songs")
    monkeypatch.setattr(main_module, "MANIFEST_PATH", tmp_path / "manifest.json")
    (tmp_path / "frames").mkdir()
    (tmp_path / "songs").mkdir()

    with TestClient(main_module.app) as c:
        yield c


def _make_png(width: int = 128, height: int = 160, color: str = "white") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


_VALID_SHEET = b"C4 q\nD4 q\nE4 q\n"


def _upload_frame(client, png_bytes: bytes = None):
    if png_bytes is None:
        png_bytes = _make_png()
    return client.post(
        "/upload/frame",
        files={"file": ("frame.png", png_bytes, "image/png")},
    )


def _upload_song(client, sheet_bytes: bytes = None):
    if sheet_bytes is None:
        sheet_bytes = _VALID_SHEET
    return client.post(
        "/upload/song",
        files={"file": ("song.txt", sheet_bytes, "text/plain")},
    )


# ---------------------------------------------------------------------------
# API-01: GET /manifest.json
# ---------------------------------------------------------------------------


class TestGetManifest:
    def test_get_manifest_empty(self, client):
        resp = client.get("/manifest.json")
        assert resp.status_code == 200
        body = resp.json()
        assert "frames" in body
        assert "songs" in body
        assert "updated_at" in body
        assert body["frames"] == []
        assert body["songs"] == []

    def test_manifest_after_upload(self, client, solid_128x160_png):
        _upload_frame(client, solid_128x160_png)
        _upload_song(client)
        body = client.get("/manifest.json").json()
        assert "frame_0.bin" in body["frames"]
        assert "song_0.json" in body["songs"]


# ---------------------------------------------------------------------------
# API-02: GET /frames/{name}.bin
# ---------------------------------------------------------------------------


class TestGetFrameBin:
    def test_get_frame_bin(self, client, solid_128x160_png):
        _upload_frame(client, solid_128x160_png)
        resp = client.get("/frames/frame_0.bin")
        assert resp.status_code == 200
        assert len(resp.content) == 40960  # 128 * 160 * 2 bytes (RGB565)

    def test_get_frame_bin_not_found(self, client):
        resp = client.get("/frames/frame_99.bin")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API-03: GET /songs/{name}.json
# ---------------------------------------------------------------------------


class TestGetSongJson:
    def test_get_song_json(self, client, happy_birthday_text):
        client.post(
            "/upload/song",
            files={"file": ("song.txt", happy_birthday_text.encode(), "text/plain")},
        )
        resp = client.get("/songs/song_0.json")
        assert resp.status_code == 200
        notes = resp.json()
        assert isinstance(notes, list)
        assert all("freq" in n and "ms" in n for n in notes)

    def test_get_song_json_not_found(self, client):
        resp = client.get("/songs/song_99.json")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API-04: POST /upload/frame
# ---------------------------------------------------------------------------


class TestUploadFrame:
    def test_upload_frame_stores_files(self, client, solid_128x160_png, tmp_path):
        _upload_frame(client, solid_128x160_png)
        bin_path = tmp_path / "frames" / "frame_0.bin"
        png_path = tmp_path / "frames" / "frame_0.png"
        assert bin_path.exists()
        assert bin_path.stat().st_size == 40960
        assert png_path.exists()

    def test_upload_frame_updates_manifest(self, client, solid_128x160_png):
        resp = _upload_frame(client, solid_128x160_png)
        assert resp.status_code == 201
        manifest = client.get("/manifest.json").json()
        assert "frame_0.bin" in manifest["frames"]
        assert manifest["updated_at"] != ""

    def test_upload_frame_invalid_png(self, client):
        resp = client.post(
            "/upload/frame",
            files={"file": ("bad.png", b"not a png", "image/png")},
        )
        assert resp.status_code == 422

    def test_upload_frame_sequential_naming(self, client, solid_128x160_png):
        _upload_frame(client, solid_128x160_png)
        resp = _upload_frame(client, solid_128x160_png)
        assert resp.status_code == 201
        assert resp.json() == {"name": "frame_1"}


# ---------------------------------------------------------------------------
# API-05: POST /upload/song
# ---------------------------------------------------------------------------


class TestUploadSong:
    def test_upload_song(self, client):
        resp = _upload_song(client)
        assert resp.status_code == 201
        manifest = client.get("/manifest.json").json()
        assert "song_0.json" in manifest["songs"]

    def test_upload_song_invalid_sheet(self, client):
        resp = _upload_song(client, b"not a valid note line at all $$$")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# API-06: DELETE /frames/{name}
# ---------------------------------------------------------------------------


class TestDeleteFrame:
    def test_delete_frame(self, client, solid_128x160_png, tmp_path):
        _upload_frame(client, solid_128x160_png)
        resp = client.delete("/frames/frame_0")
        assert resp.status_code == 204
        assert not (tmp_path / "frames" / "frame_0.bin").exists()
        manifest = client.get("/manifest.json").json()
        assert "frame_0.bin" not in manifest["frames"]

    def test_delete_frame_reorders_slots(self, client, solid_128x160_png):
        for _ in range(3):
            _upload_frame(client, solid_128x160_png)
        before_updated_at = client.get("/manifest.json").json()["updated_at"]

        resp = client.delete("/frames/frame_1")
        assert resp.status_code == 204

        manifest = client.get("/manifest.json").json()
        assert manifest["frames"] == ["frame_0.bin", "frame_1.bin"]
        assert manifest["updated_at"] != before_updated_at

    def test_delete_frame_not_found(self, client):
        resp = client.delete("/frames/frame_9")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API-07: DELETE /songs/{name}
# ---------------------------------------------------------------------------


class TestDeleteSong:
    def test_delete_song(self, client, tmp_path):
        _upload_song(client)
        resp = client.delete("/songs/song_0")
        assert resp.status_code == 204
        assert not (tmp_path / "songs" / "song_0.json").exists()
        manifest = client.get("/manifest.json").json()
        assert "song_0.json" not in manifest["songs"]

    def test_delete_song_not_found(self, client):
        resp = client.delete("/songs/song_9")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API-08: ETag header
# ---------------------------------------------------------------------------


class TestETag:
    def test_etag_header_present(self, client, solid_128x160_png):
        _upload_frame(client, solid_128x160_png)
        resp = client.get("/frames/frame_0.bin")
        assert resp.status_code == 200
        etag = resp.headers.get("etag", "")
        assert etag.startswith('"'), f"ETag must start with double-quote, got: {etag!r}"
        assert etag.endswith('"'), f"ETag must end with double-quote, got: {etag!r}"

    def test_etag_stable(self, client, solid_128x160_png):
        _upload_frame(client, solid_128x160_png)
        etag1 = client.get("/frames/frame_0.bin").headers["etag"]
        etag2 = client.get("/frames/frame_0.bin").headers["etag"]
        assert etag1 == etag2

    def test_etag_song(self, client):
        _upload_song(client)
        resp = client.get("/songs/song_0.json")
        assert resp.status_code == 200
        etag = resp.headers.get("etag", "")
        assert etag.startswith('"')
        assert etag.endswith('"')


# ---------------------------------------------------------------------------
# Security: path traversal rejection
# ---------------------------------------------------------------------------


class TestPathTraversal:
    def test_path_traversal_rejected(self, client):
        # frame_x violates ^frame_\d+$ -- must be 422
        resp = client.get("/frames/frame_x.bin")
        assert resp.status_code == 422

    def test_path_traversal_dotdot_rejected(self, client):
        # URL-encoded ../ in path should be rejected with 404 or 422
        resp = client.get("/frames/..%2Fetc%2Fpasswd.bin")
        assert resp.status_code in (404, 422)

    def test_delete_path_traversal_rejected(self, client):
        resp = client.delete("/frames/frame_x")
        assert resp.status_code == 422

    def test_song_path_traversal_rejected(self, client):
        resp = client.get("/songs/song_x.json")
        assert resp.status_code == 422
