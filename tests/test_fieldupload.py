"""Tests for avgeosys/core/fieldupload.py"""

import zipfile
from pathlib import Path

import pytest

from avgeosys.core.fieldupload import prepare_field_upload


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal fake project structure."""
    project = tmp_path / "project"
    project.mkdir()

    # Two flight folders, each with RINEX obs (required by find_flight_folders)
    for i in (1, 2):
        folder = project / f"FLIGHT_{i:03d}"
        folder.mkdir()
        (folder / f"DJI_{i:04d}.JPG").write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
        (folder / f"DJI_{i:04d}_PPKOBS.obs").write_text("RINEX OBS")
        (folder / f"DJI_{i:04d}_PPKNAV.nav").write_text("RINEX NAV")
        (folder / f"DJI_{i:04d}.MRK").write_text("1 100.0 DJI_0001.JPG")
        # Generated files — should be removed
        (folder / f"FLIGHT_{i:03d}.pos").write_text("pos data")
        (folder / f"FLIGHT_{i:03d}_events.pos").write_text("events pos")
        (folder / "temp.tmp").write_text("temp")

    # Base station files at project root
    (project / "base_obs.24O").write_text("BASE OBS")
    (project / "base_nav.24N").write_text("BASE NAV")

    # PPK_Results folder (generated)
    ppk = project / "PPK_Results"
    ppk.mkdir()
    (ppk / "interpolated_data.json").write_text("{}")

    return project


def test_fieldupload_removes_pos_files(tmp_path):
    project = _make_project(tmp_path)
    prepare_field_upload(project)

    for folder_name in ("FLIGHT_001", "FLIGHT_002"):
        folder = project / folder_name
        pos_files = list(folder.glob("*.pos"))
        assert pos_files == [], f".pos files must be removed: {pos_files}"


def test_fieldupload_removes_tmp_files(tmp_path):
    project = _make_project(tmp_path)
    prepare_field_upload(project)

    for folder_name in ("FLIGHT_001", "FLIGHT_002"):
        folder = project / folder_name
        tmp_files = list(folder.glob("*.tmp"))
        assert tmp_files == [], f".tmp files must be removed: {tmp_files}"


def test_fieldupload_keeps_original_files(tmp_path):
    project = _make_project(tmp_path)
    prepare_field_upload(project)

    for i, folder_name in enumerate(("FLIGHT_001", "FLIGHT_002"), start=1):
        folder = project / folder_name
        assert (folder / f"DJI_{i:04d}.JPG").exists(), "JPEG must be kept"
        assert (folder / f"DJI_{i:04d}_PPKOBS.obs").exists(), ".obs must be kept"
        assert (folder / f"DJI_{i:04d}_PPKNAV.nav").exists(), ".nav must be kept"
        assert (folder / f"DJI_{i:04d}.MRK").exists(), ".MRK must be kept"


def test_fieldupload_base_zip_in_first_folder(tmp_path):
    project = _make_project(tmp_path)
    prepare_field_upload(project)

    zip_path = project / "FLIGHT_001" / "base_station.zip"
    assert zip_path.exists(), "base_station.zip must be in first flight folder"

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "base_obs.24O" in names
    assert "base_nav.24N" in names


def test_fieldupload_base_zip_not_in_second_folder(tmp_path):
    project = _make_project(tmp_path)
    prepare_field_upload(project)

    assert not (project / "FLIGHT_002" / "base_station.zip").exists()


def test_fieldupload_removes_ppk_results(tmp_path):
    project = _make_project(tmp_path)
    prepare_field_upload(project)

    assert not (project / "PPK_Results").exists(), "PPK_Results/ must be removed"


def test_fieldupload_returns_counts(tmp_path):
    project = _make_project(tmp_path)
    folders, removed, base = prepare_field_upload(project)

    assert folders == 2
    assert removed >= 4  # at least 2x .pos + 2x .tmp
    assert base == 2     # base_obs + base_nav


def test_fieldupload_cancel_stops_early(tmp_path):
    import threading
    project = _make_project(tmp_path)
    cancel = threading.Event()
    cancel.set()  # already cancelled

    folders, removed, base = prepare_field_upload(project, cancel_event=cancel)
    assert folders == 0
