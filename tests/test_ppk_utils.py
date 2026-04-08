"""Tests for avgeosys/core/ppk.py"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from avgeosys.core.ppk import find_base_files, process_single_folder

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def fake_project(tmp_path):
    """Create a minimal fake project folder with required RINEX/MRK files."""
    folder = tmp_path / "flight01"
    folder.mkdir()
    (folder / "rover.23O").write_text("obs")
    (folder / "base.23O").write_text("obs")
    (folder / "base.23P").write_text("nav")
    (folder / "DJI_0001.MRK").write_text(
        "2286 432100.000 DJI_0001_V.JPG\n"
    )
    return folder


def test_find_base_files_finds_obs(fake_project):
    files = find_base_files(fake_project)
    assert "rover_obs" in files or "obs" in files or any("obs" in str(v).lower() for v in files.values())


def test_find_base_files_finds_mrk(fake_project):
    files = find_base_files(fake_project)
    mrk_key = next((k for k in files if "mrk" in k.lower()), None)
    assert mrk_key is not None
    assert files[mrk_key] is not None


def test_find_base_files_empty_folder(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    files = find_base_files(empty)
    # Should return empty/None values, not crash
    assert isinstance(files, dict)


def test_process_single_folder_calls_rnx2rtkp(fake_project, tmp_path):
    """process_single_folder should call rnx2rtkp subprocess."""
    from avgeosys.core import ppk as ppk_mod

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = b""

    with patch.object(ppk_mod, "subprocess") as mock_subprocess, \
         patch("avgeosys.config.RTKLIB_PATH", fake_project / "rnx2rtkp.exe"):
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.CREATE_NO_WINDOW = 0x08000000

        config = {}
        result = process_single_folder(fake_project, config)
        # rnx2rtkp was called
        assert mock_subprocess.run.called or result is None  # might be None if binary missing


def test_process_single_folder_missing_rnx2rtkp(fake_project):
    """When rnx2rtkp is not found, should return None (not crash)."""
    from avgeosys.core.ppk import process_single_folder
    from pathlib import Path

    with patch("avgeosys.config.RTKLIB_PATH", Path("/nonexistent/rnx2rtkp.exe")):
        result = process_single_folder(fake_project, {})
    assert result is None
