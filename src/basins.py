"""Predeclared impact-basin catalogue used to operationalize H2.

These six rounded centers and main-rim radii are analysis configuration, not a
downloaded observational product and not synthetic data.  Basin boundaries vary
among lunar catalogues, so the values are deliberately exposed here and disclosed
as a model choice in Data-Sources.md.  Antipodes are always derived mathematically.
"""

from typing import Tuple


MAJOR_BASINS: Tuple[Tuple[str, float, float, float], ...] = (
    ("Imbrium", -18.0, 33.0, 580.0),
    ("Orientale", -95.0, -20.0, 465.0),
    ("Crisium", 59.0, 17.0, 370.0),
    ("Serenitatis", 19.0, 28.0, 340.0),
    ("Nectaris", 34.0, -16.0, 430.0),
    ("Humorum", -39.0, -24.0, 210.0),
)

CATALOG_METADATA = {
    "status": "predeclared approximate H2 analysis configuration",
    "coordinate_convention": "longitude east-positive in [-180, 180], latitude degrees",
    "radius_definition": "rounded approximate main-rim radius in km",
    "caveat": "not an exhaustive or independently downloaded impact-basin catalogue",
}
