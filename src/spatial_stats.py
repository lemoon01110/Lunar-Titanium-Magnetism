"""
Spatial diagnostics for autocorrelated geospatial data.

The single biggest way to over-claim with planetary-scale ML is to treat 10^5
correlated pixels as 10^5 independent samples. These diagnostics expose that
limitation but cannot create independent information:

  * `empirical_variogram` / `decorrelation_range_km` — the spatial autocorrelation
    length, which checks rather than assumes CV adequacy and yields an
    approximate *effective sample size* (independent patches, not pixels).
  * `oof_predictions` + `block_bootstrap_pr_auc_ci` — a confidence interval on
    PR-AUC interval conditional on the chosen blocks. It is not a valid confidence
    interval when those blocks are smaller than the estimated correlation range.
  * `phase_randomized_surrogate` — a 2-D Fourier phase-randomised null that
    preserves the target's *full* power spectrum (a stricter null than a
    longitudinal roll, which only preserves east-west structure).
  * `block_size_robustness` — re-runs the comparison across partitions. The curve
    may be non-monotone and is not treated as a one-dimensional leakage meter.

These are reported alongside the repository-plan rotation null and every fold score.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from sklearn.model_selection import GroupKFold

from . import config, modeling, spatial


# --------------------------------------------------------------------------- #
# Autocorrelation range and effective sample size
# --------------------------------------------------------------------------- #
def empirical_variogram(
    lon: np.ndarray, lat: np.ndarray, z: np.ndarray, n_pairs: int = 60_000,
    n_bins: int = 20, max_dist_km: float | None = None, seed: int = config.RANDOM_SEED,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Isotropic empirical semivariogram from a random subsample of point pairs.

    Returns (bin_centres_km, semivariance, sill). Semivariance γ(h) = ½·mean[(z_i−z_j)²]
    for pairs separated by ~h; the sill is the process variance.
    """
    rng = np.random.default_rng(seed)
    n = len(z)
    i = rng.integers(0, n, size=n_pairs)
    j = rng.integers(0, n, size=n_pairs)
    ok = i != j
    i, j = i[ok], j[ok]
    d = spatial.haversine_km(lon[i], lat[i], lon[j], lat[j])
    sq = 0.5 * (z[i] - z[j]) ** 2
    if max_dist_km is None:
        max_dist_km = np.quantile(d, 0.9)  # sample far enough to see the plateau
    edges = np.linspace(0, max_dist_km, n_bins + 1)
    centres = 0.5 * (edges[:-1] + edges[1:])
    gamma = np.full(n_bins, np.nan)
    idx = np.digitize(d, edges) - 1
    for b in range(n_bins):
        m = idx == b
        if m.sum() > 30:
            gamma[b] = sq[m].mean()
    return centres, gamma, float(np.var(z))


def decorrelation_range_km(centres: np.ndarray, gamma: np.ndarray, sill: float) -> float:
    """Range = first lag at which the semivariogram reaches 95% of the *plateau*.

    The sill is estimated from the far-lag plateau (mean of the outer third of
    finite bins), which is far more robust than the raw field variance for
    heavy-tailed fields.
    """
    valid = np.isfinite(gamma)
    if valid.sum() < 4:
        return float("nan")
    g = gamma[valid]
    c = centres[valid]
    plateau = float(np.mean(g[max(1, len(g) * 2 // 3):]))  # outer third
    if plateau <= 0:
        return float("nan")
    hit = np.where(g >= 0.95 * plateau)[0]
    return float(c[hit[0]]) if len(hit) else float(c[-1])


def effective_sample_size(n_pixels: int, pixel_area_km2: float, range_km: float) -> float:
    """Approximate number of independent patches ≈ mapped area / correlation area.

    A crude but honest counterweight to pixel count: correlation area ≈ π·range².
    """
    if not np.isfinite(range_km) or range_km <= 0:
        # An unestimable range cannot certify pixel independence.  Fail closed
        # at one effective region instead of silently returning nominal n.
        return 1.0
    corr_area = np.pi * range_km ** 2
    return float(min(float(n_pixels), max(1.0, n_pixels * pixel_area_km2 / corr_area)))


# --------------------------------------------------------------------------- #
# Out-of-fold predictions + spatial block bootstrap CI
# --------------------------------------------------------------------------- #
def oof_predictions(
    X: pd.DataFrame, y: pd.Series, groups: np.ndarray, n_splits: int,
    params: Dict | None = None, seed: int = config.RANDOM_SEED,
) -> np.ndarray:
    """Cross-validated out-of-fold predicted probabilities (one per row)."""
    n = modeling._n_splits(groups, n_splits)
    gkf = GroupKFold(n_splits=n)
    oof = np.full(len(y), np.nan)
    for tr, te in gkf.split(X, y, groups):
        est = modeling.build_classifier(modeling.scale_pos_weight(y.iloc[tr]), params=params, seed=seed)
        est.fit(X.iloc[tr], y.iloc[tr])
        oof[te] = est.predict_proba(X.iloc[te])[:, 1]
    return oof


def block_bootstrap_pr_auc_ci(
    y: np.ndarray, oof: np.ndarray, blocks: np.ndarray, n_boot: int = 1000,
    alpha: float = 0.05, seed: int = config.RANDOM_SEED,
) -> Dict:
    """Percentile interval for PR-AUC by resampling chosen blocks with replacement.

    Resampling blocks keeps within-block pixels together.  Independence between
    blocks is a separate assumption that the caller must check against the spatial
    range; this function does not certify it.
    """
    rng = np.random.default_rng(seed)
    finite = np.isfinite(oof)
    y, oof, blocks = y[finite], oof[finite], blocks[finite]
    uniq = np.unique(blocks)
    by_block = {b: np.where(blocks == b)[0] for b in uniq}
    scores: List[float] = []
    for _ in range(n_boot):
        chosen = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([by_block[b] for b in chosen])
        yb = y[idx]
        if yb.sum() == 0 or yb.sum() == len(yb):
            continue
        scores.append(average_precision_score(yb, oof[idx]))
    scores = np.asarray(scores)
    return {
        "PR_AUC_point": float(average_precision_score(y, oof)),
        "PR_AUC_CI_low": float(np.quantile(scores, alpha / 2)) if len(scores) else float("nan"),
        "PR_AUC_CI_high": float(np.quantile(scores, 1 - alpha / 2)) if len(scores) else float("nan"),
        "n_blocks": int(len(uniq)),
        "n_boot": int(len(scores)),
    }


# --------------------------------------------------------------------------- #
# 2-D Fourier phase-randomised null
# --------------------------------------------------------------------------- #
def phase_randomized_surrogate(grid: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Return a real surrogate with the filled grid's amplitude spectrum.

    Phases are taken from the FFT of a real white-noise field.  That preserves the
    Hermitian constraints required by ``irfft2``; drawing every complex phase
    independently does not, and silently changes boundary-frequency amplitudes.
    NaNs are filled with the finite-field mean before transforming.
    """
    filled = np.where(np.isfinite(grid), grid, np.nanmean(grid))
    f = np.fft.rfft2(filled)
    amp = np.abs(f)
    random_spectrum = np.fft.rfft2(rng.standard_normal(filled.shape))
    random_amplitude = np.abs(random_spectrum)
    phase = np.divide(
        random_spectrum,
        random_amplitude,
        out=np.ones_like(random_spectrum),
        where=random_amplitude > 0,
    )
    surrogate = np.fft.irfft2(amp * phase, s=filled.shape)
    return surrogate


def phase_randomization_null(
    df_masked: pd.DataFrame, df_all_valid: pd.DataFrame, target: str,
    grid_meta: Dict, cfg: config.PipelineConfig, real_full_mean: float,
    n_surrogates: int = 50,
) -> Dict:
    """Null PR-AUC distribution from phase-randomised surrogates of the *continuous*
    magnetic field, binarised at the observed prevalence. Stricter than the roll null."""
    width, height = int(grid_meta["width"]), int(grid_meta["height"])
    cont = np.full((height, width), np.nan)
    cont[df_all_valid["row_idx"].values, df_all_valid["col_idx"].values] = df_all_valid["mag_anomaly"].values
    prevalence = float(df_masked[target].mean())

    rows, cols = df_masked["row_idx"].values, df_masked["col_idx"].values
    X = df_masked[config.ALL_FEATURES]
    groups = df_masked["spatial_block"].values
    factory = modeling.xgb_factory(seed=cfg.random_seed, n_jobs=modeling.XGB_N_JOBS)
    rng = np.random.default_rng(cfg.random_seed + 1)

    n = 15 if cfg.mode == "fast" else n_surrogates
    null: List[float] = []
    for _ in range(n):
        sur = phase_randomized_surrogate(cont, rng)
        thr = np.nanquantile(sur[np.isfinite(cont)], 1 - prevalence)
        y_sur = (sur[rows, cols] >= thr).astype(int)
        if y_sur.sum() < 20 or y_sur.sum() == len(y_sur):
            continue
        yk = pd.Series(y_sur, index=X.index)
        scores = modeling.cross_val_pr_auc(factory, X, yk, groups, cfg.n_outer_folds)
        null.append(float(np.mean(scores)))
    null_arr = np.asarray(null)
    p = (np.sum(null_arr >= real_full_mean) + 1) / (len(null_arr) + 1)
    return {
        "n_surrogates": int(len(null_arr)),
        "Null_Mean_PR_AUC": float(np.mean(null_arr)) if len(null_arr) else float("nan"),
        "Null_95th_PR_AUC": float(np.quantile(null_arr, 0.95)) if len(null_arr) else float("nan"),
        "Empirical_p_value": float(p),
    }


# --------------------------------------------------------------------------- #
# CV partition-size sensitivity
# --------------------------------------------------------------------------- #
def block_size_robustness(
    df_masked: pd.DataFrame, target: str, cfg: config.PipelineConfig,
    block_sizes_deg: Tuple[float, ...] = (15.0, 20.0, 30.0, 45.0, 60.0),
) -> Dict:
    """Re-derive CV partitions and report non-monotone score sensitivity."""
    from .evaluation import feature_sets  # local import to avoid a cycle
    y = df_masked[target]
    lon, lat = df_masked["lon"].values, df_masked["lat"].values
    out: Dict[str, Dict] = {}
    for size in block_sizes_deg:
        groups = spatial.spatial_block_ids(lon, lat, size)
        if len(np.unique(groups)) < cfg.n_outer_folds:
            out[f"{int(size)}deg"] = {"skipped": "too few blocks"}
            continue
        factory = modeling.xgb_factory(seed=cfg.random_seed)
        full = modeling.cross_val_pr_auc(factory, df_masked[config.ALL_FEATURES], y, groups, cfg.n_outer_folds)
        noh1 = modeling.cross_val_pr_auc(factory, df_masked[feature_sets()["no_h1_tio2"]], y, groups, cfg.n_outer_folds)
        h2 = modeling.cross_val_pr_auc(factory, df_masked[config.H2_FEATURES], y, groups, cfg.n_outer_folds)
        out[f"{int(size)}deg"] = {
            "n_blocks": int(len(np.unique(groups))),
            "XGB_Full_PR_AUC": float(np.mean(full)),
            "H2_Only_PR_AUC": float(np.mean(h2)),
            "H1_tio2_drop_mean": float(np.mean(full - noh1)),
            "beats_h2_and_h1_helps": bool(np.mean(full) > np.mean(h2) and np.mean(full - noh1) > 0),
        }
    return out
