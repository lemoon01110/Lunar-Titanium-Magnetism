"""
Shared geospatial utilities.

These functions are deliberately small, pure, and unit-tested (see
``tests/test_spatial.py``). Every distance is a real great-circle distance on a
sphere of lunar radius; every coordinate transform goes through pyproj with the
lunar CRSs defined in :mod:`src.config`. The original pipeline faked all of this
(distance-from-map-centre masquerading as distance-to-antipode), which is the
single most important bug this module fixes.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
from pyproj import Transformer
from scipy.ndimage import gaussian_filter

from . import config


# --------------------------------------------------------------------------- #
# Great-circle geometry
# --------------------------------------------------------------------------- #
def haversine_km(
    lon1: np.ndarray,
    lat1: np.ndarray,
    lon2: np.ndarray,
    lat2: np.ndarray,
    radius_km: float = config.LUNAR_RADIUS_KM,
) -> np.ndarray:
    """Great-circle distance (km) between two points/arrays given in degrees."""
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    a = np.clip(a, 0.0, 1.0)  # guard against tiny FP excursions > 1
    return radius_km * 2.0 * np.arcsin(np.sqrt(a))


def antipode(lon: float, lat: float) -> Tuple[float, float]:
    """Return the antipodal (lon, lat) in degrees, longitude wrapped to [-180, 180]."""
    an_lon = wrap_lon(lon + 180.0)
    an_lat = -lat
    return an_lon, an_lat


def wrap_lon(lon: np.ndarray) -> np.ndarray:
    """Wrap longitude(s) to the half-open interval [-180, 180)."""
    return (np.asarray(lon) + 180.0) % 360.0 - 180.0


def min_distance_to_points_km(
    lon_grid: np.ndarray,
    lat_grid: np.ndarray,
    target_lons: np.ndarray,
    target_lats: np.ndarray,
) -> np.ndarray:
    """Minimum great-circle distance (km) from every grid cell to any target point.

    ``lon_grid``/``lat_grid`` are 2-D arrays of pixel-centre coordinates (deg).
    Returns an array the same shape as the grid.
    """
    out = np.full(lon_grid.shape, np.inf, dtype="float64")
    for tlon, tlat in zip(np.atleast_1d(target_lons), np.atleast_1d(target_lats)):
        d = haversine_km(lon_grid, lat_grid, tlon, tlat)
        np.minimum(out, d, out=out)
    return out


# --------------------------------------------------------------------------- #
# Pixel <-> geographic coordinate inversion
# --------------------------------------------------------------------------- #
def pixel_lonlat_grids(
    transform, width: int, height: int, src_crs: str
) -> Tuple[np.ndarray, np.ndarray]:
    """Return (lon, lat) 2-D grids of pixel *centres* for a projected raster.

    ``transform`` is the raster's affine transform (projected, e.g. lunar CEA).
    We compute projected pixel-centre coordinates then inverse-project them to
    lunar geographic degrees. This is the correct way to recover latitude/
    longitude after an equal-area reprojection.
    """
    rows, cols = np.mgrid[0:height, 0:width]
    # Affine maps (col+0.5, row+0.5) -> projected (x, y) at pixel centres.
    x = transform.c + transform.a * (cols + 0.5) + transform.b * (rows + 0.5)
    y = transform.f + transform.d * (cols + 0.5) + transform.e * (rows + 0.5)

    to_geo = Transformer.from_crs(src_crs, config.LUNAR_GEO_CRS, always_xy=True)
    lon, lat = to_geo.transform(x, y)
    return np.asarray(lon), np.asarray(lat)


# --------------------------------------------------------------------------- #
# Spatially-blocked cross-validation groups
# --------------------------------------------------------------------------- #
def spatial_block_ids(
    lon: np.ndarray, lat: np.ndarray, block_size_deg: float = config.SPATIAL_BLOCK_SIZE_DEG
) -> np.ndarray:
    """Assign each (lon, lat) to a contiguous block_size x block_size degree tile.

    Neighbouring pixels are nearly identical in geospatial data, so random
    k-fold leaks information between train and test. Holding out whole blocks
    (via GroupKFold on these ids) is the correct, leakage-free scheme.
    """
    lon = wrap_lon(lon)
    col = np.floor((lon + 180.0) / block_size_deg).astype(int)
    row = np.floor((lat + 90.0) / block_size_deg).astype(int)
    # Encode the 2-D tile index into a single integer id.
    n_cols = int(np.ceil(360.0 / block_size_deg))
    return row * n_cols + col


# --------------------------------------------------------------------------- #
# Spatial permutation (rotation) of a global grid
# --------------------------------------------------------------------------- #
def gaussian_smooth(
    grid: np.ndarray, sigma_pixels: float, wrap_lon_axis: bool = True
) -> np.ndarray:
    """Isotropic Gaussian smoothing of a global grid.

    Longitude wraps around the sphere, so we use ``mode='wrap'`` on the column
    axis and ``mode='reflect'`` on the row (latitude) axis to avoid seam and
    edge artefacts. ``sigma_pixels <= 0`` is a no-op.
    """
    if sigma_pixels <= 0:
        return grid.astype("float64", copy=True)
    if wrap_lon_axis:
        # gaussian_filter takes one mode; emulate per-axis by filtering axes
        # separately (row: reflect, col: wrap).
        out = gaussian_filter(grid.astype("float64"), sigma=(sigma_pixels, 0), mode="reflect")
        out = gaussian_filter(out, sigma=(0, sigma_pixels), mode="wrap")
        return out
    return gaussian_filter(grid.astype("float64"), sigma=sigma_pixels, mode="reflect")


def dog_bandpass(
    grid: np.ndarray, res_km: float, low_cut_km: float, high_cut_km: float
) -> np.ndarray:
    """Difference-of-Gaussians band-pass on a grid (proxy for a spherical-harmonic
    band-pass).

    Keeps spatial structure with wavelengths between ``high_cut_km`` (removes
    finer / pixel-scale noise) and ``low_cut_km`` (removes broader basin-scale
    mascons). Implemented as ``lowpass(high_cut) - lowpass(low_cut)``.
    """
    sigma_high = max(high_cut_km / res_km, 0.0)
    sigma_low = max(low_cut_km / res_km, 0.0)
    keep_fine = gaussian_smooth(grid, sigma_high)   # structure larger than high_cut
    keep_broad = gaussian_smooth(grid, sigma_low)   # structure larger than low_cut
    return keep_fine - keep_broad


def longitudinal_rotation(grid: np.ndarray, shift_pixels: int) -> np.ndarray:
    """Roll a 2-D global grid along the longitude axis by ``shift_pixels``.

    A longitudinal roll produces a spatially-plausible null: it fully decouples
    the target from the fixed predictors while *preserving* the target's own
    spatial autocorrelation structure. A naive element-wise shuffle (what the
    original code did) destroys autocorrelation and yields a falsely optimistic
    p-value -- exactly the mistake the proposal warns against.
    """
    return np.roll(grid, shift=int(shift_pixels), axis=1)
