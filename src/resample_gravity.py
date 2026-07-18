"""Deprecated shim -> src.ingest.ingest_gravity. Run: python -m src.ingest gravity"""
from .ingest import ingest_gravity

if __name__ == "__main__":
    ingest_gravity()
