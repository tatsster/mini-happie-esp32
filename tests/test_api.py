"""Full HTTP integration test suite for the Phase 2 FastAPI server.

Covers all eight API requirements (API-01..API-08) plus path-traversal rejection.
Each test class maps to one API requirement or security concern.
"""

import io
import json
import shutil

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


def _upload_frame(client, png_bytes: bytes = None):
    if png_bytes is None:
        png_bytes = _make_png()
    return client.post(
        "/upload/frame",
        files={"file": ("frame.png", png_bytes, "image/png")},
    )


def _upload_wav(client, wav_bytes: bytes, filename: str = "song.wav"):
    return client.post(
        "/upload/song",
        files={"file": (filename, wav_bytes, "audio/wav")},
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

    def test_manifest_after_upload(self, client, solid_128x160_png, sine_wav):
        _upload_frame(client, solid_128x160_png)
        _upload_wav(client, sine_wav)
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
# GET /frames/{name}.png
# ---------------------------------------------------------------------------


class TestGetFramePng:
    def test_get_frame_png(self, client, solid_128x160_png):
        _upload_frame(client, solid_128x160_png)
        resp = client.get("/frames/frame_0.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes

    def test_get_frame_png_not_found(self, client):
        resp = client.get("/frames/frame_99.png")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API-03: GET /songs/{name}.json
# ---------------------------------------------------------------------------


class TestGetSongJson:
    def test_get_song_json(self, client, sine_wav):
        _upload_wav(client, sine_wav)
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

    def test_upload_frame_limit(self, client, solid_128x160_png):
        from server.storage import MAX_FRAMES
        for _ in range(MAX_FRAMES):
            assert _upload_frame(client, solid_128x160_png).status_code == 201
        resp = _upload_frame(client, solid_128x160_png)
        assert resp.status_code == 400
        assert "limit" in resp.json()["detail"].lower()

    def test_upload_frame_jpeg(self, client, solid_jpeg, tmp_path):
        resp = client.post(
            "/upload/frame",
            files={"file": ("photo.jpg", solid_jpeg, "image/jpeg")},
        )
        assert resp.status_code == 201
        assert resp.json() == {"name": "frame_0"}
        bin_path = tmp_path / "frames" / "frame_0.bin"
        png_path = tmp_path / "frames" / "frame_0.png"
        assert bin_path.stat().st_size == 40960  # auto-resized to 128×160
        # Thumbnail stored as PNG regardless of JPEG input
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(png_path.read_bytes()))
        assert img.format == "PNG"


# ---------------------------------------------------------------------------
# API-05: POST /upload/song
# ---------------------------------------------------------------------------


class TestUploadSong:
    def test_upload_wav(self, client, sine_wav):
        resp = _upload_wav(client, sine_wav)
        assert resp.status_code == 201
        body = resp.json()
        assert "name" in body
        assert body["notes"] > 0
        assert body["is_complex"] is False
        manifest = client.get("/manifest.json").json()
        assert "song_0.json" in manifest["songs"]

    def test_upload_wav_complex(self, client, noise_wav):
        resp = _upload_wav(client, noise_wav)
        assert resp.status_code == 201
        assert resp.json()["is_complex"] is True

    def test_upload_wav_corrupt(self, client):
        resp = _upload_wav(client, b"not audio at all")
        assert resp.status_code == 422

    def test_upload_wav_too_short(self, client, short_wav):
        resp = _upload_wav(client, short_wav)
        assert resp.status_code == 422
        assert "too short" in resp.json()["detail"].lower()

    def test_upload_song_too_large(self, client):
        big = b"\x00" * (2 * 1024 * 1024 + 1)
        resp = _upload_wav(client, big)
        assert resp.status_code == 413

    def test_upload_unsupported_type(self, client):
        resp = client.post(
            "/upload/song",
            files={"file": ("song.ogg", b"junk", "audio/ogg")},
        )
        assert resp.status_code == 415

    def test_upload_replaces_existing_song(self, client, tmp_path, sine_wav, noise_wav):
        _upload_wav(client, sine_wav)
        content_after_first = (tmp_path / "songs" / "song_0.json").read_text()
        _upload_wav(client, noise_wav)
        content_after_second = (tmp_path / "songs" / "song_0.json").read_text()
        manifest = client.get("/manifest.json").json()
        assert manifest["songs"] == ["song_0.json"]  # still only one slot
        assert content_after_first != content_after_second  # content replaced

    @pytest.mark.skipif(
        not shutil.which("ffmpeg"),
        reason="ffmpeg not installed"
    )
    def test_upload_mp3(self, client, sine_wav):
        from pydub import AudioSegment
        import io as _io
        seg = AudioSegment.from_file(_io.BytesIO(sine_wav), format="wav")
        buf = _io.BytesIO()
        seg.export(buf, format="mp3")
        resp = client.post(
            "/upload/song",
            files={"file": ("song.mp3", buf.getvalue(), "audio/mpeg")},
        )
        assert resp.status_code == 201


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
    def test_delete_song(self, client, tmp_path, sine_wav):
        _upload_wav(client, sine_wav)
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

    def test_etag_song(self, client, sine_wav):
        _upload_wav(client, sine_wav)
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
        # %2F causes Starlette to route-normalize the path out of /frames/ entirely → 404.
        # 422 would only fire if the pattern validator ran; both responses confirm no traversal.
        resp = client.get("/frames/..%2Fetc%2Fpasswd.bin")
        assert resp.status_code in (404, 422)

    def test_delete_path_traversal_rejected(self, client):
        resp = client.delete("/frames/frame_x")
        assert resp.status_code == 422

    def test_song_path_traversal_rejected(self, client):
        resp = client.get("/songs/song_x.json")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Static serving: GET /
# ---------------------------------------------------------------------------


class TestStaticServing:
    def test_get_root_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert b"<html" in resp.content.lower()
