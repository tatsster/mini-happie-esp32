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
