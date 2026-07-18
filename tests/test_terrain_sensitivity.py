"""Targeted tests for the fail-closed TiO2 terrain-validity sensitivity."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import config, modeling, terrain_sensitivity as terrain


def _identity_frame(n: int = 8) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_idx": np.arange(n) // 4,
            "col_idx": np.arange(n) % 4,
            "tio2_terrain_valid": np.arange(n) % 2 == 0,
        }
    )


def test_usgs_mare_classifier_is_an_exact_allowlist_not_an_age_prefix():
    values = ["Em", "Im1", "Im2", "Imd", "Ip", "Iohs", "Im", "em", None, " Im1 "]
    actual = terrain.classify_usgs_mare_symbols(values)
    assert actual.tolist() == [True, True, True, True, False, False, False, False, False, True]


def test_missing_mask_fails_closed_instead_of_using_age_or_tio2():
    df = _identity_frame().drop(columns="tio2_terrain_valid")
    df["age_class"] = config.AGE_IMBRIAN
    df["tio2"] = 8.0

    with pytest.raises(terrain.TerrainMaskError, match="cannot infer mare validity"):
        terrain.validate_terrain_mask(df)


@pytest.mark.parametrize(
    "bad_values",
    [
        [0, 1, 2, 0, 1, 0, 1, 0],
        [True, False, None, False, True, False, True, False],
        ["true", "false", "true", "false", "true", "false", "true", "false"],
    ],
)
def test_mask_must_be_complete_strict_boolean_or_zero_one(bad_values):
    df = _identity_frame()
    df["tio2_terrain_valid"] = bad_values
    with pytest.raises(terrain.TerrainMaskError):
        terrain.validate_terrain_mask(df)


@pytest.mark.parametrize("unsafe_field", ["tio2", "tio2_25km", "age_class", "mag_binary_5nT"])
def test_provenance_rejects_circular_or_outcome_derived_masks(unsafe_field):
    with pytest.raises(terrain.TerrainMaskError, match="may not be derived"):
        terrain.TerrainMaskProvenance(
            source="made-up proxy",
            source_fields=(unsafe_field,),
            selection_rule="threshold it",
            limitations=("This is not an independent terrain product.",),
        )


def test_mask_alignment_uses_grid_identity_after_reordering_and_subsetting():
    df = _identity_frame()
    mask = terrain.validate_terrain_mask(df)

    reordered = df.iloc[[6, 1, 4]].copy()
    subsets = terrain.terrain_subsets(reordered, mask)

    assert list(zip(subsets["mare_valid"]["row_idx"], subsets["mare_valid"]["col_idx"])) == [
        (1, 2),
        (1, 0),
    ]
    metadata = mask.metadata()
    assert metadata["is_proxy"] is True
    assert metadata["uses_target_to_define_mask"] is False
    assert metadata["uses_tio2_to_define_mask"] is False
    assert metadata["limitations"]


def test_shared_folds_are_target_free_and_never_split_a_spatial_block():
    n_groups, rows_per_group = 10, 7
    df = pd.DataFrame(
        {
            "spatial_block": np.repeat(np.arange(n_groups), rows_per_group),
            "arbitrary_target_a": np.tile([0, 1, 0, 0, 1, 0, 0], n_groups),
            "arbitrary_target_b": np.tile([1, 0, 1, 1, 0, 1, 1], n_groups),
        }
    )

    folds_a = terrain.shared_spatial_fold_ids(df, 5)
    folds_b = terrain.shared_spatial_fold_ids(df.drop(columns="arbitrary_target_a"), 5)

    assert np.array_equal(folds_a, folds_b)
    by_group = pd.DataFrame({"group": df["spatial_block"], "fold": folds_a})
    assert by_group.groupby("group")["fold"].nunique().eq(1).all()


def _evaluation_frame(seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_groups, rows_per_group = 10, 30
    n = n_groups * rows_per_group
    groups = np.repeat(np.arange(n_groups), rows_per_group)
    local = np.tile(np.arange(rows_per_group), n_groups)
    tio2 = rng.normal(size=n)
    # Each spatial block has positives and both terrain classes.  The target is
    # generated only for this machinery test; it never defines the terrain mask.
    y = (tio2 + 0.25 * rng.normal(size=n) > 0.45).astype(int)
    return pd.DataFrame(
        {
            "row_idx": groups,
            "col_idx": local,
            "spatial_block": groups,
            "tio2_terrain_valid": local % 2 == 0,
            "tio2": tio2,
            "tio2_25km": tio2 + 99.0,  # present but unsupported and must be excluded
            "dist_to_antipode_km": rng.uniform(0, 5_000, n),
            "dist_to_basin_rim_km": rng.uniform(0, 2_000, n),
            "crustal_thickness": rng.uniform(20, 60, n),
            "abs_latitude": rng.uniform(0, 80, n),
            "nearside": rng.uniform(-1, 1, n),
            "mag_binary_5nT": y,
        }
    )


def test_full_vs_mare_uses_inherited_spatial_folds_and_only_supported_tio2():
    df = _evaluation_frame()
    cfg = config.PipelineConfig(n_outer_folds=5, random_seed=17, mode="fast")
    result = terrain.evaluate_full_vs_mare(
        df,
        "mag_binary_5nT",
        cfg,
        model_factory=modeling.logreg_factory(seed=17),
        min_rows=50,
    )

    assert result["full_scope"]["skipped"] is False
    assert result["mare_valid"]["skipped"] is False
    assert result["mask"]["n_terrain_valid_in_analysis_scope"] == len(df) // 2
    assert result["design"]["folds_assigned_on_full_scope_before_terrain_filter"] is True
    assert result["design"]["fold_assignment_uses_target"] is False
    assert result["design"]["h1_features_evaluated"] == ["tio2"]
    assert "tio2_25km" in result["design"]["excluded_unsupported_tio2_buffers"]
    assert result["design"]["exploratory_tio2_gravity_interactions_excluded"] is True
    assert set(result["mare_valid"]["usable_inherited_fold_ids"]).issubset(
        result["full_scope"]["usable_inherited_fold_ids"]
    )
    assert "H1_tio2_drop_mean" in result["mare_minus_full"]
    assert result["mare_minus_full"]["uses_identical_fold_ids_for_both_scopes"] is True
    assert result["mare_minus_full"]["comparison_inherited_fold_ids"] == sorted(
        set(result["mare_valid"]["usable_inherited_fold_ids"])
        & set(result["full_scope"]["usable_inherited_fold_ids"])
    )


def test_documented_buffer_support_enables_only_covered_buffer_features():
    provenance = terrain.TerrainMaskProvenance(
        source="independent eroded USGS mare mask",
        source_fields=("FIRST_Unit",),
        selection_rule="exact mare units eroded by 50 km",
        limitations=("Raster erosion is grid-resolution dependent.",),
        buffer_support_km=50.0,
    )
    df = _evaluation_frame()
    # All configured feature columns are needed once 25/50 km support is claimed.
    df["tio2_50km"] = df["tio2"]
    result = terrain.evaluate_full_vs_mare(
        df,
        "mag_binary_5nT",
        config.PipelineConfig(n_outer_folds=5, mode="fast"),
        provenance=provenance,
        model_factory=modeling.logreg_factory(seed=42),
        min_rows=50,
    )

    assert result["design"]["h1_features_evaluated"] == [
        "tio2",
        "tio2_25km",
        "tio2_50km",
    ]
    assert result["design"]["excluded_unsupported_tio2_buffers"] == ["tio2_100km"]
