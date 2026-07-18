"""Tests for the real-data ingestion path (src/ingest.py)."""

import os

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import Affine
from rasterio.warp import Resampling

from src import config, ingest
from src.data_acquisition import generate_synthetic_data

RES = 4.0  # coarse for speed


@pytest.fixture
def canonical_raw(tmp_path):
    """Fresh, coarse canonical dataset for isolated validator mutations."""
    raw = os.path.join(tmp_path, "raw")
    os.makedirs(raw)
    generate_synthetic_data(raw, grid_res_deg=RES, scenario="h1_lean", random_seed=3)
    return raw


def test_map_unit_to_age():
    assert ingest._map_unit_to_age("Im") == config.AGE_IMBRIAN     # Imbrian
    assert ingest._map_unit_to_age("Nc") == config.AGE_NECTARIAN   # Nectarian
    assert ingest._map_unit_to_age("EIp") == config.AGE_OTHER      # pre-Nectarian etc.
    assert ingest._map_unit_to_age(None) == config.AGE_OTHER
    assert ingest._map_unit_to_age("") == config.AGE_OTHER


def test_mare_unit_symbols_are_explicit_and_narrow():
    assert set(config.MARE_UNIT_SYMBOLS) == {"Em", "Im1", "Im2", "Imd"}
    assert "Ip" not in config.MARE_UNIT_SYMBOLS  # ambiguous plains, not mapped mare


def test_canonical_write_maps_nan_to_nodata(tmp_path):
    """The magnetic bug fix: out-of-coverage cells must become NODATA, never 0.0."""
    arr = np.ones((int(180 / RES), int(360 / RES)), dtype="float32")
    arr[0, 0] = np.nan
    path = os.path.join(tmp_path, "canon.tif")
    ingest.write_canonical_raster(path, arr, RES)
    with rasterio.open(path) as src:
        assert src.nodata == config.NODATA
        assert "1737400" in src.crs.to_proj4()  # lunar radius, not Earth
        back = src.read(1)
    assert back[0, 0] == config.NODATA and back[1, 1] == 1.0


def test_regrid_roundtrip(tmp_path):
    arr = np.random.default_rng(0).random((int(180 / RES), int(360 / RES))).astype("float32")
    path = os.path.join(tmp_path, "rt.tif")
    ingest.write_canonical_raster(path, arr, RES)
    back = ingest.regrid_to_canonical(path, Resampling.nearest, RES)
    assert back.shape == arr.shape and np.isfinite(back).all()


def test_validate_raises_on_empty_dir(tmp_path):
    with pytest.raises(ValueError):
        ingest.validate_raw_grids(str(tmp_path), RES)


def test_validate_passes_on_canonical_synthetic(tmp_path):
    """The synthetic generator writes the exact canonical schema, so the real-data
    schema validator accepts it while provenance remains a separate real-mode gate."""
    raw = os.path.join(tmp_path, "raw")
    os.makedirs(raw)
    generate_synthetic_data(raw, grid_res_deg=RES, scenario="h1_lean", random_seed=3)
    report = ingest.validate_raw_grids(raw, RES)
    assert report["_ok"]
    for key in config.RAW_FILES:
        assert report[key]["crs_is_lunar"] and report[key]["valid_fraction"] > 0.9
    terrain = report["tio2_terrain_validity"]
    assert terrain["valid_fraction"] == 1.0
    assert "mare_fraction" not in terrain
    assert "USGS" not in terrain["scope"]


def test_validate_requires_terrain_mask_even_without_real_provenance(canonical_raw):
    os.remove(os.path.join(canonical_raw, config.TERRAIN_VALIDITY_FILE))
    with pytest.raises(ValueError, match=f"{config.TERRAIN_VALIDITY_FILE} missing"):
        ingest.validate_raw_grids(
            canonical_raw, RES, require_real_provenance=False,
        )


def test_canonical_grid_rejects_resolution_that_does_not_divide_globe():
    with pytest.raises(ValueError, match="must divide both 360 and 180 exactly"):
        ingest.canonical_grid(7.0)


def test_validate_rejects_earth_crs(canonical_raw):
    path = os.path.join(canonical_raw, config.RAW_FILES["magnetic"])
    with rasterio.open(path, "r+") as dst:
        dst.crs = "EPSG:4326"

    with pytest.raises(ValueError, match="CRS is not lunar geographic"):
        ingest.validate_raw_grids(canonical_raw, RES)


def test_validate_rejects_shifted_transform(canonical_raw):
    path = os.path.join(canonical_raw, config.RAW_FILES["tio2"])
    with rasterio.open(path, "r+") as dst:
        original = dst.transform
        dst.transform = Affine(
            original.a,
            original.b,
            original.c + RES / 2,
            original.d,
            original.e,
            original.f,
        )

    with pytest.raises(ValueError, match=r"bounds .* are not global"):
        ingest.validate_raw_grids(canonical_raw, RES)


def test_validate_rejects_malformed_basin_schema(canonical_raw):
    path = os.path.join(canonical_raw, config.BASINS_CSV)
    basins = pd.read_csv(path).drop(columns="radius_km")
    basins.to_csv(path, index=False)

    with pytest.raises(ValueError, match=r"basins\.csv missing columns \['radius_km'\]"):
        ingest.validate_raw_grids(canonical_raw, RES)


def test_validate_rejects_mathematically_wrong_antipode(canonical_raw):
    path = os.path.join(canonical_raw, config.ANTIPODES_CSV)
    antipodes = pd.read_csv(path)
    antipodes.loc[0, "lon"] += 1.0
    antipodes.to_csv(path, index=False)

    with pytest.raises(ValueError, match="is not the mathematical antipode"):
        ingest.validate_raw_grids(canonical_raw, RES)
