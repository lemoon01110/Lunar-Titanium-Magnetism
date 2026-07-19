"""Deprecated shim -> src.ingest.ingest_magnetic_surface_svm.

Run: python -m src.ingest magnetic
"""
from .ingest import ingest_magnetic_surface_svm

if __name__ == "__main__":
    ingest_magnetic_surface_svm()
