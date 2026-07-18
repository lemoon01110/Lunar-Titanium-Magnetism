"""Transparent continuous-field analysis for the TiO2 spatial proxy.

The repository-plan classifier dichotomises a strongly clustered magnetic field at an
arbitrary threshold.  That analysis is retained for traceability, but it is not a
sufficient evidential basis.  This module keeps the measured field continuous and
uses a deliberately simple model whose contribution from the TiO2 family can be
read directly.

No p-value is emitted.  With very few effective spatial regions, row-level model
standard errors would be pseudo-replication.  Instead we publish every held-out
spatial-fold score, the spread across folds, and the change when TiO2 is added to
the same controls.
"""

from __future__ import annotations

from typing import Dict, Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import config


def _validated_columns(df: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    selected = list(columns)
    missing = sorted(set(selected) - set(df.columns))
    if missing:
        raise ValueError(f"continuous analysis is missing columns: {missing}")
    if not selected:
        raise ValueError("continuous analysis requires at least one feature")
    values = df[selected].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("continuous-analysis features must all be finite")
    return selected


def _blocked_scores(
    df: pd.DataFrame,
    y: np.ndarray,
    features: Sequence[str],
    groups: np.ndarray,
    n_folds: int,
    alpha: float,
    fold_ids: np.ndarray | None = None,
) -> Dict[str, list[float]]:
    unique_groups = np.unique(groups)
    if len(unique_groups) < 2:
        raise ValueError("continuous analysis requires at least two spatial groups")
    if fold_ids is None:
        splitter = GroupKFold(n_splits=min(int(n_folds), len(unique_groups)))
        splits = splitter.split(df, y, groups)
    else:
        fold_ids = np.asarray(fold_ids)
        if fold_ids.ndim != 1 or len(fold_ids) != len(df):
            raise ValueError("fixed fold_ids must be one-dimensional and match dataframe rows")
        if pd.isna(fold_ids).any() or np.unique(fold_ids).size < 2:
            raise ValueError("fixed fold_ids require at least two non-null folds")
        group_fold_counts = pd.DataFrame({"group": groups, "fold": fold_ids}).groupby(
            "group"
        )["fold"].nunique()
        if int(group_fold_counts.max()) != 1:
            raise ValueError("fixed fold_ids split at least one spatial group")
        splits = (
            (np.flatnonzero(fold_ids != fold), np.flatnonzero(fold_ids == fold))
            for fold in sorted(np.unique(fold_ids).tolist())
        )
    r2: list[float] = []
    mae: list[float] = []
    for train, test in splits:
        if len(train) < 2 or len(test) < 2:
            raise ValueError("each continuous-analysis fold needs at least two train/test rows")
        model = Pipeline([
            ("scale", StandardScaler()),
            ("ridge", Ridge(alpha=alpha)),
        ])
        model.fit(df.iloc[train][list(features)], y[train])
        pred = model.predict(df.iloc[test][list(features)])
        r2.append(float(r2_score(y[test], pred)))
        mae.append(float(mean_absolute_error(y[test], pred)))
    return {"r2_per_fold": r2, "mae_log1p_nT_per_fold": mae}


def _summary(values: Sequence[float]) -> Dict[str, float | list[float]]:
    arr = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "per_fold": arr.tolist(),
    }


def continuous_field_analysis(
    df: pd.DataFrame,
    *,
    target: str = "mag_anomaly",
    group_column: str = "spatial_block",
    h1_features: Sequence[str] | None = None,
    control_features: Sequence[str] | None = None,
    n_folds: int = config.N_OUTER_FOLDS,
    alpha: float = config.CONTINUOUS_RIDGE_ALPHA,
    fold_ids: Sequence[int] | np.ndarray | None = None,
) -> Dict:
    """Compare a controls-only ridge model with the same model plus TiO2.

    The response is ``log1p(abs(surface field))`` so all original magnitudes are
    retained while the extreme right tail cannot dominate the fit.  Features are
    standardised within each training fold.  The returned all-data coefficients
    are descriptive only and are labelled accordingly.
    """
    if target not in df or group_column not in df:
        raise ValueError(f"continuous analysis requires {target!r} and {group_column!r}")
    field = df[target].to_numpy(dtype=float)
    groups = df[group_column].to_numpy()
    fixed_folds = None if fold_ids is None else np.asarray(fold_ids)
    if not np.isfinite(field).all() or np.any(field < 0):
        raise ValueError("magnetic-field magnitude must be finite and non-negative")
    if len(df) < 10:
        raise ValueError("continuous analysis requires at least ten observations")

    h1 = _validated_columns(df, h1_features or config.H1_FEATURES)
    controls = _validated_columns(df, control_features or config.CONTROL_FEATURES)
    full = list(dict.fromkeys([*controls, *h1]))
    y = np.log1p(field)

    controls_scores = _blocked_scores(
        df, y, controls, groups, n_folds, alpha, fixed_folds
    )
    full_scores = _blocked_scores(
        df, y, full, groups, n_folds, alpha, fixed_folds
    )
    delta = np.asarray(full_scores["r2_per_fold"]) - np.asarray(
        controls_scores["r2_per_fold"]
    )

    descriptive = Pipeline([
        ("scale", StandardScaler()),
        ("ridge", Ridge(alpha=alpha)),
    ])
    descriptive.fit(df[full], y)
    coefficients = dict(zip(full, descriptive.named_steps["ridge"].coef_.astype(float)))

    return {
        "estimand": "held-out prediction of log1p(surface magnetic-field magnitude in nT)",
        "model": "standardised ridge regression",
        "target_transform": "log1p(mag_anomaly)",
        "n_rows": int(len(df)),
        "n_spatial_blocks": int(len(np.unique(groups))),
        "fold_assignment": (
            "caller-supplied inherited spatial folds"
            if fixed_folds is not None else "GroupKFold assigned within analysis scope"
        ),
        "n_folds": int(
            np.unique(fixed_folds).size if fixed_folds is not None
            else min(int(n_folds), len(np.unique(groups)))
        ),
        "fold_ids": (
            sorted(int(value) for value in np.unique(fixed_folds))
            if fixed_folds is not None
            else list(range(min(int(n_folds), len(np.unique(groups)))))
        ),
        "controls_only": {
            "features": controls,
            "r2": _summary(controls_scores["r2_per_fold"]),
            "mae_log1p_nT": _summary(controls_scores["mae_log1p_nT_per_fold"]),
        },
        "controls_plus_tio2": {
            "features": full,
            "r2": _summary(full_scores["r2_per_fold"]),
            "mae_log1p_nT": _summary(full_scores["mae_log1p_nT_per_fold"]),
        },
        "tio2_incremental_r2": _summary(delta),
        "descriptive_standardised_coefficients_no_independence_claim": coefficients,
        "inference_note": (
            "Fold scores and coefficients are descriptive; no row-level p-value is valid "
            "when the effective number of independent spatial regions is small."
        ),
    }
