import struct
import pytest
from server.converters import convert_png, convert_sheet


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

    def test_big_endian_packing(self, solid_red_1x1_png):
        result = convert_png(solid_red_1x1_png, 1, 1)
        assert struct.unpack(">H", result)[0] == 0xF800

    def test_invalid_bytes_raises_value_error(self):
        with pytest.raises(ValueError, match="PNG conversion failed"):
            convert_png(b"not a png")

    def test_returns_bytes(self, solid_red_1x1_png):
        result = convert_png(solid_red_1x1_png, 1, 1)
        assert isinstance(result, bytes)


class TestConvertSheet:
    def test_d4_quarter_at_120bpm(self):
        notes = convert_sheet("D4 q\n", bpm=120.0)
        assert notes == [{"freq": 294, "ms": 500}]

    def test_rest_returns_freq_zero(self):
        notes = convert_sheet("R e\n", bpm=120.0)
        assert notes == [{"freq": 0, "ms": 250}]

    def test_dotted_half_fsharp4(self):
        notes = convert_sheet("F#4 h.\n", bpm=120.0)
        assert notes == [{"freq": 370, "ms": 1500}]

    def test_comments_and_blank_lines_ignored(self):
        notes = convert_sheet("# comment\n\nD4 q\n")
        assert len(notes) == 1
        assert notes[0]["freq"] == 294

    def test_happy_birthday_note_count(self, happy_birthday_text):
        notes = convert_sheet(happy_birthday_text)
        assert len(notes) == 25

    def test_happy_birthday_first_note(self, happy_birthday_text):
        notes = convert_sheet(happy_birthday_text)
        assert notes[0] == {"freq": 294, "ms": 500}

    def test_default_bpm_is_120(self):
        result_explicit = convert_sheet("D4 q\n", bpm=120.0)
        result_default = convert_sheet("D4 q\n")
        assert result_explicit == result_default

    def test_invalid_line_raises_value_error_with_line_number(self):
        with pytest.raises(ValueError, match="Line 1"):
            convert_sheet("BADLINE\n")

    def test_unknown_duration_raises_value_error(self):
        with pytest.raises(ValueError, match="unknown duration"):
            convert_sheet("D4 z\n")

    def test_missing_octave_raises_value_error(self):
        with pytest.raises(ValueError, match="Missing octave"):
            convert_sheet("D q\n")

    def test_returns_list_of_dicts(self):
        notes = convert_sheet("D4 q\n")
        assert isinstance(notes, list)
        assert isinstance(notes[0], dict)
        assert set(notes[0].keys()) == {"freq", "ms"}
        assert isinstance(notes[0]["freq"], int)
        assert isinstance(notes[0]["ms"], int)

    def test_rest_lowercase(self):
        notes = convert_sheet("r q\n")
        assert notes[0]["freq"] == 0

    def test_semitones_module_level(self):
        from server.converters import SEMITONES, DURATION_BEATS
        assert len(SEMITONES) == 20
        assert len(DURATION_BEATS) == 9
        assert SEMITONES["C"] == 0
        assert SEMITONES["A"] == 9
        assert DURATION_BEATS["w"] == 4.0
        assert DURATION_BEATS["s"] == 0.25
