"""Deprecated shim -> src.ingest.ingest_magnetic_csv.

Run: python -m src.convert_idl_csv_to_tif --csv path/to/grid.csv
(An IDL-exported dense magnetic grid, top-left = -180,90, at config.GRID_RES_DEG.)
"""
import argparse

from . import config
from .ingest import ingest_magnetic_csv

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Convert an IDL CSV magnetic grid to the canonical GeoTIFF")
    p.add_argument("--csv", required=True, help="path to the IDL-exported CSV grid")
    p.add_argument("--res", type=float, default=config.GRID_RES_DEG)
    a = p.parse_args()
    ingest_magnetic_csv(a.csv, a.res)
