"""Backward-compatible LROC-only entry point for :mod:`src.acquire`.

Unlike the former best-effort script, this downloads both PDS4 XML labels and
their IMG payloads atomically, verifies them, and records a source manifest.
"""

from .acquire import acquire


def download() -> None:
    acquire(["lroc"])
    print("done; next: python -m src.ingest tio2")


if __name__ == "__main__":
    download()
