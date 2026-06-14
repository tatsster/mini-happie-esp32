"""Integration tests for the FastAPI server upload endpoints and manifest.

Tests cover:
- POST /upload/frame: valid PNG → 201 + .bin (40960 bytes) + .png stored + manifest updated
- POST /upload/frame: second upload creates frame_1 (sequential naming)
- POST /upload/frame: non-PNG bytes → 422
- GET /manifest.json: returns frames, songs, updated_at
- POST /upload/song: valid sheet → 201 + .json stored + manifest updated
- POST /upload/song: malformed/un-decodable bytes → 422
"""

import io
import json
import tempfile
from pathlib import Path

import pytest
from PIL import Image
from fastapi.testclient import TestClient

import server.main as main_module
from server.main import app


def _make_png(width: int = 128, height: int = 160, color: str = "white") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def tmp_data(tmp_path: Path, monkeypatch):
    """Redirect all server Path constants to a temp directory and initialize the manifest."""
    frames_dir = tmp_path / "frames"
    songs_dir = tmp_path / "songs"
    manifest_path = tmp_path / "manifest.json"

    frames_dir.mkdir()
    songs_dir.mkdir()

    monkeypatch.setattr(main_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main_module, "FRAMES_DIR", frames_dir)
    monkeypatch.setattr(main_module, "SONGS_DIR", songs_dir)
    monkeypatch.setattr(main_module, "MANIFEST_PATH", manifest_path)

    main_module._write_manifest_atomic(dict(main_module.EMPTY_MANIFEST))
    return tmp_path


@pytest.fixture()
def client(tmp_data):
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /manifest.json
# ---------------------------------------------------------------------------

class TestGetManifest:
    def test_returns_empty_manifest_on_fresh_data_dir(self, client):
        resp = client.get("/manifest.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["frames"] == []
        assert data["songs"] == []
        assert "updated_at" in data


# ---------------------------------------------------------------------------
# POST /upload/frame
# ---------------------------------------------------------------------------

class TestUploadFrame:
    def test_valid_png_returns_201_and_name(self, client):
        png = _make_png()
        resp = client.post("/upload/frame", files={"file": ("frame.png", png, "image/png")})
        assert resp.status_code == 201
        assert resp.json() == {"name": "frame_0"}

    def test_valid_png_writes_bin_of_40960_bytes(self, client, tmp_data):
        png = _make_png()
        client.post("/upload/frame", files={"file": ("frame.png", png, "image/png")})
        bin_path = tmp_data / "frames" / "frame_0.bin"
        assert bin_path.exists()
        assert bin_path.stat().st_size == 40960

    def test_valid_png_writes_original_png(self, client, tmp_data):
        png = _make_png()
        client.post("/upload/frame", files={"file": ("frame.png", png, "image/png")})
        png_path = tmp_data / "frames" / "frame_0.png"
        assert png_path.exists()
        assert png_path.read_bytes() == png

    def test_frame_name_appears_in_manifest(self, client):
        png = _make_png()
        client.post("/upload/frame", files={"file": ("frame.png", png, "image/png")})
        manifest = client.get("/manifest.json").json()
        assert "frame_0.bin" in manifest["frames"]
        assert manifest["updated_at"] != ""

    def test_second_upload_creates_frame_1(self, client):
        png = _make_png()
        client.post("/upload/frame", files={"file": ("f1.png", png, "image/png")})
        resp2 = client.post("/upload/frame", files={"file": ("f2.png", png, "image/png")})
        assert resp2.status_code == 201
        assert resp2.json() == {"name": "frame_1"}
        manifest = client.get("/manifest.json").json()
        assert "frame_0.bin" in manifest["frames"]
        assert "frame_1.bin" in manifest["frames"]

    def test_non_png_bytes_return_422(self, client):
        resp = client.post(
            "/upload/frame",
            files={"file": ("bad.png", b"this is not a png", "image/png")},
        )
        assert resp.status_code == 422

    def test_small_png_is_auto_resized_not_rejected(self, client):
        """convert_png auto-resizes any valid PNG (Phase 1 D-01) — no 422 for wrong dimensions."""
        small_png = _make_png(32, 32)
        resp = client.post("/upload/frame", files={"file": ("small.png", small_png, "image/png")})
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# POST /upload/song
# ---------------------------------------------------------------------------

class TestUploadSong:
    VALID_SHEET = b"C4 q\nD4 q\nE4 q\n"

    def test_valid_sheet_returns_201_and_name(self, client):
        resp = client.post("/upload/song", files={"file": ("song.txt", self.VALID_SHEET, "text/plain")})
        assert resp.status_code == 201
        assert resp.json() == {"name": "song_0"}

    def test_valid_sheet_writes_json_file(self, client, tmp_data):
        client.post("/upload/song", files={"file": ("song.txt", self.VALID_SHEET, "text/plain")})
        json_path = tmp_data / "songs" / "song_0.json"
        assert json_path.exists()
        notes = json.loads(json_path.read_text())
        assert isinstance(notes, list)
        assert all("freq" in n and "ms" in n for n in notes)

    def test_song_name_appears_in_manifest(self, client):
        client.post("/upload/song", files={"file": ("song.txt", self.VALID_SHEET, "text/plain")})
        manifest = client.get("/manifest.json").json()
        assert "song_0.json" in manifest["songs"]
        assert manifest["updated_at"] != ""

    def test_malformed_sheet_returns_422(self, client):
        bad = b"not a valid note line at all $$$"
        resp = client.post("/upload/song", files={"file": ("bad.txt", bad, "text/plain")})
        assert resp.status_code == 422

    def test_invalid_utf8_bytes_return_422(self, client):
        invalid_utf8 = b"\xff\xfe not utf8"
        resp = client.post("/upload/song", files={"file": ("bad.txt", invalid_utf8, "text/plain")})
        assert resp.status_code == 422

    def test_second_upload_creates_song_1(self, client):
        client.post("/upload/song", files={"file": ("s1.txt", self.VALID_SHEET, "text/plain")})
        resp2 = client.post("/upload/song", files={"file": ("s2.txt", self.VALID_SHEET, "text/plain")})
        assert resp2.status_code == 201
        assert resp2.json() == {"name": "song_1"}


# ---------------------------------------------------------------------------
# Manifest lock coverage (grep-based check is in plan; pytest-level smoke)
# ---------------------------------------------------------------------------

class TestManifestLockCoverage:
    def test_both_upload_handlers_use_manifest_lock(self):
        """Verify the lock is referenced at least twice (once per upload handler)."""
        import server.main
        import inspect
        source = inspect.getsource(server.main)
        assert source.count("_manifest_lock") >= 2, (
            "Expected _manifest_lock to appear at least twice in server/main.py"
        )
