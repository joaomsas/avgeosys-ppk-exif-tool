import pandas as pd
import pytest
from avgeosys.core.interpolator import interpolate_positions

def make_pos_df():
    # duas medições às 0 e 10 segundos
    return pd.DataFrame({
        "seconds": [0.0, 10.0],
        "lat":     [10.0, 20.0],
        "lon":     [30.0, 50.0],
        "height":  [100.0, 200.0],
        "quality": [1, 2],
    })

def make_mrk_df():
    # uma foto tirada aos 5 segundos
    return pd.DataFrame({
        "index": [1],
        "time":  [5.0],
        "lat":   [None],  # lat/lon originais não usadas aqui
        "lon":   [None],
        "height":[None],
    })

def test_interpolation_midpoint():
    pos_df = make_pos_df()
    mrk_df = make_mrk_df()
    result = interpolate_positions(pos_df, mrk_df)
    assert len(result) == 1

    point = result[0]
    # tempo 5 está no meio: lat=15, lon=40, height=150, quality ~ 1.5≈2
    assert pytest.approx(15.0) == point["lat"]
    assert pytest.approx(40.0) == point["lon"]
    assert pytest.approx(150.0) == point["height"]
    assert point["quality"] in (1, 2)

def test_interpolation_empty_inputs():
    empty = pd.DataFrame()
    assert interpolate_positions(empty, empty) == []
