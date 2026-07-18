"""Deprecated shim -> src.ingest.ingest_magnetic_jaxa. Run: python -m src.ingest magnetic"""
from .ingest import ingest_magnetic_jaxa

if __name__ == "__main__":
    ingest_magnetic_jaxa()
