"""Unit tests for the shared geospatial utilities."""

import numpy as np
import pytest

from src import config, spatial


def test_haversine_antipode_is_half_circumference():
    # Distance from a point to its antipode is pi * R.
    d = spatial.haversine_km(0.0, 0.0, 180.0, 0.0)
    assert d == pytest.approx(np.pi * config.LUNAR_RADIUS_KM, rel=1e-6)


def test_haversine_quarter_circle():
    d = spatial.haversine_km(0.0, 0.0, 0.0, 90.0)
    assert d == pytest.approx(np.pi * config.LUNAR_RADIUS_KM / 2.0, rel=1e-6)


def test_haversine_zero_distance():
    assert spatial.haversine_km(30.0, -12.0, 30.0, -12.0) == pytest.approx(0.0, abs=1e-9)


def test_antipode_wraps_and_flips():
    lon, lat = spatial.antipode(-18.0, 33.0)  # Imbrium
    assert lon == pytest.approx(162.0)
    assert lat == pytest.approx(-33.0)
    # Antipode longitude must stay in [-180, 180).
    lon2, _ = spatial.antipode(170.0, 0.0)
    assert -180.0 <= lon2 < 180.0


def test_wrap_lon_range():
    vals = spatial.wrap_lon(np.array([-190.0, 190.0, 0.0, 180.0, -180.0]))
    assert np.all(vals >= -180.0) and np.all(vals < 180.0)


def test_min_distance_to_points():
    lon = np.array([[0.0, 10.0]])
    lat = np.array([[0.0, 0.0]])
    d = spatial.min_distance_to_points_km(lon, lat, np.array([0.0]), np.array([0.0]))
    assert d[0, 0] == pytest.approx(0.0, abs=1e-6)
    assert d[0, 1] > 0.0


def test_spatial_block_ids_partition():
    # Two points 40 deg apart in longitude belong to different 30-deg blocks.
    lon = np.array([-170.0, -120.0])
    lat = np.array([0.0, 0.0])
    ids = spatial.spatial_block_ids(lon, lat, block_size_deg=30.0)
    assert ids[0] != ids[1]
    # Two nearby points share a block.
    ids2 = spatial.spatial_block_ids(np.array([-170.0, -169.0]), np.array([0.0, 1.0]), 30.0)
    assert ids2[0] == ids2[1]


def test_dog_bandpass_removes_constant():
    # A constant field has only DC; a band-pass must return ~zero everywhere.
    grid = np.full((60, 120), 7.3)
    bp = spatial.dog_bandpass(grid, res_km=30.0, low_cut_km=600.0, high_cut_km=40.0)
    assert np.allclose(bp, 0.0, atol=1e-6)


def test_longitudinal_rotation_preserves_values():
    grid = np.arange(12).reshape(3, 4).astype(float)
    rolled = spatial.longitudinal_rotation(grid, 1)
    # Rolling is a permutation of the columns -> same multiset of values per row.
    assert np.array_equal(np.sort(rolled, axis=1), np.sort(grid, axis=1))
    # A full-width roll is the identity.
    assert np.array_equal(spatial.longitudinal_rotation(grid, 4), grid)


def test_gaussian_smooth_preserves_mean_and_reduces_variance():
    rng = np.random.default_rng(0)
    grid = rng.standard_normal((80, 160))
    sm = spatial.gaussian_smooth(grid, sigma_pixels=3.0)
    assert sm.mean() == pytest.approx(grid.mean(), abs=0.05)
    assert sm.var() < grid.var()
