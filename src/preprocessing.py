"""
Preprocessing: build the analysis-ready tabular dataset from the raw grids.

This module fixes the most serious defect in the original pipeline: the
``dist_to_antipode`` feature was never actually computed from the antipodes --
it was distance from the *map centre*, and ``antipodes.csv`` was loaded but
ignored. Here every geographic feature is a real great-circle distance on the
lunar sphere, computed after a proper equal-area reprojection.

Pipeline:
  1. Reproject every raw grid to a lunar cylindrical-equal-area CRS
     (continuous fields: average resampling; categorical age: nearest).
  2. Recover real lon/lat per pixel by inverse-projecting pixel centres.
  3. Engineer features:
       - band-passed gravity (mid-wavelength density proxy)
       - buffered TiO2 x positive band-passed gravity interaction at 25/50/100 km
       - great-circle distance to nearest basin antipode (H2)
       - great-circle distance to nearest basin rim (control)
       - |latitude| and crustal thickness (controls)
       - an externally sourced USGS mare-proxy flag; terrain-sensitive analysis
         uses raw row-local TiO2 because the legacy buffers cross mask boundaries
  4. Emit binary targets at every threshold + a continuous regression target,
     the age class, and spatially-blocked CV group ids -- for ALL valid pixels,
     so downstream age-mask sensitivity runs need no re-preprocessing.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from scipy.signal import fftconvolve

from . import config
from . import spatial


def reproject_raster(src_path: str, dst_path: str, resampling: Resampling) -> None:
    """Reproject a raster to the lunar CEA CRS, preserving nodata."""
    with rasterio.open(src_path) as src:
        dst_transform, width, height = calculate_default_transform(
            src.crs, config.LUNAR_CEA_CRS, src.width, src.height, *src.bounds
        )
        meta = src.meta.copy()
        meta.update(
            crs=config.LUNAR_CEA_CRS,
            transform=dst_transform,
            width=width,
            height=height,
            nodata=config.NODATA,
        )
        with rasterio.open(dst_path, "w", **meta) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=src.nodata,
                dst_transform=dst_transform,
                dst_crs=config.LUNAR_CEA_CRS,
                dst_nodata=config.NODATA,
                resampling=resampling,
            )


def _read(path: str) -> Tuple[np.ndarray, float]:
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float64")
        nodata = src.nodata
    if nodata is not None:
        arr = np.where(arr == nodata, np.nan, arr)
    return arr, nodata


def _circular_kernel(radius_px: float) -> np.ndarray:
    r = int(np.ceil(radius_px))
    if r < 1:
        return np.ones((1, 1))
    y, x = np.ogrid[-r : r + 1, -r : r + 1]
    return (x * x + y * y <= radius_px * radius_px).astype("float64")


def circular_buffer_mean(field: np.ndarray, valid: np.ndarray, radius_px: float) -> np.ndarray:
    """Neighbourhood mean within a circular kernel of ``radius_px``, ignoring
    invalid pixels (true nodata-aware convolution)."""
    kernel = _circular_kernel(radius_px)
    filled = np.where(valid, field, 0.0)
    num = fftconvolve(filled, kernel, mode="same")
    den = fftconvolve(valid.astype("float64"), kernel, mode="same")
    out = np.divide(num, den, out=np.zeros_like(num), where=den > 0)
    return out


def preprocess_data(
    raw_dir: str = config.RAW_DIR,
    processed_dir: str = config.PROCESSED_DIR,
    grid_res_deg: float = config.GRID_RES_DEG,
) -> str:
    """Run preprocessing and return the path to the tabular dataset."""
    os.makedirs(processed_dir, exist_ok=True)

    # 1. Reproject to lunar equal-area (categorical age uses nearest).
    resampling_by_key = {
        "magnetic": Resampling.average,
        "tio2": Resampling.average,
        "gravity": Resampling.average,
        "thickness": Resampling.average,
        "age": Resampling.nearest,
    }
    cea_paths: Dict[str, str] = {}
    for key, fname in config.RAW_FILES.items():
        out_path = os.path.join(processed_dir, "cea_" + fname)
        reproject_raster(os.path.join(raw_dir, fname), out_path, resampling_by_key[key])
        cea_paths[key] = out_path
    terrain_source = os.path.join(raw_dir, config.TERRAIN_VALIDITY_FILE)
    if not os.path.isfile(terrain_source):
        raise ValueError(
            f"{config.TERRAIN_VALIDITY_FILE} is required by the canonical "
            "terrain/domain schema; regenerate synthetic inputs or rerun "
            "`python -m src.ingest all` for real data"
        )
    terrain_out = os.path.join(processed_dir, "cea_" + config.TERRAIN_VALIDITY_FILE)
    reproject_raster(terrain_source, terrain_out, Resampling.nearest)
    cea_paths["terrain"] = terrain_out
    print("Reprojection to lunar CEA complete.")

    # 2. Read layers + geometry.
    mag, _ = _read(cea_paths["magnetic"])
    tio2, _ = _read(cea_paths["tio2"])
    gravity, _ = _read(cea_paths["gravity"])
    thickness, _ = _read(cea_paths["thickness"])
    age, _ = _read(cea_paths["age"])
    terrain, _ = _read(cea_paths["terrain"])

    with rasterio.open(cea_paths["magnetic"]) as src:
        transform, width, height = src.transform, src.width, src.height
    res_km = abs(transform.a) / 1000.0

    lon_grid, lat_grid = spatial.pixel_lonlat_grids(
        transform, width, height, config.LUNAR_CEA_CRS
    )

    # Validity: a pixel is usable only where every layer is present.
    valid = np.isfinite(mag) & np.isfinite(tio2) & np.isfinite(gravity) & \
        np.isfinite(thickness) & np.isfinite(age) & np.isfinite(terrain)
    terrain_finite = terrain[np.isfinite(terrain)]
    terrain_values = np.unique(terrain_finite)
    if not np.isin(terrain_values, (0.0, 1.0)).all():
        raise ValueError(
            f"{config.TERRAIN_VALIDITY_FILE} contains non-binary values "
            f"{terrain_values.tolist()}"
        )
    terrain_binary = np.where(np.isfinite(terrain), terrain, 0.0).astype("int8")
    tio2_terrain_valid = valid & (terrain_binary == 1)

    # Snap age to nearest integer class (nearest-resampling can leave floats).
    age_class = np.where(valid, np.rint(age), np.nan)

    # 3a. Band-pass gravity (fill nodata with valid mean so the filter is stable).
    grav_filled = np.where(valid, gravity, np.nanmean(gravity[valid]))
    gravity_bp = spatial.dog_bandpass(
        grav_filled, res_km, config.GRAVITY_BANDPASS_LOW_KM, config.GRAVITY_BANDPASS_HIGH_KM
    )

    # 3b. Buffered features.
    #  - tio2_{r}km  : legacy surface-TiO2 proxy, spread over a neighbourhood.
    #  - interaction_{r}km : EXPLORATORY only -- buffered TiO2 x positive
    #    band-passed gravity. This is NOT the Nichols mechanism (F1); retained to
    #    test whether the invented "subsurface density" term adds anything.
    print("Building legacy TiO2 buffers + exploratory interactions...")
    tio2_buffer_cols: Dict[str, np.ndarray] = {}
    interaction_cols: Dict[str, np.ndarray] = {}
    grav_pos = np.clip(gravity_bp, 0.0, None)
    for radius_km, tcol, icol in zip(
        config.BUFFER_RADII_KM, config.TIO2_BUFFER_FEATURES, config.INTERACTION_FEATURES
    ):
        radius_px = radius_km / res_km
        tio2_buf = circular_buffer_mean(tio2, valid, radius_px)
        grav_buf = circular_buffer_mean(grav_pos, valid, radius_px)
        tio2_buffer_cols[tcol] = tio2_buf
        interaction_cols[icol] = tio2_buf * grav_buf

    # 3c. Real great-circle distances (the fix).
    print("Computing great-circle distances to antipodes and basin rims...")
    antipodes = pd.read_csv(os.path.join(raw_dir, config.ANTIPODES_CSV))
    basins = pd.read_csv(os.path.join(raw_dir, config.BASINS_CSV))

    dist_to_antipode = spatial.min_distance_to_points_km(
        lon_grid, lat_grid, antipodes["lon"].values, antipodes["lat"].values
    )
    dist_to_basin_rim = _min_distance_to_rims(lon_grid, lat_grid, basins)
    abs_latitude = np.abs(lat_grid)
    # Nearside-ness (sub-Earth-point proximity): +1 at (0,0), -1 at the farside
    # centre, 0 at the limb. Controls the Procellarum/nearside confound (F8): high
    # Ti, thin crust, big basins and strong anomalies all cluster on the nearside.
    nearside = np.cos(np.radians(lat_grid)) * np.cos(np.radians(lon_grid))

    # 4. Tabulate ALL valid pixels (age filtering happens downstream).
    block_ids = spatial.spatial_block_ids(lon_grid, lat_grid, config.SPATIAL_BLOCK_SIZE_DEG)
    # Retain grid indices so the spatial-rotation permutation test can rebuild
    # and roll the target on the full grid.
    row_idx = np.repeat(np.arange(height), width).reshape(height, width)
    col_idx = np.tile(np.arange(width), height).reshape(height, width)

    columns = {
        "row_idx": row_idx,
        "col_idx": col_idx,
        "lon": lon_grid,
        "lat": lat_grid,
        "abs_latitude": abs_latitude,
        "mag_anomaly": mag,
        "tio2": tio2,
        "gravity": gravity,
        "gravity_bandpass": gravity_bp,
        "crustal_thickness": thickness,
        "dist_to_antipode_km": dist_to_antipode,
        "dist_to_basin_rim_km": dist_to_basin_rim,
        "nearside": nearside,
        "age_class": age_class,
        "tio2_terrain_valid": tio2_terrain_valid.astype("int8"),
        "spatial_block": block_ids,
        **tio2_buffer_cols,
        **interaction_cols,
    }
    df = pd.DataFrame({k: np.asarray(v).ravel() for k, v in columns.items()})
    df = df[valid.ravel()].copy()
    df = df.dropna().reset_index(drop=True)

    # Targets.
    for thr in config.BINARY_THRESHOLDS_NT:
        df[f"mag_binary_{int(thr)}nT"] = (df["mag_anomaly"] >= thr).astype(int)

    out_csv = os.path.join(processed_dir, "modeling_dataset.csv")
    df.to_csv(out_csv, index=False)

    # Grid metadata for the spatial-rotation permutation test.
    with open(os.path.join(processed_dir, "grid_meta.json"), "w") as fh:
        json.dump({"width": int(width), "height": int(height), "res_km": float(res_km)}, fh)

    prev5 = df[f"mag_binary_{int(config.PRIMARY_THRESHOLD_NT)}nT"].mean()
    imbrian_frac = float(np.mean(df["age_class"] == config.AGE_IMBRIAN))
    print(
        f"Preprocessing complete: {len(df):,} valid pixels, "
        f"{imbrian_frac:.0%} Imbrian, {prev5:.1%} anomalous at "
        f"{config.PRIMARY_THRESHOLD_NT:.0f} nT. Saved -> {out_csv}"
    )
    return out_csv


def _min_distance_to_rims(lon_grid: np.ndarray, lat_grid: np.ndarray, basins: pd.DataFrame) -> np.ndarray:
    """Min distance (km) from each pixel to the nearest basin *rim* (a circle of
    given radius around the basin centre)."""
    out = np.full(lon_grid.shape, np.inf)
    for _, b in basins.iterrows():
        d_centre = spatial.haversine_km(lon_grid, lat_grid, b["lon"], b["lat"])
        d_rim = np.abs(d_centre - b["radius_km"])
        np.minimum(out, d_rim, out=out)
    return out


if __name__ == "__main__":
    preprocess_data()
