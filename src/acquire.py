"""Reproducible acquisition of the authoritative lunar source products.

The canonical GeoTIFFs consumed by the model are *derived* data.  This module
downloads the immutable/native products into ``data/raw/sources`` and writes a
machine-readable manifest containing the resolved URL, byte size and SHA-256 of
every file.  Downloads are atomic (``.part`` files), resumable, and a failed or
partial acquisition exits non-zero.

Run::

    python -m src.acquire all

The four product families can also be acquired independently with ``lroc``,
``grail``, ``usgs`` or ``jaxa``.  Archive files are retained alongside their
safe, deterministic extraction so the original institutional bytes are never
lost during conversion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
import urllib.error
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Sequence

from . import config


SOURCES_DIR = Path(config.RAW_DIR) / "sources"
SOURCE_MANIFEST = SOURCES_DIR / "source_manifest.json"

LROC_BASE = (
    "https://pds.lroc.asu.edu/data/LRO-L-LROC-5-RDR-V1.0/"
    "LROLRC_2001/DATA/SDP/WAC_TIO2"
)
LROC_TILES = (
    "WAC_TIO2_E350N0450", "WAC_TIO2_E350N1350",
    "WAC_TIO2_E350N2250", "WAC_TIO2_E350N3150",
    "WAC_TIO2_E350S0450", "WAC_TIO2_E350S1350",
    "WAC_TIO2_E350S2250", "WAC_TIO2_E350S3150",
)

# Exact bytes used by the canonical analysis.  Pinning every institutional
# payload closes a subtle first-run gap: an arbitrary pre-existing file must
# never be accepted merely because no earlier manifest exists yet.
PINNED_SHA256: Dict[str, str] = {
    "grail-bouguer-geotiff": "1780b1b756135749ea9478dce793a05caaf94003b545b8a4514f618a00d9013d",
    "grail-bouguer-label": "fbf5f97612607d561d7e5efc307d19d4342259140d852b7f2103fef87664d084",
    "grail-thickness-archive": "4ea89cac2564f666c0eed5300c6d4852b43c284d46f80631d0bdd5710353ad2c",
    "tsunakawa-wieczorek-sh": "4db0b77b3863f38d6fb6e62c5c1116bf7123b77c5aad65df7dae598714edd655",
    "lroc-WAC_TIO2_E350N0450.IMG": "71987000fce8d03f49d8020b8c9dddefe293cd17988359d4c630f6b05db0e499",
    "lroc-WAC_TIO2_E350N0450.xml": "b57bb10305ae852c044e7f8b46586a3fbe5cb6c697040b30d5a7aaf3d495106d",
    "lroc-WAC_TIO2_E350N1350.IMG": "f02bd49f8fd2281499b2f5d10aa0639a81e4cf4893345324afd8442a1bbebaf5",
    "lroc-WAC_TIO2_E350N1350.xml": "ed0fce5608c5cc1abac751ced5a1d329d2818ec5f79d92f44920a3113bfcf569",
    "lroc-WAC_TIO2_E350N2250.IMG": "031b1078163608b6b3472284e92a4016c7b3ab845d09e6e8e5758f19d8feb45c",
    "lroc-WAC_TIO2_E350N2250.xml": "dd98454dcd15dd73f18687ceb90346f4773f722e3fd3f6c7c41e97d5a2af7ff1",
    "lroc-WAC_TIO2_E350N3150.IMG": "2ee61c98dee1b0afd2f5a99c2e45696cbc2ff2e8bdc9da1ad2babd8b5e7e4dbf",
    "lroc-WAC_TIO2_E350N3150.xml": "5d9928b8f0d748fb8f71fc49306a26c64c6fcbff2aaefbd8367cf29e7b3712a9",
    "lroc-WAC_TIO2_E350S0450.IMG": "4a7ad0962328f07eb2495af72f4925c71171ffee47393d4542269558af622c5b",
    "lroc-WAC_TIO2_E350S0450.xml": "e13c839f65e83a49383951630b0dc18d32a03f79c5f630014ddc47777e4ba0fb",
    "lroc-WAC_TIO2_E350S1350.IMG": "0e0ef62d02b772fdb620e7ea7557a26b2b604fab14d172e32a45a3f8c00bc8d7",
    "lroc-WAC_TIO2_E350S1350.xml": "618ae9b9cebd07feb1b5d0d4639ef55c2e0278ac109698feea16b9f321cd628f",
    "lroc-WAC_TIO2_E350S2250.IMG": "94772a818f1c7e32249bebab77f0a9e6b65556e583d88ed08ff129adeab324a2",
    "lroc-WAC_TIO2_E350S2250.xml": "998ab26d96322f4ced0851546e6d85013776e358b59a1d09463761be72489275",
    "lroc-WAC_TIO2_E350S3150.IMG": "7db0925d9b087a9ba64ae01206b989ffb6ae8565fc1043d034b8998b95cd7092",
    "lroc-WAC_TIO2_E350S3150.xml": "346b29240b3bfe01ab042ce3178cca4093b3f17fb6b7ca80f9ffa7529ec7410e",
    "lroc-readme": "5d08ae25a439b23eadccb0fd0fcfbf89a6584506f30eb8544f51bd1bd7282292",
    "usgs-geology-v2": "f3ec29803c1ad3b8c41a7fff3e9339bd66f9fbb8f63e30f13c52561b8d5559a1",
}


@dataclass(frozen=True)
class SourceSpec:
    """One pinned institutional file and its local staging path."""

    key: str
    family: str
    url: str
    relative_path: str
    product_id: str
    expected_size: Optional[int] = None
    expected_md5: Optional[str] = None
    expected_sha256: Optional[str] = None


def _specs() -> List[SourceSpec]:
    specs: List[SourceSpec] = []
    for stem in LROC_TILES:
        for suffix in (".IMG", ".xml"):
            name = stem + suffix
            specs.append(SourceSpec(
                key=f"lroc-{name}", family="lroc", url=f"{LROC_BASE}/{name}",
                relative_path=f"lroc_wac_tio2/{name}",
                product_id="LRO-L-LROC-5-RDR-V1.0/LROLRC_2001 WAC_TIO2",
            ))
    specs.append(SourceSpec(
        key="lroc-readme", family="lroc", url=f"{LROC_BASE}/WAC_TIO2_README.TXT",
        relative_path="lroc_wac_tio2/WAC_TIO2_README.TXT",
        product_id="LRO-L-LROC-5-RDR-V1.0/LROLRC_2001 WAC_TIO2",
    ))

    specs.append(SourceSpec(
        key="tsunakawa-wieczorek-sh", family="magnetic",
        url="https://zenodo.org/records/3873648/files/T2015_449.sh.gz?download=1",
        relative_path="tsunakawa_svm/T2015_449.sh.gz",
        product_id="Wieczorek T2015_449 SH expansion of Tsunakawa et al. 2015 SVM",
        expected_size=2_319_052,
        expected_md5="a332b1210761855b9bbf85215ff28a41",
        expected_sha256=PINNED_SHA256["tsunakawa-wieczorek-sh"],
    ))

    pds_grail = (
        "https://pds-geosciences.wustl.edu/grail/"
        "grail-l-lgrs-5-rdr-v1/grail_1001/extras/geotiff"
    )
    specs.extend([
        SourceSpec(
            key="grail-bouguer-geotiff", family="grail",
            url=f"{pds_grail}/gggrx_1200a_boug_l180.tif",
            relative_path="grail/gggrx_1200a_boug_l180.tif",
            product_id="GRAIL GRGM1200A Bouguer gravity disturbance L=180",
        ),
        SourceSpec(
            key="grail-bouguer-label", family="grail",
            url=(
                "https://pds-geosciences.wustl.edu/grail/"
                "grail-l-lgrs-5-rdr-v1/grail_1001/rsdmap/"
                "gggrx_1200a_boug_l180.lbl"
            ),
            relative_path="grail/gggrx_1200a_boug_l180.lbl",
            product_id="GRAIL GRGM1200A Bouguer gravity disturbance L=180",
        ),
        SourceSpec(
            key="grail-thickness-archive", family="grail",
            url=(
                "https://zenodo.org/records/997347/files/"
                "GRAILCrustalThicknessArchive.zip?download=1"
            ),
            relative_path="archives/GRAILCrustalThicknessArchive.zip",
            product_id="GRAIL Crustal Thickness Archive v1 (Zenodo 997347)",
            expected_size=96_142_347,
            expected_md5="88467d4cf4960ab7416e36a79d4f2da7",
        ),
    ])

    specs.append(SourceSpec(
        key="usgs-geology-v2", family="usgs",
        url=(
            "https://asc-astropedia.s3.us-west-2.amazonaws.com/Moon/Geology/"
            "Unified_Geologic_Map_of_the_Moon_GIS_v2.zip"
        ),
        relative_path="archives/Unified_Geologic_Map_of_the_Moon_GIS_v2.zip",
        product_id="USGS Unified Geologic Map of the Moon 1:5M GIS v2 (2020)",
        expected_size=224_413_040,
    ))
    missing_pins = [spec.key for spec in specs if spec.key not in PINNED_SHA256]
    if missing_pins:
        raise RuntimeError(f"source specifications lack pinned SHA-256 values: {missing_pins}")
    return [
        SourceSpec(**{**asdict(spec), "expected_sha256": PINNED_SHA256[spec.key]})
        for spec in specs
    ]


SPECS: Sequence[SourceSpec] = tuple(_specs())

PRODUCTS: Dict[str, Dict[str, object]] = {
    "lroc_wac_tio2": {
        "institution": "NASA PDS LROC / Arizona State University",
        "version": "LRO-L-LROC-5-RDR-V1.0, volume LROLRC_2001",
        "dataset_doi_pds3": "10.17189/1520341",
        "bundle_doi_pds4": "10.17189/a6a1-mw73",
        "coverage": "70 S to 70 N; eight 70 x 90 degree equirectangular tiles",
        "native_unit": "TiO2 weight percent",
        "citation": (
            "Sato et al. (2017), Icarus 296, 216-238, "
            "doi:10.1016/j.icarus.2017.06.013"
        ),
    },
    "grail_bouguer": {
        "institution": "NASA PDS Geosciences / NASA GSFC PGDA",
        "version": "GRGM1200A Bouguer gravity disturbance, degree/order 180",
        "native_unit": "mGal",
        "citation": (
            "Lemoine et al. (2014), doi:10.1002/2014GL060027; "
            "Goossens et al. (2016), LPSC abstract 1484"
        ),
    },
    "grail_crustal_thickness": {
        "institution": "GRAIL / Zenodo",
        "version": "GRAIL Crustal Thickness Archive v1",
        "doi": "10.5281/zenodo.997347",
        "native_unit": "km",
        "citation": "Wieczorek et al. (2013), Science 339, doi:10.1126/science.1231530",
    },
    "usgs_geology": {
        "institution": "USGS Astrogeology Science Center",
        "version": "Unified Geologic Map of the Moon 1:5M, GIS version 2, 2020-03-03",
        "license": "CC0 (citation requested)",
        "citation": "Fortezzo, Spudis & Shannon L. Harrel (2020), LPSC abstract 2760",
    },
    "tsunakawa_svm": {
        "institution": "Zenodo / Tsunakawa et al. 2015 surface SVM",
        "version": "Wieczorek T2015_449.sh.gz (degree/order 449)",
        "doi": "10.5281/zenodo.3873648",
        "native_unit": "nT (surface-evaluated |B|)",
        "citation": (
            "Tsunakawa et al. (2015), doi:10.1002/2014JE004785; "
            "Wieczorek SH model, doi:10.5281/zenodo.3873648 "
            "(expansion of globalSVM20150511/LunarSVM_000_02_v01.dat)"
        ),
        "note": (
            "Supersedes v1.0.0's JAXA MA_GDOP_001, which is a 30 km altitude "
            "grid and must not be described as a surface map."
        ),
    },
}


def _hash(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verified_existing(path: Path, spec: SourceSpec, previous: Dict[str, object]) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    size = path.stat().st_size
    if spec.expected_size is not None and size != spec.expected_size:
        return False
    if spec.expected_md5 and _hash(path, "md5") != spec.expected_md5:
        return False
    sha256 = _hash(path)
    if spec.expected_sha256 and sha256 != spec.expected_sha256:
        return False
    old_sha = previous.get("sha256") if previous else None
    if old_sha and sha256 != old_sha:
        return False
    # Size alone is not provenance.  A first-run local file is reusable only
    # when code pins a cryptographic digest; otherwise it must be downloaded.
    return bool(spec.expected_sha256 or old_sha)


def _validated_payload(path: Path, spec: SourceSpec) -> Dict[str, object]:
    """Hash a payload and enforce all code-pinned expectations."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{spec.relative_path}: payload is not a regular file")
    size = path.stat().st_size
    md5 = _hash(path, "md5")
    sha256 = _hash(path)
    if spec.expected_size is not None and size != spec.expected_size:
        raise ValueError(
            f"{spec.relative_path}: size {size:,} != pinned {spec.expected_size:,}"
        )
    if spec.expected_md5 and md5 != spec.expected_md5:
        raise ValueError(f"{spec.relative_path}: MD5 {md5} != pinned {spec.expected_md5}")
    if spec.expected_sha256 and sha256 != spec.expected_sha256:
        raise ValueError(
            f"{spec.relative_path}: SHA-256 {sha256} != pinned {spec.expected_sha256}"
        )
    return {"size_bytes": size, "md5": md5, "sha256": sha256}


def _download(spec: SourceSpec, force: bool, previous: Dict[str, object]) -> Dict[str, object]:
    destination = SOURCES_DIR / spec.relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not force and _verified_existing(destination, spec, previous):
        print(f"[acquire] verified {spec.relative_path}")
    else:
        part = destination.with_name(destination.name + ".part")
        for attempt in range(1, 4):
            try:
                start = part.stat().st_size if part.exists() else 0
                headers = {"User-Agent": "lunar-titanium-magnetism-real-data-ingest/1.0"}
                if start:
                    headers["Range"] = f"bytes={start}-"
                req = urllib.request.Request(spec.url, headers=headers)
                with urllib.request.urlopen(req, timeout=120) as response:
                    status = getattr(response, "status", 200)
                    append = bool(start and status == 206)
                    if start and not append:
                        start = 0
                    mode = "ab" if append else "wb"
                    total = response.headers.get("Content-Length")
                    total_text = f"/{int(total) + start:,}" if total else ""
                    print(f"[acquire] {spec.relative_path}: {start:,}{total_text} bytes")
                    with part.open(mode) as out:
                        shutil.copyfileobj(response, out, length=8 * 1024 * 1024)
                # Validate the temporary payload before promotion.  A failed
                # forced refresh therefore cannot overwrite a known-good file.
                _validated_payload(part, spec)
                os.replace(part, destination)
                break
            except ValueError as exc:
                part.unlink(missing_ok=True)
                if attempt == 3:
                    raise
                print(f"[acquire] retry {attempt}/3 for {spec.relative_path}: {exc}")
                time.sleep(2 ** attempt)
            except (OSError, urllib.error.URLError) as exc:
                if attempt == 3:
                    raise RuntimeError(f"failed to download {spec.url}: {exc}") from exc
                print(f"[acquire] retry {attempt}/3 for {spec.relative_path}: {exc}")
                time.sleep(2 ** attempt)

    payload = _validated_payload(destination, spec)
    return {
        **asdict(spec),
        "resolved_path": str(destination.relative_to(SOURCES_DIR)),
        **payload,
    }


def _validated_member_path(root: Path, member_name: str) -> Path:
    """Resolve one POSIX ZIP member without permitting an escape."""
    posix = PurePosixPath(member_name)
    if posix.is_absolute() or ".." in posix.parts or "\\" in member_name:
        raise ValueError(f"unsafe ZIP member: {member_name!r}")
    candidate = root / Path(*posix.parts)
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"unsafe ZIP member: {member_name!r}")
    return candidate


def _verify_zip_extraction(archive: Path, destination: Path) -> Dict[str, Dict[str, object]]:
    """Bind every extracted regular file byte-for-byte to its pinned ZIP member."""
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError(f"extraction is not a regular directory: {destination}")
    root = destination.resolve()
    records: Dict[str, Dict[str, object]] = {}
    expected_names = set()
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            member = _validated_member_path(root, info.filename)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"ZIP symlink is not allowed: {info.filename!r}")
            if info.is_dir():
                continue
            normalized_name = PurePosixPath(info.filename).as_posix()
            if normalized_name in expected_names:
                raise ValueError(f"duplicate ZIP member: {info.filename!r}")
            expected_names.add(normalized_name)
            if member.is_symlink() or not member.is_file():
                raise ValueError(f"extracted member missing/not regular: {info.filename!r}")
            if member.stat().st_size != info.file_size:
                raise ValueError(f"extracted member size changed: {info.filename!r}")
            archive_digest = hashlib.sha256()
            with zf.open(info) as src:
                for block in iter(lambda: src.read(8 * 1024 * 1024), b""):
                    archive_digest.update(block)
            extracted_sha = _hash(member)
            if extracted_sha != archive_digest.hexdigest():
                raise ValueError(f"extracted member bytes changed: {info.filename!r}")
            records[normalized_name] = {
                "size_bytes": info.file_size,
                "sha256": extracted_sha,
            }

    marker_name = ".extracted_from_sha256"
    actual_names = set()
    for path in destination.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlink in extracted tree: {path.relative_to(destination)}")
        if path.is_file() and path != destination / marker_name:
            actual_names.add(path.relative_to(destination).as_posix())
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        raise ValueError(f"extracted member set changed (missing={missing}, extra={extra})")
    return dict(sorted(records.items()))


def _safe_extract_zip(archive: Path, destination: Path) -> Dict[str, object]:
    """Safely extract and cryptographically bind every member to the archive."""
    archive_sha = _hash(archive)
    marker = destination / ".extracted_from_sha256"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == archive_sha:
        try:
            members = _verify_zip_extraction(archive, destination)
        except ValueError as exc:
            print(f"[extract] existing tree changed ({exc}); rebuilding")
        else:
            print(f"[extract] verified {destination.relative_to(SOURCES_DIR)}")
            return {
                "archive_sha256": archive_sha,
                "path": str(destination.relative_to(SOURCES_DIR)),
                "members": members,
            }

    staging = destination.with_name(destination.name + ".extracting")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    root = staging.resolve()
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            _validated_member_path(root, info.filename)
            # Unix mode in the upper 16 bits; 0o120000 denotes a symlink.
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"ZIP symlink is not allowed: {info.filename!r}")
        zf.extractall(staging)
    (staging / ".extracted_from_sha256").write_text(archive_sha + "\n", encoding="utf-8")
    members = _verify_zip_extraction(archive, staging)
    if destination.exists():
        shutil.rmtree(destination)
    os.replace(staging, destination)
    print(f"[extract] {archive.name} -> {destination.relative_to(SOURCES_DIR)}")
    return {
        "archive_sha256": archive_sha,
        "path": str(destination.relative_to(SOURCES_DIR)),
        "members": members,
    }


def _verify_lroc_pds4_pairs(records: List[Dict[str, object]]) -> None:
    """Use each authoritative PDS4 label's size/MD5 to verify its IMG payload."""
    by_path = {str(record["relative_path"]): record for record in records}
    namespace = {"pds": "http://pds.nasa.gov/pds4/pds/v1"}
    for stem in LROC_TILES:
        xml_rel = f"lroc_wac_tio2/{stem}.xml"
        img_rel = f"lroc_wac_tio2/{stem}.IMG"
        label_path = SOURCES_DIR / xml_rel
        image_path = SOURCES_DIR / img_rel
        if not label_path.is_file() or not image_path.is_file():
            continue
        root = ET.parse(label_path).getroot()
        file_node = root.find(".//pds:File_Area_Observational/pds:File", namespace)
        if file_node is None:
            raise ValueError(f"{xml_rel}: missing PDS4 File_Area_Observational/File")
        labelled_name = file_node.findtext("pds:file_name", namespaces=namespace)
        labelled_size = file_node.findtext("pds:file_size", namespaces=namespace)
        labelled_md5 = file_node.findtext("pds:md5_checksum", namespaces=namespace)
        if labelled_name != image_path.name or not labelled_size or not labelled_md5:
            raise ValueError(f"{xml_rel}: incomplete or mismatched payload metadata")
        actual_size = image_path.stat().st_size
        actual_md5 = _hash(image_path, "md5")
        if actual_size != int(labelled_size) or actual_md5 != labelled_md5.lower():
            raise ValueError(
                f"{img_rel}: does not match its PDS4 label "
                f"(size {actual_size}/{labelled_size}, MD5 {actual_md5}/{labelled_md5})"
            )
        record = by_path.get(img_rel)
        if record is not None:
            record["label_verified_size_bytes"] = int(labelled_size)
            record["label_verified_md5"] = labelled_md5.lower()


def _load_previous() -> Dict[str, Dict[str, object]]:
    if not SOURCE_MANIFEST.is_file():
        return {}
    try:
        data = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
        return {item["key"]: item for item in data.get("files", [])}
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return {}


def acquire(families: Iterable[str], force: bool = False, workers: int = 4) -> Path:
    selected = set(families)
    if "all" in selected:
        selected = {"lroc", "grail", "usgs", "magnetic"}
    # Accept legacy alias "jaxa" as "magnetic" during the v2 product switch.
    selected = {"magnetic" if name == "jaxa" else name for name in selected}
    unknown = selected - {"lroc", "grail", "usgs", "magnetic"}
    if unknown:
        raise ValueError(f"unknown acquisition families: {sorted(unknown)}")
    specs = [spec for spec in SPECS if spec.family in selected]
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    previous = _load_previous()

    records: List[Dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(_download, spec, force, previous.get(spec.key, {})): spec
            for spec in specs
        }
        for future in as_completed(futures):
            records.append(future.result())

    # Preserve verified records from families not requested in this incremental run.
    selected_keys = {spec.key for spec in specs}
    specs_by_key = {spec.key: spec for spec in SPECS}
    for key, record in previous.items():
        if key not in selected_keys:
            spec = specs_by_key.get(key)
            if spec is None:
                continue
            path = SOURCES_DIR / spec.relative_path
            if _verified_existing(path, spec, record):
                records.append({
                    **asdict(spec),
                    "resolved_path": str(path.relative_to(SOURCES_DIR)),
                    **_validated_payload(path, spec),
                })

    _verify_lroc_pds4_pairs(records)

    extracted: Dict[str, object] = {}
    thickness = SOURCES_DIR / "archives/GRAILCrustalThicknessArchive.zip"
    if thickness.is_file():
        extracted["grail_crustal_thickness"] = _safe_extract_zip(
            thickness, SOURCES_DIR / "grail/crustal_thickness_archive"
        )
    geology = SOURCES_DIR / "archives/Unified_Geologic_Map_of_the_Moon_GIS_v2.zip"
    if geology.is_file():
        extracted["usgs_geology"] = _safe_extract_zip(
            geology, SOURCES_DIR / "usgs/unified_geologic_map_v2"
        )

    manifest = {
        "schema_version": 2,
        "data_mode": "real-source-products",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "products": PRODUCTS,
        "files": sorted(records, key=lambda item: str(item["key"])),
        "extracted_archives": extracted,
    }
    tmp = SOURCE_MANIFEST.with_suffix(".json.part")
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, SOURCE_MANIFEST)
    print(f"[acquire] source manifest -> {SOURCE_MANIFEST}")
    return SOURCE_MANIFEST


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Acquire authoritative real lunar datasets")
    parser.add_argument(
        "family", nargs="+", choices=["all", "lroc", "grail", "usgs", "magnetic", "jaxa"],
        help="source family/families to download (jaxa is a legacy alias for magnetic)",
    )
    parser.add_argument("--force", action="store_true", help="redownload even verified files")
    parser.add_argument("--workers", type=int, default=4, help="parallel download workers")
    args = parser.parse_args(argv)
    acquire(args.family, force=args.force, workers=args.workers)


if __name__ == "__main__":
    main()
