"""Guards on the scientific prose: description accuracy and overclaim control.

The pipeline's own runtime already fails closed on false *machine* claims (see
tests/test_runtime_hardening.py). These tests guard the human-readable *narrative*
in the docs so that a well-meaning edit cannot reintroduce a physically wrong
description or an inference stronger than the evidence supports.

v2.0.0 science facts enforced here:
  - magnetic target is surface-evaluated Tsunakawa/Wieczorek (not MA_GDOP as surface)
  - 30 km may appear as horizontal resolution; altitude framing only for superseded MA_GDOP
  - TiO2 <2 wt% detection limit disclosed
  - nested tuning is diagnostic; default XGBoost is binding
  - v1.0.0 superseded
  - preregistration timing cannot be independently verified
  - low-strength simulation grid (not "realistic regime" overclaim)
"""

import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _pptx_text(path: Path, prefix: str) -> str:
    """Return normalized visible text from a selected family of PPTX XML parts."""
    chunks = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.startswith(prefix) or not name.endswith(".xml"):
                continue
            root = ElementTree.fromstring(archive.read(name))
            chunks.extend(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
    return " ".join(" ".join(chunks).split())


# --------------------------------------------------------------------------- #
# Magnetic product and 30 km framing
# --------------------------------------------------------------------------- #

def test_30km_horizontal_resolution_ok_altitude_only_for_superseded_product():
    """30 km is horizontal grid resolution for the surface SVM.

    Altitude framing is allowed only when describing why MA_GDOP_001 is wrong /
    superseded — never as a description of the v2 magnetic target.
    """
    for name in ("Data-Sources.md", "Analysis-Plan.md", "README.md"):
        text = _read(name)
        for m in re.finditer(r"[^\n.]*30\s?km[^\n.]*", text):
            span = m.group(0)
            span_l = span.lower()
            # Negation / contrast ("not altitude", "grid resolution, not altitude") is fine.
            if re.search(r"not\s+altitude|grid resolution|horizontal", span_l):
                continue
            if "altitude" in span_l:
                assert re.search(
                    r"ma_gdop|superseded|wrongly|not a surface|must never|\bv1\b",
                    span_l,
                ), (
                    f"{name}: '30 km' + altitude without MA_GDOP/superseded framing: {span!r}"
                )
            else:
                assert re.search(
                    r"resolution|per ?deg|/deg|degree|equator|horizontal|grid|pixel",
                    span_l,
                ), (
                    f"{name}: '30 km' not framed as horizontal resolution: {span!r}"
                )


def test_magnetic_target_is_surface_tsunakawa_wieczorek():
    ds = _read("Data-Sources.md")
    readme = _read("README.md")
    assert re.search(r"Tsunakawa", ds) and re.search(r"Wieczorek|T2015_449", ds), (
        "Data-Sources.md must name Tsunakawa/Wieczorek surface magnetic product"
    )
    assert re.search(
        r"surface[-\s]?(evaluated|vector|SVM|magnetic)|evaluated at lunar mean radius",
        ds, re.I,
    ), "Data-Sources.md must describe the magnetic target as surface-evaluated"
    assert re.search(r"MA_GDOP|superseded", ds, re.I), (
        "Data-Sources.md must note MA_GDOP as superseded altitude product"
    )
    for name, text in (("README.md", readme), ("Data-Sources.md", ds)):
        # Must not present MA_GDOP as the current surface map.
        assert not re.search(
            r"magnetic target[^\n]*MA_GDOP_001(?![^\n]*(altitude|superseded))",
            text, re.I,
        ), f"{name} still presents MA_GDOP as the magnetic target"


def test_tio2_detection_limit_disclosed():
    for name in ("README.md", "Data-Sources.md", "Pre-Registration.md"):
        text = _read(name)
        assert re.search(r"2\s*wt%|detection limit|tio2_quantitative", text, re.I), (
            f"{name} must disclose TiO2 <2 wt% detection limit / tio2_quantitative"
        )
        assert re.search(r"non-quantitative|nonquantitative|below detection", text, re.I), (
            f"{name} must state below-detection cells are non-quantitative"
        )


def test_binding_estimator_is_default_xgb_nested_diagnostic():
    for name in ("README.md", "Pre-Registration.md", "Analysis-Plan.md"):
        text = _read(name)
        assert re.search(r"default-config XGBoost|default.?config XGBoost", text, re.I), (
            f"{name} must name default-config XGBoost as binding"
        )
        assert re.search(r"diagnostic only|nested.*diagnostic", text, re.I), (
            f"{name} must say nested tuning is diagnostic only"
        )


def test_v1_superseded_disclosed():
    for name in ("README.md", "References.md", "CITATION.cff", "pyproject.toml"):
        text = _read(name)
        assert "2.0.0" in text, f"{name} must be at version 2.0.0"
    readme = _read("README.md")
    assert re.search(r"v1\.0\.0 is superseded|superseded.*v1\.0\.0", readme, re.I)
    assert re.search(r"must not be cited|must not.*deposit", readme, re.I)


# --------------------------------------------------------------------------- #
# Overclaim detection
# --------------------------------------------------------------------------- #

_OVERCLAIM_PATTERNS = [
    r"mathematically\s+prove(?:s|n|d)?",
    r"\bproves\s+that\b",
    r"\bdefinitively\b",
    r"\bconclusively\s+prove",
    r"\birrefutabl",
]


def test_readme_does_not_overclaim_the_negative_result():
    readme = _read("README.md")
    assert "negative_result_may_be_underpowered = true" in readme, (
        "README dropped the explicit low-power caveat"
    )
    for pattern in _OVERCLAIM_PATTERNS:
        assert not re.search(pattern, readme, re.I), (
            f"README overclaims an underpowered negative via /{pattern}/"
        )
    assert not re.search(r"seven times stronger", readme, re.I), (
        "README must not use 'seven times stronger' claim wording"
    )


def test_readme_reports_the_fail_closed_inconclusive_status_faithfully():
    readme = _read("README.md")
    assert "INCONCLUSIVE_LOW_POWER" in readme
    assert re.search(r"`?H1_Supported`?\s+is\s+`?false`?", readme)
    assert not re.search(r"\bH1\s+is\s+(supported|confirmed)\b", readme, re.I)
    assert not re.search(r"\bconfirms?\s+the\s+(intermittent[- ]dynamo|H1)\b", readme, re.I)
    assert re.search(r"temporal.*mechanism.*(?:not|neither)|does not test.*temporal", readme, re.I | re.S)


def test_authoritative_sources_withdraw_scale_and_leakage_robustness_claims():
    for name in (
        "README.md", "Analysis-Plan.md", "Fallacy-Audit.md", "Data-Sources.md",
        "Pre-Registration.md", "Paper-and-Pitch/README.md",
        "Paper-and-Pitch/Research-Paper.typ", "Paper-and-Pitch/Exploratory-Robustness.md",
    ):
        text = _read(name)
        assert "Scale Discovery" not in text
        assert not re.search(r"robust to leakage|negative is robust", text, re.I)
        assert not re.search(r"\bsuggestive\b", text, re.I), (
            f"{name} calls a non-significant result 'suggestive'"
        )


def test_readme_reports_matched_h2_null_and_completed_power_without_adequacy():
    """README must quote the *committed artifact's* p-value, not a hand-typed one."""
    readme = _read("README.md")
    assert "Matched H2-only null" in readme
    calibration = json.loads(_read("Paper-and-Pitch/impact_antipode_benchmark_calibration.json"))
    artifact_p = calibration["result"]["empirical_p_value"]
    assert f"{artifact_p:.4f}"[:6] in readme, (
        f"README must quote the committed calibration p-value (~{artifact_p:.4f})"
    )
    assert re.search(r"fragile", readme, re.I), "H2-recovery fragility caveat missing"
    # Fold-matched pool may exhaust below the requested 100 (v2: 86 → resolution 1/87).
    assert re.search(r"1/87|86\+1|1/101", readme), (
        "empirical-p resolution disclosure missing (expect 86+1 → 1/87, or legacy 1/101)"
    )
    assert "positive_control_recovered" in readme
    assert re.search(r"`adequate_power`\s+is\s+false", readme)
    assert not re.search(r"injection-recovery power analysis[^\n]*result pending", readme, re.I)


def test_continuous_result_is_reported_as_descriptive_not_independent_evidence():
    readme = _read("README.md")
    metrics = json.loads(_read("Paper-and-Pitch/metrics.json"))
    cont = metrics.get("Transparent_Continuous_Analysis", {})
    # Prefer quoting the committed continuous ΔR² when present; otherwise require
    # the descriptive framing alone (v2 metrics may still be regenerating).
    delta = cont.get("tio2_increment_mean") or cont.get("full_minus_controls_r2_mean")
    if delta is not None:
        assert f"{float(delta):+.4f}"[:6] in readme or f"{float(delta):.4f}" in readme
    assert "no row-level p-value" in readme
    assert re.search(r"remains descriptive|descriptive because", readme, re.I)
    assert re.search(r"estimands separately|binary and continuous", readme, re.I)


def test_no_false_verifiable_registration_claim():
    """Prereg timing cannot be verified; forbid fake timestamp / rewrite claims."""
    readme = _read("README.md")
    prereg = _read("Pre-Registration.md")
    refs = _read("References.md")
    assert "Registered: 2026-07-16" not in readme and "Registered: 2026-07-16" not in prereg
    assert not re.search(r"git hash[^.\n]*pin", prereg, re.I)
    for doc in (readme, prereg, refs):
        assert "9f782b3" not in doc
        assert "no commits were rewritten" not in doc.lower()
    # Softened prereg honesty
    assert re.search(
        r"cannot be independently verified|timing cannot be verified|author-declared",
        readme, re.I,
    )
    assert re.search(
        r"cannot be independently verified|author-declared|timing cannot",
        prereg, re.I,
    )
    assert not re.search(r"ORIGINAL REGISTRATION PRESERVED", readme)
    assert not re.search(r"preserved verbatim", prereg, re.I)


def test_prevalence_is_expected_not_absolute_lower_bound():
    readme = _read("README.md")
    assert not re.search(r"absolute lower bound", readme, re.I)
    assert re.search(r"expected PR-AUC|no-skill|random", readme, re.I)


def test_machine_readable_power_and_benchmark_artifacts_fail_closed():
    power = json.loads(_read("Paper-and-Pitch/positive_control_power_analysis.json"))
    gate = power["Detection_Power"]
    assert gate["adequate_power"] is False
    assert gate["power_at_target_effect"] is None
    assert power["structural_diagnostics"]["structurally_limited"] is True
    assert any(row["strength"] == 0.0 for row in power["power_curve"])

    benchmark = json.loads(_read("Paper-and-Pitch/impact_antipode_benchmark_calibration.json"))
    assert benchmark["null"]["statistic_matches_observed_model"] is True
    assert benchmark["null"]["accepted_rotation_valid_fold_counts_all_equal_observed"] is True
    assert benchmark["features"] == ["dist_to_antipode_km"]
    # Docs must quote the committed calibration at artifact or rounded precision.
    null_mean = benchmark["result"]["null_mean_pr_auc"]
    null_95th = benchmark["result"]["null_95th_pr_auc"]
    p_value = benchmark["result"]["empirical_p_value"]
    quantities = [
        (f"{null_mean:.6f}", f"{null_mean:.4f}"),
        (f"{null_95th:.6f}", f"{null_95th:.4f}"),
        (f"{p_value:.6f}", f"{p_value:.3f}"),
    ]
    for name in (
        "README.md", "Analysis-Plan.md", "Fallacy-Audit.md",
        "Paper-and-Pitch/README.md", "Paper-and-Pitch/Research-Paper.typ",
    ):
        text = _read(name)
        for exact, rounded in quantities:
            assert exact in text or rounded in text, (
                f"{name} must quote the H2 calibration ({exact} or {rounded})"
            )


def test_pitch_deck_carries_v2_surface_product_framing():
    """Pitch.pptx must not retain v1 altitude-product / overclaim language."""
    pitch = ROOT / "Paper-and-Pitch" / "Pitch.pptx"
    slides = _pptx_text(pitch, "ppt/slides/")
    notes = _pptx_text(pitch, "ppt/notesSlides/")
    combined = slides + " " + notes
    assert re.search(r"Tsunakawa|surface|50\s*nT|detection", combined, re.I)
    assert "INCONCLUSIVE_LOW_POWER" in slides or "INCONCLUSIVE" in slides
    forbidden = (
        r"everything is pre-registered",
        r"H2 is at chance",
        r"robust negative",
        r"registered verdict:\s*H1 not supported",
        r"negative (?:is )?robust to leakage",
        r"69 automated tests",
        r"pins down where (?:the )?chemistry stops",
        r"MA_GDOP",
        r"seven times",
        r"\bsuggestive\b",
    )
    for pattern in forbidden:
        assert not re.search(pattern, combined, re.I), (
            f"Pitch.pptx contains a superseded claim: /{pattern}/"
        )


def test_h1_power_artifact_measures_the_hypothesis_under_test():
    """H1 arm must probe the low-strength simulation grid (not only elephant sizes)."""
    power = json.loads(_read("Paper-and-Pitch/h1_tio2_power_analysis.json"))
    assert power["control"] == "h1_tio2"
    strengths = [row["strength"] for row in power["power_curve"]]
    assert 0.0 in strengths, "zero-strength false-positive row missing"
    assert min(s for s in strengths if s > 0) <= 0.1, (
        "strength grid must extend down into the low-strength simulation grid"
    )
    assert power["minimum_detectable_effect"]["status"] in {
        "not_reached_on_tested_grid",
        "reached_on_tested_grid",
    }
    assert power["Detection_Power"]["adequate_power"] is False
    row = next(r for r in power["power_curve"] if r["strength"] == 1.0)
    measured = row["spatially_robust_detection_probability"]
    assert f"{measured:.3f}" in _read("README.md"), (
        f"README must report measured H1 power {measured:.3f} at the declared target"
    )
    readme = _read("README.md")
    assert re.search(r"low-strength simulation|far above", readme, re.I), (
        "README must not overclaim the strength-1.0 synthetic scenario as realism"
    )


def test_declared_target_effect_is_documented_not_wired_post_hoc():
    prereg = _read("Pre-Registration.md")
    assert "A8" in prereg and "latent strength" in prereg and "0.400" in prereg
    readme = _read("README.md")
    assert re.search(r"demonstrated rather than asserted|demonstrated, not asserted", readme)


def test_h2_low_strength_extension_shows_no_low_strength_grid_power():
    """H2 arm's 90%-power headline applies only to very large injected effects."""
    ext = json.loads(_read("Paper-and-Pitch/h2_antipode_low_strength_extension.json"))
    assert ext["control"] == "h2_antipode"
    strengths = [row["strength"] for row in ext["power_curve"]]
    assert 0.0 in strengths and max(strengths) <= 0.3
    assert all(
        row["spatially_robust_detection_probability"] < 0.5
        for row in ext["power_curve"]
    ), "no low-strength-grid strength may approach target power"
    assert ext["minimum_detectable_effect"]["status"] == "not_reached_on_tested_grid"
    # README must disclose that low-strength injected scores stay above observed
    # without claiming a demonstrated realistic regime.
    assert re.search(r"0\.\d{2,3}", _read("README.md"))
    assert re.search(r"low-strength|far above|not demonstrated realism", _read("README.md"), re.I)


def test_learning_project_and_llm_disclosure_is_prominent():
    readme = _read("README.md")
    assert re.search(r"\blearning project\b", readme, re.I)
    assert re.search(r"\bLLMs?\b|large language model", readme)
    assert re.search(r"not\s+(professional|peer\s+reviewed)", readme, re.I)
    assert re.search(r"Jack Wu|lemoon01110", readme)
    paper = _read("Paper-and-Pitch/Research-Paper.typ")
    assert re.search(r"\blearning project\b", paper, re.I)
    assert re.search(r"\bLLM", paper)
    assert re.search(r"Jack Wu|orcid\.org/0009-0004-1710-9018", paper, re.I)


def test_mechanism_vs_mappability_distinction_is_prominent():
    readme = _read("README.md")
    assert "What this does and doesn't show" in readme
    assert re.search(r"failure to detect is not evidence of absence", readme, re.I)
    assert re.search(r"map[- ]?proxy", readme, re.I)
    assert re.search(
        r"radiogenic melting|core.?mantle boundary|ilmenite",
        readme, re.I,
    ), "README must state the Nichols CMB radiogenic-melting mechanism"
    assert not re.search(
        r"(?<![Nn]ot )(?<!\()simply continued sinking|sinking Ti-rich cumulates perturb",
        readme,
    ), "README must not present sinking-only as the Nichols mechanism"
    for name in ("README.md", "Paper-and-Pitch/Research-Paper.typ",
                 "Paper-and-Pitch/README.md"):
        assert "completely decoupled" not in _read(name).lower()


def test_author_credit_and_orcid():
    citation = _read("CITATION.cff")
    assert "Jack" in citation and "Wu" in citation
    assert "0009-0004-1710-9018" in citation
    assert "2.0.0" in citation
    assert "Shannon L." in citation or "Shannon L. Harrel" in _read("References.md")
