"""Tests for avgeosys/core/report.py"""

import zipfile
from pathlib import Path
from avgeosys.core.report import generate_report_and_kmz

SAMPLE_DATA = [
    {
        "filename": "DJI_0001_V.JPG",
        "gps_week": 2286,
        "gps_seconds": 432100.0,
        "latitude": -15.7796,
        "longitude": -47.9196,
        "height": 1050.200,
        "quality": 1,
    },
    {
        "filename": "DJI_0002_V.JPG",
        "gps_week": 2286,
        "gps_seconds": 432102.5,
        "latitude": -15.7795,
        "longitude": -47.9195,
        "height": 1050.225,
        "quality": 2,
    },
    {
        "filename": "DJI_0003_V.JPG",
        "gps_week": 2286,
        "gps_seconds": 432104.0,
        "latitude": -15.7794,
        "longitude": -47.9194,
        "height": 1050.250,
        "quality": 1,
    },
    {
        "filename": "DJI_0005_V.JPG",
        "gps_week": 2286,
        "gps_seconds": 435000.0,
        "latitude": -15.7780,
        "longitude": -47.9180,
        "height": 1050.000,
        "quality": 3,
    },
]


def test_generate_report_creates_files(tmp_path):
    report_txt, kmz_interp, kmz_exif = generate_report_and_kmz(SAMPLE_DATA, tmp_path)
    assert Path(report_txt).exists()
    assert Path(kmz_interp).exists()
    assert Path(kmz_exif).exists()


def test_report_contains_quality_labels(tmp_path):
    report_txt, _, _ = generate_report_and_kmz(SAMPLE_DATA, tmp_path)
    content = Path(report_txt).read_text(encoding="utf-8")
    assert "Fixed" in content
    assert "Float" in content
    assert "Unknown" in content


def test_report_contains_percentages(tmp_path):
    report_txt, _, _ = generate_report_and_kmz(SAMPLE_DATA, tmp_path)
    content = Path(report_txt).read_text(encoding="utf-8")
    # 4 photos: 2 Fixed=50%, 1 Float=25%, 1 Unknown=25%
    assert "50" in content or "50.0" in content


def test_kmz_is_valid_zip(tmp_path):
    _, kmz_interp, _ = generate_report_and_kmz(SAMPLE_DATA, tmp_path)
    assert zipfile.is_zipfile(kmz_interp)


def test_kmz_contains_kml(tmp_path):
    _, kmz_interp, _ = generate_report_and_kmz(SAMPLE_DATA, tmp_path)
    with zipfile.ZipFile(kmz_interp) as zf:
        kml_files = [n for n in zf.namelist() if n.endswith(".kml")]
    assert len(kml_files) >= 1


def test_kmz_exif_is_valid_zip(tmp_path):
    _, _, kmz_exif = generate_report_and_kmz(SAMPLE_DATA, tmp_path)
    assert zipfile.is_zipfile(kmz_exif)
