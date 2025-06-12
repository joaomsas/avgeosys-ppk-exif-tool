import pytest
from avgeosys.core.geoid import geoid_height, ellipsoid_to_orthometric


def test_geoid_height_zero_equator():
    assert pytest.approx(0.0) == geoid_height(0.0, 0.0)


def test_height_conversion_simple():
    # para lat=30, geoid_height ~= 10*sin(30deg)=5
    result = ellipsoid_to_orthometric(30.0, 0.0, 100.0)
    assert pytest.approx(95.0) == result
