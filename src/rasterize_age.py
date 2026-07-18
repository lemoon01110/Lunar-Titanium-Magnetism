"""Deprecated shim -> src.ingest.ingest_age. Run: python -m src.ingest age"""
from .ingest import ingest_age

if __name__ == "__main__":
    ingest_age()
