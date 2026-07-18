"""
PDF report generator (fpdf2).

Uses the modern fpdf2 API (``text=`` / ``new_x`` / ``new_y``) and core fonts, so
it works on current fpdf2 without deprecation warnings. Text is kept ASCII
("TiO2", "x") to avoid font-embedding requirements.
"""

from __future__ import annotations

import json
import os

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from .inference import status_from_metrics


class ReportPDF(FPDF):
    """Small report-specific PDF class with unobtrusive page numbering."""

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, text=f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)


def _line(pdf: FPDF, text: str, size: int = 11, style: str = "") -> None:
    pdf.set_font("Helvetica", size=size, style=style)
    pdf.cell(0, 7, text=text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _para(pdf: FPDF, text: str, size: int = 11, style: str = "") -> None:
    pdf.set_font("Helvetica", size=size, style=style)
    pdf.multi_cell(0, 6, text=text)
    pdf.ln(2)


def _ensure_space(pdf: FPDF, height_mm: float) -> None:
    """Keep a section heading with a useful amount of its following content."""
    if pdf.get_y() + height_mm > pdf.h - pdf.b_margin:
        pdf.add_page()


def report_inference_status(metrics: dict) -> str:
    """Re-derive the fail-closed status from the metrics (single source of truth in
    src/inference.py). Defensive: catches a hand-edited/inconsistent Inference_Status."""
    return status_from_metrics(metrics)


def validate_report_claims(metrics: dict) -> None:
    """Refuse a paper when a synthetic negative control claims proxy support."""
    run = metrics.get("Run_Metadata", {})
    claims_support = (
        bool(metrics.get("Surface_Proxy_Supported", metrics.get("H1_Supported")))
        or metrics.get("Inference_Status") == "SUPPORTED"
    )
    if (
        run.get("data_mode") == "synthetic"
        and run.get("scenario") in {"h2_lean", "null"}
        and claims_support
    ):
        raise RuntimeError(
            f"False-positive guard: synthetic {run.get('scenario')!r} data claimed "
            "surface-proxy support; refusing to generate a PDF."
        )


def generate_pdf_report(metrics_path: str, figures_dir: str, output_pdf: str) -> str:
    with open(metrics_path) as fh:
        m = json.load(fh)
    validate_report_claims(m)

    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    _line(pdf, "Surface TiO2 and Lunar Crustal Magnetism", size=17, style="B")
    _line(pdf, "Spatial Co-location Analysis - Results", size=13, style="B")
    pdf.ln(3)

    pdf.set_font("helvetica", "I", 10)
    pdf.multi_cell(0, 5, "DISCLAIMER: AI-ASSISTED LEARNING PROJECT\n"
                         "This is an educational project created for learning and experience. "
                         "Large Language Models (AI) were used extensively to aid in completing, "
                         "writing, and architecting this analysis pipeline and its documentation.")
    pdf.ln(3)
    pdf.set_font("helvetica", "", 10)

    cfg = m.get("config", {})
    _para(pdf,
          "This report analyses whether a present-day surface TiO2 retrieval spatially "
          "co-locates with lunar crustal magnetism. The retrieval is mare-calibrated; "
          "the full declared footprint includes out-of-domain highlands, and a separate "
          "USGS mare-proxy sensitivity is reported. It does not test the "
          "temporal/thermal intermittent-dynamo mechanism of Nichols et al. (2026). "
          "The impact-antipode feature is a literature benchmark, not an exhaustive "
          "rival. Binary XGBoost/SHAP results are legacy diagnostics. Their scores use "
          "30x30 degree spatially-blocked "
          f"GroupKFold (seed {cfg.get('random_seed')}, grid {cfg.get('grid_res_deg')} deg, "
          f"age mask '{cfg.get('age_mask')}', threshold {cfg.get('primary_threshold_nT')} nT).")

    run = m.get("Run_Metadata", {})
    if run.get("data_mode"):
        scenario_text = f", scenario {run.get('scenario')!r}" if run.get("scenario") else ""
        _line(pdf, f"Data mode: {run['data_mode']}{scenario_text}", size=10, style="I")
        mode_note = " (smoke-test settings; not the published power curve)" if cfg.get("mode") == "fast" else ""
        _line(pdf, f"Run mode: {cfg.get('mode', 'unknown')}{mode_note}", size=10, style="I")
        pdf.ln(2)

    continuous = m.get("Transparent_Continuous_Analysis")
    if continuous:
        _line(pdf, "Transparent Continuous-Field Analysis", size=13, style="B")
        delta = continuous["tio2_incremental_r2"]
        controls = continuous["controls_only"]["r2"]
        full_cont = continuous["controls_plus_tio2"]["r2"]
        _line(pdf, f"Controls-only blocked R2: {controls['mean']:.4f} +/- {controls['std']:.4f}")
        _line(pdf, f"Controls + TiO2 blocked R2: {full_cont['mean']:.4f} +/- {full_cont['std']:.4f}")
        _line(pdf, f"Incremental TiO2 R2: {delta['mean']:+.4f} +/- {delta['std']:.4f}")
        _para(pdf, continuous.get("inference_note", "Descriptive only."), size=9, style="I")

    cv = m["Cross_Validation"]
    _line(pdf, "Legacy Threshold Classifier (PR-AUC)", size=13, style="B")
    _line(pdf, f"Positive prevalence: {cv['positive_prevalence']:.3f}  "
               f"(n={cv['n_pixels']:,} px, {cv['n_blocks']} blocks)")
    _line(pdf, f"Dummy (stratified): {cv['Dummy_Stratified_PR_AUC']:.4f}")
    _line(pdf, f"Dummy (prior):      {cv['Dummy_Prior_PR_AUC']:.4f}")
    _line(pdf, f"Logistic regression: {cv['LogReg_PR_AUC']:.4f}")
    _line(pdf, f"XGBoost H2-only:    {cv['H2_Only_PR_AUC']:.4f}")
    _line(pdf, f"XGBoost full:       {cv['XGB_Full_PR_AUC']:.4f}")
    _line(pdf, f"XGBoost full (nested-tuned): {cv['XGB_Full_Tuned_PR_AUC']:.4f}")
    pdf.ln(2)

    ab = m["Ablation"]
    _line(pdf, "Legacy Ablation (surface-TiO2 proxy)", size=13, style="B")
    _line(pdf, f"Full: {ab['PR_AUC']['full']['mean']:.4f}   "
               f"All Ti-derived terms removed: {ab['PR_AUC']['no_h1_tio2']['mean']:.4f}")
    _line(pdf, f"Mean drop from clean TiO2 ablation: {ab['H1_tio2_drop_mean']:.4f}")
    _line(pdf, f"Paired Wilcoxon p (full > no-TiO2): {ab['Wilcoxon_p_full_gt_no_h1']:.4f}")
    _line(pdf, f"Exploratory (non-Nichols) gravity/interaction drop: "
               f"{ab['Exploratory_drop_mean']:.4f}  (expected ~0)")
    pdf.ln(2)

    pt = m["Permutation_Test"]
    _line(pdf, "Spatial-Rotation Permutation Test", size=13, style="B")
    observed_pr_auc = pt.get("Observed_PR_AUC", pt.get("Real_Full_PR_AUC", float("nan")))
    _line(pdf, f"Observed full PR-AUC: {observed_pr_auc:.4f}   "
               f"Null mean: {pt['Null_Mean_PR_AUC']:.4f} +/- {pt['Null_Std_PR_AUC']:.4f}")
    _line(pdf, f"Empirical p-value: {pt['Empirical_p_value']:.4f}  "
               f"(n={pt['n_permutations']})")
    if pt.get("n_candidate_shifts_evaluated"):
        _line(
            pdf,
            "Fold-matched rotations: "
            f"{pt['n_permutations']} accepted / {pt['n_candidate_shifts_evaluated']} candidates; "
            f"{pt.get('n_rejected_for_fold_count_mismatch', 0)} rejected",
            size=9,
        )
    pdf.ln(2)

    sh = m["SHAP"]
    _line(pdf, "Exploratory SHAP: TiO2 vs antipode benchmark", size=13, style="B")
    _line(pdf, f"H1 TiO2 FAMILY |SHAP| (composition, 25/50/100 km combined): "
               f"{sh['h1_tio2_family_importance']:.4f}")
    _line(pdf, f"H2 antipode feature |SHAP|: {sh['antipode_importance']:.4f}")
    _line(pdf, f"Exploratory Ti x gravity family |SHAP| (non-Nichols): "
               f"{sh['exploratory_interaction_family_importance']:.4f}")
    _line(pdf, f"H1 TiO2 signal outranks antipode: {sh['h1_outranks_antipode']}")
    pdf.ln(2)

    cr = m["Criteria"]
    _ensure_space(pdf, 42)
    _line(pdf, "Legacy Repository-Plan Criteria", size=13, style="B")
    _line(pdf, f"(i) beats null + all baselines: {cr['criterion_i_beats_null_and_baselines']}")
    _line(pdf, f"(ii) TiO2 signal outranks antipode: {cr['criterion_ii_h1_tio2_outranks_antipode']}")
    _line(pdf, f"(iii) TiO2 ablation drop significant: {cr['criterion_iii_h1_ablation_significant']}")
    if "spatial_adequacy_support_survives_largest_block" in cr:
        _line(pdf, "Spatial adequacy gate for a POSITIVE (support survives largest block): "
                   f"{cr['spatial_adequacy_support_survives_largest_block']}")
    pdf.ln(3)

    sd = m.get("Spatial_Diagnostics")
    if sd:
        _ensure_space(pdf, 68)
        _line(pdf, "Spatial Dependence Diagnostics", size=13, style="B")
        bb = sd["block_bootstrap_pr_auc"]
        _line(pdf, f"Full PR-AUC {bb['PR_AUC_point']:.3f}, conditional block interval "
                   f"[{bb['PR_AUC_CI_low']:.3f}, {bb['PR_AUC_CI_high']:.3f}] over {bb['n_blocks']} blocks")
        if not bb.get("interval_valid_for_inference", False):
            _para(pdf, bb.get("limitation", "Block independence is not established."), size=9, style="I")
        _line(pdf, f"Large-scale structure range {sd['variogram_range_km']:.0f} km; "
                   f"CV block {sd.get('cv_block_size_km', float('nan')):.0f} km")
        pr = sd["phase_randomization_null"]
        _line(pdf, f"Phase-randomised null (strict): p = {pr['Empirical_p_value']:.3f} "
                   f"(n={pr['n_surrogates']})")
        _line(pdf, f"Partition sensitivity: proxy support at largest CV block = "
                   f"{sd.get('spatially_adequate', False)}")
        if m.get("Falsifiability_Guards", {}).get("negative_result_may_be_underpowered"):
            _para(pdf, "CAVEAT: low prevalence / few effective independent regions -- this "
                        "negative result may be underpowered to detect a weak true effect "
                        "and absence of a detected effect is not evidence of absence.", size=10, style="I")
        pdf.ln(2)

    power = m.get("Detection_Power", {})
    if power:
        _ensure_space(pdf, 58)
        _line(pdf, "Positive-Control Detection Power", size=13, style="B")
        _line(pdf, "Injected signal recovered somewhere on tested grid: "
                   f"{power.get('injected_signal_recovered_on_tested_grid', False)}")
        _line(pdf, "Observed impact-antipode benchmark recovered: "
                   f"{power.get('observed_h2_benchmark_recovered', False)}")
        _line(pdf, "Injected + observed benchmark recovery checks passed: "
                   f"{power.get('positive_control_recovered', False)}")
        if power.get("power_at_target_effect") is not None:
            _line(pdf, f"Power at target effect: {float(power['power_at_target_effect']):.3f}")
        else:
            _line(pdf, "Power at target effect: not estimable (no justified target effect)")
        _line(pdf, f"Adequate power demonstrated: {power.get('adequate_power', False)}")
        mde = power.get("minimum_detectable_effect", {})
        if mde:
            if mde.get("point_estimate_strength") is None:
                _line(pdf, "80% injected-signal floor: not reached on tested grid")
            else:
                _line(pdf, "First tested latent coefficient reaching 80% point power: "
                           f"{float(mde['point_estimate_strength']):g}")
                _line(pdf, "Conservative 95% floor: "
                           f"{mde.get('conservative_95pct_strength', 'not reached')}")
        _para(pdf, power.get("interpretation", "Power diagnostics are required for a strong negative."),
              size=9, style="I")

    terrain = m.get("Terrain_Validity_Sensitivity", {})
    if terrain:
        _ensure_space(pdf, 62)
        _line(pdf, "Mare-Validity Sensitivity", size=13, style="B")
        terrain_mask = terrain.get("mask", {})
        mare = terrain.get("mare_valid", {})
        _line(pdf, f"Mask source: {terrain_mask.get('source', 'USGS GeoUnits FIRST_Unit')}")
        _line(pdf, f"Mare rows / positives: {mare.get('n_pixels', 'n/a')} / "
                   f"{mare.get('n_positive_pixels', 'n/a')}")
        if mare.get("skipped"):
            _line(pdf, f"Mare-only classifier skipped: {mare.get('reason')}", size=9, style="I")
        elif mare:
            _line(pdf, f"Mare-only TiO2 increment (PR-AUC): {mare.get('H1_tio2_drop_mean', float('nan')):+.4f}")
            _line(pdf, f"Positive spatial blocks: {mare.get('n_positive_spatial_blocks', 'n/a')}  "
                       f"paired p: {mare.get('Wilcoxon_p_H1_gt_controls', float('nan')):.4f}")
        mare_continuous = terrain.get("mare_valid_continuous", {})
        if mare_continuous:
            continuous_delta = mare_continuous.get("tio2_incremental_r2", {})
            _line(
                pdf,
                "Mare-only continuous TiO2 incremental R2: "
                f"{continuous_delta.get('mean', float('nan')):+.4f} +/- "
                f"{continuous_delta.get('std', float('nan')):.4f}",
            )
        limitations = terrain_mask.get("limitations", [])
        _para(pdf, " ".join(limitations) if limitations else "Terrain mask is a proxy.",
              size=9, style="I")

    inference_status = report_inference_status(m)
    if inference_status == "SUPPORTED":
        conclusion = "SURFACE PROXY SUPPORTED (TEMPORAL MECHANISM UNTOUCHED)"
    elif inference_status == "INCONCLUSIVE_SPATIAL_AUTOCORRELATION":
        conclusion = "INCONCLUSIVE (spatial blocks are not independent enough)"
    elif inference_status == "INCONCLUSIVE_LOW_POWER":
        conclusion = "INCONCLUSIVE (LOW DETECTION POWER)"
    else:
        conclusion = "SURFACE PROXY NOT SUPPORTED AT A DEMONSTRATED POWER FLOOR"
    _para(pdf, f"Conclusion: {conclusion}", size=14, style="B")
    _para(pdf, "The Nichols et al. temporal intermittent-dynamo mechanism is not adjudicated "
               "by this present-day spatial analysis.", size=10, style="I")

    # Falsifiability guard (F6): flag a subset-only signal as non-confirmatory.
    fg = m.get("Falsifiability_Guards", {})
    if fg.get("subset_signal_is_hypothesis_generating_not_confirmation"):
        _para(pdf, "NOTE: the repository-plan primary test did not support the proxy; a signal in "
                    "another pre-specified subset is hypothesis-generating, not confirmation.",
              size=10, style="I")
    pdf.ln(2)

    # Scope & caveats -- the epistemic limits from the fallacy audit, surfaced here
    # (not only in Fallacy-Audit.md) so reviewers see them with the result.
    pdf.add_page()
    _line(pdf, "Scope and Caveats (see Fallacy-Audit.md)", size=13, style="B")
    for txt in [
        "Nichols et al. analyse dated samples and a time-dependent core-mantle mechanism. "
        "Present-day surface co-location is an additional proxy proposed by this repository, "
        "not a prediction stated by those authors.",
        "A dynamo is global and magnetises cooling material during active epochs; source age "
        "and cooling history are absent from this analysis.",
        "The sample relationship and pixel-scale regolith map are different estimands; no "
        "ecological scaling conclusion follows from this result.",
        "The remanence carrier is fine-grained metallic iron, not ilmenite; surface TiO2 is "
        "an indirect proxy for the strong-field basalts (F4).",
        "The TiO2 proxy and antipode benchmark are not exhaustive hypotheses (long-lived dynamo, impact-plasma "
        "amplification, basal-magma-ocean dynamo also exist). This study DISCRIMINATES two "
        "signatures; it does not adjudicate the whole field (F5).",
        "The nearside/Procellarum setting confounds Ti with basin proximity and thin crust; "
        "a 'nearside' control plus spatial-block CV mitigate but do not remove it (F8).",
        "Synthetic injection results measure this pipeline's sensitivity under declared "
        "generative assumptions; they are not evidence about the Moon.",
        "The repository plan has no independent timestamp. Its post-hoc inference amendment "
        "is disclosed rather than presented as externally verified pre-registration.",
    ]:
        _para(pdf, "- " + txt, size=10)

    # Figures.
    for fname, caption in [
        ("shap_summary.png", "SHAP Summary (feature importance)"),
        ("shap_dependence_interaction.png", "SHAP Dependence: TiO2 (H1) coloured by antipode (H2)"),
        ("shap_interaction_map.png", "Global Map: where the TiO2 (H1) signal drives predictions"),
    ]:
        path = os.path.join(figures_dir, fname)
        if os.path.exists(path):
            pdf.add_page()
            _line(pdf, caption, size=13, style="B")
            pdf.image(path, x=15, y=30, w=180)

    pdf.output(output_pdf)
    print(f"Generated PDF report at {output_pdf}")
    return output_pdf


if __name__ == "__main__":
    from . import config
    generate_pdf_report(
        os.path.join(config.RESULTS_DIR, "metrics.json"),
        config.FIGURES_DIR,
        os.path.join(config.RESULTS_DIR, "Research_Paper.pdf"),
    )
