from pathlib import Path
import pytest
import avgeosys.core.ppk as ppk_mod
from avgeosys.core.ppk import find_base_files, process_single_folder

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


def test_process_single_folder_uses_rover_nav(tmp_path, monkeypatch):
    rover_obs = tmp_path / "rover.obs"
    rover_obs.write_text("")
    rover_nav = tmp_path / "rover.nav"
    rover_nav.write_text("")
    base_obs = tmp_path / "base.O"
    base_obs.write_text("")
    base_nav = tmp_path / "base.P"
    base_nav.write_text("")

    captured = {}

    def fake_run(cmd, stdout=None, stderr=None, startupinfo=None):
        captured["cmd"] = cmd
        class R:
            returncode = 0
            stdout = b""
        return R()

    monkeypatch.setattr(ppk_mod.subprocess, "run", fake_run)
    exe = tmp_path / "rtk"
    exe.write_text("")
    monkeypatch.setattr(ppk_mod, "RINEX2RTKP_PATH", exe)
    monkeypatch.setattr(ppk_mod, "RINEX2RTKP_CONFIG", Path("conf"))

    event_file = tmp_path / "ev.txt"
    monkeypatch.setattr(
        ppk_mod, "convert_mrk_to_events_file", lambda m, o, obs: event_file
    )
    mrk = tmp_path / "site_Timestamp.MRK"
    mrk.write_text("1,0")

    process_single_folder(tmp_path, base_obs, base_nav, True)

    cmd_list = captured.get("cmd", [])
    assert str(rover_nav) in cmd_list
    assert "-k" in cmd_list
    assert str(Path("conf")) in cmd_list
    assert "-e" in cmd_list
    assert str(event_file) in cmd_list
