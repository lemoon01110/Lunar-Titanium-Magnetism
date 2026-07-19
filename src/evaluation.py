"""Evaluation of a present-day surface-TiO2 spatial co-location proxy.

This is not a test of the temporal/thermal intermittent-dynamo mechanism in
Nichols et al. (2026).  Given the tabular dataset, the module executes:

  * a transparent blocked continuous-field regression, which is the revised
    descriptive analysis and preserves magnetic-field magnitude;

  * baselines (stratified & prior dummies, logistic regression, H2-only XGBoost);
  * the full-model score under the binding default-config XGBoost estimator
    (nested tuning is retained only as a descriptive diagnostic);
  * a **spatial-rotation permutation test** (rolls the target grid in longitude,
    preserving autocorrelation) to get an empirical p-value;
  * an **ablation study** with a paired one-sided Wilcoxon test on per-fold scores
    (replacing the original arbitrary 0.02 threshold);
  * **SHAP** analysis ranking H1's compositional TiO2 feature family against the
    antipodal-distance rival; surface gravity and Ti x gravity remain explicitly
    exploratory rather than part of the Nichols et al. mechanism;
  * the three legacy repository-plan success criteria, retained for traceability;
  * **sensitivity analyses** over age masks (Imbrian / +Nectarian / none) and
    binary thresholds (5 / 10 nT).

The inference gate fails closed to ``INCONCLUSIVE_LOW_POWER`` unless independent
spatial information and injected-signal sensitivity are demonstrated.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy import stats
from sklearn.model_selection import GroupKFold

from . import config
from . import modeling
from . import interpretability
from . import spatial_stats
from . import inference
from . import power_analysis
from . import transparent_analysis
from . import terrain_sensitivity


# --------------------------------------------------------------------------- #
# Subsetting and feature sets
# --------------------------------------------------------------------------- #
AGE_MASKS = {
    "imbrian": lambda a: a == config.AGE_IMBRIAN,
    "imbrian_nectarian": lambda a: np.isin(a, [config.AGE_IMBRIAN, config.AGE_NECTARIAN]),
    "none": lambda a: np.ones_like(a, dtype=bool),
}


def subset_by_age(df: pd.DataFrame, age_mask: str) -> pd.DataFrame:
    if age_mask not in AGE_MASKS:
        raise ValueError(f"Unknown age_mask {age_mask!r}")
    keep = AGE_MASKS[age_mask](df["age_class"].values)
    return df[keep].reset_index(drop=True)


def feature_sets() -> Dict[str, List[str]]:
    """Feature subsets for the ablation.

    The clean surface-TiO2 test removes both the compositional variables and all
    TiO2-derived interaction terms; otherwise the ablated model would still carry
    Ti information. Interaction/gravity-only ablations remain exploratory and are
    not part of the Nichols mechanism (F1).
    """
    h1 = set(config.TIO2_DERIVED_FEATURES)
    inter = set(config.INTERACTION_FEATURES)
    expl = set(config.EXPLORATORY_FEATURES)
    return {
        "full": config.ALL_FEATURES,
        "no_h1_tio2": [f for f in config.ALL_FEATURES if f not in h1],       # clean H1 ablation
        "no_interaction": [f for f in config.ALL_FEATURES if f not in inter],  # exploratory
        "no_exploratory": [f for f in config.ALL_FEATURES if f not in expl],   # drop gravity+interaction
        "h1_only": config.H1_FEATURES,
        "h2_only": config.H2_FEATURES,
    }


# --------------------------------------------------------------------------- #
# Baselines + full model under one shared spatial CV
# --------------------------------------------------------------------------- #
def run_baselines_and_full(df: pd.DataFrame, target: str, cfg: config.PipelineConfig) -> Dict:
    groups = df["spatial_block"].values
    y = df[target]
    X_full = df[config.ALL_FEATURES]
    X_h2 = df[config.H2_FEATURES]
    n = cfg.n_outer_folds

    dummy_strat = modeling.cross_val_pr_auc(
        modeling.dummy_factory("stratified", seed=cfg.random_seed), X_full, y, groups, n
    )
    dummy_prior = modeling.cross_val_pr_auc(
        modeling.dummy_factory("prior", seed=cfg.random_seed), X_full, y, groups, n
    )
    logreg = modeling.cross_val_pr_auc(
        modeling.logreg_factory(seed=cfg.random_seed), X_full, y, groups, n
    )
    h2_only = modeling.cross_val_pr_auc(
        modeling.xgb_factory(seed=cfg.random_seed), X_h2, y, groups, n
    )
    full = modeling.cross_val_pr_auc(
        modeling.xgb_factory(seed=cfg.random_seed), X_full, y, groups, n
    )

    return {
        "positive_prevalence": float(y.mean()),
        "n_pixels": int(len(y)),
        "n_blocks": int(len(np.unique(groups))),
        "Dummy_Stratified_PR_AUC": _summ(dummy_strat),
        "Dummy_Prior_PR_AUC": _summ(dummy_prior),
        "LogReg_PR_AUC": _summ(logreg),
        "H2_Only_PR_AUC": _summ(h2_only),
        "XGB_Full_PR_AUC": _summ(full),
        "_full_scores": full.tolist(),
    }


# --------------------------------------------------------------------------- #
# Ablation with a paired statistical test
# --------------------------------------------------------------------------- #
def run_ablation(df: pd.DataFrame, target: str, cfg: config.PipelineConfig) -> Dict:
    groups = df["spatial_block"].values
    y = df[target]
    n = cfg.n_outer_folds

    per_fold: Dict[str, np.ndarray] = {}
    for name, feats in feature_sets().items():
        per_fold[name] = modeling.cross_val_pr_auc(
            modeling.xgb_factory(seed=cfg.random_seed), df[feats], y, groups, n
        )

    # Surface-proxy test: remove every TiO2-bearing term, including exploratory
    # TiO2 x gravity interactions, so no derived Ti signal survives the ablation.
    h1_drop = per_fold["full"] - per_fold["no_h1_tio2"]
    h1_wilcoxon_p = _paired_one_sided_greater(per_fold["full"], per_fold["no_h1_tio2"])
    # Secondary: does the (non-Nichols) interaction/gravity add anything? Expected ~no.
    expl_drop = per_fold["full"] - per_fold["no_exploratory"]

    return {
        "PR_AUC": {k: _summ(v) for k, v in per_fold.items()},
        "H1_tio2_drop_mean": float(np.mean(h1_drop)),
        "H1_tio2_drop_per_fold": h1_drop.tolist(),
        "Wilcoxon_p_full_gt_no_h1": float(h1_wilcoxon_p),
        "Exploratory_drop_mean": float(np.mean(expl_drop)),
    }


def _paired_one_sided_greater(a: np.ndarray, b: np.ndarray) -> float:
    """One-sided paired test that a > b. Wilcoxon signed-rank, t-test fallback."""
    diff = np.asarray(a) - np.asarray(b)
    if np.allclose(diff, 0):
        return 1.0
    try:
        return float(stats.wilcoxon(a, b, alternative="greater", zero_method="zsplit").pvalue)
    except ValueError:
        return float(stats.ttest_rel(a, b, alternative="greater").pvalue)


# --------------------------------------------------------------------------- #
# Spatial-rotation permutation test
# --------------------------------------------------------------------------- #
def run_permutation_test(
    df_masked: pd.DataFrame,
    df_all_valid: pd.DataFrame,
    target: str,
    grid_meta: Dict,
    cfg: config.PipelineConfig,
    real_full_mean: float,
    features: List[str] | None = None,
) -> Dict:
    width, height = int(grid_meta["width"]), int(grid_meta["height"])
    # Reconstruct the target over ALL valid pixels so rotated cells stay defined.
    grid = np.full((height, width), np.nan)
    grid[df_all_valid["row_idx"].values, df_all_valid["col_idx"].values] = df_all_valid[target].values

    rows = df_masked["row_idx"].values
    cols = df_masked["col_idx"].values
    selected_features = list(features or config.ALL_FEATURES)
    X = df_masked[selected_features]
    groups = df_masked["spatial_block"].values

    observed_y = df_masked[target].astype(int).reset_index(drop=True)
    observed_fold_count = 0
    observed_splitter = GroupKFold(
        n_splits=min(cfg.n_outer_folds, int(np.unique(groups).size))
    )
    for train_idx, test_idx in observed_splitter.split(X, observed_y, groups):
        if observed_y.iloc[train_idx].sum() > 0 and observed_y.iloc[test_idx].sum() > 0:
            observed_fold_count += 1
    if observed_fold_count < 2:
        raise RuntimeError(
            "Observed rotation-test statistic has fewer than two evaluable spatial folds"
        )

    rng = np.random.default_rng(cfg.random_seed)
    n_perm = cfg.scaled_permutations()
    available_shifts = np.arange(1, width, dtype=int)
    sampled_with_replacement = n_perm > len(available_shifts)
    shift_order = (
        rng.permutation(available_shifts).tolist()
        if not sampled_with_replacement else []
    )

    # Single-threaded XGBoost inside each worker so joblib's process pool does
    # not oversubscribe the CPU (16 workers x 16 OMP threads would thrash).
    factory = modeling.xgb_factory(seed=cfg.random_seed, n_jobs=1)

    def _one(shift: int):
        rolled = np.roll(grid, shift=int(shift), axis=1)
        y_perm = rolled[rows, cols]
        keep = np.isfinite(y_perm)
        if keep.sum() < 50 or np.unique(y_perm[keep]).size < 2:
            return None, 0, float("nan"), int(keep.sum())
        yk = pd.Series(y_perm[keep].astype(int), index=X.index[keep])
        scores = modeling.cross_val_pr_auc(factory, X[keep], yk, groups[keep], cfg.n_outer_folds)
        return float(np.mean(scores)), int(len(scores)), float(yk.mean()), int(keep.sum())

    accepted_scores: List[float] = []
    accepted_shifts: List[int] = []
    accepted_prevalence: List[float] = []
    accepted_rows: List[int] = []
    candidate_fold_counts: List[int] = []
    candidate_count = 0
    rejected_fold_mismatch = 0
    cursor = 0
    max_candidates = len(available_shifts) if not sampled_with_replacement else max(20 * n_perm, 100)
    while len(accepted_scores) < n_perm and candidate_count < max_candidates:
        needed = n_perm - len(accepted_scores)
        batch_size = max(needed + max(10, int(np.ceil(0.25 * needed))), needed)
        if sampled_with_replacement:
            batch_size = min(batch_size, max_candidates - candidate_count)
            batch = rng.choice(available_shifts, size=batch_size, replace=True).astype(int).tolist()
        else:
            batch_size = min(batch_size, len(shift_order) - cursor)
            if batch_size <= 0:
                break
            batch = [int(value) for value in shift_order[cursor:cursor + batch_size]]
            cursor += batch_size
        batch_results = Parallel(n_jobs=-1, prefer="processes")(
            delayed(_one)(shift) for shift in batch
        )
        candidate_count += len(batch)
        for shift, (score, fold_count, prevalence, n_rows) in zip(batch, batch_results):
            candidate_fold_counts.append(int(fold_count))
            if score is None or fold_count != observed_fold_count:
                rejected_fold_mismatch += 1
                continue
            if len(accepted_scores) < n_perm:
                accepted_scores.append(float(score))
                accepted_shifts.append(int(shift))
                accepted_prevalence.append(float(prevalence))
                accepted_rows.append(int(n_rows))

    if len(accepted_scores) < max(20, int(np.ceil(0.5 * n_perm))):
        raise RuntimeError(
            "Could not obtain enough rotations with the same evaluable "
            f"fold count as observed ({len(accepted_scores)}/{n_perm}; "
            f"need at least {max(20, int(np.ceil(0.5 * n_perm)))})"
        )
    if len(accepted_scores) < n_perm:
        # Exhausted the fold-matched candidate pool.  Report the largest
        # attainable matched-null sample rather than inventing replacements.
        print(
            f"  rotation null: accepted {len(accepted_scores)}/{n_perm} fold-matched "
            f"shifts (candidate pool exhausted; using attainable matched sample)"
        )
    null_arr = np.asarray(accepted_scores, dtype=float)
    # +1 smoothing avoids a p-value of exactly 0 (best practice for MC tests).
    p_value = (np.sum(null_arr >= real_full_mean) + 1) / (len(null_arr) + 1)
    return {
        "n_permutations": int(len(null_arr)),
        "n_unique_longitude_shifts": int(np.unique(accepted_shifts).size),
        "sampled_with_replacement": bool(sampled_with_replacement),
        "identity_shift_excluded": True,
        "observed_valid_fold_count": int(observed_fold_count),
        "accepted_rotation_valid_fold_counts": [
            int(observed_fold_count)
        ] * len(accepted_scores),
        "candidate_valid_fold_count_histogram": {
            str(count): int(candidate_fold_counts.count(count))
            for count in sorted(set(candidate_fold_counts))
        },
        "n_candidate_shifts_evaluated": int(candidate_count),
        "n_rejected_for_fold_count_mismatch": int(rejected_fold_mismatch),
        "n_valid_candidates_not_used": int(
            candidate_count - rejected_fold_mismatch - len(accepted_scores)
        ),
        "accepted_longitude_shifts_pixels": accepted_shifts,
        "accepted_rotation_prevalence": {
            "min": float(np.min(accepted_prevalence)),
            "mean": float(np.mean(accepted_prevalence)),
            "max": float(np.max(accepted_prevalence)),
        },
        "accepted_rotation_rows": {
            "min": int(np.min(accepted_rows)),
            "max": int(np.max(accepted_rows)),
        },
        "Null_Mean_PR_AUC": float(np.mean(null_arr)) if len(null_arr) else float("nan"),
        "Null_Std_PR_AUC": float(np.std(null_arr)) if len(null_arr) else float("nan"),
        "Null_95th_PR_AUC": float(np.quantile(null_arr, 0.95)) if len(null_arr) else float("nan"),
        "Observed_PR_AUC": float(real_full_mean),
        "statistic_label": "mean PR-AUC across the observed number of evaluable spatial folds",
        "features": selected_features,
        "Empirical_p_value": float(p_value),
    }


# --------------------------------------------------------------------------- #
# Core analysis for one (age mask, threshold) cell
# --------------------------------------------------------------------------- #
def _summ(scores: np.ndarray) -> Dict:
    return {"mean": float(np.mean(scores)), "std": float(np.std(scores)), "per_fold": np.asarray(scores).tolist()}


def core_analysis(
    df_masked: pd.DataFrame, target: str, cfg: config.PipelineConfig
) -> Dict:
    """Baselines + ablation + H1 sub-criteria that don't require the grid/SHAP."""
    baselines = run_baselines_and_full(df_masked, target, cfg)
    ablation = run_ablation(df_masked, target, cfg)

    full_mean = baselines["XGB_Full_PR_AUC"]["mean"]
    # The meaningful gates are the uninformative baselines (dummies) and the RIVAL
    # hypothesis (H2-only). Logistic regression uses the *same* features, so a
    # comparable LR score corroborates a real signal rather than refuting H1;
    # requiring XGB to beat LR would conflate model choice with hypothesis support.
    # LR is therefore reported (full_ge_logreg) but is not a hard gate.
    beats_baselines = (
        full_mean > baselines["Dummy_Prior_PR_AUC"]["mean"]
        and full_mean > baselines["Dummy_Stratified_PR_AUC"]["mean"]
        and full_mean > baselines["H2_Only_PR_AUC"]["mean"]
    )
    full_ge_logreg = full_mean >= baselines["LogReg_PR_AUC"]["mean"]
    # Criterion (iii): removing the H1 (TiO2) family significantly hurts the model.
    ablation_significant = (
        ablation["H1_tio2_drop_mean"] > 0
        and ablation["Wilcoxon_p_full_gt_no_h1"] < 0.05
    )
    return {
        "baselines": baselines,
        "ablation": ablation,
        "beats_all_baselines": bool(beats_baselines),
        "full_ge_logreg": bool(full_ge_logreg),
        "ablation_significant": bool(ablation_significant),
    }


# --------------------------------------------------------------------------- #
# Spatial-statistics diagnostics (honest uncertainty)
# --------------------------------------------------------------------------- #
def run_spatial_diagnostics(
    df_primary: pd.DataFrame, df_all: pd.DataFrame, target: str,
    grid_meta: Dict, cfg: config.PipelineConfig, real_full_mean: float,
) -> Dict:
    lon = df_primary["lon"].values
    lat = df_primary["lat"].values
    z = df_primary["mag_anomaly"].values
    centres, gamma, sill = spatial_stats.empirical_variogram(lon, lat, z, seed=cfg.random_seed)
    range_km = spatial_stats.decorrelation_range_km(centres, gamma, sill)
    res_km = float(grid_meta.get("res_km", 30.0))
    n_eff = spatial_stats.effective_sample_size(len(df_primary), res_km ** 2, range_km)
    block_km = cfg.spatial_block_size_deg * (np.pi * config.LUNAR_RADIUS_KM / 180.0)

    groups = df_primary["spatial_block"].values
    oof = spatial_stats.oof_predictions(
        df_primary[config.ALL_FEATURES], df_primary[target], groups, cfg.n_outer_folds, seed=cfg.random_seed
    )
    n_boot = 300 if cfg.mode == "fast" else 1000
    ci = spatial_stats.block_bootstrap_pr_auc_ci(
        df_primary[target].values, oof, groups, n_boot=n_boot, seed=cfg.random_seed
    )
    phase = spatial_stats.phase_randomization_null(
        df_primary, df_all, target, grid_meta, cfg, real_full_mean
    )
    robustness = spatial_stats.block_size_robustness(df_primary, target, cfg)
    ratio = float(block_km / range_km) if np.isfinite(range_km) and range_km > 0 else float("nan")
    interval_valid = bool(
        np.isfinite(ratio) and ratio >= 1.0
        and n_eff >= inference.MIN_EFFECTIVE_REGIONS
    )
    ci["interval_valid_for_inference"] = interval_valid
    ci["limitation"] = (
        "Conditional block-resampling interval only; selected blocks are smaller than "
        "the estimated spatial range and/or too few effective regions exist."
        if not interval_valid else
        "Block size and effective-region diagnostics meet the configured minimum."
    )
    diag = {
        # NB: for a rare, clustered binary target the variogram range-to-sill is
        # intrinsically ~hemispheric and reflects large-scale clustering rather
        # than directly proving train/test leakage.  Even so, blocks far smaller
        # than that range cannot establish independent replication, so the ratio
        # participates in the conservative inference gate (Fallacy-Audit.md F10).
        "variogram_range_km": range_km,
        "cv_block_size_km": float(block_km),
        "block_to_range_ratio": ratio,
        "block_exceeds_range": bool(np.isfinite(ratio) and ratio >= 1.0),
        "approx_effective_sample_size": n_eff,
        "n_pixels": int(len(df_primary)),
        "block_bootstrap_pr_auc": ci,
        "phase_randomization_null": phase,
        "block_size_robustness": robustness,
        "block_size_interpretation": (
            "Non-monotone partition sensitivity; block size is not treated as a "
            "one-dimensional leakage meter."
        ),
    }
    # Partition sensitivity is one adequacy component; expose it separately from
    # the composite gate so downstream reports cannot mistake one check for all.
    diag["support_survives_largest_partition"] = inference.spatial_adequate(diag)
    diag["spatially_adequate"] = bool(
        diag["support_survives_largest_partition"]
        and inference.independent_regions_adequate(diag)
    )
    return diag


# --------------------------------------------------------------------------- #
# Full pipeline orchestration
# --------------------------------------------------------------------------- #
def _pick_best_params(best_params: List[Dict], scores: np.ndarray) -> Dict:
    """Choose the modal inner-selected configuration without outer-test leakage.

    ``scores`` is retained in the signature for backward compatibility but is
    deliberately ignored: choosing the parameters attached to the highest outer
    held-out score would reuse test outcomes for the final SHAP model.
    """
    if not best_params:
        return {}
    del scores
    serialized = [json.dumps(params, sort_keys=True) for params in best_params]
    counts = {value: serialized.count(value) for value in set(serialized)}
    winner = sorted(counts, key=lambda value: (-counts[value], value))[0]
    return dict(best_params[serialized.index(winner)])


def run_detection_power(
    df_all: pd.DataFrame,
    grid_meta: Dict,
    target: str,
    cfg: config.PipelineConfig,
    observed_h2_recovered: bool,
) -> tuple[Dict, Dict]:
    """Run the declared spatial injection/recovery experiment and fail closed.

    The detailed experiment keeps its own definition of successful injected-
    signal recovery.  The canonical gate additionally requires the real-data H2
    benchmark to clear its separately calibrated spatial null; otherwise the
    pipeline has not recovered the literature-motivated diagnostic control in
    the data it is trying to interpret.
    """
    experiment = power_analysis.run_power_analysis_frame(
        df_all,
        grid_meta,
        power_analysis.PowerAnalysisConfig(
            control="h2_antipode",
            strengths=cfg.resolved_power_strengths(),
            n_simulations=cfg.scaled_power_simulations(),
            age_mask=cfg.age_mask,
            target_column=target,
            noise_method="phase",
            estimator="xgboost",
            n_outer_folds=cfg.n_outer_folds,
            primary_block_size_deg=cfg.spatial_block_size_deg,
            adequacy_block_size_deg=config.POWER_ADEQUACY_BLOCK_DEG,
            target_effect_strength=None,
            simulation_seed=cfg.random_seed,
            model_seed=cfg.random_seed,
            variogram_pairs=1_000 if cfg.mode == "fast" else 60_000,
            include_simulations=False,
        ),
    )
    raw = experiment["Detection_Power"]
    injected_recovered = bool(raw.get("positive_control_recovered", False))
    canonical = {
        **raw,
        "injected_signal_recovered_on_tested_grid": injected_recovered,
        "observed_h2_benchmark_recovered": bool(observed_h2_recovered),
        "positive_control_recovered": bool(
            injected_recovered and observed_h2_recovered
        ),
        # The module already requires structural adequacy and an externally
        # justified target effect.  The observed benchmark is an additional,
        # necessary diagnostic—not a way to override those requirements.
        "adequate_power": bool(
            raw.get("adequate_power", False) and observed_h2_recovered
        ),
        "minimum_detectable_effect": experiment["minimum_detectable_effect"],
        "interpretation": (
            "The injected curve quantifies a design-conditional detection floor. "
            "No externally justified target effect was declared, and the observed "
            "impact-antipode benchmark must also clear its own spatial null."
        ),
    }
    return experiment, canonical


# The spatial-adequacy gate lives in src/inference.py (single source of truth,
# shared with the report generator). Re-exported here under its historical name.
spatially_gated_inference = inference.gate_inference


def evaluate_pipeline(
    processed_dir: str = config.PROCESSED_DIR,
    results_dir: str = config.RESULTS_DIR,
    cfg: config.PipelineConfig | None = None,
    run_metadata: Dict | None = None,
) -> Dict:
    cfg = cfg or config.PipelineConfig()
    if cfg.primary_threshold_nt not in config.BINARY_THRESHOLDS_NT:
        raise ValueError(
            f"primary_threshold_nt={cfg.primary_threshold_nt!r} is not configured; "
            f"choose from {config.BINARY_THRESHOLDS_NT}"
        )
    os.makedirs(results_dir, exist_ok=True)
    fig_dir = os.path.join(results_dir, "figures")

    df_all = pd.read_csv(os.path.join(processed_dir, "modeling_dataset.csv"))
    with open(os.path.join(processed_dir, "grid_meta.json")) as fh:
        grid_meta = json.load(fh)

    target = f"mag_binary_{int(cfg.primary_threshold_nt)}nT"
    df_primary = subset_by_age(df_all, cfg.age_mask)
    if cfg.require_tio2_quantitative:
        if "tio2_quantitative" not in df_primary.columns:
            raise ValueError(
                "require_tio2_quantitative=True but modeling_dataset lacks "
                "tio2_quantitative; regenerate via preprocess_data"
            )
        df_primary = df_primary[df_primary["tio2_quantitative"] == 1].reset_index(drop=True)
    run_data_mode = (run_metadata or {}).get("data_mode")
    inherited_primary_folds = terrain_sensitivity.shared_spatial_fold_ids(
        df_primary, cfg.n_outer_folds
    )
    print(
        f"Primary analysis: age_mask={cfg.age_mask}, target={target}, "
        f"tio2_quantitative={cfg.require_tio2_quantitative}, "
        f"{len(df_primary):,} pixels, prevalence {df_primary[target].mean():.1%}"
    )

    # 1. Transparent continuous-field analysis.  This preserves magnitude and
    # makes the TiO2 increment directly inspectable; it emits no pseudo-replicated
    # row-level p-value.
    continuous = transparent_analysis.continuous_field_analysis(
        df_primary,
        n_folds=cfg.n_outer_folds,
        fold_ids=inherited_primary_folds,
    )
    if run_data_mode == "real":
        terrain_validity = terrain_sensitivity.evaluate_full_vs_mare(
            df_primary, target, cfg,
            provenance=terrain_sensitivity.USGS_MARE_PROXY,
        )
    elif run_data_mode == "synthetic":
        synthetic_mask = terrain_sensitivity.validate_terrain_mask(
            df_primary,
            provenance=terrain_sensitivity.SYNTHETIC_ALL_VALID_DOMAIN,
        )
        synthetic_keep = synthetic_mask.align_to(df_primary)
        if not np.all(synthetic_keep):
            raise terrain_sensitivity.TerrainMaskError(
                "synthetic generator terrain flag must mark the complete artificial "
                "TiO2 domain as valid"
            )
        synthetic_metadata = synthetic_mask.metadata()
        synthetic_metadata.update({
            "n_rows_in_analysis_scope": int(len(df_primary)),
            "n_terrain_valid_in_analysis_scope": int(synthetic_keep.sum()),
            "terrain_valid_fraction_in_analysis_scope": float(synthetic_keep.mean()),
        })
        terrain_validity = {
            "analysis": "synthetic_all_valid_domain_check",
            "status": "not_applicable_to_real_wac_terrain_calibration",
            "mask": synthetic_metadata,
            "design": {
                "terrain_scope": "artificial all-valid TiO2 domain",
                "all_rows_marked_valid": True,
                "real_usgs_geology_proxy_used": False,
                "real_wac_calibration_inference_allowed": False,
                "interpretation": (
                    "Software-validation domain check only; no lunar terrain-validity "
                    "claim is made from synthetic data."
                ),
            },
        }
    else:
        # The direct API can be called without run metadata.  In that case the
        # origin of a terrain flag is unknowable, so do not silently label it as
        # the repository's USGS-derived real-data proxy.
        terrain_validity = {
            "analysis": "terrain_validity_not_evaluated",
            "status": "skipped_unknown_input_provenance",
            "reason": (
                "Run_Metadata.data_mode is missing or unrecognised; terrain-mask "
                "provenance cannot be asserted."
            ),
        }
    # Apply the same external USGS mare-proxy restriction to the continuous check.
    # Fold membership is assigned once on the full age-restricted scope and then
    # inherited after filtering; only row-local TiO2 is supported by this mask.
    if run_data_mode == "real":
        terrain_validity["full_scope_continuous_raw_tio2"] = (
            transparent_analysis.continuous_field_analysis(
                df_primary,
                h1_features=("tio2",),
                control_features=config.CONTROL_FEATURES,
                n_folds=cfg.n_outer_folds,
                fold_ids=inherited_primary_folds,
            )
        )
        terrain_validity["full_scope_continuous_raw_tio2"]["terrain_scope"] = (
            "full age-restricted scope; raw row-local TiO2 comparator"
        )
        terrain_mask = terrain_sensitivity.validate_terrain_mask(df_primary)
        mare_keep = terrain_mask.align_to(df_primary)
        mare_frame = df_primary.loc[mare_keep].reset_index(drop=True)
        terrain_validity["mare_valid_continuous"] = (
            transparent_analysis.continuous_field_analysis(
                mare_frame,
                h1_features=("tio2",),
                control_features=config.CONTROL_FEATURES,
                n_folds=cfg.n_outer_folds,
                fold_ids=inherited_primary_folds[mare_keep],
            )
        )
        terrain_validity["mare_valid_continuous"]["terrain_scope"] = (
            "USGS mare-proxy mask; raw row-local TiO2 only"
        )
        full_continuous_by_fold = dict(zip(
            terrain_validity["full_scope_continuous_raw_tio2"]["fold_ids"],
            terrain_validity["full_scope_continuous_raw_tio2"]["tio2_incremental_r2"]["per_fold"],
        ))
        mare_continuous_by_fold = dict(zip(
            terrain_validity["mare_valid_continuous"]["fold_ids"],
            terrain_validity["mare_valid_continuous"]["tio2_incremental_r2"]["per_fold"],
        ))
        common_continuous_folds = sorted(
            set(full_continuous_by_fold) & set(mare_continuous_by_fold)
        )
        terrain_validity["mare_minus_full_continuous"] = {
            "comparison_inherited_fold_ids": common_continuous_folds,
            "uses_identical_fold_ids_for_both_scopes": True,
            "tio2_incremental_r2_difference": float(
                np.mean([mare_continuous_by_fold[fold] for fold in common_continuous_folds])
                - np.mean([full_continuous_by_fold[fold] for fold in common_continuous_folds])
            ),
            "interpretation": (
                "Descriptive common-fold scope contrast; the mare and full scopes contain "
                "different rows, so this is not a paired causal effect."
            ),
        }
        mare_centres, mare_gamma, mare_sill = spatial_stats.empirical_variogram(
            mare_frame["lon"].to_numpy(),
            mare_frame["lat"].to_numpy(),
            mare_frame["mag_anomaly"].to_numpy(),
            seed=cfg.random_seed,
        )
        mare_range_km = spatial_stats.decorrelation_range_km(
            mare_centres, mare_gamma, mare_sill
        )
        mare_res_km = float(grid_meta.get("res_km", 30.0))
        mare_block_km = cfg.spatial_block_size_deg * (
            np.pi * config.LUNAR_RADIUS_KM / 180.0
        )
        terrain_validity["mare_valid_spatial_structure"] = {
            "variogram_range_km": float(mare_range_km),
            "approx_effective_sample_size": spatial_stats.effective_sample_size(
                len(mare_frame), mare_res_km ** 2, mare_range_km
            ),
            "cv_block_size_km": float(mare_block_km),
            "block_to_range_ratio": (
                float(mare_block_km / mare_range_km)
                if np.isfinite(mare_range_km) and mare_range_km > 0 else None
            ),
            "inference_note": (
                "Descriptive mare-scope structure diagnostic; it does not supply a "
                "terrain-specific rotation null or full-decision power calibration."
            ),
        }

    # 2. Legacy threshold classifier: retained for exact result traceability and
    # diagnostic comparison, not elevated above the continuous analysis.
    core = core_analysis(df_primary, target, cfg)
    full_mean = core["baselines"]["XGB_Full_PR_AUC"]["mean"]

    # 3. Nested-tuned classifier diagnostic (not binding for criteria / nulls).
    print("Running nested (spatially-tuned) cross-validation diagnostic...")
    groups = df_primary["spatial_block"].values
    tuned_scores, tuned_params = modeling.nested_cv_pr_auc(
        df_primary[config.ALL_FEATURES], df_primary[target], groups,
        cfg.resolved_param_grid(), cfg.n_outer_folds, cfg.n_inner_folds, cfg.random_seed,
    )
    best_params = _pick_best_params(tuned_params, tuned_scores)

    # 4. Spatial-rotation permutation diagnostic (legacy binary statistic).
    print("Running spatial-rotation permutation test...")
    permutation = run_permutation_test(df_primary, df_all, target, grid_meta, cfg, full_mean)

    # Literature benchmark diagnostic: calibrate its one-feature score against its
    # own spatial-rotation null.  The full-model null is not interchangeable.
    print("Running impact-antipode benchmark recovery test...")
    h2_mean = core["baselines"]["H2_Only_PR_AUC"]["mean"]
    h2_permutation = run_permutation_test(
        df_primary, df_all, target, grid_meta, cfg, h2_mean,
        features=config.H2_FEATURES,
    )
    h2_recovered = bool(
        h2_permutation["Empirical_p_value"] < 0.05
        and h2_mean > h2_permutation["Null_95th_PR_AUC"]
    )
    diagnostic_controls = {
        "impact_antipode_benchmark": {
            "role": (
                "Literature-motivated positive-control benchmark; the simple global "
                "distance feature is not assumed to encode every antipodal process."
            ),
            "PR_AUC": float(h2_mean),
            "spatial_rotation_null": h2_permutation,
            "recovered_above_own_spatial_null": h2_recovered,
            "interpretation": (
                "Failure to recover this benchmark prevents strong negative inference "
                "about the surface-TiO2 proxy."
                if not h2_recovered else
                "The benchmark clears its separately calibrated spatial null."
            ),
        }
    }

    # 5. Injection/recovery power.  This is run before interpreting a criteria
    # failure so the negative gate has an empirical sensitivity check.
    print("Running spatial positive-control injection/recovery power analysis...")
    power_experiment, detection_power = run_detection_power(
        df_all, grid_meta, target, cfg, h2_recovered,
    )

    # 6. SHAP on the binding default-config estimator (same family as criteria).
    print("Fitting binding default-config model and computing SHAP...")
    final_model = modeling.fit_final_model(
        df_primary[config.ALL_FEATURES], df_primary[target], {}, cfg.random_seed
    )
    shap_values, X_sample, importance = interpretability.compute_shap(
        final_model, df_primary[config.ALL_FEATURES], cfg.random_seed
    )
    ranking = interpretability.h1_vs_h2_ranking(importance, shap_values, config.ALL_FEATURES)
    lonlat = df_primary.loc[X_sample.index, ["lon", "lat"]]
    interpretability.make_figures(
        final_model, shap_values, X_sample, lonlat, fig_dir, seed=cfg.random_seed
    )

    # 7. Repository-plan criteria (all three must hold). Spatial
    # adequacy is applied separately below as a mandatory publication gate.
    crit_i = bool(permutation["Empirical_p_value"] < 0.05 and core["beats_all_baselines"])
    crit_ii = bool(ranking["h1_outranks_antipode"])
    crit_iii = bool(core["ablation_significant"])
    criteria_supported = crit_i and crit_ii and crit_iii

    # 8. Spatial diagnostics (they expose but cannot repair dependence).
    print("Running spatial diagnostics (variogram, block-bootstrap CI, phase null, block-size sweep)...")
    spatial_diag = run_spatial_diagnostics(df_primary, df_all, target, grid_meta, cfg, full_mean)
    h1_supported, inference_status = spatially_gated_inference(
        criteria_supported, spatial_diag, detection_power,
    )

    # 9. Sensitivity analyses (default config, lighter) + FDR across the grid.
    print("Running sensitivity analyses (age masks x thresholds)...")
    sensitivity = _run_sensitivity(df_all, cfg)
    _apply_fdr_to_sensitivity(sensitivity)

    # F6 guard (moving-goalposts / no-true-Scotsman): the PRIMARY repository-plan
    # cell (config.age_mask x primary threshold) is the binding verdict. If it
    # fails but some OTHER pre-specified subset shows a signal, that is explicitly
    # flagged as hypothesis-generating -- NOT confirmation.
    sens_partial = any(
        cell.get("ablation_significant") and cell.get("beats_h2_only")
        for by_thr in sensitivity.values() for cell in by_thr.values()
        if isinstance(cell, dict) and "ablation_significant" in cell
    )
    underpowered = inference.is_underpowered(
        spatial_diag, core["baselines"]["positive_prevalence"], detection_power,
    )
    falsifiability_guards = {
        "repository_plan_primary_cell": f"{cfg.age_mask} / {int(cfg.primary_threshold_nt)}nT",
        "repository_plan_primary_supported": bool(h1_supported),
        "repository_plan_criteria_met_before_spatial_gate": bool(criteria_supported),
        "spatial_adequacy_required_for_a_positive": True,
        "spatial_adequacy_passed": bool(spatial_diag.get("spatially_adequate", False)),
        "support_survives_largest_partition": bool(
            spatial_diag.get("support_survives_largest_partition", False)
        ),
        # A negative under low power may reflect insufficient independent regions
        # rather than a true absence of signal (reported, not used to flip the verdict).
        "negative_result_may_be_underpowered": bool((not criteria_supported) and underpowered),
        "adequate_detection_power_demonstrated": bool(
            detection_power.get("adequate_power", False)
        ),
        "observed_h2_benchmark_recovered": bool(h2_recovered),
        "sensitivity_shows_partial_signal": bool(sens_partial),
        "subset_signal_is_hypothesis_generating_not_confirmation":
            bool((not h1_supported) and sens_partial),
    }

    metrics = {
        "Run_Metadata": dict(run_metadata or {}),
        "config": {
            "mode": cfg.mode,
            "random_seed": cfg.random_seed,
            "grid_res_deg": cfg.grid_res_deg,
            "age_mask": cfg.age_mask,
            "primary_threshold_nT": cfg.primary_threshold_nt,
            "n_outer_folds": cfg.n_outer_folds,
            "n_inner_folds": cfg.n_inner_folds,
            "n_permutations_requested": cfg.scaled_permutations(),
            "n_power_simulations_per_strength": cfg.scaled_power_simulations(),
            "spatial_block_size_deg": cfg.spatial_block_size_deg,
            "features": config.ALL_FEATURES,
            "parameter_provenance": config.PARAMETER_PROVENANCE,
        },
        "Method_Roles": {
            "transparent_continuous_regression": "descriptive complement with no binding headline",
            "threshold_classifier_default_xgb": (
                "binding estimator for observed scores, spatial nulls, ablation, "
                "and decision criteria"
            ),
            "nested_tuned_xgb": "descriptive tuning diagnostic only; not used for criteria",
            "xgboost_shap": (
                "exploratory interpretation of the binding default-config model; "
                "not a substitute for independent regions"
            ),
            "injection_recovery": "conditional design-sensitivity analysis; not evidence about the Moon",
        },
        "Transparent_Continuous_Analysis": continuous,
        "Terrain_Validity_Sensitivity": terrain_validity,
        "Cross_Validation": {
            "positive_prevalence": core["baselines"]["positive_prevalence"],
            "n_pixels": core["baselines"]["n_pixels"],
            "n_blocks": core["baselines"]["n_blocks"],
            "Dummy_Stratified_PR_AUC": core["baselines"]["Dummy_Stratified_PR_AUC"]["mean"],
            "Dummy_Prior_PR_AUC": core["baselines"]["Dummy_Prior_PR_AUC"]["mean"],
            "LogReg_PR_AUC": core["baselines"]["LogReg_PR_AUC"]["mean"],
            "H2_Only_PR_AUC": core["baselines"]["H2_Only_PR_AUC"]["mean"],
            "H2_Only_PR_AUC_std": core["baselines"]["H2_Only_PR_AUC"]["std"],
            "H2_Only_PR_AUC_per_fold": core["baselines"]["H2_Only_PR_AUC"]["per_fold"],
            "XGB_Full_PR_AUC": core["baselines"]["XGB_Full_PR_AUC"]["mean"],
            "XGB_Full_PR_AUC_std": core["baselines"]["XGB_Full_PR_AUC"]["std"],
            "XGB_Full_PR_AUC_per_fold": core["baselines"]["XGB_Full_PR_AUC"]["per_fold"],
            "XGB_Full_Tuned_PR_AUC": float(np.mean(tuned_scores)),
            "XGB_Full_Tuned_best_params": best_params,
        },
        "Ablation": core["ablation"],
        "Permutation_Test": permutation,
        "Diagnostic_Controls": diagnostic_controls,
        "Power_Analysis": power_experiment,
        "Detection_Power": detection_power,
        "SHAP": ranking,
        "Criteria": {
            "criterion_i_beats_null_and_baselines": crit_i,
            "criterion_ii_h1_tio2_outranks_antipode": crit_ii,
            "criterion_iii_h1_ablation_significant": crit_iii,
            "spatial_adequacy_support_survives_largest_block":
                bool(spatial_diag.get("support_survives_largest_partition", False)),
            "reported_full_ge_logreg": bool(core["full_ge_logreg"]),
        },
        "Inference_Status": inference_status,
        "Surface_Proxy_Supported": bool(h1_supported),
        # Backward-compatible field name.  It refers only to the surface proxy;
        # no metrics file can establish or refute the Nichols temporal mechanism.
        "H1_Supported": bool(h1_supported),
        "Falsifiability_Guards": falsifiability_guards,
        "Spatial_Diagnostics": spatial_diag,
        "Sensitivity": sensitivity,
    }

    out_path = os.path.join(results_dir, "metrics.json")
    with open(out_path, "w") as fh:
        json.dump(metrics, fh, indent=2, default=_json_default)
    print(f"\nSurface-TiO2 proxy inference: {inference_status}  "
          f"(i={crit_i}, ii={crit_ii}, iii={crit_iii}, "
          f"spatially_adequate={spatial_diag.get('spatially_adequate', False)})")
    print(f"Metrics written to {out_path}")
    return metrics


def _light_verdict(df_sub: pd.DataFrame, target: str, cfg: config.PipelineConfig) -> Dict:
    """Lightweight per-cell sensitivity: full, no-H1-TiO2 (the H1 ablation), and
    H2-only. Tests whether removing the compositional TiO2 signal degrades the
    model in this age/threshold cell."""
    groups = df_sub["spatial_block"].values
    y = df_sub[target]
    n = cfg.n_outer_folds
    full = modeling.cross_val_pr_auc(
        modeling.xgb_factory(seed=cfg.random_seed),
        df_sub[config.ALL_FEATURES], y, groups, n,
    )
    no_h1 = modeling.cross_val_pr_auc(
        modeling.xgb_factory(seed=cfg.random_seed),
        df_sub[feature_sets()["no_h1_tio2"]], y, groups, n,
    )
    h2 = modeling.cross_val_pr_auc(
        modeling.xgb_factory(seed=cfg.random_seed),
        df_sub[config.H2_FEATURES], y, groups, n,
    )
    drop = full - no_h1
    wilcoxon_p = _paired_one_sided_greater(full, no_h1)
    return {
        "prevalence": float(y.mean()),
        "n_pixels": int(len(y)),
        "XGB_Full_PR_AUC": float(np.mean(full)),
        "No_H1_TiO2_PR_AUC": float(np.mean(no_h1)),
        "H2_Only_PR_AUC": float(np.mean(h2)),
        "H1_tio2_drop_mean": float(np.mean(drop)),
        "Wilcoxon_p": float(wilcoxon_p),
        "beats_h2_only": bool(np.mean(full) > np.mean(h2)),
        "ablation_significant": bool(np.mean(drop) > 0 and wilcoxon_p < 0.05),
    }


def _sufficient_for_spatial_cv(df_sub: pd.DataFrame, target: str, n_folds: int) -> bool:
    """A blocked CV is only meaningful if positives span several blocks; otherwise
    every fold is degenerate (empty test or train positives)."""
    y = df_sub[target]
    if y.nunique() < 2 or len(df_sub) < 100:
        return False
    n_pos_blocks = df_sub.loc[y == 1, "spatial_block"].nunique()
    return n_pos_blocks >= max(3, n_folds - 1)


def _apply_fdr_to_sensitivity(sensitivity: Dict, alpha: float = 0.05) -> None:
    """Benjamini-Hochberg FDR across every sensitivity cell's ablation Wilcoxon p.

    The sensitivity grid is many correlated tests; controlling the false-discovery
    rate prevents cherry-picking a lucky cell. Adds `Wilcoxon_p_fdr` and
    `significant_after_fdr` in place."""
    cells = [
        cell for by_thr in sensitivity.values() for cell in by_thr.values()
        if isinstance(cell, dict) and "Wilcoxon_p" in cell
    ]
    if not cells:
        return
    p = np.array([c["Wilcoxon_p"] for c in cells], dtype=float)
    m = len(p)
    order = np.argsort(p)
    adj_sorted = np.clip(p[order] * m / np.arange(1, m + 1), 0, 1)
    adj_sorted = np.minimum.accumulate(adj_sorted[::-1])[::-1]  # enforce monotonicity
    for pos, i in enumerate(order):
        cells[i]["Wilcoxon_p_fdr"] = float(adj_sorted[pos])
        cells[i]["significant_after_fdr"] = bool(adj_sorted[pos] < alpha)


def _run_sensitivity(df_all: pd.DataFrame, cfg: config.PipelineConfig) -> Dict:
    out: Dict[str, Dict] = {}
    for age_mask in AGE_MASKS:
        df_sub = subset_by_age(df_all, age_mask)
        out[age_mask] = {}
        for thr in config.BINARY_THRESHOLDS_NT:
            target = f"mag_binary_{int(thr)}nT"
            if not _sufficient_for_spatial_cv(df_sub, target, cfg.n_outer_folds):
                n_pos = int(df_sub[target].sum())
                out[age_mask][f"{int(thr)}nT"] = {
                    "skipped": True,
                    "reason": "insufficient positives spread across spatial blocks",
                    "n_positives": n_pos,
                }
                continue
            out[age_mask][f"{int(thr)}nT"] = _light_verdict(df_sub, target, cfg)
    return out


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"Not JSON serializable: {type(o)}")
