"""
Modelling: spatially-blocked cross-validation, baselines, and nested tuning.

Everything here operates on the tabular dataset and the precomputed
``spatial_block`` group ids. The key guarantees:

* **No spatial leakage.** Cross-validation always holds out whole 30x30-degree
  blocks via ``GroupKFold``. Neighbouring, near-identical pixels can never sit
  in both train and test.
* **Comparable numbers.** Baselines, ablations, and the permutation null are all
  scored under the *same* outer CV scheme with a shared default model config, so
  differences reflect features, not incidental hyper-parameters.
* **Honest tuning.** Hyper-parameters are selected by *nested* GridSearchCV whose
  inner folds are also spatial, so tuning never sees an outer test block.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import config

# XGBoost thread cap. On small tabular data, tree_method="hist" with n_jobs=-1
# (all cores) is DRAMATICALLY slower than a few threads -- thread-sync overhead
# dominates (measured ~27 s/fit at 16 threads vs ~0.16 s at 4 on this data). Never
# use -1 here; a small fixed cap is both fast and avoids oversubscription when an
# outer parallel loop (GridSearchCV / joblib) is also running.
XGB_N_JOBS: int = 4

# Shared default XGBoost configuration. Used for every baseline/ablation so
# comparisons are apples-to-apples; nested tuning explores around it.
DEFAULT_PARAMS: Dict = dict(
    n_estimators=300,
    max_depth=4,
    learning_rate=0.07,
    subsample=0.9,
    colsample_bytree=0.9,
    min_child_weight=3,
    reg_lambda=2.0,
)


def scale_pos_weight(y: pd.Series) -> float:
    pos = float(np.sum(y))
    neg = float(len(y) - pos)
    return neg / pos if pos > 0 else 1.0


def build_classifier(spw: float, params: Dict | None = None, n_jobs: int = XGB_N_JOBS,
                     seed: int = config.RANDOM_SEED) -> xgb.XGBClassifier:
    merged = {**DEFAULT_PARAMS, **(params or {})}
    return xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="aucpr",
        tree_method="hist",
        random_state=seed,
        n_jobs=n_jobs,
        scale_pos_weight=spw,
        **merged,
    )


def _n_splits(groups: np.ndarray, requested: int) -> int:
    return max(2, min(requested, len(np.unique(groups))))


def cross_val_pr_auc(
    factory: Callable[[pd.Series], object],
    X: pd.DataFrame,
    y: pd.Series,
    groups: np.ndarray,
    n_splits: int,
) -> np.ndarray:
    """Per-fold PR-AUC under spatially-blocked GroupKFold.

    ``factory(y_train)`` returns a fresh, unfitted estimator (so class weights
    can be derived per fold). Returns an array of per-fold PR-AUC scores.
    """
    gkf = GroupKFold(n_splits=_n_splits(groups, n_splits))
    scores: List[float] = []
    for train_idx, test_idx in gkf.split(X, y, groups):
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        # PR-AUC is undefined when a test fold has no positives; skip such folds
        # (deterministic given groups, so identical across the compared feature
        # sets -- the paired ablation test stays valid).
        if y_test.sum() == 0 or y_train.sum() == 0:
            continue
        est = factory(y_train)
        est.fit(X.iloc[train_idx], y_train)
        proba = est.predict_proba(X.iloc[test_idx])[:, 1]
        scores.append(average_precision_score(y_test, proba))
    return np.asarray(scores) if scores else np.asarray([0.0])


# --------------------------------------------------------------------------- #
# Estimator factories for each competitor
# --------------------------------------------------------------------------- #
def xgb_factory(params: Dict | None = None, seed: int = config.RANDOM_SEED,
                n_jobs: int = XGB_N_JOBS) -> Callable:
    def factory(y_train: pd.Series):
        return build_classifier(scale_pos_weight(y_train), params=params, n_jobs=n_jobs, seed=seed)
    return factory


def logreg_factory(seed: int = config.RANDOM_SEED) -> Callable:
    def factory(_y_train: pd.Series):
        return Pipeline([
            ("scale", StandardScaler()),
            ("lr", LogisticRegression(class_weight="balanced", max_iter=2000, random_state=seed)),
        ])
    return factory


def dummy_factory(strategy: str = "prior", seed: int = config.RANDOM_SEED) -> Callable:
    def factory(_y_train: pd.Series):
        return DummyClassifier(strategy=strategy, random_state=seed)
    return factory


# --------------------------------------------------------------------------- #
# Nested spatial cross-validation with hyper-parameter tuning
# --------------------------------------------------------------------------- #
def nested_cv_pr_auc(
    X: pd.DataFrame,
    y: pd.Series,
    groups: np.ndarray,
    param_grid: Dict[str, List],
    n_outer: int,
    n_inner: int,
    seed: int = config.RANDOM_SEED,
) -> Tuple[np.ndarray, List[Dict]]:
    """Nested CV: outer spatial folds for scoring, inner spatial folds for tuning."""
    outer = GroupKFold(n_splits=_n_splits(groups, n_outer))
    scores: List[float] = []
    best_params: List[Dict] = []
    for train_idx, test_idx in outer.split(X, y, groups):
        g_train = groups[train_idx]
        spw = scale_pos_weight(y.iloc[train_idx])
        base = build_classifier(spw, n_jobs=1, seed=seed)  # n_jobs=1: GridSearch parallelises
        inner = GroupKFold(n_splits=_n_splits(g_train, n_inner))
        search = GridSearchCV(
            base, param_grid, scoring="average_precision", cv=inner, n_jobs=-1, refit=True
        )
        search.fit(X.iloc[train_idx], y.iloc[train_idx], groups=g_train)
        proba = search.best_estimator_.predict_proba(X.iloc[test_idx])[:, 1]
        scores.append(average_precision_score(y.iloc[test_idx], proba))
        best_params.append(search.best_params_)
    return np.asarray(scores), best_params


def fit_final_model(
    X: pd.DataFrame, y: pd.Series, params: Dict, seed: int = config.RANDOM_SEED
) -> xgb.XGBClassifier:
    """Fit the chosen model on all supplied rows (for SHAP interpretation)."""
    model = build_classifier(scale_pos_weight(y), params=params, seed=seed)
    model.fit(X, y)
    return model
