"""Product-aware real-data ingestion into the canonical lunar grid.

Native institutional downloads live below ``data/raw/sources`` and are never
treated as model inputs directly.  ``python -m src.ingest all`` converts every
required product into a temporary staging directory, validates the complete
aligned dataset, writes input/output provenance, and only then promotes the five
canonical science rasters, the USGS-derived mare-validity mask, and two basin
tables into ``data/raw``.

Canonical contract
------------------
* lunar geographic CRS: ``+proj=longlat +R=1737400``;
* global plate-carree grid: ``from_origin(-180, 90, res, res)``;
* one float32 band with nodata ``-9999``;
* age values exactly ``{0: Other, 1: Nectarian, 2: Imbrian}``.

The converters are deliberately specific to the pinned products in
``src.acquire``.  Guessing an arbitrary first raster, NetCDF variable or
shapefile is not scientifically reproducible and therefore fails closed.
"""

from __future__ import annotations

import glob
import hashlib
import json
import math
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import rasterio
from pyproj import CRS
from rasterio.features import rasterize
from rasterio.transform import Affine, from_origin
from rasterio.warp import Resampling, reproject
from scipy.interpolate import RegularGridInterpolator

from . import config, spatial
from .basins import CATALOG_METADATA, MAJOR_BASINS


SOURCES_DIR = os.path.join(config.RAW_DIR, "sources")
SOURCE_MANIFEST = os.path.join(SOURCES_DIR, "source_manifest.json")
REAL_DATA_MANIFEST = getattr(config, "REAL_DATA_MANIFEST", "real_data_manifest.json")

VALUE_RANGES: Dict[str, Tuple[float, float]] = {
    "magnetic": (0.0, 3000.0),       # nT, total surface-field magnitude
    "tio2": (0.0, 15.0),             # wt%; official product warns >15 is unreliable
    "gravity": (-2000.0, 2000.0),    # mGal
    "thickness": (0.0, 120.0),       # km
    "age": (0.0, 2.0),               # categorical
}
MIN_VALID_FRACTION: Dict[str, float] = {
    "magnetic": 0.95,
    "tio2": 0.50,       # LROC product is intentionally limited to 70 S--70 N
    "gravity": 0.99,
    "thickness": 0.99,
    "age": 0.95,
}
MIN_COMMON_VALID_FRACTION = 0.45


# --------------------------------------------------------------------------- #
# Canonical grid and generic raster helpers
# --------------------------------------------------------------------------- #
def canonical_grid(res_deg: float = config.GRID_RES_DEG) -> Tuple[Affine, int, int]:
    if not np.isfinite(res_deg) or res_deg <= 0:
        raise ValueError(f"grid resolution must be positive and finite, got {res_deg!r}")
    width_float, height_float = 360.0 / res_deg, 180.0 / res_deg
    if not math.isclose(width_float, round(width_float), abs_tol=1e-9) or not math.isclose(
        height_float, round(height_float), abs_tol=1e-9
    ):
        raise ValueError(f"grid resolution {res_deg} must divide both 360 and 180 exactly")
    width, height = int(round(width_float)), int(round(height_float))
    return from_origin(-180.0, 90.0, res_deg, res_deg), width, height


def write_canonical_raster(
    path: str, arr: np.ndarray, res_deg: float = config.GRID_RES_DEG,
) -> None:
    transform, width, height = canonical_grid(res_deg)
    if arr.shape != (height, width):
        raise ValueError(f"{path}: array shape {arr.shape} != canonical {(height, width)}")
    out = np.where(np.isfinite(arr), arr, config.NODATA).astype("float32")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with rasterio.open(
        path, "w", driver="GTiff", height=height, width=width, count=1,
        dtype="float32", crs=config.LUNAR_GEO_CRS, transform=transform,
        nodata=config.NODATA, compress="deflate", predictor=3,
    ) as dst:
        dst.write(out, 1)


def _reproject_array(
    source: np.ndarray,
    src_transform: Affine,
    src_crs: Any,
    resampling: Resampling,
    res_deg: float,
) -> np.ndarray:
    dst_transform, width, height = canonical_grid(res_deg)
    destination = np.full((height, width), np.nan, dtype="float32")
    reproject(
        source=np.asarray(source, dtype="float32"),
        destination=destination,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=config.LUNAR_GEO_CRS,
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=resampling,
    )
    return destination


def _looks_geographic(bounds: rasterio.coords.BoundingBox) -> bool:
    return (
        -361.0 <= bounds.left <= 361.0
        and -361.0 <= bounds.right <= 361.0
        and -91.0 <= bounds.bottom <= 91.0
        and -91.0 <= bounds.top <= 91.0
    )


def regrid_to_canonical(
    src_path: str,
    resampling: Resampling,
    res_deg: float = config.GRID_RES_DEG,
    src_crs_override: Optional[str] = None,
) -> np.ndarray:
    """Reproject raster band 1 while genuinely honoring a lunar CRS override."""
    with rasterio.open(src_path) as src:
        source = src.read(1, masked=True).filled(np.nan).astype("float32")
        transform = src.transform
        source_crs = src_crs_override or src.crs or config.LUNAR_GEO_CRS
        bounds = src.bounds

        # Several planetary GeoTIFFs are distributed on 0..360 longitudes.  A
        # half-width roll makes the seam explicit before PROJ sees the raster.
        if _looks_geographic(bounds) and bounds.left >= -1e-6 and bounds.right > 180.0:
            half = src.width // 2
            if src.width % 2:
                raise ValueError(f"{src_path}: cannot rotate odd-width 0..360 raster")
            source = np.roll(source, -half, axis=1)
            transform = from_origin(
                -180.0, bounds.top, abs(src.transform.a), abs(src.transform.e)
            )
            source_crs = config.LUNAR_GEO_CRS
        elif _looks_geographic(bounds) and src_crs_override is None:
            # A WGS84 tag on angular lunar data is metadata, not permission to
            # perform an Earth-to-Moon transform.
            source_crs = config.LUNAR_GEO_CRS

    return _reproject_array(source, transform, source_crs, resampling, res_deg)


def _source_path(*parts: str) -> str:
    return os.path.join(SOURCES_DIR, *parts)


def _out(key: str, output_dir: str) -> str:
    return os.path.join(output_dir, config.RAW_FILES[key])


def _find_recursive(*patterns: str) -> Optional[str]:
    for pattern in patterns:
        hits = sorted(glob.glob(pattern, recursive=True))
        if hits:
            return hits[0]
    return None


# --------------------------------------------------------------------------- #
# Product-aware converters
# --------------------------------------------------------------------------- #
def ingest_gravity(
    res_deg: float = config.GRID_RES_DEG,
    output_dir: str = config.RAW_DIR,
) -> Optional[Dict[str, Any]]:
    """GRAIL GRGM1200A L=180 Bouguer disturbance GeoTIFF (mGal)."""
    source = _find_recursive(
        _source_path("grail", "gggrx_1200a_boug_l180.tif"),
        _source_path("**", "gggrx_1200a_boug_l180.tif"),
    )
    if not source:
        print("[gravity] required GRGM1200A L=180 GeoTIFF is missing")
        return None
    arr = regrid_to_canonical(source, Resampling.average, res_deg)
    write_canonical_raster(_out("gravity", output_dir), arr, res_deg)
    print(f"[gravity] {os.path.relpath(source, SOURCES_DIR)} -> {config.RAW_FILES['gravity']}")
    return {
        "source": os.path.relpath(source, SOURCES_DIR),
        "product": "GRGM1200A Bouguer gravity disturbance L=180",
        "native_unit": "mGal",
        "conversion": "longitude seam normalized; area-average to canonical grid",
        "native_frame": "Moon Principal Axes (DE430)",
    }


def _load_grail_thickness_grid(path: str) -> Tuple[np.ndarray, Affine]:
    values = np.fromfile(path, dtype="float64", sep=" ")
    expected = 721 * 1441
    if values.size != expected:
        raise ValueError(f"{path}: {values.size:,} values, expected {expected:,}")
    grid = values.reshape(721, 1441)[:, :-1]  # discard duplicated 360 E meridian
    grid = np.roll(grid, -(grid.shape[1] // 2), axis=1)  # 0..360 -> -180..180
    # Archive values are point samples at 0.25-degree intervals including both
    # poles.  Represent each point as a cell centre for conservative averaging.
    transform = from_origin(-180.125, 90.125, 0.25, 0.25)
    return grid.astype("float32"), transform


def ingest_thickness(
    res_deg: float = config.GRID_RES_DEG,
    output_dir: str = config.RAW_DIR,
) -> Optional[Dict[str, Any]]:
    """Published GRAIL Model 1 total crustal-thickness grid (km)."""
    source = _find_recursive(
        _source_path("grail", "crustal_thickness_archive", "**", "Model1_thick.dat"),
    )
    if not source:
        print("[thickness] required GRAIL Model1_thick.dat is missing")
        return None
    grid, transform = _load_grail_thickness_grid(source)
    arr = _reproject_array(
        grid, transform, config.LUNAR_GEO_CRS, Resampling.average, res_deg
    )
    write_canonical_raster(_out("thickness", output_dir), arr, res_deg)
    print(f"[thickness] {os.path.relpath(source, SOURCES_DIR)} -> {config.RAW_FILES['thickness']}")
    return {
        "source": os.path.relpath(source, SOURCES_DIR),
        "product": "GRAIL Crustal Thickness Archive Model 1",
        "native_unit": "km",
        "conversion": "721x1441 0.25-degree ASCII; drop duplicate seam; average to canonical",
        "model_choice": (
            "Model 1: published 12% porosity solution, 34 km global mean, "
            "3220 kg m-3 mantle density"
        ),
        "native_frame": "Moon Principal Axes",
    }


PDS_NS = {"pds": "http://pds.nasa.gov/pds4/pds/v1", "cart": "http://pds.nasa.gov/pds4/cart/v1"}


def _pds_text(root: ET.Element, xpath: str) -> str:
    value = root.findtext(xpath, namespaces=PDS_NS)
    if value is None:
        raise ValueError(f"PDS4 label missing {xpath}")
    return value.strip()


def _load_lroc_tio2_tile(label_path: str) -> Tuple[np.ndarray, Affine]:
    root = ET.parse(label_path).getroot()
    image_name = _pds_text(root, ".//pds:File_Area_Observational/pds:File/pds:file_name")
    image_path = os.path.join(os.path.dirname(label_path), image_name)
    offset = int(_pds_text(root, ".//pds:File_Area_Observational/pds:Array_2D_Image/pds:offset"))
    axes = root.findall(".//pds:File_Area_Observational/pds:Array_2D_Image/pds:Axis_Array", PDS_NS)
    sizes = {_pds_text(axis, "pds:axis_name"): int(_pds_text(axis, "pds:elements")) for axis in axes}
    if set(sizes) != {"Line", "Sample"}:
        raise ValueError(f"{label_path}: unexpected PDS4 axes {sizes}")
    dtype_name = _pds_text(
        root, ".//pds:File_Area_Observational/pds:Array_2D_Image/pds:Element_Array/pds:data_type"
    )
    if dtype_name != "IEEE754LSBSingle":
        raise ValueError(f"{label_path}: unsupported data type {dtype_name!r}")
    expected_bytes = offset + sizes["Line"] * sizes["Sample"] * 4
    if os.path.getsize(image_path) != expected_bytes:
        raise ValueError(f"{image_path}: byte size does not match PDS4 array declaration")

    with rasterio.open(image_path) as src:
        if src.shape != (sizes["Line"], sizes["Sample"]):
            raise ValueError(f"{image_path}: PDS driver shape disagrees with PDS4 label")
        source_crs = CRS.from_user_input(src.crs)
        if not source_crs.is_projected or not math.isclose(
            source_crs.ellipsoid.semi_major_metre, config.LUNAR_RADIUS_M, abs_tol=0.01
        ):
            raise ValueError(f"{image_path}: expected lunar equirectangular source CRS")
        arr = src.read(1, masked=True).filled(np.nan).astype("float32")
        native_transform = src.transform
    # The official README states >15 wt% is unreliable; PDS special constants
    # are extreme negative float sentinels.  Both become canonical nodata.
    arr[(~np.isfinite(arr)) | (arr < 0.0) | (arr > 15.0)] = np.nan

    labelled_res = float(_pds_text(root, ".//cart:pixel_resolution_x"))
    metres_per_degree = np.pi * config.LUNAR_RADIUS_M / 180.0
    xres = native_transform.a / metres_per_degree
    yres = abs(native_transform.e) / metres_per_degree
    if not math.isclose(xres, labelled_res, rel_tol=0, abs_tol=1e-9) or not math.isclose(
        yres, labelled_res, rel_tol=0, abs_tol=1e-9
    ):
        raise ValueError(f"{label_path}: raster transform disagrees with PDS4 pixel resolution")
    west_edge = native_transform.c / metres_per_degree
    north_edge = native_transform.f / metres_per_degree
    if west_edge >= 180.0 - 1e-8:
        west_edge -= 360.0
    transform = from_origin(west_edge, north_edge, xres, yres)
    return arr, transform


def ingest_tio2(
    res_deg: float = config.GRID_RES_DEG,
    output_dir: str = config.RAW_DIR,
) -> Optional[Dict[str, Any]]:
    labels = sorted(glob.glob(_source_path("lroc_wac_tio2", "WAC_TIO2_*.xml")))
    if len(labels) != 8:
        print(f"[tio2] required eight PDS4 WAC_TIO2 labels; found {len(labels)}")
        return None
    _, width, height = canonical_grid(res_deg)
    total = np.zeros((height, width), dtype="float64")
    count = np.zeros((height, width), dtype="uint8")
    for label in labels:
        native, transform = _load_lroc_tio2_tile(label)
        tile = _reproject_array(
            native, transform, config.LUNAR_GEO_CRS, Resampling.average, res_deg
        )
        valid = np.isfinite(tile)
        total[valid] += tile[valid]
        count[valid] += 1
    mosaic = np.full((height, width), np.nan, dtype="float32")
    valid = count > 0
    mosaic[valid] = (total[valid] / count[valid]).astype("float32")
    write_canonical_raster(_out("tio2", output_dir), mosaic, res_deg)
    print(f"[tio2] 8 PDS4 label+IMG tiles -> {config.RAW_FILES['tio2']}")
    return {
        "sources": [os.path.relpath(path, SOURCES_DIR) for path in labels],
        "product": "LROC WAC TiO2 abundance, LROLRC_2001, PDS4 label version 2.0",
        "native_unit": "TiO2 weight percent",
        "conversion": "decode IEEE754LSBSingle payloads; mask <0/>15; area-average mosaic",
        "coverage": "70 S to 70 N",
    }


def ingest_magnetic_jaxa(
    res_deg: float = config.GRID_RES_DEG,
    output_dir: str = config.RAW_DIR,
) -> Optional[Dict[str, Any]]:
    source = _find_recursive(_source_path("jaxa_lmag", "MA_GDOP_001.dat"))
    if not source:
        print("[magnetic] required JAXA MA_GDOP_001.dat is missing")
        return None
    df = pd.read_csv(
        source, sep=",", header=None, usecols=[0, 1, 5],
        names=["lat", "lon", "F"], dtype="float64",
    )
    if not np.isfinite(df[["lat", "lon", "F"]].to_numpy()).all():
        raise ValueError(f"{source}: non-finite coordinate or field value")
    lats = np.sort(df["lat"].unique())
    lons = np.sort(spatial.wrap_lon(df["lon"].unique()))
    if len(lats) != 179 or len(lons) != 360 or not np.allclose(np.diff(lats), 1.0) or not np.allclose(
        np.diff(lons), 1.0
    ):
        raise ValueError(f"{source}: unexpected MA_GDOP grid coordinates")
    df = df.assign(lon=spatial.wrap_lon(df["lon"].to_numpy()))
    native = df.pivot(index="lat", columns="lon", values="F").reindex(index=lats, columns=lons)
    if native.isna().any().any():
        raise ValueError(f"{source}: MA_GDOP grid is incomplete or duplicated")
    values = np.abs(native.to_numpy(dtype="float64"))

    # Add symmetric polar and periodic seam guards, then interpolate to the
    # canonical cell centres.  This avoids the former order-dependent "last
    # point wins" assignment and the north/south bias from boundary flooring.
    extended = np.pad(values, ((1, 1), (1, 1)), mode="edge")
    extended[:, 0] = extended[:, -2]
    extended[:, -1] = extended[:, 1]
    lat_ext = np.concatenate(([-90.0], lats, [90.0]))
    lon_ext = np.concatenate(([-180.5], lons, [180.5]))
    interpolator = RegularGridInterpolator(
        (lat_ext, lon_ext), extended, method="linear", bounds_error=True
    )
    _, width, height = canonical_grid(res_deg)
    target_lons = -180.0 + res_deg * (np.arange(width) + 0.5)
    target_lats = 90.0 - res_deg * (np.arange(height) + 0.5)
    lon_grid, lat_grid = np.meshgrid(target_lons, target_lats)
    points = np.column_stack((lat_grid.ravel(), lon_grid.ravel()))
    grid = interpolator(points).reshape(height, width).astype("float32")
    write_canonical_raster(_out("magnetic", output_dir), grid, res_deg)
    print(f"[magnetic] {len(df):,} MA_GDOP points -> {config.RAW_FILES['magnetic']}")
    return {
        "source": os.path.relpath(source, SOURCES_DIR),
        "product": "JAXA LMAG MA_GDOP_001 surface vector map option",
        "native_unit": "nT",
        "conversion": "absolute F column; periodic linear interpolation to cell centres",
    }


def ingest_magnetic_csv(
    csv_path: str,
    res_deg: float = config.GRID_RES_DEG,
    output_dir: str = config.RAW_DIR,
) -> Optional[Dict[str, Any]]:
    """Explicit legacy fallback; never used by strict ``ingest all``."""
    if not os.path.exists(csv_path):
        print(f"[magnetic-csv] {csv_path} not found")
        return None
    data = np.loadtxt(csv_path, delimiter=",").astype("float32")
    _, width, height = canonical_grid(res_deg)
    if data.shape != (height, width):
        raise ValueError(f"CSV grid {data.shape} != canonical {(height, width)}")
    write_canonical_raster(_out("magnetic", output_dir), np.abs(data), res_deg)
    return {"source": csv_path, "conversion": "legacy dense CSV; absolute magnitude"}


def _pick_unit_column(gdf: Any) -> str:
    for candidate in (
        "FIRST_Unit", "UnitSymbol", "UNIT", "Unit", "MapUnit", "MapSymbol", "SYMBOL",
    ):
        if candidate in gdf.columns:
            return candidate
    raise ValueError(
        "USGS GeoUnits has no recognized unit-symbol field; "
        f"available columns={list(gdf.columns)}"
    )


def _map_unit_to_age(unit: Any) -> int:
    if not isinstance(unit, str) or not unit.strip():
        return config.AGE_OTHER
    symbol = unit.strip()
    # USGS map symbols are case-sensitive stratigraphic codes.  Definite
    # Imbrian/Nectarian units start with I/N; transitional E-I etc. units are
    # conservatively left as Other rather than silently broadening the mask.
    return {
        "I": config.AGE_IMBRIAN,
        "N": config.AGE_NECTARIAN,
    }.get(symbol[0].upper(), config.AGE_OTHER)


def _pick_age_column(gdf: Any) -> Tuple[str, str]:
    """Prefer the USGS period field; retain an explicit unit-symbol fallback."""
    if "FIRST_Un_1" in gdf.columns:
        return "FIRST_Un_1", "period"
    return _pick_unit_column(gdf), "symbol"


def _map_period_to_age(period: Any) -> int:
    if not isinstance(period, str):
        return config.AGE_OTHER
    value = period.strip()
    if value == "Imbrian":
        return config.AGE_IMBRIAN
    if value in {"Nectarian", "Imbrian-Nectarian"}:
        # Ambiguous I-N units are excluded from the strict Imbrian primary mask
        # but retained by the Imbrian+Nectarian sensitivity analysis.
        return config.AGE_NECTARIAN
    return config.AGE_OTHER


def _find_geounits_shapefile() -> Optional[str]:
    hits = sorted(glob.glob(_source_path("usgs", "unified_geologic_map_v2", "**", "*.shp"), recursive=True))
    preferred = [path for path in hits if "geounit" in os.path.basename(path).lower()]
    if len(preferred) == 1:
        return preferred[0]
    if len(preferred) > 1:
        exact = [path for path in preferred if os.path.basename(path).lower() == "geounits.shp"]
        if len(exact) == 1:
            return exact[0]
        raise ValueError(f"ambiguous USGS GeoUnits layers: {preferred}")
    return None


def ingest_age(
    res_deg: float = config.GRID_RES_DEG,
    output_dir: str = config.RAW_DIR,
) -> Optional[Dict[str, Any]]:
    source = _find_geounits_shapefile()
    if not source:
        print("[age] required USGS GeoUnits polygon shapefile is missing")
        return None
    import geopandas as gpd

    gdf = gpd.read_file(source)
    if gdf.empty or not gdf.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError(f"{source}: expected a non-empty polygon GeoUnits layer")
    age_col, age_encoding = _pick_age_column(gdf)
    unit_col = _pick_unit_column(gdf)
    gdf = gdf.loc[gdf.geometry.notna()].copy()
    mapper = _map_period_to_age if age_encoding == "period" else _map_unit_to_age
    gdf["age_class"] = gdf[age_col].map(mapper).astype("int8")
    gdf["tio2_mare_valid"] = gdf[unit_col].isin(config.MARE_UNIT_SYMBOLS).astype("int8")
    if gdf.crs is None:
        raise ValueError(f"{source}: missing CRS")
    native_crs = CRS.from_user_input(gdf.crs)
    bounds = gdf.total_bounds
    if native_crs.is_geographic and np.all(np.abs(bounds[[0, 2]]) <= 361) and np.all(
        np.abs(bounds[[1, 3]]) <= 91
    ):
        gdf = gdf.set_crs(config.LUNAR_GEO_CRS, allow_override=True)
    else:
        gdf = gdf.to_crs(config.LUNAR_GEO_CRS)

    transform, width, height = canonical_grid(res_deg)
    grid = rasterize(
        ((geometry, int(age)) for geometry, age in zip(gdf.geometry, gdf["age_class"])),
        out_shape=(height, width), transform=transform,
        fill=config.AGE_OTHER, dtype="float32", all_touched=False,
    )
    write_canonical_raster(_out("age", output_dir), grid, res_deg)
    mare_grid = rasterize(
        ((geometry, int(is_mare)) for geometry, is_mare in zip(
            gdf.geometry, gdf["tio2_mare_valid"]
        )),
        out_shape=(height, width), transform=transform,
        fill=0, dtype="float32", all_touched=False,
    )
    write_canonical_raster(
        os.path.join(output_dir, config.TERRAIN_VALIDITY_FILE), mare_grid, res_deg
    )
    fractions = {
        "Imbrian": float(np.mean(grid == config.AGE_IMBRIAN)),
        "Nectarian": float(np.mean(grid == config.AGE_NECTARIAN)),
        "Other": float(np.mean(grid == config.AGE_OTHER)),
    }
    if fractions["Imbrian"] == 0 or fractions["Nectarian"] == 0:
        raise ValueError(f"{source}: age mapping produced missing primary classes {fractions}")
    print(f"[age] {os.path.relpath(source, SOURCES_DIR)} ({age_col}) -> {config.RAW_FILES['age']} {fractions}")
    return {
        "source": os.path.relpath(source, SOURCES_DIR),
        "product": "USGS Unified Geologic Map of the Moon 1:5M GIS v2 GeoUnits",
        "conversion": (
            f"rasterize {age_col}; Imbrian=2; Nectarian and ambiguous "
            "Imbrian-Nectarian=1; all other periods=0"
            if age_encoding == "period" else
            f"rasterize {age_col}; leading I=Imbrian, N=Nectarian, else Other"
        ),
        "class_fractions": fractions,
        "tio2_terrain_validity": {
            "output": config.TERRAIN_VALIDITY_FILE,
            "unit_column": unit_col,
            "mare_unit_symbols": list(config.MARE_UNIT_SYMBOLS),
            "valid_fraction": float(np.mean(mare_grid == 1)),
            "interpretation": (
                "USGS units explicitly mapped as mare; sensitivity mask for the "
                "mare-calibrated LROC WAC TiO2 algorithm"
            ),
        },
    }


def write_basin_catalog(output_dir: str = config.RAW_DIR) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    rows = [{"name": name, "lon": lon, "lat": lat, "radius_km": radius}
            for name, lon, lat, radius in MAJOR_BASINS]
    basins = pd.DataFrame(rows)
    basins.to_csv(os.path.join(output_dir, config.BASINS_CSV), index=False)
    antipodes = []
    for name, lon, lat, _ in MAJOR_BASINS:
        anti_lon, anti_lat = spatial.antipode(lon, lat)
        antipodes.append({"name": f"{name}_antipode", "lon": anti_lon, "lat": anti_lat})
    pd.DataFrame(antipodes).to_csv(os.path.join(output_dir, config.ANTIPODES_CSV), index=False)
    print(f"[basins] wrote {len(rows)} documented centres and derived antipodes")
    return {
        "source": "src.basins.MAJOR_BASINS",
        "catalog_metadata": CATALOG_METADATA,
        "conversion": "antipode=(wrap(lon+180), -lat)",
        "n_basins": len(rows),
    }


# --------------------------------------------------------------------------- #
# Strict schema/provenance validation
# --------------------------------------------------------------------------- #
def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_lunar_geographic(crs: Any) -> bool:
    if crs is None:
        return False
    try:
        parsed = CRS.from_user_input(crs)
        return parsed.is_geographic and math.isclose(
            parsed.ellipsoid.semi_major_metre, config.LUNAR_RADIUS_M, abs_tol=0.01
        ) and math.isclose(
            parsed.ellipsoid.semi_minor_metre, config.LUNAR_RADIUS_M, abs_tol=0.01
        )
    except Exception:
        return False


def _validate_catalogs(raw_dir: str, fatal: List[str], report: Dict[str, Any]) -> None:
    basin_path = os.path.join(raw_dir, config.BASINS_CSV)
    antipode_path = os.path.join(raw_dir, config.ANTIPODES_CSV)
    tables: Dict[str, pd.DataFrame] = {}
    for filename, required in (
        (config.BASINS_CSV, {"name", "lon", "lat", "radius_km"}),
        (config.ANTIPODES_CSV, {"name", "lon", "lat"}),
    ):
        path = os.path.join(raw_dir, filename)
        if not os.path.isfile(path):
            fatal.append(f"{filename} missing")
            continue
        try:
            table = pd.read_csv(path)
        except Exception as exc:
            fatal.append(f"{filename} unreadable: {exc}")
            continue
        missing = required - set(table.columns)
        if missing:
            fatal.append(f"{filename} missing columns {sorted(missing)}")
            continue
        if table.empty or table["name"].isna().any() or table["name"].duplicated().any():
            fatal.append(f"{filename} must contain unique non-empty names")
        numeric = ["lon", "lat"] + (["radius_km"] if "radius_km" in required else [])
        if not np.isfinite(table[numeric].to_numpy(dtype="float64")).all():
            fatal.append(f"{filename} has non-finite coordinates/radii")
        if not table["lon"].between(-180, 180).all() or not table["lat"].between(-90, 90).all():
            fatal.append(f"{filename} has coordinates outside lunar lon/lat bounds")
        if "radius_km" in table and not table["radius_km"].between(0, 2000, inclusive="neither").all():
            fatal.append(f"{filename} has non-positive/implausible basin radii")
        tables[filename] = table
        report[filename] = {"rows": int(len(table)), "columns": list(table.columns)}

    if config.BASINS_CSV in tables and config.ANTIPODES_CSV in tables:
        basins, antipodes = tables[config.BASINS_CSV], tables[config.ANTIPODES_CSV]
        if len(basins) != len(antipodes):
            fatal.append("basins.csv and antipodes.csv row counts differ")
        else:
            anti_by_name = antipodes.set_index("name")
            for row in basins.itertuples(index=False):
                name = f"{row.name}_antipode"
                if name not in anti_by_name.index:
                    fatal.append(f"antipodes.csv missing {name}")
                    continue
                expected_lon, expected_lat = spatial.antipode(float(row.lon), float(row.lat))
                actual = anti_by_name.loc[name]
                if not np.allclose([actual.lon, actual.lat], [expected_lon, expected_lat], atol=1e-9):
                    fatal.append(f"{name} is not the mathematical antipode of {row.name}")


def _validate_real_manifest(
    raw_dir: str, res_deg: float, fatal: List[str], report: Dict[str, Any],
) -> None:
    path = os.path.join(raw_dir, REAL_DATA_MANIFEST)
    if not os.path.isfile(path):
        fatal.append(f"{REAL_DATA_MANIFEST} missing (real data provenance required)")
        return
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fatal.append(f"{REAL_DATA_MANIFEST} unreadable: {exc}")
        return
    if manifest.get("data_mode") != "real":
        fatal.append(f"{REAL_DATA_MANIFEST}: data_mode must be 'real'")
    if manifest.get("schema_version") != 2:
        fatal.append(f"{REAL_DATA_MANIFEST}: schema_version must be 2")
    if not math.isclose(float(manifest.get("grid_resolution_deg", -1)), res_deg, abs_tol=1e-12):
        fatal.append(f"{REAL_DATA_MANIFEST}: grid resolution mismatch")
    source_info = manifest.get("source_manifest", {})
    source_rel = source_info.get("path", "sources/source_manifest.json")
    source_path = os.path.join(raw_dir, source_rel)
    if not os.path.isfile(source_path) and os.path.abspath(raw_dir) != os.path.abspath(config.RAW_DIR):
        # ``ingest all`` validates a staging directory before promotion; the
        # immutable source tree remains in the canonical raw directory.
        source_path = os.path.join(config.RAW_DIR, source_rel)
    if not os.path.isfile(source_path):
        fatal.append(f"source manifest missing: {source_rel}")
    elif source_info.get("sha256") != _sha256(source_path):
        fatal.append("source_manifest.json hash differs from real-data manifest")
    else:
        try:
            source_manifest = json.loads(Path(source_path).read_text(encoding="utf-8"))
            from .acquire import SPECS

            source_records = {
                item.get("key"): item for item in source_manifest.get("files", [])
            }
            if source_manifest.get("schema_version") != 2:
                fatal.append("source_manifest.json schema_version must be 2")
            for spec in SPECS:
                record = source_records.get(spec.key, {})
                if record.get("sha256") != spec.expected_sha256:
                    fatal.append(f"source_manifest.json lacks pinned SHA-256 for {spec.key}")
            extractions = source_manifest.get("extracted_archives", {})
            for name in ("grail_crustal_thickness", "usgs_geology"):
                if not extractions.get(name, {}).get("members"):
                    fatal.append(f"source_manifest.json lacks verified members for {name}")
        except (OSError, TypeError, json.JSONDecodeError) as exc:
            fatal.append(f"source_manifest.json unreadable: {exc}")

    outputs = manifest.get("canonical_outputs", {})
    for filename in (
        *config.RAW_FILES.values(), config.TERRAIN_VALIDITY_FILE,
        config.BASINS_CSV, config.ANTIPODES_CSV,
    ):
        file_path = os.path.join(raw_dir, filename)
        expected = outputs.get(filename, {}).get("sha256")
        if not expected:
            fatal.append(f"{REAL_DATA_MANIFEST}: missing hash for {filename}")
        elif os.path.isfile(file_path) and _sha256(file_path) != expected:
            fatal.append(f"{filename} hash differs from real-data manifest")
    report[REAL_DATA_MANIFEST] = {
        "schema_version": manifest.get("schema_version"),
        "created_utc": manifest.get("created_utc"),
    }


def _validate_terrain_mask(
    raw_dir: str,
    res_deg: float,
    fatal: List[str],
    report: Dict[str, Any],
    *,
    required: bool,
    require_realistic_mare_fraction: bool,
) -> None:
    """Validate the required terrain/domain flag without making it a model feature.

    Only provenance-verified real mode may label the flag as the repository's
    USGS mare proxy. Schema-only and synthetic validation report a neutral valid
    fraction because this function cannot infer where their flag came from.
    """
    path = os.path.join(raw_dir, config.TERRAIN_VALIDITY_FILE)
    if not os.path.isfile(path):
        if required:
            fatal.append(f"{config.TERRAIN_VALIDITY_FILE} missing")
        report["tio2_terrain_validity"] = {"status": "MISSING"}
        return
    expected_transform, width, height = canonical_grid(res_deg)
    try:
        with rasterio.open(path) as src:
            arr = src.read(1).astype("float64")
            nodata = src.nodata
            if (src.height, src.width) != (height, width):
                fatal.append(
                    f"{config.TERRAIN_VALIDITY_FILE} shape {(src.height, src.width)} "
                    f"!= {(height, width)}"
                )
            if src.count != 1 or src.dtypes[0] != "float32":
                fatal.append(f"{config.TERRAIN_VALIDITY_FILE} must be one float32 band")
            if nodata is None or not math.isclose(float(nodata), config.NODATA, abs_tol=1e-6):
                fatal.append(f"{config.TERRAIN_VALIDITY_FILE} has invalid nodata metadata")
            if not src.transform.almost_equals(expected_transform, precision=12):
                fatal.append(f"{config.TERRAIN_VALIDITY_FILE} is not on the canonical grid")
            if not _is_lunar_geographic(src.crs):
                fatal.append(f"{config.TERRAIN_VALIDITY_FILE} CRS is not lunar geographic")
    except Exception as exc:
        fatal.append(f"{config.TERRAIN_VALIDITY_FILE} unreadable: {exc}")
        return
    valid = np.isfinite(arr) & (arr != nodata)
    values = np.unique(arr[valid])
    if not valid.all() or not set(values.tolist()) <= {0.0, 1.0}:
        fatal.append(
            f"{config.TERRAIN_VALIDITY_FILE} must be a complete binary 0/1 mask"
        )
    mare_fraction = float(np.mean(arr[valid] == 1)) if valid.any() else 0.0
    if require_realistic_mare_fraction and not 0.001 < mare_fraction < 0.5:
        fatal.append(
            f"{config.TERRAIN_VALIDITY_FILE} mare fraction {mare_fraction:.3f} is implausible"
        )
    terrain_report: Dict[str, Any] = {
        "status": "OK" if not fatal else "CHECK_FATAL_LIST",
        "valid_fraction": mare_fraction,
    }
    if require_realistic_mare_fraction:
        terrain_report.update({
            "mare_fraction": mare_fraction,
            "mare_unit_symbols": list(config.MARE_UNIT_SYMBOLS),
            "scope": "provenance-verified USGS mare geology proxy",
        })
    else:
        terrain_report["scope"] = "terrain/domain flag; source provenance not asserted"
    report["tio2_terrain_validity"] = terrain_report


def validate_raw_grids(
    raw_dir: str = config.RAW_DIR,
    res_deg: float = config.GRID_RES_DEG,
    require_real_provenance: bool = False,
) -> Dict[str, Any]:
    transform, width, height = canonical_grid(res_deg)
    expected_bounds = (-180.0, -90.0, 180.0, 90.0)
    report: Dict[str, Any] = {}
    fatal: List[str] = []
    valid_masks: List[np.ndarray] = []

    for key, filename in config.RAW_FILES.items():
        path = os.path.join(raw_dir, filename)
        entry: Dict[str, Any] = {"path": filename}
        if not os.path.isfile(path):
            fatal.append(f"{filename} missing")
            entry["status"] = "MISSING"
            report[key] = entry
            continue
        try:
            with rasterio.open(path) as src:
                arr = src.read(1).astype("float64")
                entry.update({
                    "shape": [src.height, src.width],
                    "dtype": src.dtypes[0],
                    "count": src.count,
                    "nodata": src.nodata,
                    "transform": list(src.transform)[:6],
                    "bounds": list(src.bounds),
                    "crs_is_lunar_geographic": _is_lunar_geographic(src.crs),
                })
                # Backward-compatible report alias used by the original tests.
                entry["crs_is_lunar"] = entry["crs_is_lunar_geographic"]
                if (src.height, src.width) != (height, width):
                    fatal.append(f"{filename} shape {(src.height, src.width)} != {(height, width)}")
                if src.count != 1:
                    fatal.append(f"{filename} has {src.count} bands; expected 1")
                if src.dtypes[0] != "float32":
                    fatal.append(f"{filename} dtype {src.dtypes[0]} != float32")
                if src.nodata is None or not math.isclose(float(src.nodata), config.NODATA, abs_tol=1e-6):
                    fatal.append(f"{filename} nodata {src.nodata!r} != {config.NODATA}")
                if not src.transform.almost_equals(transform, precision=12):
                    fatal.append(f"{filename} transform is not the canonical aligned transform")
                if not np.allclose(list(src.bounds), expected_bounds, atol=1e-9):
                    fatal.append(f"{filename} bounds {tuple(src.bounds)} are not global")
                if not entry["crs_is_lunar_geographic"]:
                    fatal.append(f"{filename} CRS is not lunar geographic R={config.LUNAR_RADIUS_M}")
                nodata = src.nodata
        except Exception as exc:
            fatal.append(f"{filename} unreadable: {exc}")
            report[key] = entry
            continue

        valid = np.isfinite(arr) & (arr != nodata)
        valid_masks.append(valid)
        entry["valid_fraction"] = float(valid.mean())
        if valid.mean() < MIN_VALID_FRACTION[key]:
            fatal.append(
                f"{filename} valid fraction {valid.mean():.3f} < required {MIN_VALID_FRACTION[key]:.3f}"
            )
        if valid.any():
            values = arr[valid]
            vmin, vmax = float(values.min()), float(values.max())
            entry["min"], entry["max"] = vmin, vmax
            lo, hi = VALUE_RANGES[key]
            if vmin < lo - 1e-6 or vmax > hi + 1e-6:
                fatal.append(f"{filename} values [{vmin}, {vmax}] outside [{lo}, {hi}]")
            if key == "age":
                unique = np.unique(values)
                entry["unique_values"] = unique.tolist()
                if not set(unique.tolist()) <= {
                    float(config.AGE_OTHER), float(config.AGE_NECTARIAN), float(config.AGE_IMBRIAN)
                }:
                    fatal.append(f"{filename} has non-categorical age values {unique.tolist()}")
                if config.AGE_IMBRIAN not in unique or config.AGE_NECTARIAN not in unique:
                    fatal.append(f"{filename} is missing Imbrian or Nectarian cells")
        else:
            fatal.append(f"{filename} has no valid pixels")
        report[key] = entry

    if len(valid_masks) == len(config.RAW_FILES) and all(mask.shape == valid_masks[0].shape for mask in valid_masks):
        common = np.logical_and.reduce(valid_masks)
        report["common_valid_fraction"] = float(common.mean())
        if common.mean() < MIN_COMMON_VALID_FRACTION:
            fatal.append(
                f"common five-layer coverage {common.mean():.3f} < {MIN_COMMON_VALID_FRACTION:.3f}"
            )

    _validate_terrain_mask(
        raw_dir,
        res_deg,
        fatal,
        report,
        required=True,
        require_realistic_mare_fraction=require_real_provenance,
    )
    _validate_catalogs(raw_dir, fatal, report)
    if require_real_provenance:
        _validate_real_manifest(raw_dir, res_deg, fatal, report)
    report["_fatal"] = fatal
    report["_ok"] = not fatal
    if fatal:
        raise ValueError("Raw-data validation FAILED:\n  - " + "\n  - ".join(fatal))
    provenance_text = " with verified real-data provenance" if require_real_provenance else ""
    print(f"[validate] canonical grids/tables satisfy the strict lunar schema{provenance_text}.")
    return report


# --------------------------------------------------------------------------- #
# Source validation, provenance creation, staged orchestration
# --------------------------------------------------------------------------- #
def _validated_source_manifest() -> Tuple[Dict[str, Any], str]:
    if not os.path.isfile(SOURCE_MANIFEST):
        raise ValueError("source_manifest.json missing; run `python -m src.acquire all` first")
    manifest = json.loads(Path(SOURCE_MANIFEST).read_text(encoding="utf-8"))
    if manifest.get("data_mode") != "real-source-products":
        raise ValueError("source manifest has the wrong data_mode")
    if manifest.get("schema_version") != 2:
        raise ValueError("source manifest schema is stale; run `python -m src.acquire all`")
    from .acquire import SPECS, _verify_zip_extraction

    record_items = manifest.get("files", [])
    records = {item.get("key"): item for item in record_items}
    expected_keys = {spec.key for spec in SPECS}
    if len(records) != len(record_items):
        raise ValueError("source manifest contains duplicate source keys")
    missing = sorted(expected_keys - set(records))
    if missing:
        raise ValueError(f"source manifest is incomplete; missing {missing}")
    extra = sorted(set(records) - expected_keys)
    if extra:
        raise ValueError(f"source manifest contains unexpected sources: {extra}")
    root = Path(SOURCES_DIR).resolve()
    for spec in SPECS:
        record = records[spec.key]
        if record.get("relative_path") != spec.relative_path:
            raise ValueError(f"source path changed for {spec.key}")
        if record.get("expected_sha256") != spec.expected_sha256:
            raise ValueError(f"manifest pin changed for {spec.key}")
        if record.get("sha256") != spec.expected_sha256:
            raise ValueError(f"source digest is not the code-pinned digest for {spec.key}")
        candidate = root / str(record.get("relative_path", ""))
        if candidate.is_symlink():
            raise ValueError(f"source file is a symlink: {candidate.relative_to(root)}")
        path = candidate.resolve()
        if root not in path.parents:
            raise ValueError(f"source path escapes sources directory: {path}")
        if not path.is_file():
            raise ValueError(f"source file missing: {path.relative_to(root)}")
        if path.stat().st_size != int(record.get("size_bytes", -1)):
            raise ValueError(f"source size changed: {path.relative_to(root)}")
        if _sha256(str(path)) != record.get("sha256"):
            raise ValueError(f"source hash changed: {path.relative_to(root)}")

    expected_extractions = {
        "grail_crustal_thickness": (
            "archives/GRAILCrustalThicknessArchive.zip",
            "grail/crustal_thickness_archive",
        ),
        "usgs_geology": (
            "archives/Unified_Geologic_Map_of_the_Moon_GIS_v2.zip",
            "usgs/unified_geologic_map_v2",
        ),
    }
    extractions = manifest.get("extracted_archives", {})
    if set(extractions) != set(expected_extractions):
        raise ValueError("source manifest has missing or unexpected archive extractions")
    for name, (archive_rel, destination_rel) in expected_extractions.items():
        entry = extractions[name]
        if entry.get("path") != destination_rel:
            raise ValueError(f"extraction path changed for {name}")
        archive = root / archive_rel
        destination = root / destination_rel
        archive_sha = _sha256(str(archive))
        if entry.get("archive_sha256") != archive_sha:
            raise ValueError(f"archive digest changed for {name}")
        marker = destination / ".extracted_from_sha256"
        if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != archive_sha:
            raise ValueError(f"extraction marker changed for {name}")
        try:
            verified_members = _verify_zip_extraction(archive, destination)
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            raise ValueError(f"archive extraction invalid for {name}: {exc}") from exc
        if entry.get("members") != verified_members:
            raise ValueError(f"extracted-member manifest changed for {name}")
    return manifest, _sha256(SOURCE_MANIFEST)


def _write_real_manifest(
    output_dir: str,
    res_deg: float,
    source_manifest: Dict[str, Any],
    source_manifest_sha: str,
    conversions: Dict[str, Any],
) -> str:
    output_names: Sequence[str] = (
        *config.RAW_FILES.values(), config.TERRAIN_VALIDITY_FILE,
        config.BASINS_CSV, config.ANTIPODES_CSV,
    )
    outputs = {
        name: {
            "size_bytes": os.path.getsize(os.path.join(output_dir, name)),
            "sha256": _sha256(os.path.join(output_dir, name)),
        }
        for name in output_names
    }
    manifest = {
        "schema_version": 2,
        "data_mode": "real",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "grid_resolution_deg": res_deg,
        "lunar_radius_m": config.LUNAR_RADIUS_M,
        "source_manifest": {
            "path": "sources/source_manifest.json",
            "sha256": source_manifest_sha,
            "created_utc": source_manifest.get("created_utc"),
        },
        "products": source_manifest.get("products", {}),
        "conversions": conversions,
        "coordinate_frame_note": (
            "GRAIL Bouguer and crustal-thickness sources are native Moon Principal Axes; "
            "at this 1-degree analysis scale their sub-pixel PA/ME offset is retained as "
            "a documented control-layer uncertainty rather than hidden."
        ),
        "canonical_outputs": outputs,
    }
    path = os.path.join(output_dir, REAL_DATA_MANIFEST)
    Path(path).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_all(res_deg: float = config.GRID_RES_DEG) -> Dict[str, Any]:
    """Convert all required sources transactionally; skips are fatal."""
    canonical_grid(res_deg)
    os.makedirs(config.RAW_DIR, exist_ok=True)
    source_manifest, source_sha = _validated_source_manifest()
    staging = tempfile.mkdtemp(prefix=".canonical-staging-", dir=config.RAW_DIR)
    conversions: Dict[str, Any] = {}
    try:
        steps = (
            ("tio2", ingest_tio2),
            ("gravity", ingest_gravity),
            ("thickness", ingest_thickness),
            ("age", ingest_age),
            ("magnetic", ingest_magnetic_jaxa),
        )
        for key, converter in steps:
            metadata = converter(res_deg, staging)
            if not metadata:
                raise ValueError(f"strict real-data ingestion failed: {key} source unavailable")
            conversions[key] = metadata
        conversions["basins"] = write_basin_catalog(staging)
        validate_raw_grids(staging, res_deg, require_real_provenance=False)
        _write_real_manifest(staging, res_deg, source_manifest, source_sha, conversions)

        # Validate the manifest against the eventual raw-dir source path before
        # promoting any canonical output.
        validate_raw_grids(staging, res_deg, require_real_provenance=True)
        promote = [
            *config.RAW_FILES.values(), config.TERRAIN_VALIDITY_FILE,
            config.BASINS_CSV, config.ANTIPODES_CSV,
            REAL_DATA_MANIFEST,
        ]
        for filename in promote:
            os.replace(os.path.join(staging, filename), os.path.join(config.RAW_DIR, filename))
        print("[ingest] five real layers + mare mask validated and promoted atomically per file")
        return conversions
    finally:
        shutil.rmtree(staging, ignore_errors=True)


STEPS = {
    "tio2": ingest_tio2,
    "gravity": ingest_gravity,
    "thickness": ingest_thickness,
    "age": ingest_age,
    "magnetic": ingest_magnetic_jaxa,
    "basins": write_basin_catalog,
    "validate": validate_raw_grids,
    "all": run_all,
}


def main(argv: Optional[List[str]] = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Ingest authoritative lunar data")
    parser.add_argument("step", choices=list(STEPS), help="ingestion step")
    parser.add_argument("--res", type=float, default=config.GRID_RES_DEG, help="degrees per pixel")
    parser.add_argument(
        "--allow-missing-provenance", action="store_true",
        help="validate schema only (intended for synthetic test fixtures)",
    )
    args = parser.parse_args(argv)
    if args.step == "validate":
        validate_raw_grids(
            config.RAW_DIR, args.res,
            require_real_provenance=not args.allow_missing_provenance,
        )
    elif args.step == "basins":
        write_basin_catalog(config.RAW_DIR)
    elif args.step == "all":
        run_all(args.res)
    else:
        STEPS[args.step](args.res, config.RAW_DIR)


if __name__ == "__main__":
    main()
