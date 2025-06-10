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

import subprocess
import avgeosys.core.ppk as ppk_mod


def test_process_single_folder_creates_pos_and_cmd(tmp_path, monkeypatch):
    folder = tmp_path / "site"
    folder.mkdir()
    rover_obs = folder / "rover.obs"
    rover_obs.write_text("")
    base_obs = tmp_path / "base.obs"
    base_nav = tmp_path / "base.nav"
    base_obs.write_text("")
    base_nav.write_text("")

    monkeypatch.setattr(subprocess, "STARTUPINFO", lambda: None, raising=False)
    recorded = {}

    def fake_run(cmd, check, stdout, stderr, startupinfo):
        recorded["cmd"] = cmd
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(ppk_mod, "RINEX2RTKP_PATH", Path("tool.exe"))

    pos_file = ppk_mod.process_single_folder(folder, base_obs, base_nav)

    expected_pos = folder / "PPK_Results" / "rover_PPKOBS.pos"
    assert pos_file == expected_pos
    assert expected_pos.exists(), "Arquivo .pos nao criado"
    expected_cmd = [
        str(Path("tool.exe")),
        "-o",
        str(expected_pos),
        str(rover_obs),
        str(base_obs),
        str(base_nav),
    ]
    assert recorded["cmd"] == expected_cmd


def test_process_all_folders_invokes_single(tmp_path, monkeypatch):
    f1 = tmp_path / "f1"
    f2 = tmp_path / "f2"
    f3 = tmp_path / "f3"
    for f in (f1, f2, f3):
        f.mkdir()
    (f1 / "a_Timestamp.MRK").write_text("")
    (f2 / "b_Timestamp.MRK").write_text("")

    monkeypatch.setattr(ppk_mod, "find_base_files", lambda root: (Path("b.obs"), Path("b.nav")))
    called = []

    def fake_single(folder, base_obs, base_nav):
        called.append(folder)
        return folder / "out.pos"

    monkeypatch.setattr(ppk_mod, "process_single_folder", fake_single)

    ppk_mod.process_all_folders(tmp_path, max_workers=1)

    assert set(called) == {f1, f2}
