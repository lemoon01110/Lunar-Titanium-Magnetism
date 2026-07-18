"""
SHAP-based diagnostics for the TiO2-family-versus-antipode ranking criterion.

Produces the mean |SHAP| importance per feature, evaluates repository-plan
criterion (ii)—whether the compositional TiO2 family outranks the antipodal-
distance feature—and writes descriptive summary, dependence, and map figures.
The TiO2 x gravity family remains explicitly exploratory.
"""

from __future__ import annotations

import os
from typing import Dict, Tuple

import matplotlib
matplotlib.use("Agg")  # headless / reproducible
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from . import config


def _normalize_shap(shap_values) -> np.ndarray:
    """Return a 2-D (n_samples, n_features) SHAP array across shap versions."""
    if isinstance(shap_values, list):  # older API: [class0, class1]
        return np.asarray(shap_values[-1])
    arr = np.asarray(shap_values)
    if arr.ndim == 3:  # (n, f, classes)
        return arr[..., -1]
    return arr


def compute_shap(
    model, X: pd.DataFrame, seed: int = config.RANDOM_SEED, sample_n: int = 2000
) -> Tuple[np.ndarray, pd.DataFrame, Dict[str, float]]:
    """Compute SHAP values on a deterministic subsample; return values, the
    sampled X, and the per-feature mean |SHAP| importance."""
    rng = np.random.default_rng(seed)
    n = min(sample_n, len(X))
    idx = np.sort(rng.choice(len(X), size=n, replace=False))
    X_sample = X.iloc[idx]

    explainer = shap.TreeExplainer(model)
    shap_values = _normalize_shap(explainer.shap_values(X_sample))
    mean_abs = np.abs(shap_values).mean(axis=0)
    importance = {feat: float(v) for feat, v in zip(X.columns, mean_abs)}
    return shap_values, X_sample, importance


def _family_importance(shap_values: np.ndarray, columns, feats) -> float:
    """Family SHAP importance = mean |row-summed contribution across the family|.
    Accounts for within-family cancellation and does NOT over-count collinear
    features (unlike naively summing per-feature mean |SHAP|)."""
    idx = [columns.index(f) for f in feats if f in columns]
    if not idx:
        return 0.0
    return float(np.mean(np.abs(shap_values[:, idx].sum(axis=1))))


def h1_vs_h2_ranking(
    importance: Dict[str, float], shap_values: np.ndarray, columns
) -> Dict:
    """Repository-plan criterion (ii): does the surface proxy -- the compositional
    TiO2 family inspired by Nichols et al. -- outrank the H2 antipodal-distance feature in
    SHAP importance? (The Ti x gravity interaction is reported only as an
    exploratory family; it is not the hypothesis -- see Fallacy-Audit.md F1.)
    """
    columns = list(columns)
    h1_importance = _family_importance(shap_values, columns, config.H1_FEATURES)
    interaction_importance = _family_importance(shap_values, columns, config.INTERACTION_FEATURES)
    best_h1_feat = max(config.H1_FEATURES, key=lambda f: importance.get(f, 0.0))
    antipode_val = importance.get("dist_to_antipode_km", 0.0)
    return {
        "h1_tio2_family_importance": h1_importance,
        "best_h1_feature": best_h1_feat,
        "best_h1_importance": float(importance.get(best_h1_feat, 0.0)),
        "antipode_importance": float(antipode_val),
        "exploratory_interaction_family_importance": interaction_importance,
        "h1_outranks_antipode": bool(h1_importance > antipode_val),
        "importance_ranking": dict(sorted(importance.items(), key=lambda kv: -kv[1])),
    }


def make_figures(
    model,
    shap_values: np.ndarray,
    X_sample: pd.DataFrame,
    lonlat: pd.DataFrame,
    out_dir: str,
    seed: int = config.RANDOM_SEED,
) -> None:
    os.makedirs(out_dir, exist_ok=True)

    # SHAP's plotting helpers use NumPy's legacy global RNG for beeswarm jitter.
    # Preserve the caller's state while making every rendered point placement
    # deterministic across otherwise identical runs.
    random_state = np.random.get_state()
    np.random.seed(seed)

    try:
        # 1. Global summary.
        plt.figure(figsize=(10, 8))
        shap.summary_plot(
            shap_values, X_sample, show=False, rng=np.random.default_rng(seed)
        )
        plt.title("SHAP feature importance (full model)")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, "shap_summary.png"), dpi=130, bbox_inches="tight")
        plt.close()

        # 2. Dependence on the H1 (TiO2) signal, coloured by the H2 antipode feature.
        h1_feat = config.H1_FEATURES[len(config.H1_FEATURES) // 2]
        if h1_feat in X_sample.columns:
            plt.figure(figsize=(8, 6))
            shap.dependence_plot(h1_feat, shap_values, X_sample, interaction_index="dist_to_antipode_km", show=False)
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, "shap_dependence_interaction.png"), dpi=130, bbox_inches="tight")
            plt.close()

        # 3. Global map: where the H1 TiO2 signal drives predictions (candidate sites).
        if h1_feat in X_sample.columns and {"lon", "lat"}.issubset(lonlat.columns):
            feat_idx = list(X_sample.columns).index(h1_feat)
            contrib = shap_values[:, feat_idx]
            vmax = np.percentile(np.abs(contrib), 99) or 1.0
            plt.figure(figsize=(11, 5.5))
            sc = plt.scatter(
                lonlat["lon"], lonlat["lat"], c=contrib, cmap="RdBu_r",
                vmin=-vmax, vmax=vmax, s=6, edgecolors="none",
            )
            plt.colorbar(sc, label=f"SHAP value of {h1_feat}")
            plt.xlabel("Longitude (deg)")
            plt.ylabel("Latitude (deg)")
            plt.title("Where the H1 TiO2 (compositional) signal drives predicted magnetism")
            plt.xlim(-180, 180)
            plt.ylim(-90, 90)
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, "shap_interaction_map.png"), dpi=130, bbox_inches="tight")
            plt.close()
    finally:
        plt.close("all")
        np.random.set_state(random_state)
