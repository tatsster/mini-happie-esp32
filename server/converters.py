import io
import struct

from PIL import Image

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
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def convert_png(data: bytes, width: int = 128, height: int = 160) -> bytes:
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


def _note_to_freq(note_str: str) -> int:
    note_str = note_str.strip()
    if note_str.upper() == "R":
        return 0
    i = len(note_str) - 1
    while i >= 0 and (note_str[i].isdigit() or note_str[i] == "-"):
        i -= 1
    note_name = note_str[: i + 1].upper()
    octave_str = note_str[i + 1 :]
    if note_name not in SEMITONES:
        raise ValueError(f"Unknown note name: '{note_str}'")
    if not octave_str:
        raise ValueError(f"Missing octave in: '{note_str}'")
    midi = (int(octave_str) + 1) * 12 + SEMITONES[note_name]
    return round(440.0 * (2 ** ((midi - 69) / 12.0)))


def _beats_to_ms(beats: float, bpm: float) -> int:
    return round((beats / bpm) * 60_000)


def convert_sheet(text: str, bpm: float = 120.0) -> list[dict]:
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
        result.append({"freq": freq, "ms": ms})
    return result
