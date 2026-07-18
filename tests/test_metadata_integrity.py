"""Repository-metadata integrity guards.

These tests protect the project's *claims about itself* -- citation metadata,
release/version consistency, dependency declarations, documentation links, and
the code/data licensing boundary -- rather than the scientific pipeline. They are
deliberately filesystem/VCS aware and read the real tracked files.
"""

import os
import re
import subprocess
from pathlib import Path, PurePosixPath

import pytest

try:  # tomllib is stdlib on >=3.11; requires-python is >=3.10
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on 3.10
    import tomli as tomllib  # type: ignore

yaml = pytest.importorskip("yaml", reason="PyYAML (a dev dependency) is required to parse CITATION.cff")

ROOT = Path(__file__).resolve().parents[1]

# The exact DOI set this repository vouches for in CITATION.cff. Freezing it turns
# any accidental edit (typo, dropped digit, wrong article) into a failing test.
VETTED_CFF_DOIS = {
    "10.1038/s41561-026-01929-y",   # Nichols et al. 2026 (H1)
    "10.1016/j.icarus.2007.08.023",  # Hood & Artemieva 2008 (H2)
    "10.1126/sciadv.adr7401",        # Narrett et al. 2025 (context)
    "10.1002/2014JE004785",          # Tsunakawa et al. 2015 (magnetic target)
    "10.1016/j.icarus.2017.06.013",  # Sato et al. 2017 (TiO2)
    "10.1126/science.1231530",       # Wieczorek et al. 2013 (GRAIL crust)
}

# CFF 1.2.0 reference object `type` values we actually use / allow.
ALLOWED_REFERENCE_TYPES = {"article", "data", "book", "report", "conference-paper", "proceedings"}

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'`)<>,]+")


def _norm_doi(doi: str) -> str:
    """DOIs are case-insensitive; strip trailing sentence punctuation."""
    return doi.rstrip(".,);").lower()


def _dois_in(text: str) -> set[str]:
    return {_norm_doi(d) for d in _DOI_RE.findall(text)}


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _load_cff() -> dict:
    return yaml.safe_load(_read("CITATION.cff"))


def _load_pyproject() -> dict:
    return tomllib.loads(_read("pyproject.toml"))


def _parse_requirement(line: str):
    """Return (canonical_name, specifier) for a requirement line, or None."""
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith("-"):
        return None
    m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)$", line)
    if not m:
        return None
    name = m.group(1).lower().replace("_", "-")
    return name, m.group(2).replace(" ", "")


def _requirements_map(name: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in _read(name).splitlines():
        parsed = _parse_requirement(raw)
        if parsed:
            out[parsed[0]] = parsed[1]
    return out


def _dep_list_map(deps: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for dep in deps:
        parsed = _parse_requirement(dep)
        if parsed:
            out[parsed[0]] = parsed[1]
    return out


def _git(*args) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _is_git_checkout() -> bool:
    return _git("rev-parse", "--is-inside-work-tree") is not None


def _case_sensitive_exists(rel: str) -> bool:
    """os.path.exists() is case-insensitive on some filesystems; walk each path
    component against the real directory listing to enforce exact case."""
    current = ROOT
    for part in PurePosixPath(rel).parts:
        try:
            entries = os.listdir(current)
        except (NotADirectoryError, FileNotFoundError):
            return False
        if part not in entries:
            return False
        current = current / part
    return True


# --------------------------------------------------------------------------- #
# 1. CFF schema, reference types, author completeness, vetted DOI snapshot
# --------------------------------------------------------------------------- #

def test_cff_has_valid_top_level_schema():
    cff = _load_cff()
    for key in ("cff-version", "message", "title", "authors", "version", "type", "license"):
        assert key in cff, f"CITATION.cff is missing required key: {key}"
    assert cff["cff-version"] == "1.2.0"
    assert cff["type"] == "software"
    assert isinstance(cff["authors"], list) and cff["authors"], "authors must be a non-empty list"


def test_cff_authors_are_identifiable():
    for author in _load_cff()["authors"]:
        identifiers = [author.get(k) for k in ("family-names", "given-names", "name", "alias")]
        assert any(v for v in identifiers), f"author has no identifying field: {author}"


def test_cff_reference_types_and_completeness():
    for ref in _load_cff().get("references", []):
        rtype = ref.get("type")
        assert rtype in ALLOWED_REFERENCE_TYPES, f"unexpected reference type: {rtype}"
        assert ref.get("title"), f"reference missing title: {ref}"
        authors = ref.get("authors")
        assert authors, f"reference missing authors: {ref}"
        for author in authors:
            assert author.get("family-names"), f"cited author missing family-names: {author}"


def test_cff_doi_snapshot_is_vetted():
    cff_dois = _dois_in(_read("CITATION.cff"))
    vetted = {_norm_doi(d) for d in VETTED_CFF_DOIS}
    assert cff_dois == vetted, (
        "CITATION.cff DOI set drifted from the vetted snapshot.\n"
        f"  added:   {sorted(cff_dois - vetted)}\n"
        f"  removed: {sorted(vetted - cff_dois)}"
    )


# --------------------------------------------------------------------------- #
# 2. Dataset citations vs supporting-paper citations (incl. products w/o DOI)
# --------------------------------------------------------------------------- #

def test_article_references_carry_a_doi():
    for ref in _load_cff().get("references", []):
        if ref.get("type") == "article":
            assert ref.get("doi"), f"peer-reviewed article without a DOI: {ref.get('title')}"


def test_data_products_without_doi_are_explicitly_documented():
    """A dataset citation may legitimately lack a DOI (e.g. a conference abstract
    or archive), but only if it says so via `notes`; it must never be silent."""
    for ref in _load_cff().get("references", []):
        if ref.get("type") != "data":
            continue
        if not ref.get("doi"):
            notes = (ref.get("notes") or "")
            assert re.search(r"abstract|archive|conference|LPSC", notes, re.I), (
                f"data product without DOI must justify it in notes: {ref.get('title')!r} "
                f"(notes={notes!r})"
            )


# --------------------------------------------------------------------------- #
# 3. Release claims vs actual git tags & version consistency
# --------------------------------------------------------------------------- #

def test_version_string_is_consistent_across_metadata():
    version = _load_cff()["version"]
    assert _load_pyproject()["project"]["version"] == version
    # References.md carries the human-readable citation, including the version.
    assert f"v{version}" in _read("References.md"), (
        f"References.md does not reference the declared release v{version}"
    )


def test_release_claim_is_backed_by_a_git_tag():
    if not _is_git_checkout():
        pytest.skip("not a git checkout (e.g. installed sdist); tag check not applicable")
    cff = _load_cff()
    if not cff.get("date-released"):
        pytest.skip("no date-released claim, so no released tag is required")
    version = cff["version"]
    tags = {t.strip() for t in (_git("tag", "--list") or "").splitlines() if t.strip()}
    assert f"v{version}" in tags or version in tags, (
        f"CITATION.cff claims a {cff['date-released']} release of v{version}, "
        f"but no matching git tag exists (tags: {sorted(tags) or 'none'})"
    )


# --------------------------------------------------------------------------- #
# 4. Citation consistency across CFF, README, References, Data-Sources
# --------------------------------------------------------------------------- #

def test_every_cff_doi_appears_in_the_bibliography():
    references = _dois_in(_read("References.md"))
    for doi in _dois_in(_read("CITATION.cff")):
        assert doi in references, f"CFF DOI {doi} is not present in References.md"


def test_data_source_dois_are_in_the_bibliography():
    references = _dois_in(_read("References.md"))
    for doi in _dois_in(_read("Data-Sources.md")):
        assert doi in references, f"Data-Sources.md DOI {doi} is not present in References.md"


# --------------------------------------------------------------------------- #
# 5. Product license / terms completeness
# --------------------------------------------------------------------------- #

def test_license_covers_code_and_disclaims_third_party_data():
    license_text = _read("LICENSE")
    assert license_text.lstrip().startswith("MIT License")
    assert _load_cff()["license"] == "MIT"
    assert _load_pyproject()["project"]["license"] == {"file": "LICENSE"}
    assert (ROOT / "LICENSE").exists()
    # The code license must not be mistaken for a data license.
    assert re.search(r"data", license_text, re.I), "LICENSE lacks the data-terms note"
    assert re.search(r"no third-party data", license_text, re.I), (
        "LICENSE must state that no third-party data are distributed"
    )
    assert "[MIT](LICENSE)" in _read("README.md")


# --------------------------------------------------------------------------- #
# 6. Dependency drift between requirements.txt and pyproject.toml
# --------------------------------------------------------------------------- #

def test_requirements_and_pyproject_do_not_drift():
    req = _requirements_map("requirements.txt")
    project = _load_pyproject()["project"]
    core = _dep_list_map(project.get("dependencies", []))
    optional: dict[str, str] = {}
    for group in project.get("optional-dependencies", {}).values():
        optional.update(_dep_list_map(group))
    pyproject_all = {**optional, **core}

    # Every runtime requirement must be declared somewhere in pyproject...
    for name, spec in req.items():
        assert name in pyproject_all, (
            f"{name} is in requirements.txt but missing from pyproject.toml"
        )
        assert pyproject_all[name] == spec, (
            f"version floor drift for {name}: requirements.txt={spec!r} "
            f"pyproject={pyproject_all[name]!r}"
        )
    # ...and every core pyproject dependency must be in requirements.txt.
    for name, spec in core.items():
        assert name in req, f"{name} is a core pyproject dependency but not in requirements.txt"
        assert req[name] == spec, (
            f"version floor drift for {name}: pyproject={spec!r} requirements.txt={req[name]!r}"
        )


def test_dev_requirements_align():
    dev = _requirements_map("requirements-dev.txt")
    pyproject_dev = _dep_list_map(
        _load_pyproject()["project"].get("optional-dependencies", {}).get("dev", [])
    )
    for name, spec in pyproject_dev.items():
        assert name in dev, f"{name} is in pyproject [dev] but not requirements-dev.txt"
        assert dev[name] == spec, f"dev floor drift for {name}: {spec!r} vs {dev[name]!r}"


# --------------------------------------------------------------------------- #
# 7. Broken / case-sensitive document links and stale renamed files
# --------------------------------------------------------------------------- #

_MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_relative_markdown_links_resolve_case_sensitively():
    problems = []
    for md in sorted(ROOT.glob("*.md")):
        for target in _MD_LINK_RE.findall(md.read_text(encoding="utf-8")):
            rel = target.split("#", 1)[0].strip().strip("`")
            if not rel or rel.startswith(("http://", "https://", "mailto:")):
                continue
            if not _case_sensitive_exists(rel):
                problems.append(f"{md.name} -> {target}")
    assert not problems, f"broken or wrong-case links: {problems}"


def test_no_stale_renamed_paths_remain():
    """The project was renamed away from `MoonResearch`/`DATA.md`; nothing tracked
    should still reference the old names."""
    stale = re.compile(r"MoonResearch|\bDATA\.md\b")
    offenders = []
    for path in ROOT.glob("*.md"):
        if stale.search(path.read_text(encoding="utf-8")):
            offenders.append(path.name)
    for extra in ("CITATION.cff", "pyproject.toml", "README.md"):
        if stale.search(_read(extra)):
            offenders.append(extra)
    assert not offenders, f"stale renamed-path references remain in: {sorted(set(offenders))}"


# --------------------------------------------------------------------------- #
# 8. Untracked-data and licensing boundaries
# --------------------------------------------------------------------------- #

def test_no_data_or_results_files_are_tracked():
    if not _is_git_checkout():
        pytest.skip("not a git checkout; cannot inspect tracked files")
    tracked = (_git("ls-files", "data", "results") or "").split()
    assert not tracked, f"data/results must never be committed, but git tracks: {tracked}"


def test_gitignore_excludes_generated_and_downloaded_data():
    gitignore = _read(".gitignore")
    for pattern in ("data/", "results/", "venv/"):
        assert pattern in gitignore, f".gitignore is missing {pattern!r}"
