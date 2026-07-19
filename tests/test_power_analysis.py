"""Tests for the spatial positive-control injection/recovery analysis."""

from __future__ import annotations

import json
import hashlib

import numpy as np
import pandas as pd
import pytest

from src import config, spatial
from src.spatial_stats import phase_randomized_surrogate
from src import spatial_stats
from src.power_analysis import (
    PowerAnalysisConfig,
    build_signal_score,
    control_feature_sets,
    generate_spatial_noise_fields,
    grouped_fold_audit,
    inject_binary_target,
    minimum_detectable_effect,
    run_power_analysis,
    run_power_analysis_frame,
    structural_diagnostics,
    wilson_interval,
    write_power_result,
)


def _toy_frame(seed: int = 4) -> tuple[pd.DataFrame, dict]:
    """Small complete lunar-like grid containing every repository-plan feature."""
    rng = np.random.default_rng(seed)
    height, width = 18, 36
    res_deg = 10.0
    lons = -180.0 + res_deg * (np.arange(width) + 0.5)
    lats = 90.0 - res_deg * (np.arange(height) + 0.5)
    lon, lat = np.meshgrid(lons, lats)
    rows, cols = np.mgrid[:height, :width]

    base = spatial.gaussian_smooth(rng.standard_normal((height, width)), 1.6)
    magnetic = np.exp(base - base.min()) - 1.0
    tio2 = 1.5 + 0.8 * np.cos(np.radians(lon + 40)) * np.cos(np.radians(lat))
    tio2 += 0.12 * spatial.gaussian_smooth(rng.standard_normal((height, width)), 1.0)
    tio2 = np.clip(tio2, 0.1, None)
    gravity = 70 * np.sin(np.radians(lon)) + 15 * base
    distance = spatial.haversine_km(lon, lat, 30.0, -10.0)

    flat = pd.DataFrame({
        "row_idx": rows.ravel(),
        "col_idx": cols.ravel(),
        "lon": lon.ravel(),
        "lat": lat.ravel(),
        "abs_latitude": np.abs(lat).ravel(),
        "mag_anomaly": magnetic.ravel(),
        "tio2": tio2.ravel(),
        "gravity": gravity.ravel(),
        "gravity_bandpass": (gravity - gravity.mean()).ravel(),
        "crustal_thickness": (35 + 5 * np.cos(np.radians(lat))).ravel(),
        "dist_to_antipode_km": distance.ravel(),
        "dist_to_basin_rim_km": spatial.haversine_km(lon, lat, -80.0, 25.0).ravel(),
        "nearside": np.cos(np.radians(lon)).ravel(),
        "age_class": np.full(height * width, config.AGE_IMBRIAN),
    })
    flat["spatial_block"] = spatial.spatial_block_ids(
        flat["lon"].to_numpy(), flat["lat"].to_numpy(), config.SPATIAL_BLOCK_SIZE_DEG
    )
    for radius, scale in zip(config.BUFFER_RADII_KM, (0.98, 0.94, 0.88)):
        flat[f"tio2_{int(radius)}km"] = scale * flat["tio2"] + (1 - scale) * flat["tio2"].mean()
        flat[f"interaction_{int(radius)}km"] = (
            flat[f"tio2_{int(radius)}km"] * flat["gravity_bandpass"]
        )

    n_positive = int(round(0.10 * len(flat)))
    order = np.argsort(flat["mag_anomaly"].to_numpy())
    target = np.zeros(len(flat), dtype=np.int8)
    target[order[-n_positive:]] = 1
    flat["mag_binary_10nT"] = target
    flat["mag_binary_25nT"] = 0
    meta = {
        "height": height,
        "width": width,
        "res_km": res_deg * np.pi * config.LUNAR_RADIUS_KM / 180.0,
    }
    return flat, meta


def test_power_defaults_share_the_canonical_adequacy_constants():
    defaults = PowerAnalysisConfig()
    assert defaults.strengths == config.POWER_STRENGTHS
    assert defaults.n_simulations == config.N_POWER_SIMULATIONS
    assert defaults.adequacy_block_size_deg == config.POWER_ADEQUACY_BLOCK_DEG
    assert defaults.target_power == config.MIN_DETECTION_POWER


def test_control_scores_are_standardized_and_have_physical_direction():
    df, _ = _toy_frame()
    h2 = build_signal_score(df, "h2_antipode")
    h1 = build_signal_score(df, "h1_tio2")

    assert h2.mean() == pytest.approx(0.0, abs=1e-12)
    assert h2.std() == pytest.approx(1.0)
    assert h1.mean() == pytest.approx(0.0, abs=1e-12)
    assert h1.std() == pytest.approx(1.0)
    assert h2[np.argmin(df["dist_to_antipode_km"])] == pytest.approx(h2.max())
    assert h1[np.argmax(df["tio2"])] > np.median(h1)

    full, no_h2 = control_feature_sets("h2")
    assert full == config.ALL_FEATURES
    assert "dist_to_antipode_km" not in no_h2

    _, no_h1 = control_feature_sets("h1")
    assert set(no_h1).isdisjoint(config.TIO2_DERIVED_FEATURES)


def test_injection_preserves_prevalence_and_known_strength_increases_contrast():
    rng = np.random.default_rng(8)
    n = 2000
    noise = rng.standard_normal(n)
    signal = np.linspace(-2, 2, n)
    weak = inject_binary_target(noise, signal, strength=0.0, prevalence=0.07)
    strong = inject_binary_target(noise, signal, strength=5.0, prevalence=0.07)

    assert weak.sum() == strong.sum() == round(n * 0.07)
    assert np.corrcoef(strong, signal)[0, 1] > np.corrcoef(weak, signal)[0, 1] + 0.2
    assert np.array_equal(
        strong, inject_binary_target(noise, signal, strength=5.0, prevalence=0.07)
    )


def test_phase_noise_is_seeded_and_uses_whole_spatial_fields():
    df, meta = _toy_frame()
    first, first_meta = generate_spatial_noise_fields(df, df, 2, 12, "phase", meta)
    second, _ = generate_spatial_noise_fields(df, df, 2, 12, "phase", meta)

    assert first_meta["simulations_exchangeable"] is True
    assert len(first) == 2 and first[0].shape == (len(df),)
    assert np.array_equal(first[0], second[0])
    assert np.array_equal(first[1], second[1])
    assert not np.array_equal(first[0], first[1])
    assert first[0].std() == pytest.approx(1.0)


def test_phase_randomizer_preserves_the_filled_real_field_spectrum():
    rng = np.random.default_rng(33)
    field = rng.normal(size=(18, 36))
    field[2:4, 7:10] = np.nan
    filled = np.where(np.isfinite(field), field, np.nanmean(field))
    surrogate = phase_randomized_surrogate(field, np.random.default_rng(12))
    assert np.allclose(
        np.abs(np.fft.rfft2(surrogate)),
        np.abs(np.fft.rfft2(filled)),
        rtol=1e-10,
        atol=1e-10,
    )


def test_effective_sample_size_fails_closed_and_never_exceeds_nominal_n():
    assert spatial_stats.effective_sample_size(100, 1.0, float("nan")) == 1.0
    assert spatial_stats.effective_sample_size(100, 1.0, 0.0) == 1.0
    assert spatial_stats.effective_sample_size(100, 1.0, 1e-9) == 100.0


def test_unestimable_variogram_cannot_pass_structural_adequacy(monkeypatch):
    df, meta = _toy_frame()
    monkeypatch.setattr(
        spatial_stats, "decorrelation_range_km", lambda centres, gamma, sill: float("nan")
    )
    result = structural_diagnostics(
        df,
        "mag_binary_10nT",
        meta,
        PowerAnalysisConfig(n_simulations=1, strengths=(0.0,)),
    )
    assert result["variogram_range_estimable"] is False
    assert result["approx_effective_independent_regions"] == 1.0
    assert result["structurally_limited"] is True


@pytest.mark.parametrize("invalid_label", [0.5, "1"])
def test_power_paths_reject_coerced_fractional_or_string_targets(invalid_label):
    df, meta = _toy_frame()
    target = df["mag_binary_10nT"].astype(object)
    target.iloc[0] = invalid_label
    df["mag_binary_10nT"] = target
    cfg = PowerAnalysisConfig(
        strengths=(0.0,),
        n_simulations=1,
        estimator="logistic",
        variogram_pairs=100,
        include_simulations=False,
    )

    with pytest.raises(ValueError, match="non-null boolean/0/1"):
        run_power_analysis_frame(df, meta, cfg)
    with pytest.raises(ValueError, match="non-null boolean/0/1"):
        structural_diagnostics(df, "mag_binary_10nT", meta, cfg)


def test_rotation_noise_never_uses_identity_and_is_finite():
    df, meta = _toy_frame()
    fields, metadata = generate_spatial_noise_fields(df, df, 3, 2, "rotation", meta)
    shifts = metadata["longitude_shifts_pixels"]
    assert len(set(shifts)) == 3
    assert all(0 < shift < meta["width"] for shift in shifts)
    assert all(np.isfinite(field).all() for field in fields)


def test_grouped_fold_audit_proves_group_separation_and_p_resolution():
    df, _ = _toy_frame()
    audit = grouped_fold_audit(
        df["mag_binary_10nT"].to_numpy(), df["spatial_block"].to_numpy(), 5
    )
    assert audit["groups_disjoint_in_every_split"] is True
    assert audit["actual_folds"] == 5
    assert audit["valid_pr_auc_folds"] == 5
    assert audit["best_case_one_sided_p_resolution"] == pytest.approx(1 / 32)


def test_wilson_interval_and_grid_bounded_mde_are_honest():
    low, high = wilson_interval(8, 10)
    assert low < 0.8 < high
    curve = [
        {
            "strength": 0.0,
            "spatially_robust_detection_probability": 0.05,
            "spatially_robust_detection_wilson_95": [0.01, 0.16],
            "median_top_minus_bottom_risk": 0.0,
            "median_top_vs_bottom_corrected_odds_ratio": 1.0,
        },
        {
            "strength": 0.5,
            "spatially_robust_detection_probability": 0.65,
            "spatially_robust_detection_wilson_95": [0.45, 0.80],
            "median_top_minus_bottom_risk": 0.02,
            "median_top_vs_bottom_corrected_odds_ratio": 3.0,
        },
        {
            "strength": 1.0,
            "spatially_robust_detection_probability": 0.85,
            "spatially_robust_detection_wilson_95": [0.66, 0.94],
            "median_top_minus_bottom_risk": 0.05,
            "median_top_vs_bottom_corrected_odds_ratio": 8.0,
        },
    ]
    mde = minimum_detectable_effect(curve, target_power=0.8)
    assert mde["point_estimate_strength"] == 1.0
    assert mde["tested_grid_bracket"] == [0.5, 1.0]
    # The point estimate crosses 80%, but its lower CI does not: no conservative MDE.
    assert mde["conservative_95pct_strength"] is None


def test_end_to_end_frame_api_reports_power_and_separates_effective_sample():
    df, meta = _toy_frame()
    cfg = PowerAnalysisConfig(
        strengths=(0.0, 3.0),
        n_simulations=2,
        estimator="logistic",
        noise_method="phase",
        prevalence=0.10,
        variogram_pairs=1000,
        include_simulations=False,
    )
    result = run_power_analysis_frame(df, meta, cfg)

    assert result["analysis"] == "positive_control_spatial_injection_recovery_power"
    assert [row["strength"] for row in result["power_curve"]] == [0.0, 3.0]
    assert all(row["n_simulations"] == 2 for row in result["power_curve"])
    structural = result["structural_diagnostics"]
    assert structural["nominal_pixel_count"] == len(df)
    assert structural["approx_effective_independent_regions"] <= len(df)
    assert structural["distinction"].startswith("Geometric CV blocks")
    assert set(result["Detection_Power"]) >= {
        "adequate_power", "power_at_target_effect", "positive_control_recovered"
    }
    # No arbitrary target effect was declared, so the canonical adequacy gate fails closed.
    assert result["Detection_Power"]["power_at_target_effect"] is None
    assert result["Detection_Power"]["adequate_power"] is False


def test_json_writer_round_trips_machine_readable_result(tmp_path):
    output = tmp_path / "power.json"
    payload = {
        "Detection_Power": {
            "adequate_power": False,
            "power_at_target_effect": None,
            "positive_control_recovered": True,
        },
        "value": np.float64(0.25),
    }
    write_power_result(payload, str(output))
    assert json.loads(output.read_text()) == {
        "Detection_Power": {
            "adequate_power": False,
            "power_at_target_effect": None,
            "positive_control_recovered": True,
        },
        "value": 0.25,
    }


def test_target_effect_must_be_predeclared_on_strength_grid():
    with pytest.raises(ValueError, match="included in strengths"):
        PowerAnalysisConfig(
            strengths=(0.0, 1.0), target_effect_strength=0.5
        ).validated()


def test_file_api_hashes_the_exact_input_artifacts(tmp_path):
    df, meta = _toy_frame()
    dataset = tmp_path / "modeling_dataset.csv"
    grid = tmp_path / "grid_meta.json"
    df.to_csv(dataset, index=False)
    grid.write_text(json.dumps(meta), encoding="utf-8")
    result = run_power_analysis(
        str(dataset),
        str(grid),
        PowerAnalysisConfig(
            strengths=(0.0, 3.0),
            n_simulations=1,
            estimator="logistic",
            prevalence=0.10,
            variogram_pairs=100,
            include_simulations=False,
        ),
    )
    inputs = result["input_artifacts"]
    assert inputs["modeling_dataset"]["sha256"] == hashlib.sha256(
        dataset.read_bytes()
    ).hexdigest()
    assert inputs["grid_metadata"]["sha256"] == hashlib.sha256(
        grid.read_bytes()
    ).hexdigest()
