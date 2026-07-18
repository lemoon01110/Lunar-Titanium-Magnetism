"""Guards on the scientific prose: description accuracy and overclaim control.

The pipeline's own runtime already fails closed on false *machine* claims (see
tests/test_runtime_hardening.py). These tests guard the human-readable *narrative*
in the docs so that a well-meaning edit cannot reintroduce a physically wrong
description or an inference stronger than the evidence supports.
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
# 9. Scientific-description checks (30 km resolution vs. "surface"/altitude)
# --------------------------------------------------------------------------- #

def test_30km_is_framed_as_horizontal_resolution_not_altitude():
    """"30 km" is the ground footprint of a 1-degree pixel at the equator, not an
    observation altitude. The magnetic product is a *surface* vector map, so the
    docs must never present 30 km as an altitude."""
    for name in ("Data-Sources.md", "Analysis-Plan.md"):
        text = _read(name)
        for m in re.finditer(r"[^\n.]*30\s?km[^\n.]*", text):
            span = m.group(0).lower()
            # Wherever 30 km appears it must be about resolution/degree/equator...
            assert re.search(r"resolution|per ?deg|/deg|degree|equator", span), (
                f"{name}: '30 km' not framed as horizontal resolution: {span!r}"
            )
            # ...and must never be attached to the word 'altitude'.
            assert "altitude" not in span, (
                f"{name}: '30 km' incorrectly described as an altitude: {span!r}"
            )


def test_magnetic_target_is_described_as_a_surface_field():
    ds = _read("Data-Sources.md")
    assert re.search(
        r"surface[-\s]vector[-\s]map|surface\s+crustal\s+magnetic|surface\s+magnetic\s+map",
        ds, re.I,
    ), "Data-Sources.md must describe the magnetic target as a surface field (SVM)"
    # No document may claim the magnetic field was measured/continued at 30 km up.
    for name in ("README.md", "Data-Sources.md"):
        assert not re.search(r"30\s?km\s+(altitude|above|elevation)", _read(name), re.I), (
            f"{name} describes the surface magnetic field as if measured at 30 km altitude"
        )


# --------------------------------------------------------------------------- #
# 10. Overclaim detection: conclusions must match underpowered / null evidence
# --------------------------------------------------------------------------- #

# Absolute-certainty language that a possibly-underpowered negative cannot support.
_OVERCLAIM_PATTERNS = [
    r"mathematically\s+prove(?:s|n|d)?",
    r"\bproves\s+that\b",
    r"\bdefinitively\b",
    r"\bconclusively\s+prove",
    r"\birrefutabl",
]


def test_readme_does_not_overclaim_the_negative_result():
    readme = _read("README.md")
    # The result is explicitly flagged as possibly underpowered...
    assert "negative_result_may_be_underpowered = true" in readme, (
        "README dropped the explicit low-power caveat"
    )
    # ...so it must not simultaneously assert mathematical proof of no effect.
    for pattern in _OVERCLAIM_PATTERNS:
        assert not re.search(pattern, readme, re.I), (
            f"README overclaims an underpowered negative via /{pattern}/"
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
        # A non-significant subgroup mean must never be marketed as "suggestive".
        assert not re.search(r"\bsuggestive\b", text, re.I), (
            f"{name} calls a non-significant result 'suggestive'"
        )


def test_readme_reports_matched_h2_null_and_completed_power_without_adequacy():
    """README must quote the *committed artifact's* p-value, not a hand-typed one.

    Deriving the expected string from the frozen JSON keeps this guard from
    enshrining a Monte-Carlo draw: if the artifact is ever regenerated, the test
    tracks it instead of breaking on a stale magic constant."""
    readme = _read("README.md")
    assert "Matched H2-only null" in readme
    calibration = json.loads(_read("Paper-and-Pitch/impact_antipode_benchmark_calibration.json"))
    artifact_p = calibration["result"]["empirical_p_value"]
    assert f"{artifact_p:.4f}"[:6] in readme, (
        f"README must quote the committed calibration p-value (~{artifact_p:.4f})"
    )
    # The knife-edge nature of the recovery must be disclosed alongside it.
    assert re.search(r"fragile", readme, re.I), "H2-recovery fragility caveat missing"
    assert "1/101" in readme, "empirical-p resolution disclosure missing"
    assert "positive_control_recovered" in readme
    assert re.search(r"`adequate_power`\s+is\s+false", readme)
    assert not re.search(r"injection-recovery power analysis[^\n]*result pending", readme, re.I)


def test_continuous_result_is_reported_as_descriptive_not_independent_evidence():
    readme = _read("README.md")
    assert "+0.0121" in readme
    assert "no row-level p-value" in readme
    assert re.search(r"remains descriptive|descriptive because", readme, re.I)


def test_registration_limit_is_explicit():
    readme = _read("README.md")
    assert "no OSF/Zenodo registration" in readme
    assert "not externally verifiable" in readme


def test_machine_readable_power_and_benchmark_artifacts_fail_closed():
    power = json.loads(_read("Paper-and-Pitch/positive_control_power_analysis.json"))
    gate = power["Detection_Power"]
    assert gate["adequate_power"] is False
    assert gate["power_at_target_effect"] is None
    assert power["structural_diagnostics"]["structurally_limited"] is True
    assert power["structural_diagnostics"]["approx_effective_independent_regions"] == 1.0
    assert any(row["strength"] == 0.0 for row in power["power_curve"])

    benchmark = json.loads(_read("Paper-and-Pitch/impact_antipode_benchmark_calibration.json"))
    assert benchmark["null"]["statistic_matches_observed_model"] is True
    assert benchmark["null"]["observed_valid_fold_count"] == 5
    assert benchmark["null"]["accepted_rotation_valid_fold_counts_all_equal_observed"] is True
    assert benchmark["null"]["n_candidate_shifts_evaluated"] == 125
    assert benchmark["null"]["n_rejected_for_fold_count_mismatch"] == 12
    assert benchmark["result"]["recovered_above_matched_spatial_null"] is True
    assert benchmark["features"] == ["dist_to_antipode_km"]
    assert benchmark["result"]["null_mean_pr_auc"] == 0.03197020246622187
    assert benchmark["result"]["null_95th_pr_auc"] == 0.10683156558832459
    assert benchmark["result"]["empirical_p_value"] == 0.039603960396039604

    # Documents must quote the calibration consistently with the artifact —
    # either at full artifact precision or at resolution-honest display
    # precision (100 rotations resolve p only to ~1/101). Both accepted forms
    # are derived from the JSON so no magic constant can drift.
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


def test_pitch_slides_and_hidden_speaker_notes_match_the_amended_inference():
    pitch = ROOT / "Paper-and-Pitch" / "Pitch.pptx"
    slides = _pptx_text(pitch, "ppt/slides/")
    notes = _pptx_text(pitch, "ppt/notesSlides/")

    # The visible deck must carry the current status and matched-null results.
    assert "INCONCLUSIVE_LOW_POWER" in slides
    assert ".564356" in slides
    assert ".039604" in slides
    assert "Four stages" in slides
    assert "raw + 25/50/100 km" in slides
    assert "mapped mare-proxy" in slides
    assert "Whole-Moon" not in slides
    assert "derived validity mask" not in slides

    # Speaker notes are part of the published deck even though a PDF export hides them.
    # Guard the specific legacy claims and statistics removed by the 2026-07-17 amendment.
    forbidden = (
        r"everything is pre-registered",
        r"H2 is at chance",
        r"robust negative",
        r"registered verdict:\s*H1 not supported",
        r"negative (?:is )?robust to leakage",
        r"69 automated tests",
        r"pins down where (?:the )?chemistry stops",
        r"p\s*=\s*\.?61\b",
        r"0\.110149|0\.124159|0\.653465|0\.029445|0\.052181|0\.019802",
    )
    for pattern in forbidden:
        assert not re.search(pattern, notes, re.I), (
            f"Pitch.pptx contains a superseded claim in hidden speaker notes: /{pattern}/"
        )


def test_h1_power_artifact_measures_the_hypothesis_under_test():
    """The injection design must calibrate the H1 arm itself — not only the H2
    benchmark — and must probe the realistic score regime, not only strengths far
    beyond anything the real data shows."""
    power = json.loads(_read("Paper-and-Pitch/h1_tio2_power_analysis.json"))
    assert power["control"] == "h1_tio2"
    strengths = [row["strength"] for row in power["power_curve"]]
    assert 0.0 in strengths, "zero-strength false-positive row missing"
    assert min(s for s in strengths if s > 0) <= 0.1, (
        "strength grid must extend down into the realistic regime"
    )
    assert power["minimum_detectable_effect"]["status"] == "not_reached_on_tested_grid"
    assert power["Detection_Power"]["adequate_power"] is False
    # README must quote the measured power at the declared strength-1.0 target.
    row = next(r for r in power["power_curve"] if r["strength"] == 1.0)
    measured = row["spatially_robust_detection_probability"]
    assert f"{measured:.3f}" in _read("README.md"), (
        f"README must report measured H1 power {measured:.3f} at the declared target"
    )


def test_declared_target_effect_is_documented_not_wired_post_hoc():
    """Amendment A8 declares the target effect for interpretation and future runs;
    the machinery itself must remain unmodified (no fourth post-hoc rule change)."""
    prereg = _read("Pre-Registration.md")
    assert "A8" in prereg and "latent strength" in prereg and "0.400" in prereg
    readme = _read("README.md")
    assert re.search(r"demonstrated rather than asserted|demonstrated, not asserted", readme)


def test_h2_low_strength_extension_shows_no_realistic_regime_power():
    """The H2 arm's 90%-power headline applies only to elephant-sized effects; the
    committed extension must show the realistic regime is below target power, so
    that neither arm's sensitivity can be overquoted."""
    ext = json.loads(_read("Paper-and-Pitch/h2_antipode_low_strength_extension.json"))
    assert ext["control"] == "h2_antipode"
    strengths = [row["strength"] for row in ext["power_curve"]]
    assert 0.0 in strengths and max(strengths) <= 0.3
    assert all(
        row["spatially_robust_detection_probability"] < 0.5
        for row in ext["power_curve"]
    ), "no realistic-regime strength may approach target power"
    assert ext["minimum_detectable_effect"]["status"] == "not_reached_on_tested_grid"
    # README must temper the matched-null recovery with this regime context.
    assert "0.133–0.267" in _read("README.md")


def test_learning_project_and_llm_disclosure_is_prominent():
    """The author's request: the repo must be upfront that this is an independent
    learning project built with extensive LLM assistance — framing that manages
    reader expectations and cannot silently disappear in a future edit."""
    readme = _read("README.md")
    assert re.search(r"\blearning project\b", readme, re.I)
    assert re.search(r"\bLLMs?\b|large language model", readme)
    assert re.search(r"not\s+(professional|peer.reviewed)", readme, re.I)
    paper = _read("Paper-and-Pitch/Research-Paper.typ")
    assert re.search(r"\blearning project\b", paper, re.I)
    assert re.search(r"\bLLM", paper)


def test_mechanism_vs_mappability_distinction_is_prominent():
    """The author's framing must stay honest and visible: separate 'we did not
    test the temporal mechanism' from 'we found no usable surface map-proxy', and
    never sell the underpowered null as a disproof of physical decoupling."""
    readme = _read("README.md")
    assert "What this does and doesn't show" in readme
    assert re.search(r"failure to detect is not evidence of absence", readme, re.I)
    assert re.search(r"map[- ]?proxy", readme, re.I)
    # An underpowered null is never a proof of decoupling, in any authoritative doc.
    for name in ("README.md", "Paper-and-Pitch/Research-Paper.typ",
                 "Paper-and-Pitch/README.md"):
        assert "completely decoupled" not in _read(name).lower()
    # The deck carries the failure-to-detect framing and no longer says 'suggestive'.
    slides = _pptx_text(ROOT / "Paper-and-Pitch" / "Pitch.pptx", "ppt/slides/")
    assert "failure-to-detect" in slides
    assert "suggestive" not in slides.lower()
