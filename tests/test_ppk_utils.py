import os
from pathlib import Path
import pytest
from avgeosys.core.ppk import find_base_files

def touch(path: Path):
    path.write_text("")  # cria arquivo vazio

def test_find_base_files_selects_latest(tmp_path):
    # Cria vários arquivos .YYO e .YYP
    touch(tmp_path / "site.20O")
    touch(tmp_path / "site.21O")
    touch(tmp_path / "site.19P")
    touch(tmp_path / "site.22P")

    obs, nav = find_base_files(tmp_path)
    # deve escolher o .21O (ano mais alto) e .22P
    assert obs.suffix == ".21O"
    assert nav.suffix == ".22P"

def test_find_base_files_missing(tmp_path):
    # Se faltar qualquer tipo, deve lançar FileNotFoundError
    touch(tmp_path / "only.00O")
    with pytest.raises(FileNotFoundError):
        find_base_files(tmp_path)
