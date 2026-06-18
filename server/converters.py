import io
import struct
from typing import TypedDict

import numpy as np
from PIL import Image
from pydub import AudioSegment
import librosa


class Note(TypedDict):
    freq: int
    ms: int


def _rgb565(r: int, g: int, b: int) -> int:
    """Pack 8-bit RGB channels into a 16-bit RGB565 big-endian word."""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def to_png_bytes(data: bytes) -> bytes:
    """Re-encode any PIL-supported image (PNG, JPEG, …) as PNG bytes.

    Used to normalise uploaded images to a single format before storing
    the thumbnail copy, so GET /frames/{name}.png always serves a valid PNG
    regardless of what the user originally uploaded.
    """
    try:
        img = Image.open(io.BytesIO(data))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as exc:
        raise ValueError(f"Could not decode image: {exc}") from exc


def convert_png(data: bytes, width: int = 128, height: int = 160) -> bytes:
    """Convert image bytes to a raw RGB565 big-endian frame buffer.

    Alpha-bearing modes (RGBA, LA, P) are composited onto a black background
    before conversion so that transparency is flattened to opaque pixels.

    Args:
        data: Raw bytes of any PIL-supported image format (PNG, JPEG, …).
        width: Target width in pixels. Defaults to 128.
        height: Target height in pixels. Defaults to 160.

    Returns:
        Raw bytes — ``width * height * 2`` bytes, big-endian RGB565.

    Raises:
        ValueError: If *data* cannot be decoded or converted.
    """
    try:
        img = Image.open(io.BytesIO(data))
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
            img = Image.alpha_composite(bg, img.convert("RGBA"))
        img = img.convert("RGB")
        img = img.resize((width, height), Image.LANCZOS)
        pixels = [_rgb565(*img.getpixel((x, y))) for y in range(height) for x in range(width)]
        return struct.pack(f">{width * height}H", *pixels)
    except Exception as exc:
        raise ValueError(f"PNG conversion failed: {exc}") from exc


def convert_audio(data: bytes, fmt: str = "wav") -> tuple[list[Note], bool]:
    """Convert WAV or MP3 audio bytes into a note sequence for the ESP32 buzzer.

    Decodes the audio with pydub, resamples to 22050 Hz mono float32, detects
    note onsets with librosa, extracts per-segment pitch with librosa pyin
    (run once on the full signal), and computes a polyphony flag from spectral
    flatness and median voicing probability.

    Args:
        data: Raw bytes of a WAV or MP3 audio file.
        fmt: Audio format string — ``"wav"`` or ``"mp3"``. Must be supplied
             explicitly because pydub cannot reliably sniff MP3 from BytesIO.

    Returns:
        A tuple ``(notes, is_complex)`` where ``notes`` is an ordered list of
        :class:`Note` dicts with ``freq`` (Hz) and ``ms`` keys, and
        ``is_complex`` is ``True`` when the audio has polyphonic or noisy
        content that the ESP32 buzzer cannot reproduce accurately.

    Raises:
        ValueError: If *data* cannot be decoded (``"Could not decode audio"``),
                    if the audio is shorter than 1 second (``"Audio too short
                    for conversion"``), or if no pitched content is found
                    (``"No pitched content detected"``).
    """
    # 1. Decode audio bytes using pydub; fmt must be explicit for BytesIO (Pitfall 4).
    try:
        seg = AudioSegment.from_file(io.BytesIO(data), format=fmt)
    except Exception as exc:
        raise ValueError(f"Could not decode audio: {exc}") from exc

    # 2. Normalise to 22050 Hz mono float32 in [-1.0, 1.0] (Pitfall 3).
    seg = seg.set_frame_rate(22050).set_channels(1)
    raw = np.array(seg.get_array_of_samples(), dtype=np.float32)
    y = raw / (2 ** (seg.sample_width * 8 - 1))
    sr = 22050

    # 3. Duration guard — librosa needs at least 1 second of signal.
    if len(y) / sr < 1.0:
        raise ValueError("Audio too short for conversion")

    # 4. Onset detection; prepend 0.0 when audio starts immediately (Pitfall 1).
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    if len(onsets) == 0 or onsets[0] > 0.1:
        onsets = np.concatenate([[0.0], onsets])

    # 5. Full-signal pYIN pitch extraction (run once — not per segment).
    f0, voiced_flag, voiced_prob = librosa.pyin(y, fmin=80, fmax=2000, sr=sr)

    # 6. Per-onset segment extraction.
    hop_length = 512
    onset_frames = librosa.time_to_frames(onsets, sr=sr, hop_length=hop_length)
    total_frames = len(f0)
    boundaries = list(onset_frames) + [total_frames]

    notes: list[Note] = []
    for i in range(len(onset_frames)):
        start_f, end_f = boundaries[i], boundaries[i + 1]
        dur_ms = max(80, int((end_f - start_f) * hop_length / sr * 1000))
        seg_voiced = f0[start_f:end_f][voiced_flag[start_f:end_f]]
        freq = int(np.nanmedian(seg_voiced)) if len(seg_voiced) > 0 else 0
        notes.append(Note(freq=freq, ms=dur_ms))

    # 7. Guard against all-unvoiced / silence audio (Pitfall 6).
    if not notes:
        raise ValueError("No pitched content detected")

    # 8. Polyphony score: high flatness OR low median voicing probability → complex.
    flatness = float(np.mean(librosa.feature.spectral_flatness(y=y)))
    median_vp = float(np.median(voiced_prob))
    is_complex = flatness > 0.15 or median_vp < 0.5

    return notes, is_complex
