"""Geolocation: extract GPS from image EXIF and reverse geocode to place names."""

from typing import Any

from rpd.config import settings


def _convert_dms_to_decimal(dms: tuple, ref: str) -> float | None:
    """Convert (deg, min, sec) or ((num,den),...) tuple to decimal degrees."""
    try:
        if not dms or len(dms) < 3:
            return None

        def to_float(v):
            if hasattr(v, "__len__") and len(v) == 2:
                return v[0] / v[1] if v[1] else 0
            return float(v)

        deg = to_float(dms[0])
        min_ = to_float(dms[1])
        sec = to_float(dms[2])
        decimal = deg + (min_ / 60) + (sec / 3600)
        if ref and str(ref).upper() in ("S", "W"):
            decimal = -decimal
        return decimal
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _extract_gps_from_exif(data: bytes) -> tuple[float | None, float | None]:
    """Extract latitude and longitude from image EXIF using piexif (JPEG/TIFF)."""
    try:
        import piexif

        exif_dict = piexif.load(data)
        gps = exif_dict.get("GPS") or {}
        if not gps:
            return None, None

        lat = gps.get(piexif.GPSIFD.GPSLatitude)
        lat_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef, b"N")
        lon = gps.get(piexif.GPSIFD.GPSLongitude)
        lon_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef, b"E")

        lat_ref_str = lat_ref.decode() if isinstance(lat_ref, bytes) else str(lat_ref)
        lon_ref_str = lon_ref.decode() if isinstance(lon_ref, bytes) else str(lon_ref)

        lat_dec = _convert_dms_to_decimal(tuple(lat) if lat else (), lat_ref_str)
        lon_dec = _convert_dms_to_decimal(tuple(lon) if lon else (), lon_ref_str)
        return lat_dec, lon_dec
    except Exception:
        return None, None


def _reverse_geocode(lat: float, lon: float, enabled: bool = True) -> str | None:
    """Reverse geocode coordinates to human-readable address using Nominatim (free)."""
    if not enabled:
        return None
    try:
        from geopy.geocoders import Nominatim
        from geopy.extra.rate_limiter import RateLimiter

        geolocator = Nominatim(user_agent="rpd-meta-extractor")
        reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1.1)
        location = reverse(f"{lat}, {lon}")
        return location.address if location else None
    except Exception:
        return None


def extract_image_geolocation(
    data: bytes, *, geolocation_lookup: bool | None = None
) -> dict[str, Any]:
    """
    Extract GPS coordinates from image EXIF and optionally reverse geocode.
    Returns dict with gps_coordinates (lat, lon) and geolocation (place name).
    """
    result: dict[str, Any] = {}
    do_lookup = geolocation_lookup if geolocation_lookup is not None else settings.geolocation_lookup_enabled
    lat, lon = _extract_gps_from_exif(data)
    if lat is not None and lon is not None:
        result["gps_coordinates"] = {"latitude": lat, "longitude": lon}
        place = _reverse_geocode(lat, lon, enabled=do_lookup)
        if place:
            result["geolocation"] = place
    return result
