"""Post-plan exploratory diagnostics -- not inferentially calibrated.

The repository-plan primary analysis (config.py + Pre-Registration.md, hash-pinned) is
deliberately *not* modified here. This module instead asks an adversarial question:

    "How sensitive are descriptive scores to model selection, alternative spatial
     partitions, and edge-detecting gradient features?"

The repository-plan null distribution is for an unselected statistic.  It is invalid for the
maximum of 60 Optuna trials, a different fold construction, or a feature set selected after
inspection.  Consequently this module emits no significance or verdict claim.  Calibrating
one would require rerunning the *entire* selection procedure inside every spatial-null
replicate.  The diagnostics touch nothing in ``results/``.

Run:  ``python -m src.exploratory``  (options: ``--optuna-trials N --kmeans-k K``)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from typing import Dict, List

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol
from scipy import ndimage
from sklearn.cluster import KMeans

from . import config
from . import evaluation
from . import modeling

N_SPLITS = config.N_OUTER_FOLDS
SEED = config.RANDOM_SEED
OUT_CSV = os.path.join(config.PROJECT_ROOT, "Paper-and-Pitch", "exploratory_robustness.csv")


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _load_primary() -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(os.path.join(config.PROCESSED_DIR, "modeling_dataset.csv"))
    df = evaluation.subset_by_age(df, "imbrian")  # repository-plan primary mask
    target = df[f"mag_binary_{int(config.PRIMARY_THRESHOLD_NT)}nT"]
    return df, target


def _null_stats() -> tuple[float, float]:
    """Repository-plan full-model null: (mean, 95th percentile). The 95th percentile
    is the relevant bar for that same unselected statistic -- the permutation test asks whether the
    real score exceeds the null's upper tail, not merely its mean."""
    try:
        pt = json.load(open(os.path.join(config.RESULTS_DIR, "metrics.json")))["Permutation_Test"]
        return float(pt["Null_Mean_PR_AUC"]), float(pt["Null_95th_PR_AUC"])
    except (OSError, KeyError, ValueError):
        return 0.113, 0.226


def _full_pr_auc(X: pd.DataFrame, y: pd.Series, groups: np.ndarray, params: Dict | None = None) -> float:
    return float(modeling.cross_val_pr_auc(
        modeling.xgb_factory(params, seed=SEED), X, y, groups, N_SPLITS).mean())


def _reaches_significance(full: float, h2: float, tio2_drop: float, null_p95: float) -> bool:
    """Legacy arithmetic gate, retained for compatibility tests only.

    It must not be applied to a selected exploratory score unless the null repeats
    the same selection procedure.  ``run`` deliberately does not call it.
    """
    return bool(full > null_p95 and full > h2 and tio2_drop > 0)


# --------------------------------------------------------------------------- #
# 1. Bayesian optimization (Optuna TPE) -- selected descriptive maximum
# --------------------------------------------------------------------------- #
def optuna_best(df: pd.DataFrame, y: pd.Series, n_trials: int) -> Dict:
    import optuna

    X = df[config.ALL_FEATURES]
    groups = df["spatial_block"].values  # repository-plan 30-degree blocks

    def objective(trial):
        params = dict(
            max_depth=trial.suggest_int("max_depth", 2, 8),
            learning_rate=trial.suggest_float("learning_rate", 1e-3, 0.3, log=True),
            n_estimators=trial.suggest_int("n_estimators", 100, 600, step=50),
            subsample=trial.suggest_float("subsample", 0.6, 1.0),
            colsample_bytree=trial.suggest_float("colsample_bytree", 0.6, 1.0),
            min_child_weight=trial.suggest_float("min_child_weight", 1.0, 10.0),
            reg_lambda=trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
            reg_alpha=trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
        )
        return _full_pr_auc(X, y, groups, params)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=n_trials)
    # This maximizes PR-AUC on the folds that are then reported.  It is a selected,
    # optimistically biased diagnostic, not an effect estimate or valid test.
    return {"best_full_pr_auc": float(study.best_value), "best_params": study.best_params}


# --------------------------------------------------------------------------- #
# 2. Alternative spherical spatial partitions (not geology-aware)
# --------------------------------------------------------------------------- #
def kmeans_groups(df: pd.DataFrame, k: int) -> np.ndarray:
    """Cluster pixels on the unit sphere so folds are compact and contiguous rather
    than rigid lon/lat rectangles that can bisect a circular province."""
    lat = np.radians(df["lat"].to_numpy())
    lon = np.radians(df["lon"].to_numpy())
    xyz = np.column_stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
    return KMeans(n_clusters=k, random_state=SEED, n_init=10).fit_predict(xyz)


def kmeans_analysis(df: pd.DataFrame, y: pd.Series, ks: tuple[int, ...]) -> Dict:
    """Sweep spherical spatial-cluster partitions.

    Fewer clusters generally produce coarser holdouts, but score need not vary
    monotonically with leakage or independence.  The curve is therefore reported as
    partition sensitivity without assigning a causal leakage interpretation.
    """
    ks = tuple(sorted(ks))
    sweep = []
    for k in ks:
        groups = kmeans_groups(df, k)
        sweep.append({"k": int(k), "full_pr_auc": _full_pr_auc(df[config.ALL_FEATURES], y, groups)})

    # Reference the coarsest requested partition without calling it an adequacy gate.
    k0 = ks[0]
    g0 = kmeans_groups(df, k0)
    full0 = sweep[0]["full_pr_auc"]
    h2_0 = _full_pr_auc(df[config.H2_FEATURES], y, g0)
    no_h1 = [f for f in config.ALL_FEATURES if f not in config.TIO2_DERIVED_FEATURES]
    drop0 = full0 - _full_pr_auc(df[no_h1], y, g0)
    score_increases_with_k = sweep[-1]["full_pr_auc"] > sweep[0]["full_pr_auc"]
    return {"sweep": sweep, "adequate_k": int(k0), "adequate_full": full0,
            "adequate_h2": h2_0, "adequate_tio2_drop": drop0,
            "score_increases_with_k": bool(score_increases_with_k),
            # Compatibility alias; no causal interpretation is attached.
            "rises_with_leakage": bool(score_increases_with_k)}


# --------------------------------------------------------------------------- #
# 3. Spatial-gradient (Sobel) feature engineering -- "see the edges"
# --------------------------------------------------------------------------- #
def _sobel_magnitude(path: str) -> tuple[np.ndarray, object]:
    with rasterio.open(path) as src:
        arr = src.read(1).astype(float)
        transform = src.transform
        nodata = src.nodata
    valid = arr != nodata
    filled = np.where(valid, arr, np.nan)
    filled = np.where(np.isnan(filled), np.nanmean(filled), filled)
    gx = ndimage.sobel(filled, axis=1, mode="wrap")     # longitude wraps at +/-180
    gy = ndimage.sobel(filled, axis=0, mode="nearest")  # latitude does not
    return np.hypot(gx, gy), transform


def gradient_features(df: pd.DataFrame) -> pd.DataFrame:
    cols = {}
    for name, rel in (("tio2", "tio2_abundance.tif"), ("gravity", "bouguer_gravity.tif")):
        mag, transform = _sobel_magnitude(os.path.join(config.RAW_DIR, rel))
        rows, colidx = rowcol(transform, df["lon"].to_numpy(), df["lat"].to_numpy())
        rows = np.clip(np.asarray(rows), 0, mag.shape[0] - 1)
        colidx = np.clip(np.asarray(colidx), 0, mag.shape[1] - 1)
        cols[f"grad_{name}"] = mag[rows, colidx]
    return pd.DataFrame(cols, index=df.index)


def gradient_analysis(df: pd.DataFrame, y: pd.Series) -> Dict:
    grads = gradient_features(df)
    groups = df["spatial_block"].values
    full_reg = _full_pr_auc(df[config.ALL_FEATURES], y, groups)
    x_aug = pd.concat([df[config.ALL_FEATURES], grads], axis=1)
    full_plus = _full_pr_auc(x_aug, y, groups)
    return {"full_repository_plan": full_reg, "full_plus_gradients": full_plus,
            "added_features": list(grads.columns)}


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def run(optuna_trials: int, kmeans_ks: tuple[int, ...], out_csv: str) -> List[Dict]:
    df, y = _load_primary()
    null_mean, null_p95 = _null_stats()
    h2_ref = _full_pr_auc(df[config.H2_FEATURES], y, df["spatial_block"].values)
    print(f"Primary: {len(df):,} pixels, prevalence {y.mean():.2%} | "
          f"repository-plan full-null mean={null_mean:.3f}, null 95th={null_p95:.3f}, "
          f"H2-only={h2_ref:.3f}\n")
    print("Exploratory scores are NOT compared inferentially with that repository-plan null; "
          "the selection procedures differ.\n")

    rows: List[Dict] = []

    print(f"[1/3] Bayesian optimization (Optuna TPE, {optuna_trials} trials)...")
    op = optuna_best(df, y, optuna_trials)
    rows.append({
        "analysis": "optuna_tpe", "full_pr_auc": round(op["best_full_pr_auc"], 4),
        "h2_only_pr_auc": round(h2_ref, 4), "tio2_drop": "",
        "inferentially_calibrated": False,
        "exceeds_null_p95": "",
        "note": "selected maximum; no selection-adjusted spatial null",
    })
    print(f"      selected best full PR-AUC = {op['best_full_pr_auc']:.4f}; "
          "no valid significance comparison\n")

    print(f"[2/3] Alternative spherical K-Means partitions (k-sweep {kmeans_ks})...")
    km = kmeans_analysis(df, y, kmeans_ks)
    sweep_str = ", ".join(f"k={s['k']}:{s['full_pr_auc']:.3f}" for s in km["sweep"])
    rows.append({
        "analysis": "kmeans_folds", "full_pr_auc": round(km["adequate_full"], 4),
        "h2_only_pr_auc": round(km["adequate_h2"], 4), "tio2_drop": round(km["adequate_tio2_drop"], 4),
        "inferentially_calibrated": False,
        "exceeds_null_p95": "",
        "note": f"coarsest requested partition k={km['adequate_k']}; descriptive sweep [{sweep_str}]",
    })
    print(f"      sweep: {sweep_str}")
    print(f"      adequate (k={km['adequate_k']}) full={km['adequate_full']:.4f} "
          f"H2={km['adequate_h2']:.4f} drop={km['adequate_tio2_drop']:+.4f} "
          f"| score_increases_with_k={km['score_increases_with_k']}\n")

    print("[3/3] Spatial-gradient (Sobel) features...")
    gr = gradient_analysis(df, y)
    rows.append({
        "analysis": "sobel_gradients", "full_pr_auc": round(gr["full_plus_gradients"], 4),
        "h2_only_pr_auc": round(h2_ref, 4),
        "tio2_drop": round(gr["full_plus_gradients"] - gr["full_repository_plan"], 4),
        "inferentially_calibrated": False,
        "exceeds_null_p95": "",
        "note": f"post-inspection feature set; repository-plan full={gr['full_repository_plan']:.4f}; +{len(gr['added_features'])} features",
    })
    print(f"      full+gradients={gr['full_plus_gradients']:.4f} "
          f"(repository-plan full={gr['full_repository_plan']:.4f})\n")

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "analysis", "full_pr_auc", "h2_only_pr_auc", "tio2_drop",
            "inferentially_calibrated", "exceeds_null_p95", "note"],
            lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    print("=== summary ===")
    for r in rows:
        print(f"  {r['analysis']:16s} full={r['full_pr_auc']:.4f}  "
              f"inferentially_calibrated={r['inferentially_calibrated']}")
    print("\n  No exploratory row changes or strengthens the primary inference status.")
    print(f"\nWrote {out_csv}")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--optuna-trials", type=int, default=60)
    ap.add_argument("--kmeans-ks", type=int, nargs="+", default=[6, 12, 24, 48])
    ap.add_argument("--out", default=OUT_CSV)
    args = ap.parse_args(argv)
    run(args.optuna_trials, tuple(args.kmeans_ks), args.out)


if __name__ == "__main__":
    main()
