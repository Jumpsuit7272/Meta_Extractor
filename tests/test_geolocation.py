"""Tests for geolocation extraction from images."""

import pytest
from rpd.services.geolocation import (
    _convert_dms_to_decimal,
    _extract_gps_from_exif,
    extract_image_geolocation,
)


def test_convert_dms_to_decimal():
    # (37, 46, 29) N -> ~37.7747
    lat = _convert_dms_to_decimal((37, 46, 29), "N")
    assert lat is not None
    assert 37.7 < lat < 37.8

    # S should be negative
    lat_s = _convert_dms_to_decimal((33, 55, 0), "S")
    assert lat_s is not None
    assert lat_s < 0


def test_extract_gps_no_exif():
    # Minimal 1x1 pixel PNG - no EXIF
    png_no_exif = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT"
        b"\x08\xd7c\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    result = extract_image_geolocation(png_no_exif, geolocation_lookup=False)
    assert result == {} or "gps_coordinates" not in result


def test_extract_gps_from_jpeg_with_gps():
    """Test with a JPEG that has GPS EXIF (created via piexif)."""
    try:
        import piexif

        # Create GPS EXIF: 37.7749, -122.4194 (San Francisco)
        gps_ifd = {
            piexif.GPSIFD.GPSLatitudeRef: b"N",
            piexif.GPSIFD.GPSLatitude: ((37, 1), (46, 1), (296400, 10000)),
            piexif.GPSIFD.GPSLongitudeRef: b"W",
            piexif.GPSIFD.GPSLongitude: ((122, 1), (25, 1), (19840, 100)),
        }
        exif_dict = {"GPS": gps_ifd, "0th": {}, "Exif": {}, "1st": {}, "thumbnail": None}
        exif_bytes = piexif.dump(exif_dict)

        # We need a real JPEG to embed EXIF - piexif.insert inserts into image
        from PIL import Image
        from io import BytesIO

        img = Image.new("RGB", (10, 10), color="red")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        jpeg_bytes = buf.getvalue()
        out = BytesIO()
        piexif.insert(exif_bytes, jpeg_bytes, out)
        jpeg_with_gps = out.getvalue()

        lat, lon = _extract_gps_from_exif(jpeg_with_gps)
        assert lat is not None
        assert lon is not None
        assert 37.7 < lat < 37.8
        assert -122.5 < lon < -122.3

        result = extract_image_geolocation(jpeg_with_gps, geolocation_lookup=False)
        assert "gps_coordinates" in result
        assert abs(result["gps_coordinates"]["latitude"] - lat) < 0.0001
        assert abs(result["gps_coordinates"]["longitude"] - lon) < 0.0001
        assert "geolocation" not in result  # lookup disabled
    except ImportError:
        pytest.skip("piexif not installed")
