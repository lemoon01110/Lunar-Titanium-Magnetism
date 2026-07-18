"""Terrain-validity sensitivity analysis for the surface TiO2 proxy.

The LROC WAC TiO2 retrieval is a mare-regolith calibration.  The processed
model table does *not* otherwise contain a terrain class: ``age_class`` is a
stratigraphic age, and TiO2 abundance cannot be thresholded to define the
domain in which that same predictor is valid.  This module therefore fails
closed unless preprocessing supplies an explicit, independently derived
``tio2_terrain_valid`` column.

The repository's defensible proxy is the pinned USGS Unified Geologic Map
``GeoUnits.FIRST_Unit`` field, with the exact mare-unit allowlist ``Em``,
``Im1``, ``Im2``, and ``Imd``.  This is intentionally conservative: crater,
plains, ejecta, and dark-mantling units are not silently treated as mare even
when they lie inside a named mare.

Two design details prevent leakage in the sensitivity comparison:

* the terrain mask is validated as external provenance and may not cite an
  outcome, TiO2, coordinates, age, or any model feature as its basis; and
* spatial folds are assigned once on the full input scope, without consulting
  the target, before mare filtering.  Mare rows inherit those fold ids, so a
  spatial block can never move between training and test because of the mask.

By default only row-local ``tio2`` is evaluated.  Existing buffered TiO2
features were computed before terrain masking and can include highlands pixels.
They become eligible only when provenance records a positive
``buffer_support_km`` (for example, a mare mask eroded by that distance).

This is a post-result sensitivity analysis, not a replacement confirmatory
endpoint and not a direct test of dynamo timing.  The repository plan has no
independent timestamp, so this module does not describe itself as preregistered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Sequence

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import average_precision_score
from sklearn.model_selection import GroupKFold

from . import config, modeling


DEFAULT_MASK_COLUMN = "tio2_terrain_valid"

# Exact symbols from the pinned USGS Unified Geologic Map v2 GeoUnits layer.
# Prefix matching would incorrectly admit Imbrian crater/ejecta units.
USGS_MARE_UNIT_SYMBOLS = frozenset(config.MARE_UNIT_SYMBOLS)

USGS_MARE_PROXY_LIMITATIONS = (
    "USGS 1:5M geologic units are a generalized surface-geology proxy, not the "
    "formal pixel-level validity domain published for the LROC WAC calibration.",
    "Exact mare-unit polygons conservatively exclude mapped superposed crater, "
    "ejecta, plains, and dark-mantling units even where they occur inside a mare.",
    "Map-unit boundaries and their rasterization are resolution dependent; edge "
    "pixels can be classification mixtures.",
    "The row-local geology proxy restricts this sensitivity to raw TiO2 only; it "
    "does not establish formal WAC validity or support for buffered TiO2 features.",
)


class TerrainMaskError(ValueError):
    """Raised when a terrain mask or its provenance is not safe to use."""


_DISALLOWED_BASIS_FIELDS = frozenset(
    {
        *config.ALL_FEATURES,
        "mag_anomaly",
        "age_class",
        "lon",
        "lat",
        "row_idx",
        "col_idx",
        "spatial_block",
        "target",
        "label",
        "outcome",
    }
)
_DISALLOWED_BASIS_FIELDS_CASEFOLD = frozenset(
    value.casefold() for value in _DISALLOWED_BASIS_FIELDS
)


@dataclass(frozen=True)
class TerrainMaskProvenance:
    """Auditable definition of an independently supplied terrain mask.

    ``buffer_support_km`` is zero for an ordinary row-local real-data proxy.  It
    may be positive only when the supplied domain has been conservatively eroded
    (or is an explicitly artificial all-valid domain) so every neighbourhood out
    to that distance remains supported.
    """

    source: str
    source_fields: tuple[str, ...]
    selection_rule: str
    limitations: tuple[str, ...]
    is_proxy: bool = True
    buffer_support_km: float = 0.0

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise TerrainMaskError("terrain-mask source must be named")
        if not self.source_fields:
            raise TerrainMaskError("terrain-mask source_fields must be declared")
        if not self.selection_rule.strip():
            raise TerrainMaskError("terrain-mask selection_rule must be declared")
        if not self.limitations or any(not str(item).strip() for item in self.limitations):
            raise TerrainMaskError("terrain-mask limitations must be explicit and non-empty")
        if not np.isfinite(self.buffer_support_km) or self.buffer_support_km < 0:
            raise TerrainMaskError("buffer_support_km must be finite and non-negative")

        unsafe = []
        for field in self.source_fields:
            folded = str(field).strip().casefold()
            if (
                folded in _DISALLOWED_BASIS_FIELDS_CASEFOLD
                or folded.startswith("mag_binary_")
                or folded.startswith("tio2_")
            ):
                unsafe.append(str(field))
        if unsafe:
            raise TerrainMaskError(
                "terrain validity may not be derived from outcomes, TiO2, age, "
                f"coordinates, or model features; unsafe source_fields={unsafe}"
            )


USGS_MARE_PROXY = TerrainMaskProvenance(
    source="USGS Unified Geologic Map of the Moon 1:5M GIS v2, GeoUnits",
    source_fields=("FIRST_Unit",),
    selection_rule="exact FIRST_Unit membership in {Em, Im1, Im2, Imd}",
    limitations=USGS_MARE_PROXY_LIMITATIONS,
    is_proxy=True,
    buffer_support_km=0.0,
)

# Synthetic maps are generated with TiO2 defined over their entire artificial
# domain.  This provenance is intentionally distinct from the real USGS geology
# proxy: a validation harness must never claim that its all-valid flag is a lunar
# mare classification or evidence about the WAC product's real calibration domain.
SYNTHETIC_ALL_VALID_DOMAIN = TerrainMaskProvenance(
    source="src.data_acquisition.generate_synthetic_data artificial domain",
    source_fields=("generator_domain",),
    selection_rule="every generated grid cell is inside the artificial TiO2 domain",
    limitations=(
        "Synthetic all-domain support is a software-validation convention only; "
        "it provides no evidence about the real LROC WAC calibration domain.",
    ),
    is_proxy=False,
    buffer_support_km=max(config.BUFFER_RADII_KM),
)


def classify_usgs_mare_symbols(values: Sequence[object] | pd.Series) -> np.ndarray:
    """Return the conservative USGS mare-unit classification.

    Matching is exact and case-sensitive after stripping surrounding
    whitespace.  In particular, this function never infers mare terrain from
    an ``Im`` age prefix or from TiO2 abundance.
    """

    series = pd.Series(values, copy=False)
    normalized = series.map(lambda value: value.strip() if isinstance(value, str) else None)
    return normalized.isin(USGS_MARE_UNIT_SYMBOLS).to_numpy(dtype=bool)


def _grid_cell_index(df: pd.DataFrame) -> pd.MultiIndex:
    missing = [column for column in ("row_idx", "col_idx") if column not in df]
    if missing:
        raise TerrainMaskError(
            f"terrain-mask alignment requires grid identity columns {missing}"
        )

    arrays = []
    for column in ("row_idx", "col_idx"):
        try:
            values = pd.to_numeric(df[column], errors="raise").to_numpy(dtype=float)
        except (TypeError, ValueError) as exc:
            raise TerrainMaskError(f"{column} must contain integer grid indices") from exc
        if (
            not np.isfinite(values).all()
            or np.any(values < 0)
            or not np.equal(values, np.floor(values)).all()
        ):
            raise TerrainMaskError(f"{column} must contain finite non-negative integers")
        arrays.append(values.astype(np.int64))

    index = pd.MultiIndex.from_arrays(arrays, names=("row_idx", "col_idx"))
    if not index.is_unique:
        raise TerrainMaskError("row_idx/col_idx pairs must uniquely identify modeling rows")
    return index


def _coerce_explicit_mask(series: pd.Series, mask_col: str) -> np.ndarray:
    if series.isna().any():
        raise TerrainMaskError(f"{mask_col!r} contains missing values")

    if pd.api.types.is_bool_dtype(series.dtype):
        values = series.to_numpy(dtype=bool)
    elif pd.api.types.is_numeric_dtype(series.dtype):
        numeric = series.to_numpy(dtype=float)
        if not np.isfinite(numeric).all() or not np.isin(numeric, (0.0, 1.0)).all():
            raise TerrainMaskError(f"{mask_col!r} must contain only boolean/0/1 values")
        values = numeric.astype(bool)
    else:
        raise TerrainMaskError(
            f"{mask_col!r} must be a boolean or strict numeric 0/1 column; "
            "string truth values are not accepted"
        )

    if not np.any(values):
        raise TerrainMaskError(f"{mask_col!r} marks no rows as terrain-valid")
    return values


@dataclass(frozen=True)
class TerrainMask:
    """A provenance-bound mask keyed by stable raster cell identity."""

    values_by_cell: pd.Series
    column: str
    provenance: TerrainMaskProvenance

    def __post_init__(self) -> None:
        values = self.values_by_cell.copy(deep=True)
        if not isinstance(values.index, pd.MultiIndex) or values.index.nlevels != 2:
            raise TerrainMaskError("TerrainMask values must be keyed by row_idx/col_idx")
        if not values.index.is_unique:
            raise TerrainMaskError("TerrainMask grid-cell keys must be unique")
        if values.isna().any() or not pd.api.types.is_bool_dtype(values.dtype):
            raise TerrainMaskError("TerrainMask values must be non-null booleans")
        values.index = values.index.set_names(("row_idx", "col_idx"))
        values.name = self.column
        object.__setattr__(self, "values_by_cell", values)

    def align_to(self, df: pd.DataFrame) -> np.ndarray:
        """Align to any reordered/subset table by raster identity, never position."""

        cells = _grid_cell_index(df)
        aligned = self.values_by_cell.reindex(cells)
        if aligned.isna().any():
            missing = int(aligned.isna().sum())
            raise TerrainMaskError(
                f"terrain mask has no value for {missing} modeling grid cells"
            )
        return aligned.to_numpy(dtype=bool)

    def metadata(self) -> Dict[str, object]:
        values = self.values_by_cell.to_numpy(dtype=bool)
        return {
            "column": self.column,
            "source": self.provenance.source,
            "source_fields": list(self.provenance.source_fields),
            "selection_rule": self.provenance.selection_rule,
            "is_proxy": bool(self.provenance.is_proxy),
            "limitations": list(self.provenance.limitations),
            "buffer_support_km": float(self.provenance.buffer_support_km),
            "n_rows_at_validation": int(len(values)),
            "n_terrain_valid_at_validation": int(values.sum()),
            "terrain_valid_fraction_at_validation": float(values.mean()),
            "uses_target_to_define_mask": False,
            "uses_tio2_to_define_mask": False,
        }


def validate_terrain_mask(
    df: pd.DataFrame,
    mask_col: str = DEFAULT_MASK_COLUMN,
    *,
    provenance: TerrainMaskProvenance = USGS_MARE_PROXY,
) -> TerrainMask:
    """Validate and bind an explicit terrain column to stable grid cells.

    Missing masks fail closed.  In particular, this function will not fall back
    to ``age_class``, a TiO2 cutoff, nearside location, or any other convenient
    predictor proxy.
    """

    if mask_col not in df:
        raise TerrainMaskError(
            f"required explicit terrain mask {mask_col!r} is missing; cannot infer "
            "mare validity from age_class, TiO2 abundance, coordinates, or model features"
        )
    cells = _grid_cell_index(df)
    values = _coerce_explicit_mask(df[mask_col], mask_col)
    keyed = pd.Series(values, index=cells, dtype=bool, name=mask_col)
    return TerrainMask(keyed, mask_col, provenance)


def terrain_subsets(df: pd.DataFrame, terrain_mask: TerrainMask) -> Dict[str, pd.DataFrame]:
    """Return full-scope and mare-valid copies with deterministic alignment."""

    keep = terrain_mask.align_to(df)
    return {
        "full_scope": df.copy().reset_index(drop=True),
        "mare_valid": df.loc[keep].copy().reset_index(drop=True),
    }


def shared_spatial_fold_ids(
    df: pd.DataFrame,
    n_splits: int,
    *,
    group_col: str = "spatial_block",
) -> np.ndarray:
    """Assign outcome-free folds once on the full analysis scope.

    ``GroupKFold`` uses only group membership and group sizes here; no target is
    passed.  Filtering this returned array with the terrain mask makes both
    analyses inherit the same block-to-fold mapping.
    """

    if group_col not in df:
        raise ValueError(f"missing spatial group column {group_col!r}")
    if not isinstance(n_splits, (int, np.integer)) or int(n_splits) < 2:
        raise ValueError("n_splits must be an integer >= 2")
    groups = df[group_col].to_numpy()
    if pd.isna(groups).any():
        raise ValueError(f"{group_col!r} contains missing values")
    n_groups = int(pd.unique(groups).size)
    if n_groups < 2:
        raise ValueError("spatial cross-validation requires at least two groups")

    actual_splits = min(int(n_splits), n_groups)
    folds = np.full(len(df), -1, dtype=np.int64)
    splitter = GroupKFold(n_splits=actual_splits)
    dummy = np.zeros((len(df), 1), dtype=np.uint8)
    for fold_id, (_, test_idx) in enumerate(splitter.split(dummy, groups=groups)):
        folds[test_idx] = fold_id
    if np.any(folds < 0):  # defensive guard against an incomplete splitter
        raise RuntimeError("failed to assign every row to a spatial fold")

    mapping = pd.DataFrame({"group": groups, "fold": folds}).groupby("group")["fold"].nunique()
    if int(mapping.max()) != 1:
        raise RuntimeError("a spatial block was assigned to more than one fold")
    return folds


def _validate_binary_target(df: pd.DataFrame, target: str) -> pd.Series:
    if target not in df:
        raise ValueError(f"missing target column {target!r}")
    y = df[target]
    if y.isna().any() or not set(pd.unique(y)).issubset({0, 1, False, True}):
        raise ValueError(f"{target!r} must be a non-null binary target")
    return y.astype(int)


def _supported_h1_features(provenance: TerrainMaskProvenance) -> tuple[str, ...]:
    features = ["tio2"]
    for radius_km, feature in zip(config.BUFFER_RADII_KM, config.TIO2_BUFFER_FEATURES):
        if radius_km <= provenance.buffer_support_km + 1e-12:
            features.append(feature)
    return tuple(features)


def _usable_fold_ids(y: pd.Series, folds: np.ndarray) -> list[int]:
    usable = []
    for fold_id in sorted(int(value) for value in np.unique(folds)):
        test = folds == fold_id
        train = ~test
        if not np.any(test) or not np.any(train):
            continue
        y_train = y.iloc[np.flatnonzero(train)]
        y_test = y.iloc[np.flatnonzero(test)]
        if y_train.nunique() < 2 or int(y_test.sum()) == 0:
            continue
        usable.append(fold_id)
    return usable


def _score_on_fixed_folds(
    df: pd.DataFrame,
    y: pd.Series,
    folds: np.ndarray,
    features: Sequence[str],
    usable_folds: Sequence[int],
    model_factory: Callable[[pd.Series], object],
) -> Dict[int, float]:
    missing = [feature for feature in features if feature not in df]
    if missing:
        raise ValueError(f"missing sensitivity features {missing}")
    X = df[list(features)]
    numeric = X.to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("terrain-sensitivity features must be finite")

    scores: Dict[int, float] = {}
    for fold_id in usable_folds:
        test_idx = np.flatnonzero(folds == fold_id)
        train_idx = np.flatnonzero(folds != fold_id)
        estimator = model_factory(y.iloc[train_idx])
        estimator.fit(X.iloc[train_idx], y.iloc[train_idx])
        probabilities = np.asarray(estimator.predict_proba(X.iloc[test_idx]))[:, 1]
        scores[int(fold_id)] = float(average_precision_score(y.iloc[test_idx], probabilities))
    return scores


def _paired_one_sided_greater(a: np.ndarray, b: np.ndarray) -> float:
    if np.allclose(a - b, 0.0):
        return 1.0
    try:
        return float(stats.wilcoxon(a, b, alternative="greater", zero_method="zsplit").pvalue)
    except ValueError:
        return float(stats.ttest_rel(a, b, alternative="greater").pvalue)


def _scope_diagnostics(df: pd.DataFrame, target: str, folds: np.ndarray) -> Dict[str, object]:
    y = _validate_binary_target(df, target)
    positive = y == 1
    return {
        "n_pixels": int(len(df)),
        "n_spatial_blocks": int(df["spatial_block"].nunique()),
        "n_positive_pixels": int(positive.sum()),
        "n_positive_spatial_blocks": int(df.loc[positive, "spatial_block"].nunique()),
        "positive_prevalence": float(y.mean()) if len(y) else float("nan"),
        "n_inherited_folds_present": int(np.unique(folds).size),
    }


def _evaluate_scope(
    df: pd.DataFrame,
    target: str,
    folds: np.ndarray,
    *,
    h1_features: Sequence[str],
    model_factory: Callable[[pd.Series], object],
    min_rows: int,
) -> Dict[str, object]:
    diagnostics = _scope_diagnostics(df, target, folds)
    y = _validate_binary_target(df, target)
    n_folds = int(np.unique(folds).size)
    required_positive_blocks = min(n_folds, max(3, n_folds - 1))

    reason = None
    if len(df) < min_rows:
        reason = f"fewer than {min_rows} rows"
    elif y.nunique() < 2:
        reason = "target has only one class"
    elif int(diagnostics["n_positive_spatial_blocks"]) < required_positive_blocks:
        reason = (
            "positives occupy too few inherited spatial blocks "
            f"(<{required_positive_blocks})"
        )

    usable_folds = _usable_fold_ids(y, folds) if reason is None else []
    if reason is None and len(usable_folds) < 2:
        reason = "fewer than two inherited folds have evaluable train/test positives"
    if reason is not None:
        return {**diagnostics, "skipped": True, "reason": reason}

    # A clean proxy contrast: composition plus repository-plan controls versus
    # those same controls.  Exploratory TiO2 x gravity terms are deliberately
    # absent because they still encode TiO2 and would contaminate the ablation.
    h1_plus_controls = tuple(dict.fromkeys((*h1_features, *config.CONTROL_FEATURES)))
    controls_only = tuple(config.CONTROL_FEATURES)
    h2_only = tuple(config.H2_FEATURES)

    h1_scores = _score_on_fixed_folds(
        df, y, folds, h1_plus_controls, usable_folds, model_factory
    )
    controls_scores = _score_on_fixed_folds(
        df, y, folds, controls_only, usable_folds, model_factory
    )
    h2_scores = _score_on_fixed_folds(
        df, y, folds, h2_only, usable_folds, model_factory
    )
    ordered = sorted(set(h1_scores) & set(controls_scores) & set(h2_scores))
    h1 = np.asarray([h1_scores[fold] for fold in ordered], dtype=float)
    controls = np.asarray([controls_scores[fold] for fold in ordered], dtype=float)
    h2 = np.asarray([h2_scores[fold] for fold in ordered], dtype=float)
    drop = h1 - controls
    p_value = _paired_one_sided_greater(h1, controls)

    return {
        **diagnostics,
        "skipped": False,
        "usable_inherited_fold_ids": ordered,
        "H1_Plus_Controls_PR_AUC": float(h1.mean()),
        "Controls_Only_PR_AUC": float(controls.mean()),
        "H2_Only_PR_AUC": float(h2.mean()),
        "H1_tio2_drop_mean": float(drop.mean()),
        "Wilcoxon_p_H1_gt_controls": float(p_value),
        "beats_h2_only": bool(h1.mean() > h2.mean()),
        "ablation_significant": bool(drop.mean() > 0 and p_value < 0.05),
        "per_fold": {
            "fold_ids": ordered,
            "H1_Plus_Controls_PR_AUC": h1.tolist(),
            "Controls_Only_PR_AUC": controls.tolist(),
            "H2_Only_PR_AUC": h2.tolist(),
            "H1_tio2_drop": drop.tolist(),
        },
    }


def evaluate_full_vs_mare(
    df: pd.DataFrame,
    target: str,
    cfg: config.PipelineConfig | None = None,
    *,
    mask_col: str = DEFAULT_MASK_COLUMN,
    provenance: TerrainMaskProvenance = USGS_MARE_PROXY,
    model_factory: Callable[[pd.Series], object] | None = None,
    min_rows: int = 100,
) -> Dict[str, object]:
    """Compare the same clean H1 model on full and mare-valid scopes.

    The caller should apply the repository-plan age restriction *before* calling
    this function.  ``full_scope`` therefore means the complete caller-supplied
    scope, while ``mare_valid`` is its intersection with the external mask.
    No target value participates in mask validation or fold construction.
    """

    if not isinstance(min_rows, (int, np.integer)) or int(min_rows) < 1:
        raise ValueError("min_rows must be a positive integer")
    cfg = cfg or config.PipelineConfig()
    _validate_binary_target(df, target)
    terrain_mask = validate_terrain_mask(df, mask_col, provenance=provenance)

    # Crucially, construct folds before applying the mask and without y.
    folds = shared_spatial_fold_ids(df, cfg.n_outer_folds)
    keep = terrain_mask.align_to(df)
    full_df = df.copy().reset_index(drop=True)
    mare_df = df.loc[keep].copy().reset_index(drop=True)
    mare_folds = folds[keep]

    factory = model_factory or modeling.xgb_factory(seed=cfg.random_seed)
    h1_features = _supported_h1_features(provenance)
    full_result = _evaluate_scope(
        full_df,
        target,
        folds,
        h1_features=h1_features,
        model_factory=factory,
        min_rows=int(min_rows),
    )
    mare_result = _evaluate_scope(
        mare_df,
        target,
        mare_folds,
        h1_features=h1_features,
        model_factory=factory,
        min_rows=int(min_rows),
    )

    mask_metadata = terrain_mask.metadata()
    mask_metadata.update(
        {
            "n_rows_in_analysis_scope": int(len(df)),
            "n_terrain_valid_in_analysis_scope": int(keep.sum()),
            "terrain_valid_fraction_in_analysis_scope": float(keep.mean()),
        }
    )
    excluded_buffers = [
        feature for feature in config.TIO2_BUFFER_FEATURES if feature not in h1_features
    ]
    result: Dict[str, object] = {
        "analysis": "post_result_terrain_validity_sensitivity",
        "mask": mask_metadata,
        "design": {
            "folds_assigned_on_full_scope_before_terrain_filter": True,
            "fold_assignment_uses_target": False,
            "mare_rows_inherit_full_scope_spatial_folds": True,
            "spatial_group_column": "spatial_block",
            "h1_features_evaluated": list(h1_features),
            "excluded_unsupported_tio2_buffers": excluded_buffers,
            "exploratory_tio2_gravity_interactions_excluded": True,
            "interpretation": (
                "sensitivity analysis of present-day surface TiO2 spatial "
                "co-location; not a test of intermittent-dynamo timing"
            ),
        },
        "full_scope": full_result,
        "mare_valid": mare_result,
    }

    if not full_result.get("skipped") and not mare_result.get("skipped"):
        common_folds = sorted(
            set(full_result["per_fold"]["fold_ids"])
            & set(mare_result["per_fold"]["fold_ids"])
        )
        per_fold_names = {
            "H1_Plus_Controls_PR_AUC": "H1_Plus_Controls_PR_AUC",
            "Controls_Only_PR_AUC": "Controls_Only_PR_AUC",
            "H2_Only_PR_AUC": "H2_Only_PR_AUC",
            "H1_tio2_drop_mean": "H1_tio2_drop",
        }

        def _fold_map(scope: Dict[str, object], metric: str) -> Dict[int, float]:
            per_fold = scope["per_fold"]
            return {
                int(fold): float(value)
                for fold, value in zip(per_fold["fold_ids"], per_fold[metric])
            }

        contrast: Dict[str, object] = {
            "comparison_inherited_fold_ids": common_folds,
            "uses_identical_fold_ids_for_both_scopes": True,
            "interpretation": (
                "Descriptive scope contrast on common inherited folds; the scopes have "
                "different rows and prevalence, so this is not a paired causal effect."
            ),
        }
        for output_name, per_fold_name in per_fold_names.items():
            full_by_fold = _fold_map(full_result, per_fold_name)
            mare_by_fold = _fold_map(mare_result, per_fold_name)
            contrast[output_name] = float(
                np.mean([mare_by_fold[fold] for fold in common_folds])
                - np.mean([full_by_fold[fold] for fold in common_folds])
            )
        result["mare_minus_full"] = contrast
    return result


__all__ = [
    "DEFAULT_MASK_COLUMN",
    "TerrainMask",
    "TerrainMaskError",
    "TerrainMaskProvenance",
    "USGS_MARE_PROXY",
    "USGS_MARE_PROXY_LIMITATIONS",
    "USGS_MARE_UNIT_SYMBOLS",
    "SYNTHETIC_ALL_VALID_DOMAIN",
    "classify_usgs_mare_symbols",
    "evaluate_full_vs_mare",
    "shared_spatial_fold_ids",
    "terrain_subsets",
    "validate_terrain_mask",
]
