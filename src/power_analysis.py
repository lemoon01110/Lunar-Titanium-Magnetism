"""Spatial positive-control injection/recovery power analysis.

This module answers a narrower question than the main scientific analysis:

    *If a signal of a declared strength were present on the observed lunar
    feature maps, how often would the repository-plan spatial-CV machinery recover
    the feature family that generated it?*

The simulation deliberately reuses the real analysis table, lunar coordinates,
feature support, class prevalence, spatial blocks, XGBoost configuration, and
paired one-sided ablation test.  Only the outcome is synthetic.  Its nuisance
field is a phase-randomised version (or a longitudinal rotation) of the observed
continuous magnetic map, so treating the thousands of pixels as independent
Bernoulli trials is avoided.

``strength`` is a *standardised latent-field coefficient*: a value of 1 adds one
standard deviation of latent magnetic score for a one-standard-deviation increase
in the injected control score.  It is not an odds ratio and is not asserted to be
astrophysically realistic.  The generated binary field is thresholded to retain
the observed prevalence exactly (up to integer rounding).

The primary recovery event mirrors the pipeline's H1 ablation criterion: under
30-degree GroupKFold, the model containing the injected feature family must beat
the otherwise-identical ablated model with positive mean PR-AUC drop and a paired
one-sided p-value below alpha.  A second, spatially robust event additionally
requires the drop to stay positive at the largest requested block size (60 degrees
by default), matching the project's large-block adequacy logic.

Examples
--------
Run the antipode positive control against the canonical real-data structure::

    python -m src.power_analysis --control h2_antipode --simulations 30 \
        --output Paper-and-Pitch/positive_control_power_analysis.json

Use ``--estimator logistic`` only for a quick smoke run; ``xgboost`` is the
pipeline-matched default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.model_selection import GroupKFold

from . import config, modeling, spatial, spatial_stats


CONTROL_ALIASES: Mapping[str, str] = {
    "h1": "h1_tio2",
    "h1_tio2": "h1_tio2",
    "h2": "h2_antipode",
    "h2_antipode": "h2_antipode",
}
NOISE_METHODS: Tuple[str, ...] = ("phase", "rotation")
ESTIMATORS: Tuple[str, ...] = ("xgboost", "logistic")


@dataclass(frozen=True)
class PowerAnalysisConfig:
    """Configuration for a paired spatial injection/recovery experiment."""

    control: str = "h2_antipode"
    strengths: Tuple[float, ...] = config.POWER_STRENGTHS
    n_simulations: int = config.N_POWER_SIMULATIONS
    age_mask: str = "imbrian"
    target_column: str = f"mag_binary_{int(config.PRIMARY_THRESHOLD_NT)}nT"
    prevalence: float | None = None
    noise_method: str = "phase"
    estimator: str = "xgboost"
    n_outer_folds: int = config.N_OUTER_FOLDS
    primary_block_size_deg: float = config.SPATIAL_BLOCK_SIZE_DEG
    adequacy_block_size_deg: float = config.POWER_ADEQUACY_BLOCK_DEG
    alpha: float = 0.05
    target_power: float = config.MIN_DETECTION_POWER
    # Optional externally justified benchmark.  It must be on ``strengths``;
    # leaving it None is more honest than silently declaring an arbitrary effect.
    target_effect_strength: float | None = None
    simulation_seed: int = config.RANDOM_SEED
    model_seed: int = config.RANDOM_SEED
    xgb_n_jobs: int = 2
    variogram_pairs: int = 60_000
    include_simulations: bool = True

    def validated(self) -> "PowerAnalysisConfig":
        canonical_control(self.control)
        if not self.strengths:
            raise ValueError("At least one injected strength is required")
        if any(not np.isfinite(x) or x < 0 for x in self.strengths):
            raise ValueError("Injected strengths must be finite and non-negative")
        if self.n_simulations < 1:
            raise ValueError("n_simulations must be positive")
        if self.noise_method not in NOISE_METHODS:
            raise ValueError(f"noise_method must be one of {NOISE_METHODS}")
        if self.estimator not in ESTIMATORS:
            raise ValueError(f"estimator must be one of {ESTIMATORS}")
        if self.n_outer_folds < 2:
            raise ValueError("n_outer_folds must be at least two")
        if self.primary_block_size_deg <= 0 or self.adequacy_block_size_deg <= 0:
            raise ValueError("CV block sizes must be positive")
        if self.adequacy_block_size_deg < self.primary_block_size_deg:
            raise ValueError("adequacy block cannot be smaller than the primary block")
        if not 0 < self.alpha < 1:
            raise ValueError("alpha must lie strictly between zero and one")
        if not 0 < self.target_power < 1:
            raise ValueError("target_power must lie strictly between zero and one")
        if self.target_effect_strength is not None:
            if not np.isfinite(self.target_effect_strength) or self.target_effect_strength <= 0:
                raise ValueError("target_effect_strength must be finite and positive")
            if not any(np.isclose(self.target_effect_strength, x) for x in self.strengths):
                raise ValueError("target_effect_strength must be included in strengths")
        if self.prevalence is not None and not 0 < self.prevalence < 1:
            raise ValueError("prevalence must lie strictly between zero and one")
        if self.variogram_pairs < 100:
            raise ValueError("variogram_pairs must be at least 100")
        return self

    @property
    def block_sizes_deg(self) -> Tuple[float, ...]:
        return tuple(sorted({self.primary_block_size_deg, self.adequacy_block_size_deg}))


def canonical_control(control: str) -> str:
    """Return the canonical positive-control name, rejecting silent fallbacks."""
    try:
        return CONTROL_ALIASES[control]
    except KeyError as exc:
        raise ValueError(f"Unknown control {control!r}; choose from {tuple(CONTROL_ALIASES)}") from exc


def _zscore(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Signal/noise score contains non-finite values")
    sd = float(np.std(values))
    if sd <= 0:
        raise ValueError("Signal/noise score has zero variance")
    return (values - float(np.mean(values))) / sd


def _validated_binary_target(values: pd.Series, target_column: str) -> np.ndarray:
    """Return strict 0/1 labels without coercing fractional or string values."""
    series = pd.Series(values, copy=False)
    if series.isna().any():
        raise ValueError(
            f"Observed target {target_column!r} must contain non-null boolean/0/1 values"
        )
    if pd.api.types.is_bool_dtype(series.dtype):
        return series.to_numpy(dtype=np.int8)
    if not pd.api.types.is_numeric_dtype(series.dtype):
        raise ValueError(
            f"Observed target {target_column!r} must contain non-null boolean/0/1 values"
        )
    numeric = series.to_numpy(dtype=float)
    if not np.isfinite(numeric).all() or not np.isin(numeric, (0.0, 1.0)).all():
        raise ValueError(
            f"Observed target {target_column!r} must contain non-null boolean/0/1 values"
        )
    return numeric.astype(np.int8)


def build_signal_score(df: pd.DataFrame, control: str) -> np.ndarray:
    """Build the predeclared, outcome-free score used for signal injection.

    ``h2_antipode`` uses the project's fixed 300-km exponential proximity
    kernel. ``h1_tio2`` averages separately standardised members of the repository-plan
    compositional TiO2 family, then standardises that family score.
    """
    control = canonical_control(control)
    if control == "h2_antipode":
        _require_columns(df, ["dist_to_antipode_km"])
        distance = df["dist_to_antipode_km"].to_numpy(dtype=float)
        score = np.exp(-distance / config.ANTIPODE_LENGTH_SCALE_KM)
        return _zscore(score)

    _require_columns(df, config.H1_FEATURES)
    members = np.column_stack([_zscore(df[c].to_numpy(dtype=float)) for c in config.H1_FEATURES])
    return _zscore(np.mean(members, axis=1))


def control_feature_sets(control: str) -> Tuple[List[str], List[str]]:
    """Return (with-control, ablated) feature lists for the direct recovery test."""
    control = canonical_control(control)
    removed = set(
        config.TIO2_DERIVED_FEATURES if control == "h1_tio2" else config.H2_FEATURES
    )
    full = list(config.ALL_FEATURES)
    ablated = [feature for feature in full if feature not in removed]
    if not removed.intersection(full) or len(ablated) == len(full):
        raise RuntimeError(f"Control {control!r} has no repository-plan feature to ablate")
    return full, ablated


def inject_binary_target(
    spatial_noise: np.ndarray,
    signal_score: np.ndarray,
    strength: float,
    prevalence: float,
) -> np.ndarray:
    """Add a known latent signal and threshold to an exact binary prevalence.

    Selection uses a stable sort, so tied latent values are resolved
    deterministically by row order.  No observed labels or model scores are used.
    """
    if not np.isfinite(strength) or strength < 0:
        raise ValueError("strength must be finite and non-negative")
    if not 0 < prevalence < 1:
        raise ValueError("prevalence must lie strictly between zero and one")
    noise = _zscore(np.asarray(spatial_noise, dtype=float))
    signal = _zscore(np.asarray(signal_score, dtype=float))
    if noise.shape != signal.shape or noise.ndim != 1:
        raise ValueError("spatial_noise and signal_score must be equal-length 1-D arrays")

    n_positive = int(np.clip(round(len(noise) * prevalence), 1, len(noise) - 1))
    latent = noise + float(strength) * signal
    order = np.argsort(latent, kind="mergesort")
    y = np.zeros(len(latent), dtype=np.int8)
    y[order[-n_positive:]] = 1
    return y


def _grid_shape(df_all: pd.DataFrame, grid_meta: Mapping[str, Any] | None) -> Tuple[int, int]:
    if grid_meta is not None and "height" in grid_meta and "width" in grid_meta:
        height, width = int(grid_meta["height"]), int(grid_meta["width"])
    else:
        height = int(df_all["row_idx"].max()) + 1
        width = int(df_all["col_idx"].max()) + 1
    if height <= 0 or width <= 1:
        raise ValueError("Invalid grid dimensions")
    return height, width


def generate_spatial_noise_fields(
    df_all: pd.DataFrame,
    df_analysis: pd.DataFrame,
    n_simulations: int,
    seed: int,
    method: str = "phase",
    grid_meta: Mapping[str, Any] | None = None,
) -> Tuple[List[np.ndarray], Dict[str, Any]]:
    """Generate nuisance fields with the observed magnetic spatial structure.

    Phase randomisation keeps the observed 2-D amplitude spectrum while drawing
    new phases.  Rotation keeps the observed values and east-west arrangement
    exactly, but the finite rotations are dependent and therefore give a
    conditional placement analysis rather than independent Monte Carlo worlds.
    """
    if method not in NOISE_METHODS:
        raise ValueError(f"method must be one of {NOISE_METHODS}")
    if n_simulations < 1:
        raise ValueError("n_simulations must be positive")
    _require_columns(df_all, ["row_idx", "col_idx", "mag_anomaly"])
    _require_columns(df_analysis, ["row_idx", "col_idx"])
    height, width = _grid_shape(df_all, grid_meta)

    rows_all = df_all["row_idx"].to_numpy(dtype=int)
    cols_all = df_all["col_idx"].to_numpy(dtype=int)
    rows = df_analysis["row_idx"].to_numpy(dtype=int)
    cols = df_analysis["col_idx"].to_numpy(dtype=int)
    if (rows_all < 0).any() or (rows_all >= height).any() or (cols_all < 0).any() or (cols_all >= width).any():
        raise ValueError("df_all row/column indices fall outside the declared grid")
    if (rows < 0).any() or (rows >= height).any() or (cols < 0).any() or (cols >= width).any():
        raise ValueError("analysis row/column indices fall outside the declared grid")

    grid = np.full((height, width), np.nan, dtype=float)
    grid[rows_all, cols_all] = np.log1p(np.clip(df_all["mag_anomaly"].to_numpy(dtype=float), 0, None))
    rng = np.random.default_rng(seed)
    fields: List[np.ndarray] = []

    if method == "phase":
        for _ in range(n_simulations):
            surrogate = spatial_stats.phase_randomized_surrogate(grid, rng)
            fields.append(_zscore(surrogate[rows, cols]))
        metadata = {
            "method": "phase_randomized_log1p_observed_continuous_magnetic_field",
            "simulations_exchangeable": True,
            "preserves": (
                "two-dimensional amplitude spectrum of log1p(observed magnetic field) "
                "approximately, after missing-cell fill"
            ),
        }
        return fields, metadata

    available = np.arange(1, width, dtype=int)
    if n_simulations > len(available):
        raise ValueError(
            f"rotation noise offers only {len(available)} non-identity shifts, "
            f"fewer than n_simulations={n_simulations}"
        )
    shifts = rng.choice(available, size=n_simulations, replace=False)
    for shift in shifts:
        rotated = np.roll(grid, shift=int(shift), axis=1)
        sample = rotated[rows, cols]
        if not np.isfinite(sample).all():
            raise ValueError("Rotation moved missing grid cells into the analysis mask")
        fields.append(_zscore(sample))
    metadata = {
        "method": "non_identity_longitudinal_rotations_of_observed_continuous_magnetic_field",
        "longitude_shifts_pixels": [int(x) for x in shifts],
        "simulations_exchangeable": False,
        "preserves": "observed values and within-row east-west structure exactly",
    }
    return fields, metadata


def groups_for_block_size(df: pd.DataFrame, block_size_deg: float) -> np.ndarray:
    """Use the repository-plan primary groups exactly; rederive only sensitivity groups."""
    if np.isclose(block_size_deg, config.SPATIAL_BLOCK_SIZE_DEG) and "spatial_block" in df:
        return df["spatial_block"].to_numpy()
    _require_columns(df, ["lon", "lat"])
    return spatial.spatial_block_ids(
        df["lon"].to_numpy(dtype=float),
        df["lat"].to_numpy(dtype=float),
        block_size_deg=float(block_size_deg),
    )


def grouped_fold_audit(y: np.ndarray, groups: np.ndarray, n_splits: int) -> Dict[str, Any]:
    """Describe GroupKFold support and assert no group crosses train/test."""
    y = np.asarray(y, dtype=int)
    groups = np.asarray(groups)
    if len(y) != len(groups):
        raise ValueError("y and groups must have equal length")
    actual_splits = modeling._n_splits(groups, n_splits)
    splitter = GroupKFold(n_splits=actual_splits)
    test_positive_counts: List[int] = []
    test_positive_blocks: List[int] = []
    valid = 0
    for train_idx, test_idx in splitter.split(np.zeros((len(y), 1)), y, groups):
        if set(groups[train_idx]).intersection(set(groups[test_idx])):
            raise RuntimeError("Spatial group leakage detected")
        n_test_pos = int(y[test_idx].sum())
        n_train_pos = int(y[train_idx].sum())
        test_positive_counts.append(n_test_pos)
        test_positive_blocks.append(int(np.unique(groups[test_idx][y[test_idx] == 1]).size))
        valid += int(n_test_pos > 0 and n_train_pos > 0)
    return {
        "requested_folds": int(n_splits),
        "actual_folds": int(actual_splits),
        "valid_pr_auc_folds": int(valid),
        "test_positive_counts": test_positive_counts,
        "test_positive_block_counts": test_positive_blocks,
        # Best case for a one-sided exact signed-rank/sign pattern with no ties.
        "best_case_one_sided_p_resolution": float(0.5 ** valid) if valid else 1.0,
        "groups_disjoint_in_every_split": True,
    }


def _factory(estimator: str, seed: int, xgb_n_jobs: int):
    if estimator == "xgboost":
        return modeling.xgb_factory(seed=seed, n_jobs=xgb_n_jobs)
    if estimator == "logistic":
        return modeling.logreg_factory(seed=seed)
    raise ValueError(f"estimator must be one of {ESTIMATORS}")


def _paired_one_sided_greater(a: np.ndarray, b: np.ndarray) -> float:
    """The same paired ablation test and fallback used by ``src.evaluation``."""
    diff = np.asarray(a) - np.asarray(b)
    if np.allclose(diff, 0):
        return 1.0
    try:
        return float(stats.wilcoxon(a, b, alternative="greater", zero_method="zsplit").pvalue)
    except ValueError:
        return float(stats.ttest_rel(a, b, alternative="greater").pvalue)


def evaluate_control_ablation(
    df: pd.DataFrame,
    y: np.ndarray,
    control: str,
    groups: np.ndarray,
    n_splits: int = config.N_OUTER_FOLDS,
    alpha: float = 0.05,
    estimator: str = "xgboost",
    model_seed: int = config.RANDOM_SEED,
    xgb_n_jobs: int = 2,
) -> Dict[str, Any]:
    """Run one leakage-free with-control versus ablated spatial CV comparison."""
    y_array = np.asarray(y, dtype=int)
    if set(np.unique(y_array)) != {0, 1}:
        raise ValueError("Synthetic target must contain both binary classes")
    full_features, ablated_features = control_feature_sets(control)
    _require_columns(df, full_features)
    audit = grouped_fold_audit(y_array, groups, n_splits)
    y_series = pd.Series(y_array)
    factory = _factory(estimator, model_seed, xgb_n_jobs)
    with_scores = modeling.cross_val_pr_auc(
        factory, df[full_features], y_series, np.asarray(groups), n_splits
    )
    without_scores = modeling.cross_val_pr_auc(
        factory, df[ablated_features], y_series, np.asarray(groups), n_splits
    )
    if with_scores.shape != without_scores.shape:
        raise RuntimeError("Compared models produced non-paired fold scores")
    differences = with_scores - without_scores
    p_value = _paired_one_sided_greater(with_scores, without_scores)
    mean_drop = float(np.mean(differences))
    return {
        "with_control_pr_auc": float(np.mean(with_scores)),
        "without_control_pr_auc": float(np.mean(without_scores)),
        "mean_pr_auc_drop": mean_drop,
        "per_fold_pr_auc_drop": differences.tolist(),
        "paired_one_sided_p": float(p_value),
        "detected": bool(mean_drop > 0 and p_value < alpha),
        "fold_audit": audit,
    }


def injected_effect_summary(y: np.ndarray, signal_score: np.ndarray) -> Dict[str, float]:
    """Return an interpretable achieved contrast alongside the latent coefficient."""
    y = np.asarray(y, dtype=int)
    signal = np.asarray(signal_score, dtype=float)
    q1, q3 = np.quantile(signal, [0.25, 0.75])
    low = y[signal <= q1]
    high = y[signal >= q3]
    low_risk = float(np.mean(low))
    high_risk = float(np.mean(high))
    # Haldane-Anscombe corrected odds ratio remains finite at this rare prevalence.
    high_pos, high_neg = float(high.sum()), float(len(high) - high.sum())
    low_pos, low_neg = float(low.sum()), float(len(low) - low.sum())
    odds_ratio = ((high_pos + 0.5) * (low_neg + 0.5)) / (
        (high_neg + 0.5) * (low_pos + 0.5)
    )
    return {
        "top_quartile_positive_rate": high_risk,
        "bottom_quartile_positive_rate": low_risk,
        "top_minus_bottom_risk": high_risk - low_risk,
        "top_vs_bottom_corrected_odds_ratio": float(odds_ratio),
    }


def wilson_interval(successes: int, trials: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Wilson score interval for a Monte Carlo detection proportion."""
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("Require 0 <= successes <= trials and trials > 0")
    if not 0 < confidence < 1:
        raise ValueError("confidence must lie strictly between zero and one")
    z = float(stats.norm.ppf(0.5 + confidence / 2.0))
    phat = successes / trials
    denom = 1.0 + z * z / trials
    centre = (phat + z * z / (2.0 * trials)) / denom
    half = z * np.sqrt(phat * (1.0 - phat) / trials + z * z / (4.0 * trials * trials)) / denom
    return float(max(0.0, centre - half)), float(min(1.0, centre + half))


def _aggregate_power(simulations: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    strengths = sorted({float(row["strength"]) for row in simulations})
    curve: List[Dict[str, Any]] = []
    for strength in strengths:
        rows = [row for row in simulations if float(row["strength"]) == strength]
        n = len(rows)
        primary_hits = sum(bool(row["primary_detected"]) for row in rows)
        robust_hits = sum(bool(row["spatially_robust_detected"]) for row in rows)
        primary_ci = wilson_interval(primary_hits, n)
        robust_ci = wilson_interval(robust_hits, n)
        primary_cells = [row["blocks"][row["primary_block_key"]] for row in rows]
        adequate_cells = [row["blocks"][row["adequacy_block_key"]] for row in rows]
        effects = [row["achieved_effect"] for row in rows]
        curve.append({
            "strength": strength,
            "n_simulations": n,
            "primary_detection_count": int(primary_hits),
            "primary_detection_probability": float(primary_hits / n),
            "primary_detection_wilson_95": list(primary_ci),
            "spatially_robust_detection_count": int(robust_hits),
            "spatially_robust_detection_probability": float(robust_hits / n),
            "spatially_robust_detection_wilson_95": list(robust_ci),
            "mean_primary_with_control_pr_auc": float(np.mean([x["with_control_pr_auc"] for x in primary_cells])),
            "mean_primary_without_control_pr_auc": float(np.mean([x["without_control_pr_auc"] for x in primary_cells])),
            "mean_primary_pr_auc_drop": float(np.mean([x["mean_pr_auc_drop"] for x in primary_cells])),
            "mean_adequacy_block_pr_auc_drop": float(np.mean([x["mean_pr_auc_drop"] for x in adequate_cells])),
            "median_positive_spatial_blocks": float(np.median([row["positive_spatial_blocks"] for row in rows])),
            "median_top_minus_bottom_risk": float(np.median([x["top_minus_bottom_risk"] for x in effects])),
            "median_top_vs_bottom_corrected_odds_ratio": float(np.median([
                x["top_vs_bottom_corrected_odds_ratio"] for x in effects
            ])),
        })
    return curve


def minimum_detectable_effect(
    power_curve: Sequence[Mapping[str, Any]],
    target_power: float = config.MIN_DETECTION_POWER,
    probability_key: str = "spatially_robust_detection_probability",
    interval_key: str = "spatially_robust_detection_wilson_95",
) -> Dict[str, Any]:
    """Find the first tested positive strength reaching the requested power.

    No interpolation is performed.  The result is a tested-grid bound, not a
    precise continuous MDE.  A separate conservative value requires the lower
    Wilson bound itself to clear the target.
    """
    if not 0 < target_power < 1:
        raise ValueError("target_power must lie strictly between zero and one")
    rows = sorted((dict(row) for row in power_curve if float(row["strength"]) > 0),
                  key=lambda row: float(row["strength"]))
    if not rows:
        return {
            "status": "no_positive_strengths_tested",
            "target_power": float(target_power),
            "point_estimate_strength": None,
            "conservative_95pct_strength": None,
        }

    point_index = next(
        (i for i, row in enumerate(rows) if float(row[probability_key]) >= target_power), None
    )
    conservative_index = next(
        (i for i, row in enumerate(rows) if float(row[interval_key][0]) >= target_power), None
    )
    if point_index is None:
        return {
            "status": "not_reached_on_tested_grid",
            "target_power": float(target_power),
            "point_estimate_strength": None,
            "conservative_95pct_strength": None,
            "largest_tested_strength": float(rows[-1]["strength"]),
            "power_at_largest_strength": float(rows[-1][probability_key]),
            "interpretation": "The MDE is larger than the tested grid or is not identifiable with this design.",
        }

    point = rows[point_index]
    previous = 0.0 if point_index == 0 else float(rows[point_index - 1]["strength"])
    conservative = None if conservative_index is None else float(rows[conservative_index]["strength"])
    return {
        "status": "reached_on_tested_grid",
        "target_power": float(target_power),
        "point_estimate_strength": float(point["strength"]),
        "tested_grid_bracket": [previous, float(point["strength"])],
        "power_at_point_estimate": float(point[probability_key]),
        "wilson_95_at_point_estimate": list(point[interval_key]),
        "conservative_95pct_strength": conservative,
        "median_top_minus_bottom_risk_at_point": float(point["median_top_minus_bottom_risk"]),
        "median_top_vs_bottom_corrected_odds_ratio_at_point": float(
            point["median_top_vs_bottom_corrected_odds_ratio"]
        ),
        "interpretation": "First tested coefficient reaching the target; no between-grid interpolation was used.",
    }


def structural_diagnostics(
    df: pd.DataFrame,
    target_column: str,
    grid_meta: Mapping[str, Any] | None,
    cfg: PowerAnalysisConfig,
) -> Dict[str, Any]:
    """Separate nominal pixels/blocks from approximate independent information."""
    _require_columns(df, ["lon", "lat", "mag_anomaly", target_column])
    y = _validated_binary_target(df[target_column], target_column)
    centres, gamma, sill = spatial_stats.empirical_variogram(
        df["lon"].to_numpy(dtype=float),
        df["lat"].to_numpy(dtype=float),
        df["mag_anomaly"].to_numpy(dtype=float),
        n_pairs=cfg.variogram_pairs,
        seed=cfg.simulation_seed,
    )
    correlation_range = spatial_stats.decorrelation_range_km(centres, gamma, sill)
    if grid_meta is not None and "res_km" in grid_meta:
        res_km = float(grid_meta["res_km"])
    else:
        res_km = config.GRID_RES_DEG * (
            np.pi * config.LUNAR_RADIUS_KM / 180.0
        )
    range_estimable = bool(np.isfinite(correlation_range) and correlation_range > 0)
    effective_regions = spatial_stats.effective_sample_size(
        len(df), res_km ** 2, correlation_range
    )

    blocks: Dict[str, Any] = {}
    for size in cfg.block_sizes_deg:
        groups = groups_for_block_size(df, size)
        block_km = size * (np.pi * config.LUNAR_RADIUS_KM / 180.0)
        blocks[_block_key(size)] = {
            "block_size_deg": float(size),
            "approx_block_size_km": float(block_km),
            "n_geometric_blocks": int(np.unique(groups).size),
            "positive_blocks_observed_target": int(np.unique(groups[y == 1]).size),
            "block_to_variogram_range_ratio": (
                float(block_km / correlation_range)
                if np.isfinite(correlation_range) and correlation_range > 0 else None
            ),
            "observed_target_fold_audit": grouped_fold_audit(y, groups, cfg.n_outer_folds),
        }

    primary_ratio = blocks[_block_key(cfg.primary_block_size_deg)]["block_to_variogram_range_ratio"]
    return {
        "nominal_pixel_count": int(len(df)),
        "observed_positive_pixel_count": int(y.sum()),
        "observed_prevalence": float(y.mean()),
        "observed_positive_primary_blocks": int(
            np.unique(groups_for_block_size(df, cfg.primary_block_size_deg)[y == 1]).size
        ),
        "variogram_range_km": float(correlation_range),
        "variogram_range_estimable": range_estimable,
        "approx_effective_independent_regions": float(effective_regions),
        "effective_region_estimate_is_diagnostic_not_exact": True,
        "primary_block_smaller_than_variogram_range": bool(
            primary_ratio is not None and primary_ratio < 1
        ),
        "structurally_limited": bool(
            not range_estimable
            or effective_regions < config.MIN_EFFECTIVE_REGIONS
            or (primary_ratio is not None and primary_ratio < 1)
        ),
        "cv_block_summaries": blocks,
        "distinction": (
            "Geometric CV blocks are non-overlapping holdouts, but they are not automatically "
            "independent observations. The variogram-area estimate describes effective information."
        ),
    }


def run_power_analysis_frame(
    df_all: pd.DataFrame,
    grid_meta: Mapping[str, Any] | None = None,
    cfg: PowerAnalysisConfig | None = None,
) -> Dict[str, Any]:
    """Run the analysis from an in-memory real modeling table (testable API)."""
    cfg = (cfg or PowerAnalysisConfig()).validated()
    control = canonical_control(cfg.control)
    _require_columns(df_all, [
        "age_class", "row_idx", "col_idx", "lon", "lat", "mag_anomaly",
        "spatial_block", cfg.target_column, *config.ALL_FEATURES,
    ])
    df_analysis = _subset_by_age(df_all, cfg.age_mask)
    if len(df_analysis) < 100:
        raise ValueError("Analysis subset has fewer than 100 rows")
    observed_y = _validated_binary_target(
        df_analysis[cfg.target_column], cfg.target_column,
    )
    if set(np.unique(observed_y)) != {0, 1}:
        raise ValueError(f"Observed target {cfg.target_column!r} must contain both classes")
    prevalence = float(observed_y.mean() if cfg.prevalence is None else cfg.prevalence)
    signal = build_signal_score(df_analysis, control)
    full_features, ablated_features = control_feature_sets(control)
    noise_fields, noise_metadata = generate_spatial_noise_fields(
        df_all,
        df_analysis,
        cfg.n_simulations,
        cfg.simulation_seed,
        method=cfg.noise_method,
        grid_meta=grid_meta,
    )
    group_map = {
        _block_key(size): groups_for_block_size(df_analysis, size)
        for size in cfg.block_sizes_deg
    }
    primary_key = _block_key(cfg.primary_block_size_deg)
    adequacy_key = _block_key(cfg.adequacy_block_size_deg)

    simulations: List[Dict[str, Any]] = []
    for strength in sorted(set(float(x) for x in cfg.strengths)):
        for replicate, noise in enumerate(noise_fields):
            y = inject_binary_target(noise, signal, strength, prevalence)
            block_results: Dict[str, Any] = {}
            for block_key, groups in group_map.items():
                block_results[block_key] = evaluate_control_ablation(
                    df_analysis,
                    y,
                    control,
                    groups,
                    n_splits=cfg.n_outer_folds,
                    alpha=cfg.alpha,
                    estimator=cfg.estimator,
                    model_seed=cfg.model_seed,
                    xgb_n_jobs=cfg.xgb_n_jobs,
                )
            primary_detected = bool(block_results[primary_key]["detected"])
            adequate_drop_positive = bool(block_results[adequacy_key]["mean_pr_auc_drop"] > 0)
            simulations.append({
                "strength": strength,
                "replicate": int(replicate),
                "prevalence": float(y.mean()),
                "positive_pixels": int(y.sum()),
                "positive_spatial_blocks": int(np.unique(group_map[primary_key][y == 1]).size),
                "achieved_effect": injected_effect_summary(y, signal),
                "primary_block_key": primary_key,
                "adequacy_block_key": adequacy_key,
                "primary_detected": primary_detected,
                "adequacy_block_drop_positive": adequate_drop_positive,
                "spatially_robust_detected": bool(primary_detected and adequate_drop_positive),
                "blocks": block_results,
            })

    curve = _aggregate_power(simulations)
    mde = minimum_detectable_effect(curve, cfg.target_power)
    structure = structural_diagnostics(df_analysis, cfg.target_column, grid_meta, cfg)
    benchmark = next(
        (
            row for row in curve
            if cfg.target_effect_strength is not None
            and np.isclose(row["strength"], cfg.target_effect_strength)
        ),
        None,
    )
    benchmark_power = (
        None if benchmark is None
        else float(benchmark["spatially_robust_detection_probability"])
    )
    benchmark_ci = (
        None if benchmark is None
        else list(benchmark["spatially_robust_detection_wilson_95"])
    )
    positive_control_recovered = mde.get("status") == "reached_on_tested_grid"
    # "Adequate" is intentionally conservative: it requires a declared scientific
    # benchmark, its lower Monte Carlo confidence bound to clear the power target,
    # and no structural effective-sample warning.  Recovery of an arbitrarily huge
    # injected signal alone must not turn n_eff~1 into an adequate study.
    adequate_power = bool(
        benchmark is not None
        and benchmark_ci is not None
        and benchmark_ci[0] >= cfg.target_power
        and not structure["structurally_limited"]
    )
    result: Dict[str, Any] = {
        "schema_version": "1.0",
        "analysis": "positive_control_spatial_injection_recovery_power",
        "control": control,
        "estimand": {
            "strength_unit": (
                "standard deviations of latent magnetic nuisance field added per one-SD "
                "increase in the fixed control score"
            ),
            "binary_target": cfg.target_column,
            "fixed_prevalence": prevalence,
            "with_control_features": full_features,
            "ablated_features": ablated_features,
        },
        "design": {
            "age_mask": cfg.age_mask,
            "n_simulations_per_strength": cfg.n_simulations,
            "strengths": sorted(set(float(x) for x in cfg.strengths)),
            "noise": noise_metadata,
            "estimator": cfg.estimator,
            "n_outer_folds": cfg.n_outer_folds,
            "primary_block_size_deg": cfg.primary_block_size_deg,
            "adequacy_block_size_deg": cfg.adequacy_block_size_deg,
            "alpha": cfg.alpha,
            "target_power": cfg.target_power,
            "target_effect_strength": cfg.target_effect_strength,
            "simulation_seed": cfg.simulation_seed,
            "model_seed": cfg.model_seed,
            "primary_detection_rule": (
                "paired one-sided with-control > ablated PR-AUC at alpha, with positive mean drop"
            ),
            "spatially_robust_rule": (
                "primary detection and positive mean ablation drop at the largest block"
            ),
        },
        "structural_diagnostics": structure,
        "power_curve": curve,
        "minimum_detectable_effect": mde,
        "Detection_Power": {
            "adequate_power": adequate_power,
            "power_at_target_effect": benchmark_power,
            "power_at_target_effect_wilson_95": benchmark_ci,
            "target_effect_strength": cfg.target_effect_strength,
            "positive_control_recovered": bool(positive_control_recovered),
            "qualification": (
                "Recovery means at least one tested injected strength reached point-estimate "
                "target power; adequacy additionally requires a declared target effect, its "
                "lower confidence bound, and sufficient effective spatial information."
            ),
        },
        "limitations": [
            "Injection recovery validates sensitivity to the encoded spatial feature; it does not prove the real association exists.",
            "Strength is a standardised latent coefficient, not a lunar-physics parameter or an odds ratio.",
            "The result is conditional on this map, mask, prevalence, feature support, model, and fold geometry.",
            "The tested-grid MDE is not interpolated; Monte Carlo uncertainty is reported with every power estimate.",
            "Phase surrogates preserve the observed spectrum approximately after filling unmapped cells; rotation surrogates are dependent placements.",
            "This direct control-ablation power is not power for every conjunctive H1 publication criterion (permutation and SHAP ranking are not resimulated).",
            "Non-overlapping CV blocks prevent row leakage but cannot create independent lunar regions when the correlation range exceeds the blocks.",
        ],
    }
    if cfg.include_simulations:
        result["simulations"] = simulations
    return result


def run_power_analysis(
    dataset_path: str | None = None,
    grid_meta_path: str | None = None,
    cfg: PowerAnalysisConfig | None = None,
) -> Dict[str, Any]:
    """Load canonical artifacts and run the positive-control power analysis."""
    dataset_path = dataset_path or os.path.join(config.PROCESSED_DIR, "modeling_dataset.csv")
    grid_meta_path = grid_meta_path or os.path.join(config.PROCESSED_DIR, "grid_meta.json")
    df_all = pd.read_csv(dataset_path)
    with open(grid_meta_path, encoding="utf-8") as handle:
        grid_meta = json.load(handle)
    result = run_power_analysis_frame(df_all, grid_meta, cfg)
    result["input_artifacts"] = {
        "modeling_dataset": {
            "path": _portable_input_path(dataset_path),
            "sha256": _sha256_file(dataset_path),
        },
        "grid_metadata": {
            "path": _portable_input_path(grid_meta_path),
            "sha256": _sha256_file(grid_meta_path),
        },
    }
    return result


def write_power_result(result: Mapping[str, Any], output_path: str) -> None:
    """Write JSON atomically so an interrupted run cannot leave a partial artifact."""
    output_path = os.path.abspath(output_path)
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    temporary = output_path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False, default=_json_default)
        handle.write("\n")
    os.replace(temporary, output_path)


def _subset_by_age(df: pd.DataFrame, age_mask: str) -> pd.DataFrame:
    if age_mask == "imbrian":
        keep = df["age_class"].to_numpy() == config.AGE_IMBRIAN
    elif age_mask == "imbrian_nectarian":
        keep = np.isin(df["age_class"].to_numpy(), [config.AGE_IMBRIAN, config.AGE_NECTARIAN])
    elif age_mask == "none":
        keep = np.ones(len(df), dtype=bool)
    else:
        raise ValueError("age_mask must be one of ('imbrian', 'imbrian_nectarian', 'none')")
    return df.loc[keep].reset_index(drop=True)


def _block_key(size: float) -> str:
    return f"{float(size):g}deg"


def _require_columns(df: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = sorted(set(columns).difference(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_input_path(path: str) -> str:
    absolute = os.path.abspath(path)
    try:
        relative = os.path.relpath(absolute, config.PROJECT_ROOT)
    except ValueError:
        return absolute
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        return absolute
    return relative.replace(os.sep, "/")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=os.path.join(config.PROCESSED_DIR, "modeling_dataset.csv"))
    parser.add_argument("--grid-meta", default=os.path.join(config.PROCESSED_DIR, "grid_meta.json"))
    parser.add_argument("--control", choices=("h1_tio2", "h2_antipode"), default="h2_antipode")
    parser.add_argument("--strengths", type=float, nargs="+", default=list(PowerAnalysisConfig.strengths))
    parser.add_argument("--simulations", type=int, default=PowerAnalysisConfig.n_simulations)
    parser.add_argument("--age-mask", choices=("imbrian", "imbrian_nectarian", "none"), default="imbrian")
    parser.add_argument(
        "--target",
        default=f"mag_binary_{int(config.PRIMARY_THRESHOLD_NT)}nT",
    )
    parser.add_argument("--prevalence", type=float, default=None)
    parser.add_argument("--noise-method", choices=NOISE_METHODS, default="phase")
    parser.add_argument("--estimator", choices=ESTIMATORS, default="xgboost")
    parser.add_argument("--primary-block-deg", type=float, default=config.SPATIAL_BLOCK_SIZE_DEG)
    parser.add_argument("--adequacy-block-deg", type=float, default=60.0)
    parser.add_argument("--folds", type=int, default=config.N_OUTER_FOLDS)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--target-power", type=float, default=0.80)
    parser.add_argument(
        "--target-effect-strength", type=float, default=None,
        help="Externally justified latent-SD benchmark; must also appear in --strengths",
    )
    parser.add_argument("--seed", type=int, default=config.RANDOM_SEED)
    parser.add_argument("--xgb-jobs", type=int, default=2)
    parser.add_argument("--variogram-pairs", type=int, default=60_000)
    parser.add_argument("--omit-simulations", action="store_true")
    parser.add_argument("--output", required=True, help="Destination JSON path")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> Dict[str, Any]:
    args = parse_args(argv)
    cfg = PowerAnalysisConfig(
        control=args.control,
        strengths=tuple(args.strengths),
        n_simulations=args.simulations,
        age_mask=args.age_mask,
        target_column=args.target,
        prevalence=args.prevalence,
        noise_method=args.noise_method,
        estimator=args.estimator,
        n_outer_folds=args.folds,
        primary_block_size_deg=args.primary_block_deg,
        adequacy_block_size_deg=args.adequacy_block_deg,
        alpha=args.alpha,
        target_power=args.target_power,
        target_effect_strength=args.target_effect_strength,
        simulation_seed=args.seed,
        model_seed=args.seed,
        xgb_n_jobs=args.xgb_jobs,
        variogram_pairs=args.variogram_pairs,
        include_simulations=not args.omit_simulations,
    )
    result = run_power_analysis(args.dataset, args.grid_meta, cfg)
    write_power_result(result, args.output)
    mde = result["minimum_detectable_effect"]
    print(json.dumps({
        "output": os.path.abspath(args.output),
        "control": result["control"],
        "structurally_limited": result["structural_diagnostics"]["structurally_limited"],
        "minimum_detectable_effect": mde,
    }, indent=2))
    return result


if __name__ == "__main__":
    main()
