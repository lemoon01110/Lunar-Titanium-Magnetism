"""Data-generation, preprocessing, and end-to-end integration tests."""

import os
import hashlib

import numpy as np
import pandas as pd
import pytest

from src import config, spatial
from src.data_acquisition import generate_synthetic_data
from src.preprocessing import preprocess_data
from src.evaluation import evaluate_pipeline


COARSE_RES = 4.0  # small grid so the suite stays fast


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    """Generate + preprocess a small synthetic dataset once for the module."""
    base = tmp_path_factory.mktemp("moon")
    raw = os.path.join(base, "raw")
    proc = os.path.join(base, "processed")
    os.makedirs(raw, exist_ok=True)
    generate_synthetic_data(raw, grid_res_deg=COARSE_RES, scenario="h1_lean", random_seed=7)
    csv = preprocess_data(raw, proc, grid_res_deg=COARSE_RES)
    df = pd.read_csv(csv)
    return {"raw": raw, "proc": proc, "df": df, "base": base}


def test_generation_is_deterministic(tmp_path):
    d1 = os.path.join(tmp_path, "a")
    d2 = os.path.join(tmp_path, "b")
    os.makedirs(d1); os.makedirs(d2)
    generate_synthetic_data(d1, grid_res_deg=COARSE_RES, random_seed=123)
    generate_synthetic_data(d2, grid_res_deg=COARSE_RES, random_seed=123)
    import rasterio
    with rasterio.open(os.path.join(d1, config.RAW_FILES["magnetic"])) as a, \
         rasterio.open(os.path.join(d2, config.RAW_FILES["magnetic"])) as b:
        assert np.array_equal(a.read(1), b.read(1))


def test_required_layers_and_tables_exist(prepared):
    raw = prepared["raw"]
    for fname in config.RAW_FILES.values():
        assert os.path.exists(os.path.join(raw, fname)), fname
    assert os.path.exists(os.path.join(raw, config.ANTIPODES_CSV))
    assert os.path.exists(os.path.join(raw, config.BASINS_CSV))
    assert os.path.exists(os.path.join(raw, config.TERRAIN_VALIDITY_FILE))


def test_dataset_has_all_expected_columns(prepared):
    df = prepared["df"]
    for col in config.ALL_FEATURES + ["lon", "lat", "age_class", "spatial_block",
                                      "row_idx", "col_idx", "tio2_terrain_valid",
                                      "mag_binary_5nT", "mag_binary_10nT"]:
        assert col in df.columns, col


def test_antipode_distance_is_real_not_map_center(prepared):
    """REGRESSION TEST for the original showstopper bug.

    The old code set dist_to_antipode to distance-from-map-centre and never used
    antipodes.csv. Here we prove the stored feature is the true great-circle
    distance to the nearest actual antipode.
    """
    df = prepared["df"]
    antipodes = pd.read_csv(os.path.join(prepared["raw"], config.ANTIPODES_CSV))

    # (a) Stored distance matches an independent recomputation from stored lon/lat.
    recomputed = spatial.min_distance_to_points_km(
        df["lon"].values[None, :], df["lat"].values[None, :],
        antipodes["lon"].values, antipodes["lat"].values,
    ).ravel()
    assert np.allclose(df["dist_to_antipode_km"].values, recomputed, atol=1.0)

    # (b) The closest-to-antipode pixel actually sits near an antipode, and NOT
    #     necessarily near the map centre (0, 0) -- the old-bug signature.
    imin = int(df["dist_to_antipode_km"].idxmin())
    near_lon, near_lat = df.loc[imin, "lon"], df.loc[imin, "lat"]
    d_to_nearest_antipode = spatial.min_distance_to_points_km(
        np.array([[near_lon]]), np.array([[near_lat]]),
        antipodes["lon"].values, antipodes["lat"].values,
    )[0, 0]
    assert d_to_nearest_antipode < 2.0 * COARSE_RES * (np.pi * config.LUNAR_RADIUS_KM / 180.0)


def test_prevalence_is_realistic(prepared):
    df = prepared["df"]
    prev = df["mag_binary_5nT"].mean()
    assert 0.02 < prev < 0.40, f"unrealistic prevalence {prev}"
    # 10 nT threshold must be rarer than 5 nT.
    assert df["mag_binary_10nT"].mean() <= prev


def test_spatial_blocks_do_not_leak(prepared):
    """No spatial block may straddle a wildly large geographic extent (sanity),
    and GroupKFold on blocks must keep any block wholly in one side of a split."""
    from sklearn.model_selection import GroupKFold
    df = prepared["df"]
    groups = df["spatial_block"].values
    n_splits = min(5, len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    X = df[config.ALL_FEATURES]
    y = df["mag_binary_5nT"]
    for train_idx, test_idx in gkf.split(X, y, groups):
        assert set(groups[train_idx]).isdisjoint(set(groups[test_idx]))


def test_h1_features_are_purely_compositional():
    """F1 regression: the H1 signal must contain no gravity / interaction / antipode
    term, and the feature groups must be a clean partition. config.validate_feature_groups
    already asserts this at import; here we lock it in a test too."""
    config.validate_feature_groups()  # must not raise
    for feat in config.H1_FEATURES:
        assert "gravity" not in feat and "interaction" not in feat and "antipode" not in feat
    assert set(config.H1_FEATURES).isdisjoint(config.EXPLORATORY_FEATURES)
    assert set(config.H1_FEATURES).isdisjoint(config.H2_FEATURES)
    from src.evaluation import feature_sets
    assert set(feature_sets()["no_h1_tio2"]).isdisjoint(config.TIO2_DERIVED_FEATURES)


def _scenario_discriminators(tmp_path, scenario, res=3.0, seed=11):
    """Generate one scenario and return (core_analysis, shap ranking) on Imbrian/5nT."""
    from src import modeling, interpretability
    raw = os.path.join(tmp_path, f"raw_{scenario}"); os.makedirs(raw, exist_ok=True)
    proc = os.path.join(tmp_path, f"proc_{scenario}"); os.makedirs(proc, exist_ok=True)
    generate_synthetic_data(raw, grid_res_deg=res, scenario=scenario, random_seed=seed)
    from src.evaluation import subset_by_age, core_analysis
    df = pd.read_csv(preprocess_data(raw, proc, grid_res_deg=res))
    dfp = subset_by_age(df, "imbrian")
    cfg = config.PipelineConfig(mode="fast", grid_res_deg=res, random_seed=seed)
    core = core_analysis(dfp, "mag_binary_5nT", cfg)
    model = modeling.fit_final_model(dfp[config.ALL_FEATURES], dfp["mag_binary_5nT"], {}, seed)
    sv, _Xs, imp = interpretability.compute_shap(model, dfp[config.ALL_FEATURES], seed, 1500)
    rank = interpretability.h1_vs_h2_ranking(imp, sv, config.ALL_FEATURES)
    return core, rank


@pytest.mark.slow
def test_h1_signal_is_detected_on_h1_data(tmp_path):
    """F7 power: on H1-driven data, the TiO2 signal must be predictive AND outrank
    the antipode feature; the (non-Nichols) interaction must add ~nothing."""
    core, rank = _scenario_discriminators(tmp_path, "h1_lean")
    assert core["ablation"]["H1_tio2_drop_mean"] > 0.01           # removing TiO2 hurts
    assert rank["h1_outranks_antipode"]                            # TiO2 > antipode
    assert rank["h1_tio2_family_importance"] > rank["exploratory_interaction_family_importance"]


@pytest.mark.slow
@pytest.mark.parametrize("scenario", ["h2_lean", "null"])
def test_h1_is_refuted_on_non_h1_data(tmp_path, scenario):
    """F7 false-positive control: the repository-plan proxy criteria must fail when the
    data are not H1-driven -- the test must be able to fail.

    Scenario-appropriate refutation signal:
      * h2_lean: a real rival signal exists, so the antipode must outrank TiO2 (crit ii).
      * null:    no signal exists, so removing TiO2 must not significantly hurt (crit iii).
        (On pure noise the SHAP *ordering* is a coin flip, so it is not a valid target.)
    """
    core, rank = _scenario_discriminators(tmp_path, scenario)
    if scenario == "h2_lean":
        assert not rank["h1_outranks_antipode"]
    else:  # null
        assert not core["ablation_significant"]


def test_spatial_stats_primitives():
    """F/rigor: phase-randomisation preserves shape and returns a real field; the
    block-bootstrap CI brackets the point estimate."""
    from src import spatial_stats
    rng = np.random.default_rng(0)
    grid = rng.standard_normal((40, 60))
    sur = spatial_stats.phase_randomized_surrogate(grid, rng)
    assert sur.shape == grid.shape and np.isfinite(sur).all()

    # Synthetic classifier output where a CI must bracket the point PR-AUC.
    n = 2000
    y = (rng.random(n) < 0.2).astype(int)
    oof = np.clip(0.6 * y + 0.4 * rng.random(n), 0, 1)
    blocks = rng.integers(0, 25, size=n)
    ci = spatial_stats.block_bootstrap_pr_auc_ci(y, oof, blocks, n_boot=200, seed=1)
    assert ci["PR_AUC_CI_low"] <= ci["PR_AUC_point"] <= ci["PR_AUC_CI_high"]


def test_shap_figures_are_byte_reproducible(tmp_path):
    """Plot-only RNG (beeswarm jitter) must not change published figures."""
    from src import interpretability

    rng = np.random.default_rng(4)
    n = 40
    X = pd.DataFrame(rng.normal(size=(n, len(config.ALL_FEATURES))), columns=config.ALL_FEATURES)
    shap_values = rng.normal(size=X.shape)
    lonlat = pd.DataFrame({"lon": np.linspace(-170, 170, n), "lat": np.linspace(-70, 70, n)})
    out1, out2 = tmp_path / "one", tmp_path / "two"
    interpretability.make_figures(None, shap_values, X, lonlat, str(out1), seed=42)
    interpretability.make_figures(None, shap_values, X, lonlat, str(out2), seed=42)

    for filename in (
        "shap_summary.png", "shap_dependence_interaction.png", "shap_interaction_map.png"
    ):
        digest1 = hashlib.sha256((out1 / filename).read_bytes()).hexdigest()
        digest2 = hashlib.sha256((out2 / filename).read_bytes()).hexdigest()
        assert digest1 == digest2


@pytest.mark.slow
def test_end_to_end_fast(prepared):
    cfg = config.PipelineConfig(mode="fast", grid_res_deg=COARSE_RES, random_seed=7)
    results_dir = os.path.join(prepared["base"], "results")
    metrics = evaluate_pipeline(
        prepared["proc"], results_dir, cfg,
        run_metadata={"data_mode": "synthetic", "scenario": "h1_lean"},
    )

    # Structure.
    for key in ["Transparent_Continuous_Analysis", "Terrain_Validity_Sensitivity",
                "Cross_Validation", "Ablation", "Permutation_Test", "SHAP",
                "Criteria", "H1_Supported", "Falsifiability_Guards",
                "Power_Analysis", "Detection_Power", "Spatial_Diagnostics",
                "Sensitivity"]:
        assert key in metrics
    # Spatial diagnostics are structurally complete.
    sd = metrics["Spatial_Diagnostics"]
    for key in ["variogram_range_km", "block_exceeds_range", "block_bootstrap_pr_auc",
                "phase_randomization_null", "block_size_robustness"]:
        assert key in sd
    assert isinstance(metrics["H1_Supported"], bool)

    # The artificial all-valid TiO2 domain must never be mislabeled as USGS
    # geology or as evidence about the real WAC calibration domain.
    terrain = metrics["Terrain_Validity_Sensitivity"]
    assert terrain["analysis"] == "synthetic_all_valid_domain_check"
    assert terrain["status"] == "not_applicable_to_real_wac_terrain_calibration"
    assert terrain["mask"]["source"].startswith("src.data_acquisition")
    assert terrain["mask"]["is_proxy"] is False
    assert terrain["design"]["real_usgs_geology_proxy_used"] is False
    assert "mare_valid" not in terrain

    # F6 guard present and self-consistent.
    fg = metrics["Falsifiability_Guards"]
    assert fg["repository_plan_primary_supported"] == metrics["H1_Supported"]
    if fg["subset_signal_is_hypothesis_generating_not_confirmation"]:
        assert not metrics["H1_Supported"]

    # Dummy-prior PR-AUC must equal the positive prevalence (a strong invariant).
    cv = metrics["Cross_Validation"]
    assert cv["Dummy_Prior_PR_AUC"] == pytest.approx(cv["positive_prevalence"], abs=0.03)

    # Figures written.
    figs = os.path.join(results_dir, "figures")
    assert os.path.exists(os.path.join(figs, "shap_summary.png"))
