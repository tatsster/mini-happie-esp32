import struct
import pytest
from server.converters import convert_png, convert_audio


class TestConvertPng:
    def test_red_pixel_rgb565(self, solid_red_1x1_png):
        result = convert_png(solid_red_1x1_png, 1, 1)
        assert result == b'\xf8\x00'

    def test_green_pixel_rgb565(self, solid_green_1x1_png):
        result = convert_png(solid_green_1x1_png, 1, 1)
        assert result == b'\x07\xe0'

    def test_blue_pixel_rgb565(self, solid_blue_1x1_png):
        result = convert_png(solid_blue_1x1_png, 1, 1)
        assert result == b'\x00\x1f'

    def test_output_length_default(self, solid_128x160_png):
        result = convert_png(solid_128x160_png)
        assert len(result) == 128 * 160 * 2

    def test_output_length_custom_dimensions(self, solid_128x160_png):
        result = convert_png(solid_128x160_png, width=64, height=80)
        assert len(result) == 64 * 80 * 2

    def test_resize_small_to_default(self, small_png):
        result = convert_png(small_png)
        assert len(result) == 128 * 160 * 2

    def test_transparent_composites_to_black(self, transparent_1x1_png):
        result = convert_png(transparent_1x1_png, 1, 1)
        assert result == b'\x00\x00'

    def test_invalid_bytes_raises_value_error(self):
        with pytest.raises(ValueError, match="PNG conversion failed"):
            convert_png(b"not a png")

class TestConvertAudio:
    def test_noise_wav_is_complex(self, noise_wav):
        _, is_complex = convert_audio(noise_wav, fmt="wav")
        assert is_complex is True

    def test_sine_freq_in_range(self, sine_wav):
        # 440 Hz sine — median voiced f0 should be near 440 Hz
        notes, _ = convert_audio(sine_wav, fmt="wav")
        voiced = [n["freq"] for n in notes if n["freq"] > 0]
        assert len(voiced) > 0
        assert any(380 < f < 500 for f in voiced)

    def test_min_note_duration_80ms(self, sine_wav):
        notes, _ = convert_audio(sine_wav, fmt="wav")
        assert all(n["ms"] >= 80 for n in notes)

    def test_corrupt_bytes_raises_value_error(self):
        with pytest.raises(ValueError, match="Could not decode audio"):
            convert_audio(b"not audio", fmt="wav")

    def test_too_short_raises_value_error(self, short_wav):
        with pytest.raises(ValueError, match="too short"):
            convert_audio(short_wav, fmt="wav")

    def test_returns_list_of_note_dicts(self, sine_wav):
        notes, is_complex = convert_audio(sine_wav, fmt="wav")
        assert isinstance(notes, list)
        assert len(notes) > 0
        assert isinstance(notes[0], dict)
        assert set(notes[0].keys()) == {"freq", "ms"}
        assert isinstance(notes[0]["freq"], int)
        assert isinstance(notes[0]["ms"], int)
        assert is_complex is False  # pure sine → not complex
