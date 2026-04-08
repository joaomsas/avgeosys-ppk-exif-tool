"""End-to-end integration test: MRK + POS + JPEG → JSON + EXIF + report."""

import json
import shutil
import zipfile
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def project(tmp_path):
    """Set up a temp project directory with all required files."""
    shutil.copy(DATA_DIR / "sample.MRK", tmp_path / "flight.MRK")
    shutil.copy(DATA_DIR / "sample.pos", tmp_path / "flight.pos")
    shutil.copy(DATA_DIR / "sample.jpg", tmp_path / "DJI_0001_V.JPG")
    shutil.copy(DATA_DIR / "sample.jpg", tmp_path / "DJI_0002_V.JPG")
    shutil.copy(DATA_DIR / "sample.jpg", tmp_path / "DJI_0003_V.JPG")
    shutil.copy(DATA_DIR / "sample.jpg", tmp_path / "DJI_0004_V.JPG")
    shutil.copy(DATA_DIR / "sample.jpg", tmp_path / "DJI_0005_V.JPG")
    return tmp_path


def test_full_pipeline(project):
    from avgeosys.core.exif import batch_update_exif, extract_exif_coordinates
    from avgeosys.core.interpolator import run_interpolation
    from avgeosys.core.report import generate_report_and_kmz

    output_dir = project / "PPK_Results"

    # Step 1: Interpolation
    json_path = run_interpolation(
        project / "flight.MRK",
        project / "flight.pos",
        output_dir,
        orthometric=False,
    )
    assert json_path.exists()

    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)

    assert len(data) == 5

    # Step 2: EXIF geotagging
    batch_update_exif(data, project)

    # Verify EXIF was written to in-range photos
    in_range = [r for r in data if r["quality"] != 3]
    for rec in in_range:
        coords = extract_exif_coordinates(project / rec["filename"])
        assert coords is not None, f"No GPS EXIF in {rec['filename']}"
        assert coords["latitude"] == pytest.approx(rec["latitude"], abs=1e-4)
        assert coords["longitude"] == pytest.approx(rec["longitude"], abs=1e-4)

    # Step 3: Report + KMZ
    report_txt, kmz_interp, kmz_exif = generate_report_and_kmz(data, output_dir)

    assert report_txt.exists()
    content = report_txt.read_text(encoding="utf-8")
    assert "Fixed" in content
    assert "Float" in content

    assert kmz_interp.exists()
    assert zipfile.is_zipfile(kmz_interp)

    assert kmz_exif.exists()
    assert zipfile.is_zipfile(kmz_exif)


def test_interpolated_json_schema(project):
    from avgeosys.core.interpolator import run_interpolation

    json_path = run_interpolation(
        project / "flight.MRK",
        project / "flight.pos",
        project / "PPK_Results",
    )
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)

    required_keys = {"filename", "gps_week", "gps_seconds", "latitude", "longitude", "height", "quality"}
    for rec in data:
        assert required_keys.issubset(rec.keys()), f"Missing keys in {rec}"
