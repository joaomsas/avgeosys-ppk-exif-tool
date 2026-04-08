"""Tests for avgeosys/core/interpolator.py"""

import pytest
from pathlib import Path
from avgeosys.core.interpolator import (
    preprocess_and_read_mrk,
    load_pos_data,
    interpolate_positions,
)

DATA_DIR = Path(__file__).parent / "data"


def test_load_pos_data_row_count():
    df = load_pos_data(DATA_DIR / "sample.pos")
    assert len(df) == 20


def test_load_pos_data_columns():
    df = load_pos_data(DATA_DIR / "sample.pos")
    for col in ("gps_seconds", "latitude", "longitude", "height", "quality"):
        assert col in df.columns, f"Missing column: {col}"


def test_load_pos_data_dtypes():
    df = load_pos_data(DATA_DIR / "sample.pos")
    assert df["gps_seconds"].dtype.kind == "f"
    assert df["latitude"].dtype.kind == "f"
    assert df["longitude"].dtype.kind == "f"
    assert df["height"].dtype.kind == "f"
    assert df["quality"].dtype.kind in ("i", "u", "f")


def test_load_pos_data_first_epoch():
    """First epoch: 2023/11/03 00:01:20.000 GPST → GPS seconds-of-week.
    2023-11-03 is a Friday (weekday 4, 0=Mon in Python, but GPS week day:
    GPS week starts Sunday=0. Friday = day 5.
    GPS seconds = 5*86400 + 0*3600 + 1*60 + 20 = 432000 + 80 = 432080.
    """
    df = load_pos_data(DATA_DIR / "sample.pos")
    assert df["gps_seconds"].iloc[0] == pytest.approx(432080.0, abs=0.001)


def test_gps_time_conversion_known_value():
    """Known value: 2023/11/03 00:01:20.000 → 432080.000 GPS seconds-of-week."""
    df = load_pos_data(DATA_DIR / "sample.pos")
    assert df["gps_seconds"].iloc[0] == pytest.approx(432080.0, abs=0.001)


def test_preprocess_and_read_mrk_count():
    df = preprocess_and_read_mrk(DATA_DIR / "sample.MRK")
    assert len(df) == 5


def test_preprocess_and_read_mrk_gps_seconds():
    df = preprocess_and_read_mrk(DATA_DIR / "sample.MRK")
    assert df["gps_seconds"].iloc[0] == pytest.approx(432100.0)


def test_interpolate_positions_count():
    mrk_df = preprocess_and_read_mrk(DATA_DIR / "sample.MRK")
    pos_df = load_pos_data(DATA_DIR / "sample.pos")
    results = interpolate_positions(mrk_df, pos_df)
    assert len(results) == 5


def test_interpolate_positions_correct_lat():
    """At 432100s, pos spans 432080–432175 at 5s intervals.
    epoch index at 432100: (432100 - 432080) / 5 = 4.0 → epoch[4]
    lat[0] = -15.779800, each step = +0.000050 → lat[4] = -15.779600
    """
    mrk_df = preprocess_and_read_mrk(DATA_DIR / "sample.MRK")
    pos_df = load_pos_data(DATA_DIR / "sample.pos")
    results = interpolate_positions(mrk_df, pos_df)
    first = results[0]
    assert first["latitude"] == pytest.approx(-15.7796, abs=1e-4)


def test_interpolate_positions_filenames():
    mrk_df = preprocess_and_read_mrk(DATA_DIR / "sample.MRK")
    pos_df = load_pos_data(DATA_DIR / "sample.pos")
    results = interpolate_positions(mrk_df, pos_df)
    assert results[0]["filename"] == "DJI_0001_V.JPG"


def test_interpolate_positions_out_of_range_quality():
    """Event at 435000s is outside pos range → quality = 3."""
    mrk_df = preprocess_and_read_mrk(DATA_DIR / "sample.MRK")
    pos_df = load_pos_data(DATA_DIR / "sample.pos")
    results = interpolate_positions(mrk_df, pos_df)
    out_of_range = next(r for r in results if r["filename"] == "DJI_0005_V.JPG")
    assert out_of_range["quality"] == 3
