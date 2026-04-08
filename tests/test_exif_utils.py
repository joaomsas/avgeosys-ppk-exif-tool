"""Tests for avgeosys/core/exif.py"""

import shutil
import pytest
from pathlib import Path
from avgeosys.core.exif import (
    convert_to_dms,
    convert_from_dms,
    update_exif,
    extract_exif_coordinates,
)

DATA_DIR = Path(__file__).parent / "data"


def _copy_jpg(tmp_path: Path) -> Path:
    src = DATA_DIR / "sample.jpg"
    dst = tmp_path / "test.jpg"
    shutil.copy(src, dst)
    return dst


def test_convert_to_dms_positive():
    result = convert_to_dms(47.9201234)
    assert isinstance(result, tuple)
    assert len(result) == 3
    # Each element is a (numerator, denominator) rational
    for item in result:
        assert isinstance(item, tuple)
        assert len(item) == 2


def test_convert_to_dms_negative():
    # Should work on absolute value (sign handled by reference tag)
    result = convert_to_dms(-15.7801234)
    d, m, s = result
    deg = d[0] / d[1]
    assert deg == pytest.approx(15.0, abs=0.1)


def test_convert_from_dms_round_trip():
    original = 47.9201234
    dms = convert_to_dms(original)
    back = convert_from_dms(dms)
    assert back == pytest.approx(original, abs=1e-6)


def test_convert_from_dms_negative_round_trip():
    original = -15.7801234
    dms = convert_to_dms(abs(original))
    back = convert_from_dms(dms)
    assert back == pytest.approx(abs(original), abs=1e-6)


def test_update_and_extract_exif(tmp_path):
    jpg = _copy_jpg(tmp_path)
    update_exif(jpg, lat=-15.7801234, lon=-47.9201234, alt=1050.234)
    coords = extract_exif_coordinates(jpg)
    assert coords is not None
    assert coords["latitude"] == pytest.approx(-15.7801234, abs=1e-5)
    assert coords["longitude"] == pytest.approx(-47.9201234, abs=1e-5)
    assert coords["altitude"] == pytest.approx(1050.234, abs=0.01)


def test_update_exif_negative_lat_lon(tmp_path):
    jpg = _copy_jpg(tmp_path)
    update_exif(jpg, lat=-15.0, lon=-47.5, alt=100.0)
    coords = extract_exif_coordinates(jpg)
    assert coords["latitude"] < 0
    assert coords["longitude"] < 0


def test_update_exif_positive_lat_lon(tmp_path):
    jpg = _copy_jpg(tmp_path)
    update_exif(jpg, lat=48.8566, lon=2.3522, alt=35.0)
    coords = extract_exif_coordinates(jpg)
    assert coords["latitude"] == pytest.approx(48.8566, abs=1e-4)
    assert coords["longitude"] == pytest.approx(2.3522, abs=1e-4)


def test_extract_exif_no_gps_returns_none(tmp_path):
    """A fresh copy of sample.jpg has no GPS tags — should return None."""
    jpg = _copy_jpg(tmp_path)
    result = extract_exif_coordinates(jpg)
    assert result is None


def test_update_exif_bad_file_does_not_crash(tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not a jpeg")
    # Should not raise
    update_exif(bad, lat=0.0, lon=0.0, alt=0.0)
