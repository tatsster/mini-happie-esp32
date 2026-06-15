import io
import re
import struct
from typing import TypedDict

from PIL import Image


class Note(TypedDict):
    freq: int
    ms: int


SEMITONES = {
    "C": 0, "C#": 1, "DB": 1,
    "D": 2, "D#": 3, "EB": 3,
    "E": 4, "FB": 4,
    "F": 5, "F#": 6, "GB": 6,
    "G": 7, "G#": 8, "AB": 8,
    "A": 9, "A#": 10, "BB": 10,
    "B": 11, "CB": 11, "B#": 0,
}

DURATION_BEATS = {
    "w": 4.0,
    "h": 2.0,
    "q": 1.0,
    "e": 0.5,
    "s": 0.25,
    "w.": 6.0,
    "h.": 3.0,
    "q.": 1.5,
    "e.": 0.75,
}


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


_NOTE_RE = re.compile(r"^([A-Ga-g][#Bb]?)(-?\d+)$")


def _note_to_freq(note_str: str) -> int:
    """Convert a note string (e.g. ``'C4'``, ``'F#3'``, ``'R'``) to a frequency in Hz.

    ``'R'`` (rest) returns 0.  Frequency is calculated from equal temperament
    with A4 = 440 Hz.

    Raises:
        ValueError: If the note name or octave is missing or unrecognised.
    """
    note_str = note_str.strip()
    if note_str.upper() == "R":
        return 0
    m = _NOTE_RE.match(note_str)
    if not m:
        # Distinguish "unknown note name" from "missing octave" for test compatibility.
        letter = re.match(r"^[A-Ga-g][#Bb]?", note_str)
        if letter and note_str[letter.end():] == "":
            raise ValueError(f"Missing octave in: '{note_str}'")
        raise ValueError(f"Unknown note name: '{note_str}'")
    note_name, octave_str = m.group(1).upper(), m.group(2)
    if note_name not in SEMITONES:
        raise ValueError(f"Unknown note name: '{note_str}'")
    midi = (int(octave_str) + 1) * 12 + SEMITONES[note_name]
    return round(440.0 * (2 ** ((midi - 69) / 12.0)))


def _beats_to_ms(beats: float, bpm: float) -> int:
    """Convert a beat count to milliseconds at the given tempo."""
    return round((beats / bpm) * 60_000)


def convert_sheet(text: str, bpm: float = 120.0) -> list[Note]:
    """Parse a plain-text music sheet into a list of Note dicts.

    Each non-blank, non-comment line must be ``<note> <duration>`` where
    ``<note>`` is a standard note name with octave (e.g. ``C4``, ``F#3``) or
    ``R`` for a rest, and ``<duration>`` is one of the keys in
    :data:`DURATION_BEATS` (e.g. ``q``, ``e.``).

    Args:
        text: Raw text content of the sheet file.
        bpm: Tempo in beats per minute. Defaults to 120.

    Returns:
        Ordered list of :class:`Note` dicts with ``freq`` (Hz) and ``ms`` keys.

    Raises:
        ValueError: On any malformed line, unknown note, or unknown duration.
    """
    result = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f"Line {lineno}: expected '<note> <duration>', got: '{line}'")
        note_str, dur_str = parts
        dur_str = dur_str.lower()
        if dur_str not in DURATION_BEATS:
            raise ValueError(f"Line {lineno}: unknown duration '{dur_str}'")
        freq = _note_to_freq(note_str)
        ms = _beats_to_ms(DURATION_BEATS[dur_str], bpm)
        result.append(Note(freq=freq, ms=ms))
    return result
