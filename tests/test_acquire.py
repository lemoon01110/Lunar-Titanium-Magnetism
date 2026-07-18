"""Fail-closed provenance tests for real source acquisition/extraction."""

import hashlib
import json
import zipfile

import pytest

from src import acquire, ingest


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_unmanifested_unpinned_existing_file_is_not_reused(tmp_path):
    path = tmp_path / "source.bin"
    path.write_bytes(b"arbitrary local bytes")
    spec = acquire.SourceSpec(
        key="test-unpinned",
        family="test",
        url="https://example.invalid/source.bin",
        relative_path="source.bin",
        product_id="test",
        expected_size=path.stat().st_size,
    )

    assert not acquire._verified_existing(path, spec, {})
    assert acquire._verified_existing(path, spec, {"sha256": _sha(path.read_bytes())})


def test_code_pinned_sha_is_enforced(tmp_path):
    path = tmp_path / "source.bin"
    path.write_bytes(b"wrong bytes")
    spec = acquire.SourceSpec(
        key="test-pinned",
        family="test",
        url="https://example.invalid/source.bin",
        relative_path="source.bin",
        product_id="test",
        expected_sha256=_sha(b"right bytes"),
    )

    assert not acquire._verified_existing(path, spec, {})
    with pytest.raises(ValueError, match="SHA-256"):
        acquire._validated_payload(path, spec)


def test_safe_extract_verifies_and_repairs_every_member(tmp_path, monkeypatch):
    sources = tmp_path / "sources"
    sources.mkdir()
    monkeypatch.setattr(acquire, "SOURCES_DIR", sources)
    archive = sources / "archive.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("nested/a.txt", b"authoritative member")
        zf.writestr("b.txt", b"second member")

    destination = sources / "extracted"
    record = acquire._safe_extract_zip(archive, destination)
    assert record["members"]["nested/a.txt"]["sha256"] == _sha(b"authoritative member")

    (destination / "nested/a.txt").write_bytes(b"tampered")
    (destination / "injected.txt").write_bytes(b"not in archive")
    repaired = acquire._safe_extract_zip(archive, destination)
    assert (destination / "nested/a.txt").read_bytes() == b"authoritative member"
    assert not (destination / "injected.txt").exists()
    assert repaired["members"] == acquire._verify_zip_extraction(archive, destination)


def test_safe_extract_rejects_traversal(tmp_path, monkeypatch):
    sources = tmp_path / "sources"
    sources.mkdir()
    monkeypatch.setattr(acquire, "SOURCES_DIR", sources)
    archive = sources / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", b"no")

    with pytest.raises(ValueError, match="unsafe ZIP member"):
        acquire._safe_extract_zip(archive, sources / "extracted")
    assert not (sources / "escape.txt").exists()


def test_ingest_rejects_stale_source_manifest_schema(tmp_path, monkeypatch):
    manifest = tmp_path / "source_manifest.json"
    manifest.write_text(json.dumps({"schema_version": 1, "data_mode": "real-source-products"}))
    monkeypatch.setattr(ingest, "SOURCE_MANIFEST", str(manifest))

    with pytest.raises(ValueError, match="schema is stale"):
        ingest._validated_source_manifest()
