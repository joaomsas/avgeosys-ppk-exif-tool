import logging
from pathlib import Path

from avgeosys.core.events import (
    convert_mrk_to_events_file,
    validate_event_times,
)


def test_convert_mrk_to_events_file(tmp_path, caplog):
    mrk = tmp_path / "test.MRK"
    mrk.write_text("1 00:00:01.000\n2 00:00:02,500\n")
    obs = tmp_path / "base.obs"
    obs.write_text(
        "2024 01 01 00 00 00.0000  GPS         TIME OF FIRST OBS\n"
        "2024 01 01 00 00 10.0000  GPS         TIME OF LAST OBS\n"
    )
    caplog.set_level(logging.INFO)
    out = convert_mrk_to_events_file(mrk, tmp_path, obs)
    lines = out.read_text().splitlines()
    assert lines == ["1.000", "2.500"]
    assert "Eventos lidos: 2" in caplog.text


def _write_obs(path: Path) -> None:
    path.write_text(
        "2024 01 01 00 00 00.0000  GPS         TIME OF FIRST OBS\n"
        "2024 01 01 00 00 10.0000  GPS         TIME OF LAST OBS\n"
    )


def test_validate_event_times_within_bounds(tmp_path, caplog):
    obs = tmp_path / "base.obs"
    _write_obs(obs)
    caplog.set_level(logging.WARNING)
    validate_event_times([86401.0, 86402.0], obs)
    assert "Eventos fora do intervalo do OBS" not in caplog.text


def test_validate_event_times_outside_bounds(tmp_path, caplog):
    obs = tmp_path / "base.obs"
    _write_obs(obs)
    caplog.set_level(logging.WARNING)
    validate_event_times([20.0], obs)
    assert "Eventos fora do intervalo do OBS" in caplog.text
