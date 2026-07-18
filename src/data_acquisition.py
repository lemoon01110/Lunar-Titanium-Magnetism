"""
Synthetic lunar data generator (stand-in for the real PDS/USGS/JAXA grids).

The purpose of this module is NOT to fake a positive result. It builds a
*software validation harness*: global grids whose generative process is known.
It checks whether the surface-TiO2 proxy machinery responds to injected signals;
it does not validate power for an unspecified real-lunar effect or test the
Nichols et al. temporal mechanism. Which regime is produced is controlled by
``scenario``.

Design choices that fix defects in the original generator:

* Features are **spatially autocorrelated** (smoothed random fields), not i.i.d.
  white noise. Without spatial structure in the predictors, spatially-blocked
  cross-validation is indistinguishable from random CV and the project's central
  methodological claim would be untestable.
* Age is **three spatially-contiguous provinces** (Imbrian / Nectarian / Other),
  enabling the age-mask sensitivity analysis the proposal promises.
* The magnetic field is **calibrated to a realistic ~10% anomaly prevalence** at
  the 5 nT threshold, instead of the original ~92% (which made every score
  trivially high and inverted the class weighting).
* Predeclared major-basin centres are stored, and their **antipodes are computed**
  (lon+180, -lat) and written out, so the H2 hypothesis is genuinely encoded.
"""

from __future__ import annotations

import os
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin

from . import config
from .basins import MAJOR_BASINS
from . import spatial

# Preset generative weightings (surface-Ti proxy, antipode proxy, correlated noise).
SCENARIOS: Dict[str, Tuple[float, float, float]] = {
    "h1_lean": (1.10, 0.50, 0.80),   # Ti proxy dominant; antipode a competitor
    "mixed": (0.80, 0.80, 0.90),     # genuinely ambiguous
    "h2_lean": (0.35, 1.20, 0.80),   # antipode proxy dominant
    "null": (0.0, 0.0, 1.0),         # pure noise
}


def _res_km(grid_res_deg: float) -> float:
    """Approximate ground resolution (km) of one grid cell at the equator."""
    return grid_res_deg * (np.pi * config.LUNAR_RADIUS_KM / 180.0)


def _standardize(a: np.ndarray) -> np.ndarray:
    mu, sd = np.mean(a), np.std(a)
    return (a - mu) / sd if sd > 0 else a - mu


def _softplus(x: np.ndarray) -> np.ndarray:
    # Numerically stable softplus.
    return np.logaddexp(0.0, x)


def _calibrate_offset(z: np.ndarray, slope: float, threshold: float, prevalence: float) -> float:
    """Find offset b so that fraction(softplus(slope*z + b) >= threshold) ~= prevalence."""
    lo, hi = -50.0, 50.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        frac = float(np.mean(_softplus(slope * z + mid) >= threshold))
        if frac > prevalence:  # too many positives -> lower the field
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def generate_synthetic_data(
    data_dir: str = config.RAW_DIR,
    grid_res_deg: float = config.GRID_RES_DEG,
    scenario: str = "h1_lean",
    random_seed: int = config.RANDOM_SEED,
) -> None:
    """Generate the full set of synthetic global rasters + basin/antipode tables."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario!r}; choose from {list(SCENARIOS)}")
    os.makedirs(data_dir, exist_ok=True)
    rng = np.random.default_rng(random_seed)

    width = int(round(360.0 / grid_res_deg))
    height = int(round(180.0 / grid_res_deg))
    transform = from_origin(-180.0, 90.0, grid_res_deg, grid_res_deg)
    res_km = _res_km(grid_res_deg)

    # Pixel-centre coordinates (degrees).
    lons = -180.0 + grid_res_deg * (np.arange(width) + 0.5)
    lats = 90.0 - grid_res_deg * (np.arange(height) + 0.5)
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    def smooth_field(sigma_km: float) -> np.ndarray:
        raw = rng.standard_normal((height, width))
        return spatial.gaussian_smooth(raw, sigma_pixels=sigma_km / res_km)

    # ---- Surface TiO2 (wt%): spatially-clustered, right-skewed 0..~15 -------- #
    # Smoothing scales are kept modest so the target's autocorrelation range stays
    # below the CV block size (otherwise adjacent 30-deg blocks are correlated and
    # block CV leaks -- see Spatial_Diagnostics.block_exceeds_range).
    tio2_latent = _standardize(smooth_field(sigma_km=150.0))
    tio2 = np.clip(np.expm1(0.9 * tio2_latent + 0.4) , 0.0, None)
    tio2 = tio2 / tio2.max() * 15.0

    # ---- Bouguer gravity (mGal): basin-scale + mid-wavelength + noise ------- #
    gravity_broad = _standardize(smooth_field(sigma_km=900.0)) * 180.0   # mascon scale
    gravity_mid = _standardize(smooth_field(sigma_km=120.0)) * 70.0      # intrusions
    gravity = gravity_broad + gravity_mid + rng.standard_normal((height, width)) * 8.0

    # ---- Crustal thickness (km): broad, 5..70 ------------------------------- #
    thickness = _standardize(smooth_field(sigma_km=700.0))
    thickness = 35.0 + 15.0 * thickness
    thickness = np.clip(thickness, 5.0, 70.0)

    # ---- Age provinces: three spatially-contiguous classes ------------------ #
    age_latent = _standardize(smooth_field(sigma_km=180.0))
    # Thresholds chosen so roughly 25% Imbrian, 30% Nectarian, 45% Other.
    q_imbrian = np.quantile(age_latent, 0.75)
    q_nectarian = np.quantile(age_latent, 0.45)
    age = np.full((height, width), config.AGE_OTHER, dtype="float32")
    age[age_latent >= q_nectarian] = config.AGE_NECTARIAN
    age[age_latent >= q_imbrian] = config.AGE_IMBRIAN

    # ---- Basin / antipode tables -------------------------------------------- #
    basin_rows, antipode_rows = [], []
    for name, blon, blat, radius in MAJOR_BASINS:
        basin_rows.append({"name": name, "lon": blon, "lat": blat, "radius_km": radius})
        an_lon, an_lat = spatial.antipode(blon, blat)
        antipode_rows.append({"name": f"{name}_antipode", "lon": an_lon, "lat": an_lat})
    basins_df = pd.DataFrame(basin_rows)
    antipodes_df = pd.DataFrame(antipode_rows)
    basins_df.to_csv(os.path.join(data_dir, config.BASINS_CSV), index=False)
    antipodes_df.to_csv(os.path.join(data_dir, config.ANTIPODES_CSV), index=False)

    # ---- Ground-truth generative signal ------------------------------------- #
    # Injected Ti-proxy term: high-Ti flows coincident with stronger fields. This
    # is a synthetic COMPOSITIONAL signal (surface TiO2 in
    # Imbrian/Nectarian terrain) with NO subsurface-gravity dependence -- the deep
    # CMB driver is invisible to crustal gravity. Encoding it as Ti x gravity would
    # bake in the very non-sequitur we are guarding against. It must not be
    # described as the Nichols temporal mechanism (see Fallacy-Audit.md F1/F7).
    tio2_buf = spatial.gaussian_smooth(tio2, sigma_pixels=50.0 / res_km)
    activity = np.where(age == config.AGE_IMBRIAN, 1.0,
                        np.where(age == config.AGE_NECTARIAN, 0.25, 0.0))
    h1_term = _standardize(tio2_buf * activity)

    # H2 term: proximity to nearest major-basin antipode.
    antipode_dist = spatial.min_distance_to_points_km(
        lon_grid, lat_grid, antipodes_df["lon"].values, antipodes_df["lat"].values
    )
    h2_term = _standardize(np.exp(-antipode_dist / config.ANTIPODE_LENGTH_SCALE_KM))

    # Spatially-correlated nuisance signal + a little white noise.
    noise_term = _standardize(smooth_field(sigma_km=90.0)) + 0.3 * rng.standard_normal((height, width))

    wa, wb, wn = SCENARIOS[scenario]
    z = _standardize(wa * h1_term + wb * h2_term + wn * _standardize(noise_term))

    # Map latent -> positive nT field, calibrated to the target prevalence.
    slope = 1.5
    offset = _calibrate_offset(z, slope, config.PRIMARY_THRESHOLD_NT, config.TARGET_PREVALENCE)
    mag = _softplus(slope * z + offset).astype("float32")

    # ---- Write rasters ------------------------------------------------------ #
    layers = {
        config.RAW_FILES["magnetic"]: mag,
        config.RAW_FILES["tio2"]: tio2.astype("float32"),
        config.RAW_FILES["gravity"]: gravity.astype("float32"),
        config.RAW_FILES["age"]: age.astype("float32"),
        config.RAW_FILES["thickness"]: thickness.astype("float32"),
        # Synthetic TiO2 has no mare-only calibration boundary.  An explicit
        # all-valid mask keeps the same fail-closed schema without pretending the
        # synthetic geologic provinces are observed mare units.
        config.TERRAIN_VALIDITY_FILE: np.ones_like(tio2, dtype="float32"),
    }
    for fname, arr in layers.items():
        _write_raster(os.path.join(data_dir, fname), arr, transform)

    prevalence = float(np.mean(mag >= config.PRIMARY_THRESHOLD_NT))
    print(
        f"Synthetic data ({scenario}) written to {data_dir} | "
        f"grid {width}x{height} | global 5nT prevalence {prevalence:.1%}"
    )


def _write_raster(filepath: str, data: np.ndarray, transform) -> None:
    with rasterio.open(
        filepath,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype="float32",
        crs=config.LUNAR_GEO_CRS,
        transform=transform,
        nodata=config.NODATA,
        compress="deflate",
    ) as dst:
        dst.write(data.astype("float32"), 1)


if __name__ == "__main__":
    generate_synthetic_data()
