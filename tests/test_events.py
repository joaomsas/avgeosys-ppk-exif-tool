"""Tests for avgeosys/core/events.py"""

import pytest
from pathlib import Path
from avgeosys.core.events import read_mrk_events, validate_event_times

DATA_DIR = Path(__file__).parent / "data"


def test_read_mrk_events_count():
    """sample.MRK has 5 entries."""
    events = read_mrk_events(DATA_DIR / "sample.MRK")
    assert len(events) == 5


def test_read_mrk_events_first_entry():
    events = read_mrk_events(DATA_DIR / "sample.MRK")
    e = events[0]
    assert e.gps_week == 2286
    assert e.gps_seconds == pytest.approx(432100.0)
    assert e.filename == "DJI_0001_V.JPG"


def test_read_mrk_events_all_filenames():
    events = read_mrk_events(DATA_DIR / "sample.MRK")
    filenames = [e.filename for e in events]
    assert filenames == [
        "DJI_0001_V.JPG",
        "DJI_0002_V.JPG",
        "DJI_0003_V.JPG",
        "DJI_0004_V.JPG",
        "DJI_0005_V.JPG",
    ]


def test_validate_event_times_no_warnings_for_in_range():
    events = read_mrk_events(DATA_DIR / "sample.MRK")
    # pos range: 432080 to 432175 — first 4 events are in range
    in_range_events = events[:4]
    warnings = validate_event_times(in_range_events, pos_start=432080.0, pos_end=432175.0)
    assert warnings == []


def test_validate_event_times_detects_out_of_range():
    events = read_mrk_events(DATA_DIR / "sample.MRK")
    # All 5 events; event 5 (435000s) is outside 432080–432175
    warnings = validate_event_times(events, pos_start=432080.0, pos_end=432175.0)
    assert len(warnings) == 1
    assert "DJI_0005_V.JPG" in warnings[0]


def test_read_mrk_events_missing_file():
    with pytest.raises(FileNotFoundError):
        read_mrk_events(DATA_DIR / "nonexistent.MRK")
